#!/usr/bin/env python3
"""Publish immutable F1 final layouts exactly as supplied.

This publisher intentionally performs no visual rendering, crop, resize, text overlay,
filter, or layout reconstruction. The final image/video is the source of truth.

Queue: publisher/final_content_queue.json
Assets: publisher/final_assets/*
Delivery: Cloudinary -> Buffer -> Facebook / Instagram / LinkedIn
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import buffer_twice_daily as base

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
ALLOWED_STATUSES = {"READY", "SCHEDULED", "PUBLISHED", "ERROR", "HOLD"}
ALLOWED_FORMATS = {"photo", "carousel", "reel"}


def load_queue() -> dict[str, Any]:
    if not QUEUE_PATH.exists():
        raise base.BufferAutomationError("Missing publisher/final_content_queue.json")
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    if queue.get("pipeline") != "f1-final-assets":
        raise base.BufferAutomationError("Unexpected final asset queue pipeline")
    if queue.get("asset_policy") != "immutable-final-layout":
        raise base.BufferAutomationError("Final asset queue is not immutable")
    queue.setdefault("jobs", [])
    return queue


def persist_queue(queue: dict[str, Any]) -> None:
    queue["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def local_asset(path_value: str) -> Path:
    path = (ROOT / path_value).resolve()
    final_root = (ROOT / "publisher" / "final_assets").resolve()
    try:
        path.relative_to(final_root)
    except ValueError as exc:
        raise base.BufferAutomationError(f"Asset outside publisher/final_assets: {path_value}") from exc
    if not path.exists() or not path.is_file():
        raise base.BufferAutomationError(f"Missing final asset: {path_value}")
    if path.stat().st_size < 10_000:
        raise base.BufferAutomationError(f"Final asset unexpectedly small: {path_value}")
    return path


def verify_sha256(path: Path, expected: str | None) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected and digest.lower() != str(expected).lower():
        raise base.BufferAutomationError(f"SHA256 mismatch for immutable asset {path.name}")
    return digest


def validate_job(job: dict[str, Any]) -> None:
    status = str(job.get("status") or "")
    if status not in ALLOWED_STATUSES:
        raise base.BufferAutomationError(f"Invalid final asset status: {status}")
    fmt = str(job.get("format") or "photo")
    if fmt not in ALLOWED_FORMATS:
        raise base.BufferAutomationError(f"Unsupported final asset format: {fmt}")
    if not str(job.get("id") or "").strip():
        raise base.BufferAutomationError("Final asset job missing id")
    if not str(job.get("caption") or "").strip():
        raise base.BufferAutomationError(f"{job.get('id')}: caption missing")
    assets = job.get("assets") or []
    if not isinstance(assets, list) or not assets:
        raise base.BufferAutomationError(f"{job.get('id')}: assets missing")
    if fmt == "photo" and len(assets) != 1:
        raise base.BufferAutomationError(f"{job.get('id')}: photo must have exactly one asset")
    if fmt == "reel" and len(assets) != 1:
        raise base.BufferAutomationError(f"{job.get('id')}: reel must have exactly one asset")
    if fmt == "carousel" and not (2 <= len(assets) <= 10):
        raise base.BufferAutomationError(f"{job.get('id')}: carousel must contain 2-10 assets")


def next_ready(queue: dict[str, Any]) -> dict[str, Any] | None:
    ready = [j for j in queue.get("jobs", []) if str(j.get("status")) == "READY"]
    ready.sort(key=lambda j: (str(j.get("scheduled_at") or ""), str(j.get("id") or "")))
    return ready[0] if ready else None


def prepare_job(job: dict[str, Any]) -> tuple[dict[str, Any], list[Path]]:
    validate_job(job)
    paths: list[Path] = []
    digests: list[str] = []
    for raw in job.get("assets") or []:
        if isinstance(raw, str):
            path_value, expected = raw, None
        elif isinstance(raw, dict):
            path_value = str(raw.get("path") or "")
            expected = raw.get("sha256")
        else:
            raise base.BufferAutomationError(f"{job.get('id')}: malformed asset entry")
        path = local_asset(path_value)
        digests.append(verify_sha256(path, expected))
        paths.append(path)

    fmt = str(job.get("format") or "photo")
    scheduled_at = str(job.get("scheduled_at") or "").strip()
    if not scheduled_at:
        scheduled_at = datetime.now(base.ROME).isoformat()

    buffer_job = {
        "id": f"f1-final-{job['id']}",
        "client_id": "f1-immobiliare",
        "created_by": "final-asset-publisher",
        "title": job.get("title") or job.get("id"),
        "caption": job.get("caption"),
        "cta": job.get("cta") or "",
        "hashtags": job.get("hashtags") or [],
        "format": fmt,
        "media": [str(p.relative_to(ROOT)) for p in paths] if len(paths) > 1 else str(paths[0].relative_to(ROOT)),
        "scheduled_at": scheduled_at,
        "platforms": [{"platform": s, "integration_id": "buffer"} for s in base.TARGET_SERVICES],
        "status": "buffer_pending",
        "buffer_posts": list(job.get("buffer_posts") or []),
        "buffer_scheduled_platforms": list(job.get("buffer_scheduled_platforms") or []),
        "approval_required": False,
        "manual_approval_required": False,
        "autonomous_publish": True,
        "asset_policy": "immutable-final-layout",
        "asset_sha256": digests,
    }
    if job.get("video_made_with_ai") is not None:
        buffer_job["video_made_with_ai"] = bool(job.get("video_made_with_ai"))
    return buffer_job, paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    queue = load_queue()
    job = next_ready(queue)
    if not job:
        print("NOOP: no READY immutable final assets")
        return 0

    try:
        buffer_job, _ = prepare_job(job)
        api_key = os.getenv("BUFFER_API_KEY", "").strip()
        cloudinary_url = str(os.getenv("CLOUDINARY_URL", "")).strip().strip('"').strip("'")
        if cloudinary_url.startswith("CLOUDINARY_URL="):
            cloudinary_url = cloudinary_url.split("=", 1)[1].strip().strip('"').strip("'")
        missing = [name for name, value in (("BUFFER_API_KEY", api_key), ("CLOUDINARY_URL", cloudinary_url)) if not value]
        if missing:
            raise base.BufferAutomationError("Missing GitHub Actions Secrets: " + ", ".join(missing))

        organization_id, channels = base.discover_buffer_channels(api_key)
        buffer_job["buffer_organization_id"] = organization_id
        buffer_job["buffer_channels"] = channels
        hosted = base.ensure_cloudinary_assets(buffer_job, cloudinary_url)

        if args.dry_run:
            print(json.dumps({
                "id": job["id"],
                "status": "DRY_RUN_OK",
                "format": buffer_job["format"],
                "channels": channels,
                "asset_sha256": buffer_job["asset_sha256"],
                "hosted": [x.get("url") for x in hosted],
            }, ensure_ascii=False, indent=2))
            return 0

        scheduled = set(str(x) for x in job.get("buffer_scheduled_platforms") or [])
        results: list[dict[str, Any]] = []
        for service in base.TARGET_SERVICES:
            if service in scheduled:
                continue
            channel = channels[service]
            result = base.create_buffer_post(
                api_key,
                str(channel["id"]),
                service,
                buffer_job,
                hosted,
                datetime.now(base.ROME),
            )
            job.setdefault("buffer_posts", []).append(result)
            job.setdefault("buffer_scheduled_platforms", []).append(service)
            scheduled.add(service)
            results.append(result)
            persist_queue(queue)

        if set(base.TARGET_SERVICES).issubset(scheduled):
            job["status"] = "SCHEDULED"
            job["scheduled_via"] = "buffer"
            job["published_asset_sha256"] = buffer_job["asset_sha256"]
            job.pop("error", None)
            code = 0
        else:
            job["status"] = "ERROR"
            job["error"] = "Not all target channels were scheduled"
            code = 1
        persist_queue(queue)
        print(json.dumps({"id": job["id"], "status": job["status"], "results": results}, ensure_ascii=False, indent=2))
        return code
    except Exception as exc:
        job["status"] = "ERROR"
        job["error"] = str(exc)
        persist_queue(queue)
        print(json.dumps({"id": job.get("id"), "status": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
