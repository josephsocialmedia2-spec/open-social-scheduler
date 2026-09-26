#!/usr/bin/env python3
"""Bridge F1 Content Hub (Supabase) -> existing publisher/queue.json.

Design goals:
- one queue only: publisher/queue.json
- idempotent stable job ids derived from f1_content_calendar.id
- no accidental cross-client publishing: a social channel must be enabled+verified
- no frontend secrets: this script runs server-side in GitHub Actions
- bidirectional status sync back to Supabase
- media is materialized from Supabase Storage or the linked property images on each runner
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"
MEDIA_ROOT = ROOT / "publisher" / "media" / "supabase"

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
REQUEST_TIMEOUT = 45

PLATFORM_MAP = {
    "facebook": "facebook",
    "instagram": "instagram",
    "linkedin": "linkedin-page",
    "linkedin-page": "linkedin-page",
    "youtube": "youtube",
    "tiktok": "tiktok",
    "pinterest": "pinterest",
}


class BridgeError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_queue() -> dict[str, Any]:
    if not QUEUE_PATH.exists() or not QUEUE_PATH.read_text(encoding="utf-8").strip():
        return {"version": 6, "updated_at": now_iso(), "jobs": []}
    data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BridgeError("publisher/queue.json must contain a JSON object")
    data.setdefault("version", 6)
    data.setdefault("jobs", [])
    return data


def save_queue(queue: dict[str, Any]) -> None:
    queue["version"] = max(int(queue.get("version") or 0), 6)
    queue["updated_at"] = now_iso()
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    out = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        out.update(extra)
    return out


def rest_get(path: str, params: dict[str, str] | None = None) -> Any:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers=headers(),
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise BridgeError(f"Supabase GET {path}: {r.status_code} {r.text[:900]}")
    return r.json()


def rest_patch(path: str, match: dict[str, str], payload: dict[str, Any]) -> None:
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers=headers({"Prefer": "return=minimal"}),
        params=params,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise BridgeError(f"Supabase PATCH {path}: {r.status_code} {r.text[:900]}")


def rest_post(path: str, payload: dict[str, Any]) -> None:
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers=headers({"Prefer": "return=minimal"}),
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise BridgeError(f"Supabase POST {path}: {r.status_code} {r.text[:900]}")


def normalize_platform(value: str) -> str:
    key = re.sub(r"\s+", "-", str(value or "").strip().lower())
    return PLATFORM_MAP.get(key, key)


def safe_name(value: str, fallback: str = "media.bin") -> str:
    value = Path(str(value or fallback)).name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return clean or fallback


def download_url(url: str, dest: Path, auth: bool = False) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req_headers = {"Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY} if auth else {}
    r = requests.get(url, headers=req_headers, timeout=90)
    if not r.ok:
        raise BridgeError(f"media download failed {r.status_code}: {url}")
    dest.write_bytes(r.content)
    if dest.stat().st_size == 0:
        raise BridgeError(f"empty media downloaded: {url}")
    return str(dest.relative_to(ROOT)).replace("\\", "/")


def materialize_media(calendar_id: str, item: dict[str, Any], properties: dict[str, dict[str, Any]]) -> tuple[list[str], str]:
    media_rows = item.get("f1_content_media") or []
    paths: list[str] = []
    detected_type = ""

    for index, media in enumerate(media_rows, 1):
        storage_path = str(media.get("storage_path") or "").lstrip("/")
        if not storage_path:
            continue
        file_name = safe_name(str(media.get("file_name") or f"media-{index}.bin"))
        dest = MEDIA_ROOT / calendar_id / file_name
        encoded = "/".join(quote(part, safe="") for part in storage_path.split("/"))
        url = f"{SUPABASE_URL}/storage/v1/object/f1-content-media/{encoded}"
        paths.append(download_url(url, dest, auth=True))
        if not detected_type:
            detected_type = str(media.get("mime_type") or mimetypes.guess_type(file_name)[0] or "")

    if not paths:
        property_id = str(item.get("property_id") or "")
        prop = properties.get(property_id)
        candidates: list[str] = []
        if prop:
            cover = str(prop.get("cover_image_url") or "").strip()
            if cover:
                candidates.append(cover)
            for value in prop.get("image_urls") or []:
                value = str(value or "").strip()
                if value and value not in candidates:
                    candidates.append(value)
        for index, url in enumerate(candidates[:10], 1):
            ext = Path(url.split("?", 1)[0]).suffix.lower()
            if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                ext = ".jpg"
            dest = MEDIA_ROOT / calendar_id / f"property-{index:02d}{ext}"
            try:
                paths.append(download_url(url, dest, auth=False))
                if not detected_type:
                    detected_type = mimetypes.guess_type(dest.name)[0] or "image/jpeg"
            except Exception as exc:
                print(f"WARN media fallback {calendar_id}: {exc}")

    return paths, detected_type


def channel_key(client_id: str, platform: str) -> str:
    return f"{client_id}:{platform}"


def load_source_rows() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    calendars = rest_get(
        "f1_content_calendar",
        {
            "select": (
                "id,owner_id,content_id,client_id,platform,publication_at,status,queue_job_id,"
                "provider,external_post_id,external_url,retry_count,error,"
                "f1_content_items(id,title,description,source_text,status,campaign,property_id,source,tiktok_settings,"
                "f1_content_media(id,file_name,mime_type,storage_path,file_size)),"
                "f1_content_clients(id,name,slug,timezone,auto_publish,approval_required)"
            ),
            "order": "publication_at.asc",
            "limit": "1000",
        },
    )
    channels = rest_get(
        "f1_client_social_channels",
        {"select": "*", "limit": "1000"},
    )
    properties = rest_get(
        "f1_content_properties",
        {"select": "id,cover_image_url,image_urls", "limit": "1000"},
    )
    channel_map = {
        channel_key(str(row.get("client_id")), normalize_platform(str(row.get("platform")))): row
        for row in channels
    }
    property_map = {str(row.get("id")): row for row in properties}
    return calendars, channel_map, property_map


def event(row: dict[str, Any], action: str, status: str, **extra: Any) -> None:
    payload = {
        "owner_id": row.get("owner_id"),
        "client_id": row.get("client_id"),
        "content_id": row.get("content_id"),
        "calendar_id": row.get("id"),
        "queue_job_id": f"supabase-calendar-{row.get('id')}",
        "provider": extra.pop("provider", None),
        "platform": normalize_platform(str(row.get("platform") or "")),
        "action": action,
        "status": status,
        "retry_count": int(extra.pop("retry_count", 0) or 0),
        "error": extra.pop("error", None),
        "details": extra,
    }
    try:
        rest_post("f1_publication_events", payload)
    except Exception as exc:
        print(f"WARN publication event not written: {exc}")


def build_or_update_jobs(queue: dict[str, Any]) -> dict[str, int]:
    calendars, channels, properties = load_source_rows()
    jobs: list[dict[str, Any]] = queue.setdefault("jobs", [])
    by_id = {str(job.get("id")): job for job in jobs if job.get("id")}
    stats = {"created": 0, "updated": 0, "blocked": 0, "ready": 0, "skipped": 0}

    accepted_calendar_states = {
        "PROGRAMMATO", "APPROVATO", "CANALE_DA_COLLEGARE", "ERRORE_QUEUE",
        "IN PUBBLICAZIONE", "ERRORE_PUBBLICAZIONE", "ERRORE_MEDIA",
        "AUTO_PUBLISH_DISATTIVATO", "APPROVAZIONE_RICHIESTA",
        "CREDENZIALI_MANCANTI", "AUTH_REQUIRED", "DA_RIAUTORIZZARE",
        "TIKTOK_REVIEW_REQUIRED"
    }

    for row in calendars:
        if str(row.get("status") or "") not in accepted_calendar_states:
            stats["skipped"] += 1
            continue

        client = row.get("f1_content_clients") or {}
        item = row.get("f1_content_items") or {}
        slug = str(client.get("slug") or "").strip()
        if not slug or not item:
            stats["skipped"] += 1
            continue

        platform = normalize_platform(str(row.get("platform") or ""))
        job_id = f"supabase-calendar-{row['id']}"
        channel = channels.get(channel_key(str(row.get("client_id")), platform))
        channel_ok = bool(channel and channel.get("enabled") and channel.get("verified"))
        auto_publish = bool(client.get("auto_publish"))
        approval_required = bool(client.get("approval_required", True))
        item_status = str(item.get("status") or "")
        approval_ok = (not approval_required) or item_status in {"APPROVATO", "PROGRAMMATO", "IN PUBBLICAZIONE", "PUBBLICATO"}

        reason = ""
        if not channel_ok:
            reason = "CANALE_DA_COLLEGARE"
        elif not auto_publish:
            reason = "AUTO_PUBLISH_DISATTIVATO"
        elif not approval_ok:
            reason = "APPROVAZIONE_RICHIESTA"

        tiktok_settings = item.get("tiktok_settings") if isinstance(item.get("tiktok_settings"), dict) else {}
        if not reason and platform == "tiktok":
            mode = str(tiktok_settings.get("mode") or "").upper()
            scopes = {str(x) for x in (channel or {}).get("scopes") or []}
            if not tiktok_settings.get("consent_confirmed"):
                reason = "TIKTOK_REVIEW_REQUIRED"
            elif mode not in {"DIRECT_POST", "DRAFT_UPLOAD"}:
                reason = "TIKTOK_REVIEW_REQUIRED"
            elif mode == "DIRECT_POST" and not str(tiktok_settings.get("privacy_level") or ""):
                reason = "TIKTOK_REVIEW_REQUIRED"
            elif mode == "DIRECT_POST" and scopes and "video.publish" not in scopes:
                reason = "AUTH_REQUIRED"
            elif mode == "DRAFT_UPLOAD" and scopes and "video.upload" not in scopes:
                reason = "AUTH_REQUIRED"

        media_paths: list[str] = []
        mime = ""
        if not reason:
            try:
                media_paths, mime = materialize_media(str(row["id"]), item, properties)
            except Exception as exc:
                reason = "ERRORE_MEDIA"
                row["error"] = str(exc)
            if not media_paths:
                reason = "ERRORE_MEDIA"
                row["error"] = "Nessun media disponibile nel Content Hub o nella scheda immobile"

        fmt = "reel" if (mime.startswith("video/") or any(Path(p).suffix.lower() in {".mp4", ".mov", ".m4v"} for p in media_paths)) else "post"
        caption = str(item.get("description") or item.get("source_text") or "").strip()
        job = by_id.get(job_id)
        new_job = {
            "id": job_id,
            "enabled": not bool(reason),
            "status": "ready" if not reason else "blocked",
            "client_id": slug,
            "client_name": str(client.get("name") or slug),
            "title": str(item.get("title") or "Contenuto"),
            "caption": caption,
            "format": fmt,
            "media": media_paths,
            "scheduled_at": str(row.get("publication_at")),
            "platforms": [platform],
            "published_platforms": list((job or {}).get("published_platforms") or []),
            "source": "SUPABASE_CONTENT_HUB",
            "supabase_calendar_id": row.get("id"),
            "supabase_content_id": row.get("content_id"),
            "supabase_client_id": row.get("client_id"),
            "campaign": item.get("campaign"),
            "property_id": item.get("property_id"),
            "provider": (channel or {}).get("provider") or "direct",
            "provider_channel_id": (channel or {}).get("external_channel_id"),
            "provider_secret_prefix": (channel or {}).get("secret_prefix"),
            "tiktok_settings": tiktok_settings if platform == "tiktok" else {},
            "retry_count": int((job or {}).get("retry_count") or 0),
            "created_by": "supabase-queue-bridge",
            "autonomous_publish": True,
        }
        if reason:
            new_job["blocked_reason"] = reason
        else:
            new_job.pop("blocked_reason", None)

        if job is None:
            jobs.append(new_job)
            by_id[job_id] = new_job
            stats["created"] += 1
        else:
            published_platforms = list(job.get("published_platforms") or [])
            direct_results = list(job.get("direct_api_results") or [])
            buffer_posts = list(job.get("buffer_posts") or [])
            buffer_scheduled_platforms = list(job.get("buffer_scheduled_platforms") or [])
            cloudinary_assets = list(job.get("cloudinary_assets") or [])
            external_post_id = job.get("external_post_id")
            external_url = job.get("external_url")
            tiktok_publish_id = job.get("tiktok_publish_id")
            tiktok_publish_mode = job.get("tiktok_publish_mode")
            tiktok_last_status = job.get("tiktok_last_status")
            processing_platforms = list(job.get("processing_platforms") or [])
            review_required_platforms = list(job.get("review_required_platforms") or [])
            prior_status = str(job.get("status") or "")
            job.clear()
            job.update(new_job)
            job["published_platforms"] = published_platforms
            if direct_results:
                job["direct_api_results"] = direct_results
            if buffer_posts:
                job["buffer_posts"] = buffer_posts
            if buffer_scheduled_platforms:
                job["buffer_scheduled_platforms"] = buffer_scheduled_platforms
            if cloudinary_assets:
                job["cloudinary_assets"] = cloudinary_assets
            if external_post_id:
                job["external_post_id"] = external_post_id
            if external_url:
                job["external_url"] = external_url
            if tiktok_publish_id:
                job["tiktok_publish_id"] = tiktok_publish_id
            if tiktok_publish_mode:
                job["tiktok_publish_mode"] = tiktok_publish_mode
            if tiktok_last_status:
                job["tiktok_last_status"] = tiktok_last_status
            if processing_platforms:
                job["processing_platforms"] = processing_platforms
            if review_required_platforms:
                job["review_required_platforms"] = review_required_platforms
            if buffer_posts and prior_status != "published":
                job["status"] = "buffer_scheduled"
                job["enabled"] = True
                job.pop("blocked_reason", None)
            if prior_status == "published":
                job["status"] = "published"
                job["enabled"] = False
                job.pop("blocked_reason", None)
            elif prior_status == "partially_published" and tiktok_publish_id and not reason:
                job["status"] = "partially_published"
                job["enabled"] = True
                job["blocked_reason"] = "IN_PUBBLICAZIONE"
            stats["updated"] += 1

        target_status = "PROGRAMMATO" if not reason else reason
        patch = {
            "queue_job_id": job_id,
            "provider": (channel or {}).get("provider") or "direct",
            "last_checked_at": now_iso(),
            "error": row.get("error") if reason.startswith("ERRORE") else None,
        }
        if str(row.get("status")) != target_status and str(row.get("status")) != "PUBBLICATO":
            patch["status"] = target_status
            event(row, "QUEUE_BRIDGE", target_status, provider=patch["provider"], error=patch["error"])
        rest_patch("f1_content_calendar", {"id": str(row["id"])}, patch)

        if reason:
            stats["blocked"] += 1
        else:
            stats["ready"] += 1

    save_queue(queue)
    return stats


def extract_external(job: dict[str, Any]) -> tuple[str | None, str | None]:
    if job.get("tiktok_publish_id"):
        return str(job.get("tiktok_publish_id")), None
    if job.get("external_post_id") or job.get("external_url"):
        return (
            str(job.get("external_post_id")) if job.get("external_post_id") else None,
            str(job.get("external_url")) if job.get("external_url") else None,
        )
    for row in reversed(job.get("buffer_posts") or []):
        external_id = row.get("post_id")
        external_url = row.get("external_link")
        if external_id or external_url:
            return (
                str(external_id) if external_id else None,
                str(external_url) if external_url else None,
            )
    results = job.get("direct_api_results") or []
    for batch in reversed(results):
        for row in reversed(batch.get("results") or []):
            if row.get("status") != "published":
                continue
            payload = row.get("result") or {}
            external_id = (
                payload.get("id") or payload.get("media_id") or payload.get("video_id")
                or payload.get("publish_id") or payload.get("post_id")
            )
            external_url = payload.get("url") or payload.get("permalink")
            return (str(external_id) if external_id else None, str(external_url) if external_url else None)
    return None, None


def sync_back(queue: dict[str, Any]) -> dict[str, int]:
    stats = {"published": 0, "in_progress": 0, "errors": 0, "unchanged": 0}
    for job in queue.get("jobs", []):
        if job.get("source") != "SUPABASE_CONTENT_HUB":
            continue
        calendar_id = str(job.get("supabase_calendar_id") or "")
        content_id = str(job.get("supabase_content_id") or "")
        if not calendar_id:
            continue

        q_status = str(job.get("status") or "")
        if q_status == "published":
            is_tiktok_draft = (
                str(job.get("tiktok_publish_mode") or "").upper() == "DRAFT_UPLOAD"
                and str((job.get("tiktok_last_status") or {}).get("status") or "") == "SEND_TO_USER_INBOX"
            )
            target = "BOZZA_TIKTOK_INVIATA" if is_tiktok_draft else "PUBBLICATO"
        elif q_status == "partially_published":
            target = "IN PUBBLICAZIONE"
        elif q_status in {"ready", "buffer_scheduled"}:
            target = "PROGRAMMATO"
        elif q_status == "blocked":
            target = str(job.get("blocked_reason") or "ERRORE_QUEUE")
        else:
            stats["unchanged"] += 1
            continue

        rows = rest_get("f1_content_calendar", {"select": "id,owner_id,client_id,content_id,platform,status,retry_count", "id": f"eq.{calendar_id}", "limit": "1"})
        if not rows:
            continue
        row = rows[0]
        external_id, external_url = extract_external(job)
        patch: dict[str, Any] = {
            "status": target,
            "last_checked_at": now_iso(),
            "provider": job.get("provider") or "direct",
            "external_post_id": external_id,
            "external_url": external_url,
            "queue_job_id": job.get("id"),
        }
        if normalize_platform(str(row.get("platform") or "")) == "tiktok":
            patch["platform_metadata"] = {
                "tiktok_publish_id": job.get("tiktok_publish_id"),
                "tiktok_publish_mode": job.get("tiktok_publish_mode"),
                "tiktok_last_status": job.get("tiktok_last_status"),
                "processing_platforms": job.get("processing_platforms") or [],
                "review_required_platforms": job.get("review_required_platforms") or [],
            }

        if target == "PUBBLICATO":
            stats["published"] += 1
            if content_id:
                rest_patch("f1_content_items", {"id": content_id}, {"status": "PUBBLICATO"})
        elif target == "BOZZA_TIKTOK_INVIATA":
            stats["published"] += 1
            if content_id:
                rest_patch("f1_content_items", {"id": content_id}, {"status": "BOZZA_TIKTOK_INVIATA"})
        elif target == "IN PUBBLICAZIONE":
            stats["in_progress"] += 1
        elif target.startswith("ERRORE") or target == "CREDENZIALI_MANCANTI":
            stats["errors"] += 1

        if str(row.get("status")) != target:
            event(row, "QUEUE_SYNC_BACK", target, provider=patch["provider"], external_id=external_id, external_url=external_url)
        rest_patch("f1_content_calendar", {"id": calendar_id}, patch)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-back-only", action="store_true")
    parser.add_argument("--ingest-only", action="store_true")
    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        print("BRIDGE_DISABLED: configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in GitHub Actions secrets/variables")
        return 0

    queue = load_queue()
    report: dict[str, Any] = {"at": now_iso()}
    if not args.ingest_only:
        report["sync_back"] = sync_back(queue)
    if not args.sync_back_only:
        report["ingest"] = build_or_update_jobs(queue)
    else:
        save_queue(queue)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
