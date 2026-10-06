#!/usr/bin/env python3
"""Delete hot Supabase media after every scheduled platform confirms publication.

Safety rules:
- never delete before every calendar row for the content is terminal-published;
- wait a configurable grace period after the last publication confirmation;
- never delete a Storage object while another media row still references its path;
- keep captions, calendar history and external post identifiers in Postgres.
"""
from __future__ import annotations

import argparse
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
REQUEST_TIMEOUT = 45
GRACE_MINUTES = max(0, int(os.getenv("F1_MEDIA_CLEANUP_GRACE_MINUTES", "360") or "360"))
BATCH_CONTENTS = max(1, int(os.getenv("F1_MEDIA_CLEANUP_BATCH_CONTENTS", "25") or "25"))
TERMINAL_PUBLISHED = {"PUBBLICATO", "PUBLISHED", "COMPLETED", "SUCCESS"}


class CleanupError(RuntimeError):
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


def restricted(response: requests.Response) -> bool:
    text = (response.text or "").lower()
    return response.status_code == 402 or "service for this project is restricted" in text


def rest_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers(),
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    if restricted(response):
        print("MEDIA_CLEANUP_SKIPPED service_restricted")
        raise SystemExit(0)
    if not response.ok:
        raise CleanupError(f"GET {table}: {response.status_code} {response.text[:600]}")
    payload = response.json()
    return payload if isinstance(payload, list) else []


def rest_delete(table: str, row_id: str) -> None:
    response = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{row_id}"},
        timeout=REQUEST_TIMEOUT,
    )
    if restricted(response):
        print("MEDIA_CLEANUP_SKIPPED service_restricted")
        raise SystemExit(0)
    if not response.ok:
        raise CleanupError(f"DELETE {table}: {response.status_code} {response.text[:600]}")


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
    if restricted(response):
        print("MEDIA_CLEANUP_SKIPPED service_restricted")
        raise SystemExit(0)
    if response.status_code == 404:
        return
    if not response.ok:
        raise CleanupError(f"Storage delete: {response.status_code} {response.text[:600]}")


def eligible_content_ids(calendars: list[dict[str, Any]]) -> list[str]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in calendars:
        content_id = str(row.get("content_id") or "")
        if content_id:
            grouped[content_id].append(row)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=GRACE_MINUTES)
    eligible: list[tuple[datetime, str]] = []

    for content_id, rows in grouped.items():
        if not rows:
            continue
        if any(str(row.get("status") or "").upper() not in TERMINAL_PUBLISHED for row in rows):
            continue

        publication_times = [parse_iso(row.get("publication_at")) for row in rows]
        publication_times = [value for value in publication_times if value is not None]
        if publication_times and max(publication_times) > now:
            continue

        confirmations = [
            parse_iso(row.get("last_checked_at")) or parse_iso(row.get("updated_at"))
            for row in rows
        ]
        confirmations = [value for value in confirmations if value is not None]
        if not confirmations:
            continue
        last_confirmation = max(confirmations)
        if last_confirmation > cutoff:
            continue
        eligible.append((last_confirmation, content_id))

    eligible.sort(key=lambda pair: pair[0])
    return [content_id for _, content_id in eligible[:BATCH_CONTENTS]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        raise CleanupError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    calendars = rest_get(
        "f1_content_calendar",
        {
            "select": "id,content_id,status,publication_at,updated_at,last_checked_at",
            "limit": "5000",
        },
    )
    candidates = eligible_content_ids(calendars)
    if not candidates:
        print("MEDIA_CLEANUP no_eligible_content")
        return 0

    media = rest_get(
        "f1_content_media",
        {
            "select": "id,content_id,storage_path,file_size",
            "limit": "5000",
        },
    )
    refs_by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    media_by_content: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in media:
        content_id = str(row.get("content_id") or "")
        path = str(row.get("storage_path") or "")
        if content_id:
            media_by_content[content_id].append(row)
        if path:
            refs_by_path[path].append(row)

    deleted_rows = 0
    deleted_objects = 0
    released_bytes = 0

    for content_id in candidates:
        for row in media_by_content.get(content_id, []):
            media_id = str(row.get("id") or "")
            path = str(row.get("storage_path") or "")
            size = int(row.get("file_size") or 0)

            # Delete the binary only when this row is the last remaining DB reference.
            shared = len(refs_by_path.get(path, [])) > 1
            if args.dry_run:
                print(
                    f"MEDIA_CLEANUP_DRY_RUN content={content_id} media={media_id} "
                    f"shared={str(shared).lower()} bytes={size} path={quote(path, safe='/')}"
                )
                continue

            if path and not shared:
                storage_delete(path)
                deleted_objects += 1
                released_bytes += max(0, size)
            if media_id:
                rest_delete("f1_content_media", media_id)
                deleted_rows += 1
                if path in refs_by_path:
                    refs_by_path[path] = [
                        ref for ref in refs_by_path[path]
                        if str(ref.get("id") or "") != media_id
                    ]

    print(
        "MEDIA_CLEANUP_COMPLETED "
        f"contents={len(candidates)} rows={deleted_rows} "
        f"objects={deleted_objects} released_bytes={released_bytes} "
        f"grace_minutes={GRACE_MINUTES}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
