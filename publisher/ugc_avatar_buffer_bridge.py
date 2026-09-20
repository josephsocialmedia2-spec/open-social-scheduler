#!/usr/bin/env python3
"""Bridge Modal UGC Avatar outbox into the proven F1 Buffer publisher.

The script reuses publisher/buffer_twice_daily.py for Buffer discovery,
Cloudinary hosting and post creation. It never stores Buffer/Cloudinary
credentials in source code.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

import buffer_twice_daily as buffer

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"
MEDIA_DIR = ROOT / "publisher" / "media" / "generated" / "ugc-avatar-modal"
CREATED_BY = "ugc-avatar-modal-buffer-bridge"


def load_queue() -> dict[str, Any]:
    data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    data.setdefault("jobs", [])
    return data


def normalize_cloudinary_url(raw: str) -> str:
    value = str(raw or "").strip().strip('"').strip("'")
    if value.startswith("CLOUDINARY_URL="):
        value = value.split("=", 1)[1].strip().strip('"').strip("'")
    return value


def fetch_outbox(base_url: str) -> list[dict[str, Any]]:
    url = base_url.rstrip("/") + "/api/outbox"
    response = requests.get(url, timeout=60, headers={"User-Agent": "F1-UGC-Avatar-Bridge/1.0"})
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise RuntimeError("Modal /api/outbox did not return a jobs array")
    return [row for row in jobs if isinstance(row, dict)]


def existing_job(queue: dict[str, Any], source_job_id: str) -> dict[str, Any] | None:
    for job in queue.get("jobs", []):
        if (
            str(job.get("created_by")) == CREATED_BY
            and str(job.get("source_job_id")) == source_job_id
        ):
            return job
    return None


def download_video(row: dict[str, Any]) -> Path:
    job_id = str(row.get("job_id") or "").strip()
    url = str(row.get("video_url") or "").strip()
    if not job_id or not url.startswith("https://"):
        raise RuntimeError("UGC outbox row is missing job_id or https video_url")
    path = MEDIA_DIR / f"{job_id}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=300, stream=True, headers={"User-Agent": "F1-UGC-Avatar-Bridge/1.0"})
    response.raise_for_status()
    with path.open("wb") as fh:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                fh.write(chunk)
    if path.stat().st_size < 15_000:
        raise RuntimeError(f"Downloaded UGC video is unexpectedly small: {path.stat().st_size} bytes")
    return path


def make_job(row: dict[str, Any], path: Path) -> dict[str, Any]:
    now = datetime.now(buffer.ROME)
    due = now + timedelta(minutes=5)
    job_id = str(row["job_id"])
    return {
        "id": f"ugc-avatar-{job_id}",
        "client_id": str(row.get("client_id") or "f1-immobiliare"),
        "client_name": "F1 Immobiliare",
        "created_by": CREATED_BY,
        "source_job_id": job_id,
        "title": str(row.get("title") or "UGC Avatar"),
        "caption": str(row.get("caption") or ""),
        "hashtags": list(row.get("hashtags") or []),
        "format": "reel",
        "media": str(path.relative_to(ROOT)),
        "scheduled_at": due.isoformat(),
        "platforms": [
            {"platform": service, "integration_id": "buffer"}
            for service in buffer.TARGET_SERVICES
        ],
        "status": "buffer_pending",
        "buffer_posts": [],
        "buffer_scheduled_platforms": [],
        "approval_required": False,
        "manual_approval_required": False,
        "autonomous_publish": True,
        "quality_gate_passed": True,
        "video_made_with_ai": True,
        "test_mode": bool(row.get("test_mode", False)),
    }


def process_row(
    row: dict[str, Any],
    queue: dict[str, Any],
    api_key: str,
    cloudinary_url: str,
    organization_id: str,
    channels: dict[str, dict[str, str]],
    dry_run: bool,
) -> dict[str, Any]:
    source_job_id = str(row.get("job_id") or "").strip()
    if not source_job_id:
        raise RuntimeError("UGC row has no job_id")

    old = existing_job(queue, source_job_id)
    if old and set(buffer.TARGET_SERVICES).issubset(
        set(str(x) for x in old.get("buffer_scheduled_platforms", []))
    ):
        return {"job_id": source_job_id, "status": "already_scheduled"}

    if bool(row.get("test_mode")) and not dry_run:
        return {"job_id": source_job_id, "status": "test_mode_skipped_live"}

    path = download_video(row)
    try:
        template = make_job(row, path)
        if old:
            preserved = {
                "buffer_posts": list(old.get("buffer_posts", [])),
                "buffer_scheduled_platforms": list(old.get("buffer_scheduled_platforms", [])),
                "cloudinary_assets": list(old.get("cloudinary_assets", [])),
            }
            old.clear()
            old.update(template)
            old.update(preserved)
            job = old
        else:
            queue["jobs"].append(template)
            job = template

        job["buffer_organization_id"] = organization_id
        job["buffer_channels"] = channels
        hosted = buffer.ensure_cloudinary_assets(job, cloudinary_url)
        buffer.persist_queue(queue)

        if dry_run:
            job["status"] = "ugc_buffer_dry_run_ok"
            buffer.persist_queue(queue)
            return {
                "job_id": source_job_id,
                "status": job["status"],
                "channels": sorted(channels),
                "cloudinary": [x.get("url") for x in hosted],
            }

        scheduled = set(str(x) for x in job.get("buffer_scheduled_platforms", []))
        results: list[dict[str, Any]] = []
        for service in buffer.TARGET_SERVICES:
            if service in scheduled:
                continue
            try:
                result = buffer.create_buffer_post(
                    api_key,
                    str(channels[service]["id"]),
                    service,
                    job,
                    hosted,
                    datetime.now(buffer.ROME),
                )
                job.setdefault("buffer_posts", []).append(result)
                job.setdefault("buffer_scheduled_platforms", []).append(service)
                scheduled.add(service)
                results.append({**result, "status": "scheduled"})
                buffer.persist_queue(queue)
            except Exception as exc:
                results.append({"service": service, "status": "error", "error": str(exc)})

        if set(buffer.TARGET_SERVICES).issubset(scheduled):
            job["status"] = "scheduled_in_buffer"
            job.pop("blocked_reason", None)
        elif scheduled:
            job["status"] = "buffer_partially_scheduled"
            job["blocked_reason"] = "Buffer retry required for remaining UGC channels"
        else:
            job["status"] = "buffer_retry_required"
            job["blocked_reason"] = "Buffer did not schedule any UGC target channel"

        buffer.persist_queue(queue)
        return {"job_id": source_job_id, "status": job["status"], "results": results}
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", required=True, help="Public Modal UGC Avatar Studio base URL")
    parser.add_argument("--dry-run", action="store_true", help="Validate and upload media but do not create Buffer posts")
    parser.add_argument("--job-id", help="Optional exact Modal job ID")
    args = parser.parse_args()

    api_key = os.getenv("BUFFER_API_KEY", "").strip()
    cloudinary_url = normalize_cloudinary_url(os.getenv("CLOUDINARY_URL", ""))
    missing = [
        name for name, value in (
            ("BUFFER_API_KEY", api_key),
            ("CLOUDINARY_URL", cloudinary_url),
        ) if not value
    ]
    if missing:
        raise SystemExit("Missing GitHub Actions Secrets: " + ", ".join(missing))

    rows = fetch_outbox(args.source_url)
    if args.job_id:
        rows = [row for row in rows if str(row.get("job_id")) == args.job_id]
    if not rows:
        print(json.dumps({"status": "no_pending_ugc_jobs"}, indent=2))
        return 0

    organization_id, channels = buffer.discover_buffer_channels(api_key)
    queue = load_queue()
    report = []
    failed = False
    for row in rows:
        try:
            result = process_row(
                row, queue, api_key, cloudinary_url, organization_id, channels, args.dry_run
            )
            report.append(result)
            if result.get("status") in {"buffer_retry_required", "buffer_partially_scheduled"}:
                failed = True
        except Exception as exc:
            failed = True
            report.append({"job_id": row.get("job_id"), "status": "error", "error": str(exc)})
    buffer.persist_queue(queue)
    print(json.dumps({
        "publisher": "buffer",
        "organization_id": organization_id,
        "channels": channels,
        "dry_run": args.dry_run,
        "jobs": report,
    }, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
