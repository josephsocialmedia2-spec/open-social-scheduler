#!/usr/bin/env python3
"""Move F1 Social media from Supabase hot storage to Cloudinary cold storage.

Policy:
- HOT media stay in Supabase only when publication is due within the hot window.
- Unscheduled or later media are archived to Cloudinary, verified, then removed from Supabase Storage.
- Metadata remains in f1_content_media so the Content Hub still knows the file.
- DELETE_PENDING rows are removed from both storage providers before the content record is deleted.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import cloudinary
import cloudinary.uploader
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()
REQUEST_TIMEOUT = 60
HOT_WINDOW_MINUTES = max(0, int(os.getenv("F1_MEDIA_HOT_WINDOW_MINUTES", "120") or "120"))
BATCH_SIZE = max(1, int(os.getenv("F1_MEDIA_ARCHIVE_BATCH_SIZE", "12") or "12"))
PUBLISHED = {"PUBBLICATO", "PUBLISHED", "COMPLETED", "SUCCESS"}


class ArchiveError(RuntimeError):
    pass


def headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    out = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        out.update(extra)
    return out


def is_restricted(response: requests.Response) -> bool:
    text = (response.text or "").lower()
    return response.status_code == 402 or "service for this project is restricted" in text


def rest_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers(),
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    if is_restricted(response):
        print("MEDIA_ARCHIVE_SKIPPED service_restricted")
        raise SystemExit(0)
    if not response.ok:
        raise ArchiveError(f"GET {table}: {response.status_code} {response.text[:700]}")
    payload = response.json()
    return payload if isinstance(payload, list) else []


def rest_patch(table: str, row_id: str, payload: dict[str, Any]) -> None:
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{row_id}"},
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if is_restricted(response):
        print("MEDIA_ARCHIVE_SKIPPED service_restricted")
        raise SystemExit(0)
    if not response.ok:
        raise ArchiveError(f"PATCH {table}: {response.status_code} {response.text[:700]}")


def rest_delete(table: str, row_id: str) -> None:
    response = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{row_id}"},
        timeout=REQUEST_TIMEOUT,
    )
    if is_restricted(response):
        print("MEDIA_ARCHIVE_SKIPPED service_restricted")
        raise SystemExit(0)
    if not response.ok:
        raise ArchiveError(f"DELETE {table}: {response.status_code} {response.text[:700]}")


def parse_iso(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def storage_download(path: str, dest: Path) -> None:
    clean = str(path or "").lstrip("/")
    encoded = "/".join(quote(part, safe="") for part in clean.split("/"))
    response = requests.get(
        f"{SUPABASE_URL}/storage/v1/object/f1-content-media/{encoded}",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
        stream=True,
        timeout=180,
    )
    if is_restricted(response):
        print("MEDIA_ARCHIVE_SKIPPED service_restricted")
        raise SystemExit(0)
    if not response.ok:
        raise ArchiveError(f"Storage download: {response.status_code} {response.text[:500]}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                fh.write(chunk)
    if not dest.exists() or dest.stat().st_size <= 0:
        raise ArchiveError("Storage download vuoto")


def storage_delete(path: str) -> None:
    clean = str(path or "").lstrip("/")
    if not clean:
        return
    response = requests.delete(
        f"{SUPABASE_URL}/storage/v1/object/f1-content-media",
        headers=headers(),
        json={"prefixes": [clean]},
        timeout=REQUEST_TIMEOUT,
    )
    if is_restricted(response):
        print("MEDIA_ARCHIVE_SKIPPED service_restricted")
        raise SystemExit(0)
    if response.status_code == 404:
        return
    if not response.ok:
        raise ArchiveError(f"Storage delete: {response.status_code} {response.text[:500]}")


def cloudinary_ready() -> bool:
    return bool(CLOUDINARY_URL and CLOUDINARY_URL.startswith("cloudinary://"))


def configure_cloudinary() -> None:
    if not cloudinary_ready():
        return
    # The SDK reads CLOUDINARY_URL from the environment; secure=True only controls returned URLs.
    cloudinary.config(secure=True)


def cloudinary_upload(path: Path, content_id: str, media_id: str) -> dict[str, Any]:
    folder = f"f1-social-cold/{content_id}"
    options = {
        "resource_type": "auto",
        "folder": folder,
        "use_filename": True,
        "unique_filename": True,
        "overwrite": False,
        "tags": ["f1-social-cold", f"content-{content_id}", f"media-{media_id}"],
    }
    if path.stat().st_size >= 80 * 1024 * 1024:
        result = cloudinary.uploader.upload_large(
            str(path),
            chunk_size=20 * 1024 * 1024,
            **options,
        )
    else:
        result = cloudinary.uploader.upload(str(path), **options)
    if not isinstance(result, dict) or not result.get("public_id") or not result.get("secure_url"):
        raise ArchiveError("Cloudinary upload incompleto")
    return result


def cloudinary_destroy(public_id: str, resource_type: str) -> None:
    if not public_id:
        return
    result = cloudinary.uploader.destroy(
        public_id,
        resource_type=(resource_type or "image"),
        invalidate=True,
    )
    state = str((result or {}).get("result") or "").lower()
    if state not in {"ok", "not found"}:
        raise ArchiveError(f"Cloudinary destroy fallito: {result}")


def calendar_state() -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    rows = rest_get(
        "f1_content_calendar",
        {
            "select": "content_id,status,publication_at,last_checked_at,updated_at",
            "limit": "5000",
        },
    )
    by_content: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fully_published: set[str] = set()
    for row in rows:
        content_id = str(row.get("content_id") or "")
        if content_id:
            by_content[content_id].append(row)
    for content_id, content_rows in by_content.items():
        if content_rows and all(str(row.get("status") or "").upper() in PUBLISHED for row in content_rows):
            fully_published.add(content_id)
    return by_content, fully_published


def should_archive(content_id: str, calendar_rows: dict[str, list[dict[str, Any]]]) -> bool:
    rows = calendar_rows.get(content_id, [])
    if not rows:
        return True
    now = datetime.now(timezone.utc)
    future = [
        parse_iso(row.get("publication_at"))
        for row in rows
        if str(row.get("status") or "").upper() not in PUBLISHED
    ]
    future = [value for value in future if value is not None]
    if not future:
        return False
    nearest = min(future)
    return (nearest - now).total_seconds() > HOT_WINDOW_MINUTES * 60


def process_delete_pending(media_rows: list[dict[str, Any]], items: dict[str, dict[str, Any]], dry_run: bool) -> int:
    processed = 0
    by_content: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in media_rows:
        if str(row.get("storage_state") or "").upper() == "DELETE_PENDING":
            by_content[str(row.get("content_id") or "")].append(row)

    for content_id, rows in by_content.items():
        for row in rows:
            if dry_run:
                print(f"MEDIA_DELETE_DRY_RUN content={content_id} media={row.get('id')}")
                continue
            public_id = str(row.get("archive_public_id") or "")
            resource_type = str(row.get("archive_resource_type") or "image")
            if public_id:
                cloudinary_destroy(public_id, resource_type)
            if row.get("storage_path") and not row.get("hot_deleted_at"):
                try:
                    storage_delete(str(row["storage_path"]))
                except ArchiveError as exc:
                    print(f"WARN hot delete during pending cleanup: {exc}")
            rest_delete("f1_content_media", str(row["id"]))
            processed += 1

        item = items.get(content_id)
        if not dry_run and item and item.get("deletion_requested_at"):
            remaining = rest_get(
                "f1_content_media",
                {"select": "id", "content_id": f"eq.{content_id}", "limit": "1"},
            )
            if not remaining:
                rest_delete("f1_content_items", content_id)
                print(f"MEDIA_DELETE_CONTENT_COMPLETED content={content_id}")
    return processed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        raise ArchiveError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    if not cloudinary_ready():
        print("MEDIA_ARCHIVE_SKIPPED cloudinary_not_configured")
        return 0
    configure_cloudinary()

    calendar_rows, fully_published = calendar_state()
    items_list = rest_get(
        "f1_content_items",
        {"select": "id,status,deletion_requested_at", "limit": "5000"},
    )
    items = {str(row.get("id") or ""): row for row in items_list}
    media_rows = rest_get(
        "f1_content_media",
        {
            "select": (
                "id,content_id,client_id,owner_id,file_name,mime_type,storage_path,file_size,"
                "archive_provider,archive_public_id,archive_asset_id,archive_resource_type,"
                "archive_url,archived_at,storage_state,hot_deleted_at"
            ),
            "order": "created_at.asc",
            "limit": "5000",
        },
    )

    pending_count = process_delete_pending(media_rows, items, args.dry_run)

    archived = 0
    hot_deleted = 0
    considered = 0

    for row in media_rows:
        if archived >= BATCH_SIZE:
            break
        state = str(row.get("storage_state") or "HOT").upper()
        if state == "DELETE_PENDING":
            continue
        content_id = str(row.get("content_id") or "")
        if not content_id or content_id in fully_published:
            continue

        # Finish removal of the hot copy after a previously successful archive.
        if state == "COLD" and row.get("archive_url") and row.get("storage_path") and not row.get("hot_deleted_at"):
            if args.dry_run:
                print(f"MEDIA_ARCHIVE_DRY_RUN hot_cleanup media={row.get('id')}")
                continue
            storage_delete(str(row["storage_path"]))
            rest_patch(
                "f1_content_media",
                str(row["id"]),
                {"hot_deleted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            )
            hot_deleted += 1
            continue

        if state != "HOT" or row.get("archive_url"):
            continue
        if not should_archive(content_id, calendar_rows):
            continue

        considered += 1
        if args.dry_run:
            print(
                f"MEDIA_ARCHIVE_DRY_RUN content={content_id} media={row.get('id')} "
                f"bytes={int(row.get('file_size') or 0)}"
            )
            continue

        suffix = Path(str(row.get("file_name") or "media.bin")).suffix or ".bin"
        with tempfile.TemporaryDirectory(prefix="f1-cold-") as td:
            local = Path(td) / f"{row['id']}{suffix}"
            storage_download(str(row.get("storage_path") or ""), local)
            result = cloudinary_upload(local, content_id, str(row["id"]))
            public_id = str(result.get("public_id") or "")
            resource_type = str(result.get("resource_type") or "image")
            try:
                rest_patch(
                    "f1_content_media",
                    str(row["id"]),
                    {
                        "archive_provider": "cloudinary",
                        "archive_public_id": public_id,
                        "archive_asset_id": result.get("asset_id"),
                        "archive_resource_type": resource_type,
                        "archive_url": result.get("secure_url"),
                        "archived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "storage_state": "COLD",
                    },
                )
            except Exception:
                try:
                    cloudinary_destroy(public_id, resource_type)
                except Exception as cleanup_exc:
                    print(f"WARN Cloudinary rollback failed: {cleanup_exc}")
                raise

            storage_delete(str(row.get("storage_path") or ""))
            rest_patch(
                "f1_content_media",
                str(row["id"]),
                {"hot_deleted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            )
            archived += 1
            hot_deleted += 1
            print(
                f"MEDIA_ARCHIVED content={content_id} media={row.get('id')} "
                f"bytes={local.stat().st_size} provider=cloudinary"
            )

    print(
        "MEDIA_ARCHIVE_COMPLETED "
        f"considered={considered} archived={archived} hot_deleted={hot_deleted} "
        f"delete_pending={pending_count} hot_window_minutes={HOT_WINDOW_MINUTES}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
