#!/usr/bin/env python3
"""F1 INFORMA local autopilot.

Consumes F1_INFORMA_CHATGPT_GRAPHICS jobs from Supabase, reuses a persistent
local Chrome profile, asks ChatGPT to create the graphics for a ten-card
carousel, validates/downloads exactly ten image assets, uploads them to the
Content Hub, and schedules Facebook/Instagram publication.

No browser password, Google password, OpenAI key, or social token is stored in
this repository. The browser session lives only in the local Chrome profile.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://nqnmlsmeiynxbdojeyjt.supabase.co").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
BROWSER_ROOT = Path(os.getenv("F1_BROWSER_ROOT", r"C:\F1Social\BrowserProfiles"))
POLL_SECONDS = max(10, int(os.getenv("F1_INFORMA_AUTOPILOT_POLL_SECONDS", "20")))
CHATGPT_URL = os.getenv("F1_CHATGPT_URL", "https://chatgpt.com/").strip()
EXPECTED_EMAIL = os.getenv("F1_CHATGPT_GOOGLE_EMAIL", "joseph.socialmedia2@gmail.com").strip().lower()
JOB_TYPE = "F1_INFORMA_CHATGPT_GRAPHICS"
MEDIA_BUCKET = "f1-content-media"
EXPECTED_IMAGES = 10
MAX_TURNS = 10
REQUEST_TIMEOUT = 90


class AutopilotError(RuntimeError):
    pass


class AuthRequired(AutopilotError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    out = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        out.update(extra)
    return out


def require_env() -> None:
    if not SERVICE_KEY:
        raise AutopilotError("SUPABASE_SERVICE_ROLE_KEY mancante sul PC locale")


def rest_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers(),
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise AutopilotError(f"GET {table}: {r.status_code} {r.text[:500]}")
    data = r.json()
    return data if isinstance(data, list) else []


def rest_post(table: str, payload: Any, return_rows: bool = False) -> list[dict[str, Any]]:
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=representation" if return_rows else "return=minimal"}),
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise AutopilotError(f"POST {table}: {r.status_code} {r.text[:700]}")
    if return_rows and r.text.strip():
        data = r.json()
        return data if isinstance(data, list) else []
    return []


def rest_patch(table: str, row_id: str, payload: dict[str, Any]) -> None:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{row_id}"},
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise AutopilotError(f"PATCH {table}: {r.status_code} {r.text[:700]}")


def upload_storage(storage_path: str, file_path: Path, mime: str = "image/png") -> None:
    encoded = "/".join(quote(part, safe="") for part in storage_path.lstrip("/").split("/"))
    with file_path.open("rb") as fh:
        r = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{MEDIA_BUCKET}/{encoded}",
            headers={
                "apikey": SERVICE_KEY,
                "Authorization": f"Bearer {SERVICE_KEY}",
                "Content-Type": mime,
                "x-upsert": "false",
            },
            data=fh,
            timeout=300,
        )
    if not r.ok:
        raise AutopilotError(f"Storage upload: {r.status_code} {r.text[:600]}")


def pending_jobs() -> list[dict[str, Any]]:
    rows = rest_get(
        "f1_intelligence_jobs",
        {
            "select": "*",
            "job_type": f"eq.{JOB_TYPE}",
            "status": "in.(QUEUED,WAITING)",
            "order": "created_at.asc",
            "limit": "3",
        },
    )
    now = datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for row in rows:
        raw = str(row.get("run_after") or "").replace("Z", "+00:00")
        try:
            run_after = datetime.fromisoformat(raw)
        except Exception:
            run_after = now
        if run_after <= now:
            out.append(row)
    return out


def claim(job: dict[str, Any]) -> dict[str, Any]:
    attempts = int(job.get("attempts") or 0) + 1
    rest_patch(
        "f1_intelligence_jobs",
        str(job["id"]),
        {
            "status": "RUNNING",
            "stage": "CHATGPT_GRAPHICS",
            "attempts": attempts,
            "claimed_at": now_iso(),
            "last_error": None,
            "updated_at": now_iso(),
        },
    )
    job["attempts"] = attempts
    job["status"] = "RUNNING"
    return job


def retry_or_fail(job: dict[str, Any], exc: Exception) -> None:
    attempts = int(job.get("attempts") or 0)
    maximum = max(int(job.get("max_attempts") or 3), 8)
    message = str(exc)[:1800]
    if attempts < maximum:
        rest_patch(
            "f1_intelligence_jobs",
            str(job["id"]),
            {
                "status": "WAITING",
                "stage": "RETRY_AUTOMATICO",
                "run_after": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(timespec="seconds"),
                "last_error": message,
                "updated_at": now_iso(),
            },
        )
    else:
        rest_patch(
            "f1_intelligence_jobs",
            str(job["id"]),
            {
                "status": "ERROR",
                "stage": "ERRORE_AUTOMAZIONE",
                "last_error": message,
                "completed_at": now_iso(),
                "updated_at": now_iso(),
            },
        )


def client_profile(client_id: str) -> dict[str, Any]:
    rows = rest_get(
        "f1_client_browser_profiles",
        {
            "select": "*",
            "client_id": f"eq.{client_id}",
            "order": "updated_at.desc",
            "limit": "1",
        },
    )
    if not rows:
        raise AutopilotError("Profilo browser F1 Immobiliare non configurato")
    return rows[0]


def resolve_profile_path(profile: dict[str, Any]) -> Path:
    raw = str(profile.get("profile_path") or "").strip()
    if not raw:
        raw = f"{profile['client_id']}/chrome-profile"
    path = Path(raw)
    if not path.is_absolute():
        path = BROWSER_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def chrome_executable() -> str | None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None



def chrome_process_running() -> bool:
    if os.name != "nt":
        return False
    try:
        r = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-Command",
                "(Get-Process chrome -ErrorAction SilentlyContinue | Measure-Object).Count",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return int((r.stdout or "0").strip() or "0") > 0
    except Exception:
        return False


def chrome_cdp_endpoint() -> str | None:
    for port in (9222, 9223):
        try:
            r = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=1.5)
            data = r.json() if r.ok else {}
            if data.get("webSocketDebuggerUrl"):
                return f"http://127.0.0.1:{port}"
        except Exception:
            continue
    return None


def discover_existing_chrome_profile() -> tuple[Path, str] | None:
    """Find the Chrome profile associated with EXPECTED_EMAIL using local metadata only."""
    if os.name != "nt":
        return None
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data"
    if not root.exists():
        return None

    wanted = EXPECTED_EMAIL.lower()
    local_state = root / "Local State"
    try:
        state = json.loads(local_state.read_text(encoding="utf-8"))
        info = ((state.get("profile") or {}).get("info_cache") or {})
        for directory, meta in info.items():
            if not isinstance(meta, dict):
                continue
            values = {
                str(meta.get("user_name") or "").strip().lower(),
                str(meta.get("gaia_name") or "").strip().lower(),
            }
            if wanted in values and (root / directory).exists():
                return root, directory
    except Exception:
        pass

    candidates = ["Default"]
    try:
        candidates += sorted(
            [p.name for p in root.iterdir() if p.is_dir() and p.name.startswith("Profile ")]
        )
    except Exception:
        pass

    for directory in candidates:
        prefs = root / directory / "Preferences"
        if not prefs.exists():
            continue
        try:
            data = json.loads(prefs.read_text(encoding="utf-8"))
        except Exception:
            continue
        accounts = data.get("account_info") or []
        if isinstance(accounts, list):
            for account in accounts:
                email = str((account or {}).get("email") or "").strip().lower()
                if email == wanted:
                    return root, directory
        profile_data = data.get("profile") if isinstance(data.get("profile"), dict) else {}
        values = {
            str(profile_data.get("user_name") or "").strip().lower(),
            str(profile_data.get("gaia_name") or "").strip().lower(),
        }
        if wanted in values:
            return root, directory
    return None


def prompt_box(page):
    selectors = [
        "#prompt-textarea",
        'textarea[placeholder*="Message"]',
        'textarea[placeholder*="messaggio" i]',
        '[contenteditable="true"][data-lexical-editor="true"]',
        'div[contenteditable="true"]',
    ]
    for selector in selectors:
        loc = page.locator(selector).last
        try:
            if loc.count() and loc.is_visible(timeout=1200):
                return loc
        except Exception:
            continue
    return None


def ensure_chatgpt_session(page) -> None:
    page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2500)
    box = prompt_box(page)
    if box is None:
        login_visible = False
        for label in ("Log in", "Accedi", "Sign up", "Registrati"):
            try:
                if page.get_by_role("button", name=re.compile(label, re.I)).count():
                    login_visible = True
                    break
            except Exception:
                pass
        if login_visible:
            raise AuthRequired(
                f"Sessione ChatGPT non autenticata nel profilo locale previsto per {EXPECTED_EMAIL}"
            )
        raise AutopilotError("Casella prompt ChatGPT non trovata")
    if "/auth/login" in page.url:
        raise AuthRequired(
            f"Sessione ChatGPT non autenticata nel profilo locale previsto per {EXPECTED_EMAIL}"
        )


def send_prompt(page, text: str) -> None:
    box = prompt_box(page)
    if box is None:
        raise AutopilotError("Casella prompt ChatGPT non disponibile")
    box.click()
    try:
        box.fill(text)
    except Exception:
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(text)
    page.wait_for_timeout(400)
    sent = False
    for selector in (
        'button[data-testid="send-button"]',
        'button[aria-label*="Send" i]',
        'button[aria-label*="Invia" i]',
    ):
        try:
            btn = page.locator(selector).last
            if btn.count() and btn.is_visible() and btn.is_enabled():
                btn.click()
                sent = True
                break
        except Exception:
            continue
    if not sent:
        page.keyboard.press("Enter")


def image_candidates(page) -> list[dict[str, Any]]:
    script = """
    () => Array.from(document.querySelectorAll('[data-message-author-role="assistant"] img, article img'))
      .map((img, index) => ({
        index,
        src: img.currentSrc || img.src || '',
        alt: img.alt || '',
        w: img.naturalWidth || 0,
        h: img.naturalHeight || 0
      }))
      .filter(x => x.src && x.w >= 512 && x.h >= 512)
    """
    try:
        rows = page.evaluate(script)
    except Exception:
        rows = []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows or []:
        src = str(row.get("src") or "")
        alt = str(row.get("alt") or "").lower()
        if not src or src in seen:
            continue
        if any(x in alt for x in ("avatar", "profile", "logo")):
            continue
        seen.add(src)
        out.append(row)
    return out


def wait_for_new_images(page, known: set[str], timeout_seconds: int = 300) -> list[str]:
    deadline = time.time() + timeout_seconds
    last_change = time.time()
    found: list[str] = []
    snapshot: set[str] = set()
    while time.time() < deadline:
        current = [str(x.get("src") or "") for x in image_candidates(page)]
        fresh = [x for x in current if x and x not in known]
        now_set = set(fresh)
        if now_set != snapshot:
            snapshot = now_set
            found = fresh
            last_change = time.time()
        if found and time.time() - last_change >= 18:
            return found
        page.wait_for_timeout(4000)
    return found


def download_image(page, src: str, dest: Path) -> None:
    if src.startswith("data:image/"):
        raw = src.split(",", 1)[1]
        dest.write_bytes(base64.b64decode(raw))
        return
    if src.startswith("http://") or src.startswith("https://"):
        response = page.request.get(src, timeout=120000)
        if not response.ok:
            raise AutopilotError(f"Download immagine ChatGPT fallito: {response.status}")
        dest.write_bytes(response.body())
        return
    data = page.evaluate(
        """async (src) => {
          const r = await fetch(src);
          const b = await r.arrayBuffer();
          let binary = '';
          const bytes = new Uint8Array(b);
          for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
          return btoa(binary);
        }""",
        src,
    )
    dest.write_bytes(base64.b64decode(data))


def normalize_card(src: Path, dest: Path) -> None:
    from PIL import Image, ImageOps

    with Image.open(src) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        if image.width < 400 or image.height < 400:
            raise AutopilotError(f"Grafica troppo piccola: {image.width}x{image.height}")
        target = (1080, 1350)
        ratio = image.width / max(1, image.height)
        target_ratio = target[0] / target[1]
        if abs(ratio - target_ratio) <= 0.035:
            image = image.resize(target, Image.Resampling.LANCZOS)
        else:
            contained = ImageOps.contain(image, target, Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", target, "#0E5A3B")
            x = (target[0] - contained.width) // 2
            y = (target[1] - contained.height) // 2
            canvas.paste(contained, (x, y))
            image = canvas
        image.save(dest, "PNG", optimize=True)
    with Image.open(dest) as check:
        check.verify()
    if dest.stat().st_size < 15_000:
        raise AutopilotError(f"Grafica non valida: {dest.name}")


def collect_ten_graphics(page, initial_prompt: str, workdir: Path) -> list[Path]:
    known = {str(x.get("src") or "") for x in image_candidates(page)}
    send_prompt(page, initial_prompt)
    sources: list[str] = []
    source_seen: set[str] = set()

    for turn in range(1, MAX_TURNS + 1):
        fresh = wait_for_new_images(page, known | source_seen, timeout_seconds=300)
        for src in fresh:
            if src not in source_seen:
                source_seen.add(src)
                sources.append(src)
                if len(sources) >= EXPECTED_IMAGES:
                    break
        if len(sources) >= EXPECTED_IMAGES:
            break
        missing = EXPECTED_IMAGES - len(sources)
        followup = (
            f"Continua lo STESSO carosello F1 INFORMA. Mancano {missing} card grafiche. "
            f"Genera ora le prossime {missing} immagini separate in formato verticale 4:5, "
            "mantenendo IDENTICI stile, palette, font, gerarchia e numerazione. "
            "Non creare una tavola unica e non ripetere le card già generate."
        )
        send_prompt(page, followup)

    if len(sources) < EXPECTED_IMAGES:
        raise AutopilotError(
            f"ChatGPT ha prodotto {len(sources)}/{EXPECTED_IMAGES} grafiche dopo {MAX_TURNS} turni"
        )

    output: list[Path] = []
    hashes: set[str] = set()
    for idx, src in enumerate(sources[:EXPECTED_IMAGES], 1):
        raw = workdir / f"raw-{idx:02d}.img"
        final = workdir / f"{idx:02d}.png"
        download_image(page, src, raw)
        normalize_card(raw, final)
        digest = hashlib.sha256(final.read_bytes()).hexdigest()
        if digest in hashes:
            raise AutopilotError(f"Grafica duplicata rilevata alla card {idx}")
        hashes.add(digest)
        output.append(final)
    return output


def _mark_browser_ready(profile: dict[str, Any], **extra: Any) -> None:
    rest_patch(
        "f1_client_browser_profiles",
        str(profile["id"]),
        {
            "status": "READY",
            "google_email": EXPECTED_EMAIL,
            "last_started_at": now_iso(),
            "last_verified_at": now_iso(),
            "updated_at": now_iso(),
            "metadata": {
                **(profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}),
                "chatgpt_autopilot": True,
                "expected_google_email": EXPECTED_EMAIL,
                "execution_mode": "local_windows_pc",
                **extra,
            },
        },
    )


def launch_and_generate(profile: dict[str, Any], prompt: str, workdir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    exe = chrome_executable()
    if not exe:
        raise AutopilotError("Google Chrome non trovato sul PC locale")

    with sync_playwright() as p:
        endpoint = chrome_cdp_endpoint()
        if endpoint:
            browser = p.chromium.connect_over_cdp(endpoint)
            page = None
            try:
                context = browser.contexts[0] if browser.contexts else None
                if context is None:
                    raise AutopilotError("Chrome collegato via CDP senza contesto browser")
                page = context.new_page()
                ensure_chatgpt_session(page)
                _mark_browser_ready(profile, browser_source="existing_cdp", cdp_endpoint=endpoint)
                return collect_ten_graphics(page, prompt, workdir)
            finally:
                try:
                    if page is not None:
                        page.close()
                except Exception:
                    pass

        discovered = discover_existing_chrome_profile()
        if discovered and not chrome_process_running():
            user_data_root, profile_directory = discovered
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_root),
                executable_path=exe,
                headless=False,
                accept_downloads=True,
                args=[
                    f"--profile-directory={profile_directory}",
                    "--remote-debugging-port=9222",
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                ],
                no_viewport=True,
            )
            try:
                pages = context.pages
                page = pages[0] if pages else context.new_page()
                ensure_chatgpt_session(page)
                _mark_browser_ready(
                    profile,
                    browser_source="existing_google_profile",
                    chrome_profile_directory=profile_directory,
                )
                return collect_ten_graphics(page, prompt, workdir)
            finally:
                context.close()

        profile_path = resolve_profile_path(profile)
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            executable_path=exe,
            headless=False,
            accept_downloads=True,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
            no_viewport=True,
        )
        try:
            pages = context.pages
            page = pages[0] if pages else context.new_page()
            try:
                ensure_chatgpt_session(page)
            except AuthRequired:
                if discovered and chrome_process_running():
                    raise AuthRequired(
                        "La sessione ChatGPT è nel Chrome normale già aperto, ma quel Chrome non "
                        "espone la porta di controllo remoto. Il worker non chiude il browser "
                        "dell'utente; alla prossima apertura automatica userà il profilo "
                        f"{discovered[1]} di {EXPECTED_EMAIL}."
                    )
                raise
            _mark_browser_ready(profile, browser_source="f1_dedicated_profile")
            return collect_ten_graphics(page, prompt, workdir)
        finally:
            context.close()

def create_content_and_schedule(job: dict[str, Any], cards: list[Path]) -> dict[str, Any]:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    owner_id = str(job["owner_id"])
    client_id = str(job["client_id"])
    caption = str(payload.get("caption") or "").strip()
    title = str(payload.get("title") or "F1 INFORMA").strip()
    source_url = str(payload.get("source_url") or "").strip()

    existing_id = str(job.get("content_id") or "")
    if existing_id:
        rows = rest_get("f1_content_items", {"select": "*", "id": f"eq.{existing_id}", "limit": "1"})
        if rows:
            item = rows[0]
        else:
            existing_id = ""
    if not existing_id:
        created = rest_post(
            "f1_content_items",
            {
                "owner_id": owner_id,
                "client_id": client_id,
                "title": title,
                "description": caption,
                "source_text": caption,
                "content_type": "CAROSELLO",
                "source": "F1_INFORMA",
                "status": "APPROVATO",
                "priority": "NORMALE",
                "campaign": "F1 INFORMA",
                "tags": ["F1Informa", "F1Immobiliare", "Casa"],
                "notes": f"Autopilota F1 INFORMA · fonte {source_url}",
                "distribution_plan": {
                    "f1_informa": {
                        "autonomous": True,
                        "graphics_provider": "chatgpt_browser_session",
                        "source_url": source_url,
                        "source_updated": payload.get("source_updated"),
                        "image_count": EXPECTED_IMAGES,
                        "image_made_with_ai": True,
                        "job_id": str(job["id"]),
                    }
                },
            },
            return_rows=True,
        )
        if not created:
            raise AutopilotError("Impossibile creare contenuto F1 INFORMA")
        item = created[0]
        rest_patch(
            "f1_intelligence_jobs",
            str(job["id"]),
            {"content_id": str(item["id"]), "updated_at": now_iso()},
        )

    content_id = str(item["id"])
    existing_media = rest_get(
        "f1_content_media",
        {
            "select": "id,file_name,storage_path,sha256",
            "content_id": f"eq.{content_id}",
            "source": "eq.F1_INFORMA_CHATGPT",
            "order": "file_name.asc",
        },
    )
    if len(existing_media) < EXPECTED_IMAGES:
        existing_names = {str(x.get("file_name") or "") for x in existing_media}
        for idx, card in enumerate(cards, 1):
            name = f"{idx:02d}.png"
            if name in existing_names:
                continue
            digest = hashlib.sha256(card.read_bytes()).hexdigest()
            storage_path = (
                f"{owner_id}/{client_id}/{content_id}/"
                f"f1-informa-{uuid.uuid4().hex[:10]}-{name}"
            )
            upload_storage(storage_path, card, "image/png")
            rest_post(
                "f1_content_media",
                {
                    "owner_id": owner_id,
                    "content_id": content_id,
                    "client_id": client_id,
                    "file_name": name,
                    "mime_type": "image/png",
                    "storage_path": storage_path,
                    "file_size": card.stat().st_size,
                    "source": "F1_INFORMA_CHATGPT",
                    "sha256": digest,
                },
            )

    media_rows = rest_get(
        "f1_content_media",
        {
            "select": "id,file_name,storage_path",
            "content_id": f"eq.{content_id}",
            "source": "eq.F1_INFORMA_CHATGPT",
            "order": "file_name.asc",
        },
    )
    if len(media_rows) != EXPECTED_IMAGES:
        raise AutopilotError(f"Content Hub contiene {len(media_rows)}/{EXPECTED_IMAGES} card")

    targets = payload.get("target_platforms") or ["facebook", "instagram"]
    targets = [str(x).strip().lower() for x in targets if str(x).strip()]
    existing_cal = rest_get(
        "f1_content_calendar",
        {
            "select": "id,platform,status",
            "content_id": f"eq.{content_id}",
        },
    )
    existing_platforms = {str(x.get("platform") or "").lower() for x in existing_cal}
    publication_at = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat(timespec="seconds")

    calendar_ids = [str(x["id"]) for x in existing_cal]
    for platform in targets:
        if platform in existing_platforms:
            continue
        rows = rest_post(
            "f1_content_calendar",
            {
                "owner_id": owner_id,
                "content_id": content_id,
                "client_id": client_id,
                "platform": platform,
                "publication_at": publication_at,
                "status": "PROGRAMMATO",
                "platform_metadata": {
                    "caption": caption,
                    "publish_now": True,
                    "f1_informa": True,
                    "image_made_with_ai": True,
                    "source_url": source_url,
                    "expected_media_count": EXPECTED_IMAGES,
                },
            },
            return_rows=True,
        )
        if rows:
            calendar_ids.append(str(rows[0]["id"]))

    return {
        "content_id": content_id,
        "media_count": len(media_rows),
        "calendar_ids": calendar_ids,
        "platforms": targets,
        "source_url": source_url,
    }


def process_job(job: dict[str, Any]) -> None:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    prompt = str(payload.get("graphics_prompt") or "").strip()
    if not prompt:
        raise AutopilotError("Prompt grafico F1 INFORMA mancante")
    profile = client_profile(str(job["client_id"]))
    with tempfile.TemporaryDirectory(prefix="f1-informa-chatgpt-") as td:
        cards = launch_and_generate(profile, prompt, Path(td))
        result = create_content_and_schedule(job, cards)
    rest_patch(
        "f1_intelligence_jobs",
        str(job["id"]),
        {
            "status": "COMPLETED",
            "stage": "PROGRAMMATO",
            "result": {
                **result,
                "graphics_provider": "chatgpt_browser_session",
                "expected_google_email": EXPECTED_EMAIL,
                "completed_at": now_iso(),
            },
            "completed_at": now_iso(),
            "last_error": None,
            "updated_at": now_iso(),
        },
    )


def run_once() -> int:
    require_env()
    jobs = pending_jobs()
    if not jobs:
        return 0
    processed = 0
    for raw in jobs:
        job = claim(raw)
        try:
            process_job(job)
            processed += 1
            print(f"F1 INFORMA autopilot COMPLETED job={job['id']}")
        except Exception as exc:
            print(f"F1 INFORMA autopilot ERROR job={job.get('id')}: {exc}", file=sys.stderr)
            if isinstance(exc, AuthRequired):
                try:
                    profile = client_profile(str(job["client_id"]))
                    rest_patch(
                        "f1_client_browser_profiles",
                        str(profile["id"]),
                        {
                            "status": "AUTH_REQUIRED",
                            "google_email": EXPECTED_EMAIL,
                            "updated_at": now_iso(),
                        },
                    )
                except Exception:
                    pass
            retry_or_fail(job, exc)
    return processed


def self_test() -> None:
    assert JOB_TYPE == "F1_INFORMA_CHATGPT_GRAPHICS"
    assert EXPECTED_IMAGES == 10
    payload = {
        "caption": "Bonus mobili: detrazione Irpef del 50%. Fonte ufficiale.",
        "title": "Bonus mobili",
    }
    assert "50%" in payload["caption"]
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "src.png"
        out = Path(td) / "out.png"
        image = Image.new("RGB", (1024, 1536), "white")
        draw = ImageDraw.Draw(image)
        palette = ["#0E5A3B", "#F6F2E8", "#D9B45B", "#133126", "#FFFFFF"]
        for y in range(0, 1536, 48):
            for x in range(0, 1024, 48):
                draw.rectangle(
                    [x, y, x + 47, y + 47],
                    fill=palette[((x // 48) + (y // 48)) % len(palette)],
                )
        draw.text((80, 90), "F1 INFORMA 1/10", fill="black")
        draw.text((80, 180), "Bonus mobili 50% · test grafico", fill="black")
        image.save(src)
        normalize_card(src, out)
        with Image.open(out) as check:
            assert check.size == (1080, 1350)
    print("F1_INFORMA_AUTOPILOT_SELF_TEST_OK")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.once:
        run_once()
        return 0
    require_env()
    print(
        "F1 INFORMA Autopilot attivo · "
        f"ChatGPT={CHATGPT_URL} · account atteso={EXPECTED_EMAIL} · root={BROWSER_ROOT}"
    )
    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"F1 INFORMA loop error: {exc}", file=sys.stderr)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
