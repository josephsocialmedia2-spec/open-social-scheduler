#!/usr/bin/env python3
"""Autonomous publisher for immutable F1 final layouts.

Queue: publisher/final_content_queue.json
Assets: publisher/final_assets/*
Delivery: Cloudinary -> Buffer -> resolved Facebook / Instagram / LinkedIn channels.

A job is PUBLISHED only after Buffer reports every created target post as "sent".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import buffer_twice_daily as base
import territory_router

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
ALLOWED_STATUSES = {"READY", "PUBLISHING", "SCHEDULED", "PUBLISHED", "ERROR", "HOLD"}
ALLOWED_FORMATS = {"photo", "carousel", "reel"}
ALLOWED_PLATFORMS = {"facebook", "instagram", "linkedin"}
MAX_AUTONOMOUS_ATTEMPTS = max(1, int(os.getenv("F1_PUBLISH_MAX_ATTEMPTS", "5")))


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
    if fmt in {"photo", "reel"} and len(assets) != 1:
        raise base.BufferAutomationError(f"{job.get('id')}: {fmt} must have exactly one asset")
    if fmt == "carousel" and not (2 <= len(assets) <= 10):
        raise base.BufferAutomationError(f"{job.get('id')}: carousel must contain 2-10 assets")

    platforms = [str(x).lower() for x in (job.get("platforms") or ["facebook", "instagram"])]
    invalid = [x for x in platforms if x not in ALLOWED_PLATFORMS]
    if invalid:
        raise base.BufferAutomationError(f"{job.get('id')}: unsupported platforms: {invalid}")

    scope = str(job.get("scope") or "territory")
    if scope == "territory" and not str(job.get("territory") or "").strip():
        raise base.BufferAutomationError(f"{job.get('id')}: territory missing")


def is_communication_job(job: dict[str, Any]) -> bool:
    return str(job.get("communication_id") or "").startswith("COMM-")


def _recoverable_error(job: dict[str, Any]) -> bool:
    if str(job.get("status")) != "ERROR":
        return False
    if is_communication_job(job):
        return int(job.get("publish_attempts") or 0) < MAX_AUTONOMOUS_ATTEMPTS
    err = str(job.get("error") or "").casefold()
    markers = (
        "no buffer channels matched territory",
        "partial buffer mapping",
        "timeout",
        "temporarily unavailable",
        "rate limit",
        "429",
    )
    return any(m in err for m in markers)


def next_ready(queue: dict[str, Any], *, communications_only: bool = False) -> dict[str, Any] | None:
    candidates = [
        j
        for j in queue.get("jobs", [])
        if (str(j.get("status")) == "READY" or _recoverable_error(j))
        and (not communications_only or is_communication_job(j))
    ]
    candidates.sort(key=lambda j: (str(j.get("scheduled_at") or ""), str(j.get("id") or "")))
    return candidates[0] if candidates else None


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
    scheduled_at = str(job.get("scheduled_at") or "").strip() or datetime.now(base.ROME).isoformat()
    requested_platforms = [str(x).lower() for x in (job.get("platforms") or ["facebook", "instagram"])]

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
        "platforms": [{"platform": s, "integration_id": "buffer"} for s in requested_platforms],
        "status": "buffer_pending",
        "buffer_posts": list(job.get("buffer_posts") or []),
        "buffer_scheduled_platforms": list(job.get("buffer_scheduled_platforms") or []),
        "approval_required": False,
        "manual_approval_required": False,
        "autonomous_publish": True,
        "asset_policy": "immutable-final-layout",
        "asset_sha256": digests,
        "scope": job.get("scope") or "territory",
        "territory": job.get("territory") or "",
    }
    if job.get("video_made_with_ai") is not None:
        buffer_job["video_made_with_ai"] = bool(job.get("video_made_with_ai"))
    return buffer_job, paths


def _normalized_cloudinary_url() -> str:
    value = str(os.getenv("CLOUDINARY_URL", "")).strip().strip('"').strip("'")
    if value.startswith("CLOUDINARY_URL="):
        value = value.split("=", 1)[1].strip().strip('"').strip("'")
    return value


def _credentials() -> tuple[str, str]:
    api_key = os.getenv("BUFFER_API_KEY", "").strip()
    cloudinary_url = _normalized_cloudinary_url()
    missing = [
        name
        for name, value in (("BUFFER_API_KEY", api_key), ("CLOUDINARY_URL", cloudinary_url))
        if not value
    ]
    if missing:
        raise base.BufferAutomationError("Missing GitHub Actions Secrets: " + ", ".join(missing))
    return api_key, cloudinary_url


def _provider_snapshot(job: dict[str, Any]) -> str:
    relevant = {
        "status": job.get("status"),
        "buffer_posts": job.get("buffer_posts") or [],
        "published_at": job.get("published_at"),
        "published_urls": job.get("published_urls") or [],
        "error": job.get("error"),
    }
    return json.dumps(relevant, ensure_ascii=False, sort_keys=True)


def refresh_publication_status(job: dict[str, Any], api_key: str) -> bool:
    """Refresh one Buffer-backed job. Returns True only when durable fields changed."""
    posts = list(job.get("buffer_posts") or [])
    if not posts:
        return False

    before = _provider_snapshot(job)
    refreshed: list[dict[str, Any]] = []
    states: list[str] = []
    urls: list[str] = []

    for stored in posts:
        post_id = str(stored.get("post_id") or "").strip()
        if not post_id:
            refreshed.append(stored)
            continue
        current = base.get_buffer_post(api_key, post_id)
        merged = dict(stored)
        for key in ("buffer_status", "due_at", "sent_at", "external_link", "channel_id"):
            value = current.get(key)
            if value is not None and value != "":
                merged[key] = value
        state = str(merged.get("buffer_status") or "").lower()
        if state:
            states.append(state)
        link = str(merged.get("external_link") or "").strip()
        if link:
            urls.append(link)
        refreshed.append(merged)

    job["buffer_posts"] = refreshed
    target_services = set(str(x) for x in (job.get("buffer_scheduled_platforms") or []))
    sent_services = {
        str(row.get("service") or "")
        for row in refreshed
        if str(row.get("buffer_status") or "").lower() == "sent"
    }

    hard_error = next(
        (state for state in states if state in {"error", "needs_approval"}),
        None,
    )
    if hard_error:
        job["status"] = "ERROR"
        job["error"] = f"Buffer provider state requires recovery: {hard_error}"
    elif target_services and target_services.issubset(sent_services):
        job["status"] = "PUBLISHED"
        sent_times = [str(x.get("sent_at") or "") for x in refreshed if x.get("sent_at")]
        job["published_at"] = max(sent_times) if sent_times else datetime.now(timezone.utc).isoformat(timespec="seconds")
        job["published_urls"] = sorted(set(urls))
        job["provider"] = "buffer"
        job.pop("error", None)
    else:
        job["status"] = "SCHEDULED"
        job["scheduled_via"] = "buffer"
        job.pop("error", None)

    return before != _provider_snapshot(job)


def verify_scheduled_jobs(
    queue: dict[str, Any],
    api_key: str,
    *,
    communications_only: bool = False,
) -> tuple[int, int]:
    checked = 0
    changed = 0
    for job in queue.get("jobs", []):
        if str(job.get("status") or "") != "SCHEDULED":
            continue
        if communications_only and not is_communication_job(job):
            continue
        checked += 1
        try:
            if refresh_publication_status(job, api_key):
                changed += 1
        except Exception as exc:
            previous = _provider_snapshot(job)
            job["last_verification_error"] = f"{type(exc).__name__}: {exc}"
            # Do not downgrade an already scheduled post because a status check
            # had a transient transport failure.
            if previous != _provider_snapshot(job):
                changed += 1
    if changed:
        persist_queue(queue)
    return checked, changed


def publish_job(
    queue: dict[str, Any],
    job: dict[str, Any],
    api_key: str,
    cloudinary_url: str,
    *,
    dry_run: bool = False,
) -> int:
    try:
        job["publish_attempts"] = int(job.get("publish_attempts") or 0) + 1
        job["last_publish_attempt_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if not dry_run:
            job["status"] = "PUBLISHING"
            persist_queue(queue)

        buffer_job, _ = prepare_job(job)
        organization_id, channels = territory_router.resolve_job_channels(api_key, job)
        buffer_job["buffer_organization_id"] = organization_id
        buffer_job["buffer_channels"] = channels
        hosted = base.ensure_cloudinary_assets(buffer_job, cloudinary_url)

        if dry_run:
            print(json.dumps({
                "id": job["id"],
                "status": "DRY_RUN_OK",
                "format": buffer_job["format"],
                "scope": buffer_job["scope"],
                "territory": buffer_job["territory"],
                "channels": channels,
                "asset_sha256": buffer_job["asset_sha256"],
                "hosted": [x.get("url") for x in hosted],
            }, ensure_ascii=False, indent=2))
            return 0

        target_services = list(channels.keys())
        scheduled = set(str(x) for x in job.get("buffer_scheduled_platforms") or [])
        results: list[dict[str, Any]] = []
        for service in target_services:
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
            # Idempotency: persist every successful provider post ID before the
            # next platform is attempted.
            persist_queue(queue)

        if not set(target_services).issubset(scheduled):
            raise base.BufferAutomationError("Not all resolved target channels were scheduled")

        job["status"] = "SCHEDULED"
        job["scheduled_via"] = "buffer"
        job["resolved_channels"] = channels
        job["published_asset_sha256"] = buffer_job["asset_sha256"]
        job.pop("error", None)
        persist_queue(queue)

        # shareNow can become "sent" immediately. Verify once now; scheduled
        # posts are rechecked by the workflow until Buffer reports "sent".
        if refresh_publication_status(job, api_key):
            persist_queue(queue)

        print(json.dumps({
            "id": job["id"],
            "status": job["status"],
            "results": results,
            "published_urls": job.get("published_urls") or [],
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        job["status"] = "ERROR"
        job["error"] = f"{type(exc).__name__}: {exc}"
        persist_queue(queue)
        print(json.dumps({
            "id": job.get("id"),
            "status": "ERROR",
            "attempt": job.get("publish_attempts"),
            "error": job["error"],
        }, ensure_ascii=False, indent=2))
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--drain", action="store_true", help="Process all eligible READY jobs")
    parser.add_argument("--verify", action="store_true", help="Refresh SCHEDULED jobs from Buffer")
    parser.add_argument(
        "--communications-only",
        action="store_true",
        help="Touch only jobs created from the autonomous client communication flow",
    )
    parser.add_argument("--max-jobs", type=int, default=25)
    args = parser.parse_args()

    queue = load_queue()

    need_publish = next_ready(queue, communications_only=args.communications_only) is not None
    need_verify = args.verify and any(
        str(j.get("status") or "") == "SCHEDULED"
        and (not args.communications_only or is_communication_job(j))
        for j in queue.get("jobs", [])
    )
    if not need_publish and not need_verify:
        print("NOOP: no eligible READY/ERROR jobs and no SCHEDULED jobs to verify")
        return 0

    try:
        api_key, cloudinary_url = _credentials()
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False))
        return 2

    exit_code = 0
    processed = 0
    limit = max(1, args.max_jobs)

    while processed < limit:
        job = next_ready(queue, communications_only=args.communications_only)
        if not job:
            break
        code = publish_job(queue, job, api_key, cloudinary_url, dry_run=args.dry_run)
        processed += 1
        exit_code = max(exit_code, code)
        if not args.drain or args.dry_run:
            break

    verified = changed = 0
    if args.verify and not args.dry_run:
        verified, changed = verify_scheduled_jobs(
            queue,
            api_key,
            communications_only=args.communications_only,
        )

    print(json.dumps({
        "processed": processed,
        "verified": verified,
        "verification_changes": changed,
        "communications_only": args.communications_only,
        "exit_code": exit_code,
    }, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
