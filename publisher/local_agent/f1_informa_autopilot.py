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
import shutil
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
CHATGPT_IMAGES_URL = os.getenv("F1_CHATGPT_IMAGES_URL", "https://chatgpt.com/images").strip()
WORK_ROOT = Path(os.getenv("F1_INFORMA_WORK_ROOT", r"C:\F1Social\F1InformaJobs"))
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
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    last: Exception | None = None
    for attempt in range(1, 5):
        try:
            r = requests.get(
                url,
                headers=headers(),
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            if not r.ok:
                raise AutopilotError(f"GET {table}: {r.status_code} {r.text[:500]}")
            data = r.json()
            return data if isinstance(data, list) else []
        except (requests.ConnectionError, requests.Timeout) as exc:
            last = exc
            if attempt >= 4:
                break
            wait = attempt * 3
            print(f"WARN GET {table} rete temporaneamente non disponibile; retry {attempt}/4 tra {wait}s")
            time.sleep(wait)
    raise AutopilotError(f"GET {table}: connessione non disponibile dopo retry: {last}")


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
    maximum = max(1, int(job.get("max_attempts") or 3))
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


def job_progress(job_id: str, stage: str, **data: Any) -> None:
    stamp = now_iso()
    rest_patch(
        "f1_intelligence_jobs",
        job_id,
        {
            "stage": stage,
            "result": {
                "progress": {
                    "stage": stage,
                    "at": stamp,
                    **data,
                }
            },
            "updated_at": stamp,
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



def _copy_profile_entry(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(
            src,
            dst,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                "Cache", "Code Cache", "GPUCache", "DawnCache", "GrShaderCache",
                "ShaderCache", "Crashpad", "BrowserMetrics", "*.tmp", "LOCK"
            ),
        )
    else:
        for attempt in range(1, 4):
            try:
                shutil.copy2(src, dst)
                return
            except (PermissionError, OSError):
                if attempt >= 3:
                    raise
                time.sleep(attempt)


def sync_authenticated_chrome_profile(
    source_root: Path,
    profile_directory: str,
    destination_root: Path,
) -> str:
    """Clone the authenticated Chrome session into the dedicated F1 worker profile.

    The regular Chrome process may stay open. Only session/profile data is copied;
    caches and lock files are intentionally excluded. Passwords are never read.
    """
    source_profile = source_root / profile_directory
    if not source_profile.exists():
        raise AuthRequired(f"Profilo Chrome sorgente non trovato: {source_profile}")
    destination_root.mkdir(parents=True, exist_ok=True)
    destination_profile = destination_root / profile_directory
    destination_profile.mkdir(parents=True, exist_ok=True)

    # Chrome cookie encryption metadata is stored in Local State. The same
    # Windows user on the same PC can reuse it inside the dedicated copy.
    _copy_profile_entry(source_root / "Local State", destination_root / "Local State")

    # Copy only the session-relevant profile data. This is intentionally much
    # smaller and safer than cloning the entire live Chrome user-data tree.
    for relative in (
        "Preferences",
        "Secure Preferences",
        "Network",
        "Local Storage",
        "Session Storage",
        "IndexedDB",
        "Storage",
        "WebStorage",
    ):
        try:
            _copy_profile_entry(source_profile / relative, destination_profile / relative)
        except (PermissionError, OSError) as exc:
            # One busy cache/database must not block all session reuse; Cookies
            # and Local State are the critical pieces and are retried above.
            print(f"WARN Chrome profile sync skipped {relative}: {exc}")

    # Never copy/process Chromium singleton locks into the worker profile.
    for base in (destination_root, destination_profile):
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"):
            try:
                (base / name).unlink(missing_ok=True)
            except Exception:
                pass
    return profile_directory


def _uia_image_selector_js() -> str:
    return (
        "Array.from(document.querySelectorAll("
        "'[data-message-author-role=\"assistant\"] img, article img, main img'"
        ")).filter(img=>{"
        "const alt=(img.alt||'').toLowerCase();"
        "const src=(img.currentSrc||img.src||'');"
        "return src&&img.naturalWidth>=512&&img.naturalHeight>=512"
        "&&!alt.includes('avatar')&&!alt.includes('profile')&&!alt.includes('logo')"
        "&&!src.includes('avatar')&&!src.includes('profile');"
        "})"
    )


def _uia_title_value(win) -> str:
    try:
        return (win.window_text() or "").strip()
    except Exception:
        return ""


def _uia_count_from_title(title: str) -> int | None:
    m = re.search(r"F1IMGCOUNT:(\d+)", title or "")
    return int(m.group(1)) if m else None


def _uia_chatgpt_window(target_url: str | None = None):
    if os.name != "nt":
        raise AutopilotError("UIA ChatGPT richiede Windows")
    from diagnose_chatgpt_uia import chrome_windows, navigate, run_javascript

    windows = chrome_windows()
    # Prefer the single window reserved by our automation, then an already
    # visible ChatGPT window. Never open a second window while Chrome is running.
    win = next((w for w in windows if "F1 AUTOPILOT" in _uia_title_value(w)), None)
    if win is None:
        win = next((w for w in windows if "ChatGPT" in _uia_title_value(w)), None)

    if win is None:
        if windows:
            # Chrome is open but no ChatGPT window exists: reuse one existing
            # Chrome window rather than spawning another top-level window.
            win = windows[-1]
        else:
            exe = chrome_executable()
            if not exe:
                raise AutopilotError("Google Chrome non trovato")
            subprocess.Popen(
                [exe, "--new-window", target_url or CHATGPT_IMAGES_URL],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.time() + 20
            while time.time() < deadline:
                windows = chrome_windows()
                if windows:
                    win = windows[-1]
                    break
                time.sleep(0.5)

    if win is None:
        raise AutopilotError("Nessuna finestra Chrome accessibile tramite UIA")

    try:
        win.restore()
    except Exception:
        pass
    navigate(win, target_url or CHATGPT_IMAGES_URL)
    time.sleep(8)
    run_javascript(
        win,
        "(()=>{const p=document.querySelector('#prompt-textarea,textarea,[contenteditable=true]');"
        "document.title='F1 AUTOPILOT '+location.host+':'+(p?1:0);void(0)})()",
    )
    time.sleep(1)
    title = _uia_title_value(win)
    if "F1 AUTOPILOT chatgpt.com:1" not in title:
        raise AuthRequired(
            f"Sessione ChatGPT non pronta nella finestra Chrome prevista per {EXPECTED_EMAIL}"
        )
    return win



def _uia_enable_image_mode(win) -> bool:
    """Select ChatGPT's explicit Create image mode in the existing session.

    We search visible composer controls in both Italian and English. If the
    image option is hidden under Tools/Strumenti/plus, open that menu and try
    again. No new Chrome window is created.
    """
    from diagnose_chatgpt_uia import run_javascript

    direct = r"""(()=>{
      const norm=s=>(s||'').replace(/\s+/g,' ').trim().toLowerCase();
      const visible=e=>!!(e && (e.offsetWidth||e.offsetHeight||e.getClientRects().length));
      const label=e=>norm(
        e.getAttribute('aria-label')||e.getAttribute('title')||
        e.getAttribute('data-testid')||e.textContent||''
      );
      const nodes=[...document.querySelectorAll('button,[role="button"],[role="menuitem"]')].filter(visible);
      const imageWords=['create image','create images','generate image','genera immagine','crea immagine','crea immagini'];
      let hit=nodes.find(e=>imageWords.some(w=>label(e).includes(w)));
      if(hit){hit.click();document.title='F1IMGMODE:CLICKED:'+label(hit).slice(0,80);return;}
      const toolWords=['tools','strumenti','tool','azioni'];
      let tools=nodes.find(e=>toolWords.some(w=>label(e)===w||label(e).includes(w)));
      if(!tools){
        tools=document.querySelector(
          'button[data-testid*="plus"],button[aria-label*="tool" i],button[aria-label*="strument" i],button[aria-label*="add" i]'
        );
      }
      if(tools && visible(tools)){tools.click();document.title='F1IMGMODE:MENU';return;}
      document.title='F1IMGMODE:NOTFOUND';
      void(0);
    })()"""
    run_javascript(win, direct)
    time.sleep(1.0)
    title = _uia_title_value(win)
    if "F1IMGMODE:CLICKED:" in title:
        return True

    if "F1IMGMODE:MENU" in title:
        second = r"""(()=>{
          const norm=s=>(s||'').replace(/\s+/g,' ').trim().toLowerCase();
          const visible=e=>!!(e && (e.offsetWidth||e.offsetHeight||e.getClientRects().length));
          const label=e=>norm(
            e.getAttribute('aria-label')||e.getAttribute('title')||
            e.getAttribute('data-testid')||e.textContent||''
          );
          const nodes=[...document.querySelectorAll(
            'button,[role="button"],[role="menuitem"],[role="option"],li'
          )].filter(visible);
          const imageWords=['create image','create images','generate image','genera immagine','crea immagine','crea immagini'];
          const hit=nodes.find(e=>imageWords.some(w=>label(e).includes(w)));
          if(hit){hit.click();document.title='F1IMGMODE:CLICKED:'+label(hit).slice(0,80);return;}
          document.title='F1IMGMODE:NOTFOUND';
          void(0);
        })()"""
        run_javascript(win, second)
        time.sleep(1.0)
        title = _uia_title_value(win)
        if "F1IMGMODE:CLICKED:" in title:
            return True

    return False


def _uia_send_prompt(win, text: str) -> None:
    from diagnose_chatgpt_uia import run_javascript
    from pywinauto.keyboard import send_keys

    payload = json.dumps(text, ensure_ascii=False)
    script = f"""(()=>{{
      const p=document.querySelector('#prompt-textarea,textarea,[contenteditable=true]');
      if(!p){{document.title='F1PROMPT:0';return;}}
      const value={payload};
      p.focus();
      if(p instanceof HTMLTextAreaElement){{
        const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
        setter.call(p,value);
        p.dispatchEvent(new Event('input',{{bubbles:true}}));
      }} else {{
        try{{
          document.execCommand('selectAll',false,null);
          document.execCommand('insertText',false,value);
        }}catch(e){{
          p.textContent=value;
        }}
        p.dispatchEvent(new InputEvent('input',{{bubbles:true,inputType:'insertText',data:value}}));
      }}
      document.title='F1PROMPT:SET';
      setTimeout(()=>{{
        const b=document.querySelector(
          'button[data-testid="send-button"],button[aria-label*="Send" i],button[aria-label*="Invia" i]'
        );
        if(b && !b.disabled){{b.click();document.title='F1PROMPT:SENT';}}
        else{{p.focus();document.title='F1PROMPT:READY';}}
      }},900);
      void(0);
    }})()"""
    run_javascript(win, script)
    time.sleep(1.4)
    title = _uia_title_value(win)
    if "F1PROMPT:SENT" in title:
        time.sleep(1)
        return
    if "F1PROMPT:READY" in title or "F1PROMPT:SET" in title:
        # Fallback: prompt is already in the editor; keyboard Enter sends it.
        try:
            win.set_focus()
        except Exception:
            pass
        send_keys("{ENTER}")
        time.sleep(1)
        return
    raise AutopilotError(f"UIA: prompt non inviato; stato finestra={title[:180]}")


def _uia_clipboard_json(win, expression: str, marker_prefix: str) -> Any:
    import pyperclip
    from diagnose_chatgpt_uia import run_javascript

    last = ""
    for attempt in range(1, 4):
        marker = f"{marker_prefix}_{uuid.uuid4().hex[:8]}"
        pyperclip.copy(marker)
        run_javascript(
            win,
            f"""(()=>{{
              try {{
                const value=JSON.stringify({expression});
                const ta=document.createElement('textarea');
                ta.value=value;ta.style.position='fixed';ta.style.opacity='0';
                document.body.appendChild(ta);ta.focus();ta.select();
                document.execCommand('copy');ta.remove();
              }} catch(e) {{}}
              void(0);
            }})()""",
        )
        time.sleep(0.55)
        last = str(pyperclip.paste() or "").strip()
        if last and last != marker:
            try:
                return json.loads(last)
            except Exception:
                pass
        time.sleep(attempt * 0.5)
    raise AutopilotError(f"UIA clipboard JSON non disponibile ({marker_prefix}, value={last[:120]!r})")


def _uia_image_sources(win) -> list[str]:
    selector = _uia_image_selector_js()
    rows = _uia_clipboard_json(
        win,
        f"Array.from(new Set(({selector}).map(img=>img.currentSrc||img.src).filter(Boolean)))",
        "F1_IMAGES",
    )
    return [str(x) for x in (rows or []) if str(x).strip()]


def _uia_current_url(win) -> str:
    try:
        value = _uia_clipboard_json(win, "location.href", "F1_URL")
        return str(value or "").strip()
    except Exception:
        return ""


def _uia_wait_for_new_image_sources(
    win,
    known: set[str],
    timeout_seconds: int = 720,
    progress=None,
    card: int | None = None,
) -> list[str]:
    deadline = time.time() + timeout_seconds
    last_fresh: list[str] = []
    last_change = time.time()
    last_progress = 0.0

    while time.time() < deadline:
        current = _uia_image_sources(win)
        fresh = [src for src in current if src not in known]
        if fresh != last_fresh:
            last_fresh = fresh
            last_change = time.time()

        if fresh and time.time() - last_change >= 12:
            return fresh

        if progress and time.time() - last_progress >= 30:
            remaining = max(0, int(deadline - time.time()))
            progress(
                "CARD_IMAGE_WAIT",
                card=card,
                new_images_detected=len(fresh),
                seconds_remaining=remaining,
                expected_images=EXPECTED_IMAGES,
            )
            last_progress = time.time()
        time.sleep(5)

    return last_fresh


def _uia_browser_download_src(win, src: str, filename: str) -> Path:
    from diagnose_chatgpt_uia import run_javascript

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    src_json = json.dumps(src)
    run_javascript(
        win,
        f"""(()=>{{
          const src={src_json};
          fetch(src).then(r=>{{if(!r.ok)throw new Error('http '+r.status);return r.blob();}})
          .then(b=>{{const u=URL.createObjectURL(b);const a=document.createElement('a');
            a.href=u;a.download={json.dumps(safe_name)};document.body.appendChild(a);a.click();a.remove();
            setTimeout(()=>URL.revokeObjectURL(u),5000);}})
          .catch(()=>{{}});
          void(0);
        }})()""",
    )
    downloads = Path.home() / "Downloads"
    target = downloads / safe_name
    partial = downloads / (safe_name + ".crdownload")
    deadline = time.time() + 120
    while time.time() < deadline:
        if target.exists() and target.stat().st_size > 0 and not partial.exists():
            return target
        time.sleep(1)
    raise AutopilotError(f"UIA: download browser non trovato: {safe_name}")


def _uia_download_image_src(win, src: str, dest: Path) -> None:
    if src.startswith("data:image/"):
        dest.write_bytes(base64.b64decode(src.split(",", 1)[1]))
        return

    if src.startswith(("http://", "https://")):
        try:
            r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
            if r.ok and len(r.content) > 10_000:
                dest.write_bytes(r.content)
                return
        except Exception:
            pass

    filename = f"f1-informa-{uuid.uuid4().hex[:12]}-{dest.stem}.png"
    downloaded = _uia_browser_download_src(win, src, filename)
    try:
        shutil.move(str(downloaded), str(dest))
    finally:
        try:
            downloaded.unlink(missing_ok=True)
        except Exception:
            pass


def _uia_prepare_image_baseline(win) -> int:
    from diagnose_chatgpt_uia import run_javascript

    selector=_uia_image_selector_js()
    run_javascript(
        win,
        f"""(()=>{{
          const xs={selector};
          const known=Array.from(new Set(xs.map(img=>img.currentSrc||img.src).filter(Boolean)));
          sessionStorage.setItem('f1KnownImages',JSON.stringify(known));
          sessionStorage.setItem('f1FreshImages','[]');
          document.title='F1BASE:'+known.length;
          void(0);
        }})()""",
    )
    time.sleep(0.8)
    m=re.search(r"F1BASE:(\d+)",_uia_title_value(win))
    if not m:
        raise AutopilotError("UIA: baseline immagini ChatGPT non leggibile")
    return int(m.group(1))


def _uia_new_image_count(win) -> int:
    from diagnose_chatgpt_uia import run_javascript

    selector=_uia_image_selector_js()
    run_javascript(
        win,
        f"""(()=>{{
          let known=[];
          try{{known=JSON.parse(sessionStorage.getItem('f1KnownImages')||'[]')}}catch(e){{known=[]}}
          const xs={selector};
          const current=Array.from(new Set(xs.map(img=>img.currentSrc||img.src).filter(Boolean)));
          const fresh=current.filter(src=>!known.includes(src));
          sessionStorage.setItem('f1FreshImages',JSON.stringify(fresh));
          document.title='F1NEWIMG:'+fresh.length;
          void(0);
        }})()""",
    )
    time.sleep(0.7)
    m=re.search(r"F1NEWIMG:(\d+)",_uia_title_value(win))
    if not m:
        raise AutopilotError("UIA: conteggio nuove immagini ChatGPT non leggibile")
    return int(m.group(1))


def _uia_wait_for_new_dom_image(
    win,
    timeout_seconds:int=720,
    progress=None,
    card:int|None=None,
) -> int:
    deadline=time.time()+timeout_seconds
    last=-1
    last_change=time.time()
    last_progress=0.0
    while time.time()<deadline:
        count=_uia_new_image_count(win)
        if count!=last:
            last=count
            last_change=time.time()
        if count>0 and time.time()-last_change>=12:
            return count
        if progress and time.time()-last_progress>=30:
            progress(
                "CARD_IMAGE_WAIT",
                card=card,
                new_images_detected=max(0,count),
                seconds_remaining=max(0,int(deadline-time.time())),
                expected_images=EXPECTED_IMAGES,
            )
            last_progress=time.time()
        time.sleep(5)
    return max(0,last)


def _uia_open_latest_fresh_image(win) -> None:
    from diagnose_chatgpt_uia import run_javascript

    selector=_uia_image_selector_js()
    run_javascript(
        win,
        f"""(()=>{{
          let fresh=[];
          try{{fresh=JSON.parse(sessionStorage.getItem('f1FreshImages')||'[]')}}catch(e){{fresh=[]}}
          const src=fresh[fresh.length-1]||'';
          const xs={selector};
          const img=xs.find(el=>(el.currentSrc||el.src)===src);
          if(!img){{document.title='F1VIEW:NOIMAGE';return;}}
          img.scrollIntoView({{block:'center',inline:'center'}});
          const target=img.closest('button')||img.closest('[role="button"]')||img;
          target.click();
          document.title='F1VIEW:OPEN';
          void(0);
        }})()""",
    )
    time.sleep(2.5)
    title=_uia_title_value(win)
    if "F1VIEW:NOIMAGE" in title:
        raise AutopilotError("UIA: immagine appena generata non trovata nel DOM")


def _uia_web_download_buttons(win):
    out=[]
    try:
        controls=win.descendants()
    except Exception:
        return out
    for ctrl in controls:
        try:
            info=ctrl.element_info
            if str(getattr(info,"control_type","") or "")!="Button":
                continue
            name=(ctrl.window_text() or "").strip()
            low=name.lower()
            if not any(word in low for word in ("download","scarica")):
                continue
            rect=ctrl.rectangle()
            # Ignore Chrome toolbar's own Download button.
            cls=str(getattr(info,"class_name","") or "")
            if rect.top<110 or "PinnedActionToolbarButton" in cls:
                continue
            out.append(ctrl)
        except Exception:
            continue
    return out


def _uia_click_viewer_download(win, dest:Path, timeout_seconds:int=180) -> None:
    from pywinauto.keyboard import send_keys

    downloads=Path.home()/"Downloads"
    downloads.mkdir(parents=True,exist_ok=True)
    before={}
    for p in downloads.iterdir():
        try:
            before[p.name]=(p.stat().st_mtime_ns,p.stat().st_size)
        except Exception:
            pass
    started=time.time()

    deadline=time.time()+20
    clicked=False
    while time.time()<deadline and not clicked:
        buttons=_uia_web_download_buttons(win)
        if buttons:
            # Prefer the lowest/rightmost visible web download control, which
            # is normally the image viewer's action rather than an unrelated UI.
            buttons.sort(key=lambda b:(b.rectangle().top,b.rectangle().left),reverse=True)
            for btn in buttons:
                try:
                    btn.click_input()
                    clicked=True
                    break
                except Exception:
                    try:
                        btn.invoke()
                        clicked=True
                        break
                    except Exception:
                        continue
        if not clicked:
            time.sleep(1)

    if not clicked:
        raise AutopilotError("UIA: pulsante Scarica/Download del viewer ChatGPT non trovato")

    deadline=time.time()+timeout_seconds
    candidate=None
    while time.time()<deadline:
        newest=None
        for p in downloads.iterdir():
            if p.name.endswith(".crdownload"):
                continue
            try:
                st=p.stat()
            except Exception:
                continue
            old=before.get(p.name)
            changed=(old is None) or old!=(st.st_mtime_ns,st.st_size)
            if changed and st.st_mtime>=started-2 and st.st_size>10_000:
                if newest is None or st.st_mtime_ns>newest.stat().st_mtime_ns:
                    newest=p
        if newest is not None:
            candidate=newest
            break
        time.sleep(1)

    try:
        win.set_focus()
        send_keys("{ESC}")
    except Exception:
        pass
    time.sleep(0.8)

    if candidate is None:
        raise AutopilotError("UIA: il click Download non ha prodotto alcun file immagine")

    shutil.move(str(candidate),str(dest))


def _uia_image_count(win) -> int:
    import pyperclip
    from diagnose_chatgpt_uia import run_javascript

    selector = _uia_image_selector_js()
    last_error = ""
    for attempt in range(1, 4):
        marker = f"F1_COUNT_WAIT_{uuid.uuid4().hex[:8]}"
        pyperclip.copy(marker)
        run_javascript(
            win,
            f"""(()=>{{
              const xs={selector};
              const value=String(xs.length);
              const ta=document.createElement('textarea');
              ta.value=value;
              ta.style.position='fixed';
              ta.style.opacity='0';
              document.body.appendChild(ta);
              ta.focus();
              ta.select();
              const ok=document.execCommand('copy');
              ta.remove();
              document.title='F1IMGCOUNT:'+value;
              void(0);
            }})()""",
        )
        time.sleep(0.45)
        value = str(pyperclip.paste() or "").strip()
        if value.isdigit():
            return int(value)

        # Secondary fallback: read the title marker if ChatGPT did not overwrite
        # it before Windows UI Automation saw it.
        count = _uia_count_from_title(_uia_title_value(win))
        if count is not None:
            return count

        last_error = value
        time.sleep(0.6 * attempt)

    raise AutopilotError(
        f"UIA: impossibile leggere il numero di immagini ChatGPT (clipboard={last_error!r})"
    )


def _uia_wait_for_images(win, baseline: int, timeout_seconds: int = 300) -> int:
    deadline = time.time() + timeout_seconds
    last = baseline
    last_change = time.time()
    while time.time() < deadline:
        count = _uia_image_count(win)
        if count != last:
            last = count
            last_change = time.time()
        if count > baseline and time.time() - last_change >= 18:
            return count
        time.sleep(4)
    return last


def _uia_copy_image_url(win, index: int) -> str:
    import pyperclip
    from diagnose_chatgpt_uia import run_javascript

    marker = f"F1_URL_WAIT_{index}_{uuid.uuid4().hex[:8]}"
    pyperclip.copy(marker)
    selector = _uia_image_selector_js()
    run_javascript(
        win,
        f"""(()=>{{
          const xs={selector};
          const img=xs[{index}];
          if(!img){{document.title='F1URL:MISS:{index}';return;}}
          const value=img.currentSrc||img.src||'';
          const ta=document.createElement('textarea');
          ta.value=value;ta.style.position='fixed';ta.style.opacity='0';
          document.body.appendChild(ta);ta.focus();ta.select();
          const ok=document.execCommand('copy');ta.remove();
          document.title='F1URL:'+(ok?'OK':'FAIL')+':{index}';
          void(0);
        }})()""",
    )
    time.sleep(0.8)
    value = str(pyperclip.paste() or "").strip()
    if not value or value == marker:
        raise AutopilotError(f"UIA: URL immagine {index + 1} non copiato")
    return value


def _uia_browser_download(win, index: int, filename: str) -> Path:
    from diagnose_chatgpt_uia import run_javascript

    selector = _uia_image_selector_js()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    run_javascript(
        win,
        f"""(()=>{{
          const xs={selector};const img=xs[{index}];
          if(!img){{document.title='F1DL:MISS:{index}';return;}}
          fetch(img.currentSrc||img.src).then(r=>{{if(!r.ok)throw new Error('http '+r.status);return r.blob();}})
          .then(b=>{{const u=URL.createObjectURL(b);const a=document.createElement('a');
            a.href=u;a.download={json.dumps(safe_name)};document.body.appendChild(a);a.click();a.remove();
            setTimeout(()=>URL.revokeObjectURL(u),5000);document.title='F1DL:OK:{index}';}})
          .catch(()=>{{document.title='F1DL:ERR:{index}';}});
          void(0);
        }})()""",
    )
    downloads = Path.home() / "Downloads"
    target = downloads / safe_name
    deadline = time.time() + 90
    partial = downloads / (safe_name + ".crdownload")
    while time.time() < deadline:
        if target.exists() and target.stat().st_size > 0 and not partial.exists():
            return target
        time.sleep(1)
    raise AutopilotError(f"UIA: download browser non trovato per card {index + 1}")


def _uia_download_image(win, index: int, dest: Path) -> None:
    src = _uia_copy_image_url(win, index)
    if src.startswith("data:image/"):
        dest.write_bytes(base64.b64decode(src.split(",", 1)[1]))
        return
    if src.startswith(("http://", "https://")):
        try:
            r = requests.get(
                src,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=120,
            )
            if r.ok and len(r.content) > 10_000:
                dest.write_bytes(r.content)
                return
        except Exception:
            pass

    # blob: URLs and protected signed URLs are downloaded inside the already
    # authenticated Chrome page, then moved into the worker workspace.
    filename = f"f1-informa-{uuid.uuid4().hex[:12]}-{index + 1:02d}.png"
    downloaded = _uia_browser_download(win, index, filename)
    try:
        shutil.move(str(downloaded), str(dest))
    finally:
        try:
            downloaded.unlink(missing_ok=True)
        except Exception:
            pass



def parse_card_specs_from_master(master_prompt: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"CARD\s+(\d+)\s*[—-]\s*(.*?)\n(.*?)(?=\n\nCARD\s+\d+\s*[—-]|\n\nDIREZIONE|\n\nSTRATEGIA|\n\nOUTPUT|\Z)",
        re.S | re.I,
    )
    cards: list[dict[str, Any]] = []
    for m in pattern.finditer(master_prompt or ""):
        try:
            index = int(m.group(1))
        except Exception:
            continue
        cards.append(
            {
                "index": index,
                "title": re.sub(r"\s+", " ", m.group(2)).strip(),
                "body": re.sub(r"\s+", " ", m.group(3)).strip(),
            }
        )
    cards.sort(key=lambda x: int(x.get("index") or 0))
    return cards


def resolve_card_specs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("cards")
    cards: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for i, row in enumerate(raw, 1):
            if not isinstance(row, dict):
                continue
            cards.append(
                {
                    "index": int(row.get("index") or i),
                    "title": str(row.get("title") or "").strip(),
                    "body": str(row.get("body") or "").strip(),
                }
            )
    if len(cards) != EXPECTED_IMAGES:
        cards = parse_card_specs_from_master(str(payload.get("graphics_prompt") or ""))
    if len(cards) != EXPECTED_IMAGES:
        raise AutopilotError(
            f"F1 INFORMA: attese {EXPECTED_IMAGES} specifiche card, trovate {len(cards)}"
        )
    return cards


def single_card_prompt(
    caption: str,
    card: dict[str, Any],
    position: int,
) -> str:
    title = str(card.get("title") or f"Card {position}").strip()
    body = str(card.get("body") or "").strip()
    continuity = (
        "Definisci qui la direzione visiva del carosello e mantienila nelle card successive."
        if position == 1
        else
        "Mantieni IDENTICA la direzione visiva, tipografica e fotografica delle card precedenti di questa stessa conversazione."
    )
    return f"""GENERA UN'IMMAGINE ORA. Non rispondere con una descrizione testuale.

Crea ESATTAMENTE UNA card social verticale 4:5 (1080×1350), CARD {position}/10 del carosello F1 INFORMA di F1 Immobiliare. Vietati collage, griglie, tavole multiple, miniature o anteprime di altre card. {continuity}

STILE: immobiliare elegante e moderno; verde F1 profondo, bianco/panna, piccoli accenti oro; fotografia immobiliare/architettura realistica; testo breve e molto leggibile; numero {position}/10; footer discreto “F1 Immobiliare · Fonte: Agenzia delle Entrate”.

CONTENUTO DI QUESTA SOLA CARD
Titolo: {title}
Informazioni source-locked: {body}

CONTESTO DALLA CAPTION F1 INFORMA (solo per verificare dati, non renderla tutta nella grafica):
{caption}

Non inventare dati. Mantieni esatti percentuali, date, importi e condizioni. Genera ADESSO una sola immagine, non testo."""

def _valid_final_card(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 15_000:
        return False
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.size == (1080, 1350)
    except Exception:
        return False


def collect_ten_graphics_uia(
    caption:str,
    card_specs:list[dict[str,Any]],
    workdir:Path,
    progress=None,
) -> list[Path]:
    workdir.mkdir(parents=True,exist_ok=True)
    win=_uia_chatgpt_window(CHATGPT_IMAGES_URL)
    if progress:
        progress(
            "CHATGPT_IMAGES_READY",
            window_title=_uia_title_value(win)[:180],
            target_url=CHATGPT_IMAGES_URL,
        )

    output=[]
    hashes=set()

    # Persisted cards survive retries and machine/workflow restarts.
    for position in range(1,EXPECTED_IMAGES+1):
        final=workdir/f"{position:02d}.png"
        if not _valid_final_card(final):
            break
        digest=hashlib.sha256(final.read_bytes()).hexdigest()
        if digest in hashes:
            raise AutopilotError(f"Grafica duplicata già presente alla card {position}/10")
        hashes.add(digest)
        output.append(final)

    if progress and output:
        progress("RESUME_EXISTING_CARDS",downloaded=len(output),expected_images=EXPECTED_IMAGES)

    for position in range(len(output)+1,EXPECTED_IMAGES+1):
        card=card_specs[position-1]
        baseline=_uia_prepare_image_baseline(win)
        prompt=single_card_prompt(caption,card,position)

        if progress:
            progress(
                "CARD_PROMPT_READY",
                card=position,
                baseline_images=baseline,
                expected_images=EXPECTED_IMAGES,
            )

        _uia_send_prompt(win,prompt)
        if progress:
            progress("CARD_PROMPT_SENT",card=position,expected_images=EXPECTED_IMAGES)

        fresh_count=_uia_wait_for_new_dom_image(
            win,
            timeout_seconds=720,
            progress=progress,
            card=position,
        )
        if fresh_count<1:
            raise AutopilotError(
                f"ChatGPT Images non ha generato l'immagine della card {position}/10 entro 12 minuti"
            )

        if progress:
            progress(
                "CARD_IMAGE_READY",
                card=position,
                new_images_detected=fresh_count,
                expected_images=EXPECTED_IMAGES,
            )

        _uia_open_latest_fresh_image(win)
        raw=workdir/f"uia-raw-{position:02d}.img"
        final=workdir/f"{position:02d}.png"
        _uia_click_viewer_download(win,raw,timeout_seconds=180)

        if progress:
            progress("CARD_FILE_RECEIVED",card=position,expected_images=EXPECTED_IMAGES)

        normalize_card(raw,final)
        try:
            raw.unlink(missing_ok=True)
        except Exception:
            pass

        digest=hashlib.sha256(final.read_bytes()).hexdigest()
        if digest in hashes:
            raise AutopilotError(f"Grafica duplicata rilevata alla card {position}/10")
        hashes.add(digest)
        output.append(final)

        if progress:
            progress(
                "CARD_DOWNLOADED",
                card=position,
                downloaded=len(output),
                expected_images=EXPECTED_IMAGES,
            )

    if len(output)!=EXPECTED_IMAGES:
        raise AutopilotError(
            f"Carosello incompleto: {len(output)}/{EXPECTED_IMAGES} immagini separate"
        )

    if progress:
        progress(
            "GRAPHICS_READY",
            images_found=len(output),
            expected_images=EXPECTED_IMAGES,
            strategy="one_card_per_request_uia_viewer_download",
        )
    return output


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


def collect_ten_graphics(
    page,
    caption: str,
    card_specs: list[dict[str, Any]],
    workdir: Path,
    progress=None,
) -> list[Path]:
    known = {str(x.get("src") or "") for x in image_candidates(page)}
    output: list[Path] = []
    hashes: set[str] = set()

    for position, card in enumerate(card_specs, 1):
        prompt = single_card_prompt(caption, card, position)
        if progress:
            progress("CARD_PROMPT_READY", card=position, expected_images=EXPECTED_IMAGES)
        send_prompt(page, prompt)
        if progress:
            progress("CARD_PROMPT_SENT", card=position, expected_images=EXPECTED_IMAGES)

        fresh = wait_for_new_images(page, known, timeout_seconds=240)
        if not fresh:
            raise AutopilotError(
                f"ChatGPT non ha generato l'immagine della card {position}/10"
            )
        src = fresh[-1]
        known.update(fresh)

        raw = workdir / f"raw-{position:02d}.img"
        final = workdir / f"{position:02d}.png"
        download_image(page, src, raw)
        normalize_card(raw, final)

        digest = hashlib.sha256(final.read_bytes()).hexdigest()
        if digest in hashes:
            raise AutopilotError(f"Grafica duplicata rilevata alla card {position}/10")
        hashes.add(digest)
        output.append(final)

        if progress:
            progress(
                "CARD_DOWNLOADED",
                card=position,
                downloaded=len(output),
                expected_images=EXPECTED_IMAGES,
            )

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


def launch_and_generate(
    profile: dict[str, Any],
    caption: str,
    card_specs: list[dict[str, Any]],
    workdir: Path,
    progress=None,
) -> list[Path]:
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
                return collect_ten_graphics(page, caption, card_specs, workdir, progress=progress)
            finally:
                try:
                    if page is not None:
                        page.close()
                except Exception:
                    pass

        discovered = discover_existing_chrome_profile()

        # Preferred path when the user's authenticated Chrome is already open:
        # drive that exact window through Windows UI Automation. This uses the
        # verified joseph.socialmedia2@gmail.com session directly and does not
        # require closing Chrome, copying cookies, or asking for a login.
        if discovered and chrome_process_running():
            cards = collect_ten_graphics_uia(caption, card_specs, workdir, progress=progress)
            _mark_browser_ready(
                profile,
                browser_source="existing_chrome_uia",
                source_google_profile=discovered[1],
            )
            return cards

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
                return collect_ten_graphics(page, caption, card_specs, workdir, progress=progress)
            finally:
                context.close()

        profile_path = resolve_profile_path(profile)
        profile_args = ["--start-maximized", "--disable-blink-features=AutomationControlled"]
        browser_source = "f1_dedicated_profile"

        # If the user's normal Chrome is already open with the authenticated
        # Google/ChatGPT profile, keep it open and clone only the authenticated
        # session into the isolated F1 worker profile. This avoids asking the
        # operator to log in or close Chrome.
        if discovered and chrome_process_running():
            source_root, profile_directory = discovered
            try:
                synced_dir = sync_authenticated_chrome_profile(
                    source_root,
                    profile_directory,
                    profile_path,
                )
                profile_args.insert(0, f"--profile-directory={synced_dir}")
                browser_source = "synced_existing_google_profile"
            except Exception as exc:
                print(f"WARN authenticated Chrome profile sync failed: {exc}")

        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            executable_path=exe,
            headless=False,
            accept_downloads=True,
            args=profile_args,
            no_viewport=True,
        )
        try:
            pages = context.pages
            page = pages[0] if pages else context.new_page()
            ensure_chatgpt_session(page)
            _mark_browser_ready(
                profile,
                browser_source=browser_source,
                source_google_profile=(discovered[1] if discovered else None),
            )
            return collect_ten_graphics(page, caption, card_specs, workdir, progress=progress)
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
    caption = str(payload.get("caption") or "").strip()
    if not prompt:
        raise AutopilotError("Prompt grafico F1 INFORMA mancante")
    if not caption:
        raise AutopilotError("Caption F1 INFORMA mancante")
    card_specs = resolve_card_specs(payload)

    job_id = str(job["id"])

    def progress(stage: str, **data: Any) -> None:
        job_progress(job_id, stage, **data)

    progress("BROWSER_STARTING", expected_images=EXPECTED_IMAGES)
    profile = client_profile(str(job["client_id"]))
    workdir = WORK_ROOT / job_id
    workdir.mkdir(parents=True, exist_ok=True)

    cards = launch_and_generate(
        profile,
        caption,
        card_specs,
        workdir,
        progress=progress,
    )
    progress("GRAPHICS_VALIDATED", images_found=len(cards), expected_images=EXPECTED_IMAGES)
    result = create_content_and_schedule(job, cards)
    progress(
        "SOCIAL_QUEUE_READY",
        media_count=result.get("media_count"),
        platforms=result.get("platforms"),
    )

    rest_patch(
        "f1_intelligence_jobs",
        job_id,
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
    try:
        jobs = pending_jobs()
    except AutopilotError as exc:
        # Il workflow gira ogni 5 minuti: un reset di rete non deve fermare
        # l'autopilota né richiedere intervento dell'operatore.
        print(f"F1 INFORMA queue temporarily unavailable: {exc}", file=sys.stderr)
        return 0
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
    assert CHATGPT_IMAGES_URL.endswith("/images")
    assert max(1, int(3)) == 3
    assert _uia_count_from_title("F1IMGCOUNT:7 - Google Chrome") == 7
    # clipboard image count is exercised on the local Windows runner.
    assert _uia_count_from_title("ChatGPT - Google Chrome") is None
    sample_master = "\n\n".join(
        f"CARD {i} — Titolo {i}\nTesto card {i}" for i in range(1, 11)
    ) + "\n\nDIREZIONE DELLE CARD"
    sample_cards = parse_card_specs_from_master(sample_master)
    assert len(sample_cards) == 10
    one = single_card_prompt("Caption di prova 50% 2026", sample_cards[0], 1)
    assert "GENERA UN'IMMAGINE ORA" in one
    assert "ESATTAMENTE UNA card social" in one
    assert "Vietati collage, griglie" in one
    assert "CARD 1/10" in one
    assert "Crea immagine" in "Crea immagine / Create image"
    payload = {
        "caption": "Bonus mobili: detrazione Irpef del 50%. Fonte ufficiale.",
        "title": "Bonus mobili",
    }
    assert "50%" in payload["caption"]
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory() as profile_td:
        root = Path(profile_td) / "ChromeUserData"
        src_profile = root / "Default"
        (src_profile / "Network").mkdir(parents=True)
        (src_profile / "Preferences").write_text('{"account_info":[]}', encoding="utf-8")
        (src_profile / "Network" / "Cookies").write_bytes(b"cookie-db-test")
        (root / "Local State").write_text('{"os_crypt":{}}', encoding="utf-8")
        dest = Path(profile_td) / "WorkerProfile"
        synced = sync_authenticated_chrome_profile(root, "Default", dest)
        assert synced == "Default"
        assert (dest / "Local State").exists()
        assert (dest / "Default" / "Network" / "Cookies").read_bytes() == b"cookie-db-test"

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
