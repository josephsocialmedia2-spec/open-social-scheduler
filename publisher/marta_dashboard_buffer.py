#!/usr/bin/env python3
"""Bridge Marta Digital Hub schedules -> Buffer Free -> Facebook/Instagram.

Runs only in GitHub Actions. It never publishes unapproved captions, never
reads browser credentials, and never exposes secrets to the dashboard.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from buffer_queue_publish import buffer_config, load_client, secret_for_client
from buffer_twice_daily import ROME, create_buffer_post, ensure_cloudinary_assets, get_buffer_post

ROOT = Path(__file__).resolve().parents[1]
MEDIA_ROOT = ROOT / "publisher" / "media" / "marta-dashboard"
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()
CLIENT_ID = "marta-ruffino"
SUPPORTED = {"facebook", "instagram"}
SEND_AHEAD = timedelta(minutes=12)
PAST_DUE_GRACE = timedelta(minutes=60)
TIMEOUT = 60


class MartaPublishError(RuntimeError):
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


def rest_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers(),
        params=params,
        timeout=TIMEOUT,
    )
    if not r.ok:
        raise MartaPublishError(f"Supabase GET {table}: HTTP {r.status_code}")
    data = r.json()
    if not isinstance(data, list):
        raise MartaPublishError(f"Supabase GET {table}: risposta inattesa")
    return [x for x in data if isinstance(x, dict)]


def rest_patch(table: str, match: dict[str, str], payload: dict[str, Any]) -> None:
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params=params,
        json=payload,
        timeout=TIMEOUT,
    )
    if not r.ok:
        raise MartaPublishError(f"Supabase PATCH {table}: HTTP {r.status_code}")


def rest_post(table: str, payload: dict[str, Any]) -> None:
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        json=payload,
        timeout=TIMEOUT,
    )
    if not r.ok:
        raise MartaPublishError(f"Supabase POST {table}: HTTP {r.status_code}")


def log_event(
    owner_id: str,
    content_id: str | None,
    platform: str | None,
    outcome: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        rest_post(
            "marta_publish_logs",
            {
                "owner_id": owner_id,
                "content_id": content_id,
                "platform": platform,
                "outcome": outcome,
                "message": message[:1000],
                "details": details or {},
            },
        )
    except Exception as exc:
        print(f"WARN publish log not written: {exc}")


def parse_iso(value: str) -> datetime:
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def one(table: str, params: dict[str, str]) -> dict[str, Any] | None:
    rows = rest_get(table, {**params, "limit": "1"})
    return rows[0] if rows else None


def approved_variant(owner_id: str, content_id: str, platform: str) -> dict[str, Any]:
    row = one(
        "marta_social_variants",
        {
            "select": "platform,hook,cta,hashtags,variants,status,approved_at",
            "owner_id": f"eq.{owner_id}",
            "content_id": f"eq.{content_id}",
            "platform": f"eq.{platform}",
            "status": "eq.APPROVATO",
        },
    )
    if not row or not row.get("approved_at"):
        raise MartaPublishError("Caption non approvata")
    return row


def approved_caption(variant: dict[str, Any]) -> str:
    variants = variant.get("variants") if isinstance(variant.get("variants"), dict) else {}
    text = str(variants.get("medium") or variants.get("short") or "").strip()
    if not text:
        raise MartaPublishError("Caption approvata vuota")
    tags = [str(x).strip() for x in (variant.get("hashtags") or []) if str(x).strip()]
    missing = [x for x in tags if x not in text]
    if missing:
        text = text + "\n\n" + " ".join(missing)
    return text[:12000]


def integration(owner_id: str, platform: str, expected_channel: str) -> dict[str, Any]:
    row = one(
        "marta_integrations",
        {
            "select": "platform,provider,external_integration_id,enabled,status,last_checked_at",
            "owner_id": f"eq.{owner_id}",
            "platform": f"eq.{platform}",
        },
    )
    if not row or not row.get("enabled") or str(row.get("status")) != "CONNESSO":
        raise MartaPublishError("Canale non collegato")
    if str(row.get("provider")) != "buffer":
        raise MartaPublishError("Provider dashboard non configurato su Buffer")
    if str(row.get("external_integration_id") or "") != expected_channel:
        raise MartaPublishError("Channel ID non corrispondente alla connessione verificata")
    return row


def content_row(owner_id: str, content_id: str) -> dict[str, Any]:
    row = one(
        "marta_contents",
        {
            "select": (
                "id,owner_id,title,status,storage_path,mime_type,original_filename,"
                "publish_storage_path,publish_mime_type"
            ),
            "owner_id": f"eq.{owner_id}",
            "id": f"eq.{content_id}",
        },
    )
    if not row:
        raise MartaPublishError("Contenuto non trovato")
    if str(row.get("status")) not in {"APPROVATO", "PROGRAMMATO", "PUBBLICATO"}:
        raise MartaPublishError("Contenuto non approvato")
    return row


def choose_media(content: dict[str, Any]) -> tuple[str, str, str]:
    if content.get("publish_storage_path"):
        path = str(content["publish_storage_path"])
        mime = str(content.get("publish_mime_type") or "video/mp4")
        return "marta-content-derived", path, mime
    path = str(content.get("storage_path") or "")
    mime = str(content.get("mime_type") or "")
    if not path:
        raise MartaPublishError("Video non disponibile nello storage")
    if mime != "video/mp4":
        raise MartaPublishError("Video non ancora normalizzato in MP4")
    return "marta-content-originals", path, mime


def download_private(bucket: str, storage_path: str, schedule_id: str, mime: str) -> Path:
    ext = mimetypes.guess_extension(mime) or Path(storage_path).suffix or ".mp4"
    if ext == ".mp4v":
        ext = ".mp4"
    dest = MEDIA_ROOT / schedule_id / ("video" + ext)
    dest.parent.mkdir(parents=True, exist_ok=True)
    encoded = "/".join(quote(part, safe="") for part in storage_path.split("/"))
    r = requests.get(
        f"{SUPABASE_URL}/storage/v1/object/{quote(bucket, safe='')}/{encoded}",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
        timeout=300,
    )
    if not r.ok:
        raise MartaPublishError(f"Download video dal cloud fallito: HTTP {r.status_code}")
    dest.write_bytes(r.content)
    if dest.stat().st_size <= 0:
        raise MartaPublishError("Video cloud vuoto")
    return dest


def patch_schedule(schedule_id: str, payload: dict[str, Any]) -> None:
    rest_patch("marta_schedules", {"id": schedule_id}, {**payload, "updated_at": now_iso()})


def update_content_if_finished(owner_id: str, content_id: str) -> None:
    pending = rest_get(
        "marta_schedules",
        {
            "select": "id",
            "owner_id": f"eq.{owner_id}",
            "content_id": f"eq.{content_id}",
            "status": "in.(PROGRAMMATO,INVIATO,MANUALE_ASSISTITO,ERRORE)",
            "limit": "1",
        },
    )
    published = rest_get(
        "marta_schedules",
        {
            "select": "id",
            "owner_id": f"eq.{owner_id}",
            "content_id": f"eq.{content_id}",
            "status": "eq.PUBBLICATO",
            "limit": "1",
        },
    )
    if not pending and published:
        rest_patch("marta_contents", {"id": content_id, "owner_id": owner_id}, {"status": "PUBBLICATO", "updated_at": now_iso()})


def reconcile(schedule: dict[str, Any], api_key: str) -> str:
    owner_id = str(schedule["owner_id"])
    content_id = str(schedule["content_id"])
    platform = str(schedule["platform"])
    post_id = str(schedule.get("provider_post_id") or "")
    if not post_id:
        return "NO_POST_ID"
    state = get_buffer_post(api_key, post_id)
    if state.get("sent_at") or state.get("external_link"):
        patch_schedule(
            str(schedule["id"]),
            {
                "status": "PUBBLICATO",
                "published_url": state.get("external_link"),
                "confirmation_kind": "BUFFER_SENT",
                "confirmed_at": now_iso(),
                "last_error": None,
            },
        )
        log_event(
            owner_id, content_id, platform, "PUBBLICATO", "Pubblicazione confermata da Buffer",
            {"post_id": post_id, "url": state.get("external_link"), "buffer_status": state.get("buffer_status")},
        )
        update_content_if_finished(owner_id, content_id)
        return "PUBLISHED"
    if str(state.get("buffer_status") or "").lower() in {"error", "failed"}:
        patch_schedule(
            str(schedule["id"]),
            {
                "status": "ERRORE",
                "last_error": "Buffer ha segnalato errore",
                "retry_count": int(schedule.get("retry_count") or 0) + 1,
            },
        )
        log_event(owner_id, content_id, platform, "ERRORE", "Buffer ha segnalato errore", {"post_id": post_id})
        return "ERROR"
    patch_schedule(str(schedule["id"]), {"status": "INVIATO", "last_error": None})
    return "PENDING"


def send(schedule: dict[str, Any], api_key: str, channels: dict[str, str], dry_run: bool) -> str:
    owner_id = str(schedule["owner_id"])
    content_id = str(schedule["content_id"])
    platform = str(schedule["platform"]).lower()
    schedule_id = str(schedule["id"])

    if platform not in SUPPORTED:
        return "UNSUPPORTED"

    channel_id = channels.get(platform, "")
    if not channel_id:
        raise MartaPublishError(f"Nessun canale Buffer configurato per {platform}")
    integration(owner_id, platform, channel_id)
    variant = approved_variant(owner_id, content_id, platform)
    content = content_row(owner_id, content_id)
    caption = approved_caption(variant)

    due = parse_iso(str(schedule["scheduled_for"]))
    now = datetime.now(timezone.utc)
    if due > now + SEND_AHEAD:
        return "NOT_DUE"
    if due < now - PAST_DUE_GRACE:
        raise MartaPublishError("Programmazione scaduta da oltre 60 minuti")

    bucket, storage_path, mime = choose_media(content)
    media = download_private(bucket, storage_path, schedule_id, mime)
    try:
        rel = str(media.relative_to(ROOT)).replace("\\", "/")
        job = {
            "id": f"marta-dashboard-{schedule_id}",
            "client_id": CLIENT_ID,
            "title": str(content.get("title") or "Marta Ruffino"),
            "caption": caption,
            "format": "reel",
            "media": [rel],
            "scheduled_at": due.isoformat(),
            "platforms": [platform],
            "ai_assisted": False,
            "video_made_with_ai": False,
        }
        if dry_run:
            return "DRY_RUN_OK"
        hosted = ensure_cloudinary_assets(job, CLOUDINARY_URL)
        result = create_buffer_post(api_key, channel_id, platform, job, hosted, datetime.now(ROME))
        patch_schedule(
            schedule_id,
            {
                "status": "INVIATO",
                "provider_post_id": result.get("post_id"),
                "confirmation_kind": "BUFFER_ACCEPTED",
                "confirmed_at": None,
                "last_error": None,
            },
        )
        log_event(
            owner_id, content_id, platform, "INVIATO", "Contenuto accettato da Buffer",
            {
                "post_id": result.get("post_id"),
                "channel_id": channel_id,
                "due_at": result.get("due_at"),
            },
        )
        return "SENT"
    finally:
        shutil.rmtree(MEDIA_ROOT / schedule_id, ignore_errors=True)


def run(dry_run: bool = False, diagnose: bool = False) -> dict[str, Any]:
    if not SUPABASE_URL or not SERVICE_KEY:
        raise MartaPublishError("Supabase server credentials non configurate")
    if not CLOUDINARY_URL:
        raise MartaPublishError("Cloudinary Free non configurato")

    client = load_client(CLIENT_ID)
    api_key = secret_for_client(client)
    _, channels = buffer_config(client)

    report: dict[str, Any] = {
        "at": now_iso(),
        "dry_run": dry_run,
        "diagnose": diagnose,
        "channels": {},
        "results": [],
        "errors": [],
    }

    from buffer_queue_publish import verify_client
    verified = verify_client(CLIENT_ID)
    report["channels"] = verified.get("channels") or {}
    if diagnose:
        return report

    schedules = rest_get(
        "marta_schedules",
        {
            "select": (
                "id,owner_id,content_id,platform,scheduled_for,status,fallback_level,"
                "provider_post_id,published_url,confirmation_kind,confirmed_at,last_error,retry_count"
            ),
            "platform": "in.(facebook,instagram)",
            "status": "in.(PROGRAMMATO,INVIATO)",
            "order": "scheduled_for.asc",
            "limit": "200",
        },
    )

    for s in schedules:
        sid = str(s.get("id"))
        try:
            if s.get("provider_post_id") or str(s.get("status")) == "INVIATO":
                status = reconcile(s, api_key)
            else:
                status = send(s, api_key, channels, dry_run)
            report["results"].append({"schedule_id": sid, "platform": s.get("platform"), "status": status})
        except Exception as exc:
            msg = str(exc)[:900]
            report["errors"].append({"schedule_id": sid, "platform": s.get("platform"), "error": msg})
            if not dry_run:
                try:
                    patch_schedule(
                        sid,
                        {
                            "status": "ERRORE",
                            "last_error": msg,
                            "retry_count": int(s.get("retry_count") or 0) + 1,
                        },
                    )
                    log_event(str(s.get("owner_id")), str(s.get("content_id")), str(s.get("platform")), "ERRORE", msg)
                except Exception as inner:
                    print(f"WARN error state not persisted: {inner}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    args = parser.parse_args()
    try:
        report = run(dry_run=args.dry_run, diagnose=args.diagnose)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report.get("errors") else 0
    except Exception as exc:
        print(json.dumps({"status": "MARTA_PUBLISHER_FAILED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
