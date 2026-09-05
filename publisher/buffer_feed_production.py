#!/usr/bin/env python3
"""Publish the current approved F1 feed sequentially through Buffer.

Source of truth: publisher/f1-feed-latest.json
- exactly 28 approved entries: 14 reels + 14 carousels
- only quality_gate_passed entries are eligible
- publication state is persisted in publisher/queue.json
- one entry is scheduled per morning/evening slot across Facebook, Instagram and LinkedIn
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

import buffer_twice_daily as base

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "publisher" / "f1-feed-latest.json"
QUEUE_PATH = ROOT / "publisher" / "queue.json"
MEDIA_DIR = ROOT / "publisher" / "media" / "generated" / "buffer-feed-production"
CREATED_BY = "buffer-feed-production"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_cloudinary_url(raw: str) -> str:
    value = str(raw or "").strip().strip('"').strip("'")
    if value.startswith("CLOUDINARY_URL="):
        value = value.split("=", 1)[1].strip().strip('"').strip("'")
    return value


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("pipeline") != "f1-instagram-production-feed":
        raise base.BufferAutomationError("Unexpected F1 feed manifest pipeline")
    if manifest.get("brand") != "F1 Immobiliare":
        raise base.BufferAutomationError("Unexpected brand in F1 feed manifest")
    entries = list(manifest.get("entries") or [])
    if len(entries) != 28:
        raise base.BufferAutomationError(f"Expected 28 F1 feed entries, found {len(entries)}")
    reels = [e for e in entries if e.get("format") == "reel"]
    carousels = [e for e in entries if e.get("format") == "carousel"]
    if len(reels) != 14 or len(carousels) != 14:
        raise base.BufferAutomationError("F1 feed must contain 14 reels and 14 carousels")
    if any(e.get("quality_gate_passed") is not True for e in entries):
        raise base.BufferAutomationError("F1 feed contains an entry that did not pass the quality gate")
    for e in entries:
        if not str(e.get("caption") or "").strip():
            raise base.BufferAutomationError(f"Missing caption for {e.get('source_item_id')}")
        if e.get("format") == "reel":
            if not str(e.get("media_url") or "").startswith("https://"):
                raise base.BufferAutomationError(f"Missing reel URL for {e.get('source_item_id')}")
        else:
            slides = list(e.get("slides") or [])
            if not 2 <= len(slides) <= 10 or not all(str(x).startswith("https://") for x in slides):
                raise base.BufferAutomationError(f"Invalid carousel slides for {e.get('source_item_id')}")
    entries.sort(key=lambda e: (str(e.get("scheduled_at") or ""), str(e.get("source_item_id") or "")))
    return entries


def completed_source_ids(queue: dict[str, Any]) -> set[str]:
    done: set[str] = set()
    for job in queue.get("jobs", []):
        if str(job.get("created_by")) != CREATED_BY:
            continue
        scheduled = set(str(x) for x in job.get("buffer_scheduled_platforms", []))
        if set(base.TARGET_SERVICES).issubset(scheduled):
            source_id = str(job.get("source_item_id") or "")
            if source_id:
                done.add(source_id)
    return done


def choose_next(entries: list[dict[str, Any]], queue: dict[str, Any]) -> dict[str, Any] | None:
    done = completed_source_ids(queue)
    for entry in entries:
        if str(entry.get("source_item_id") or "") not in done:
            return entry
    return None


def download(url: str, path: Path) -> None:
    response = requests.get(
        url,
        headers={"User-Agent": "F1-Immobiliare-Feed-Publisher/1.0"},
        timeout=180,
        allow_redirects=True,
    )
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    if path.stat().st_size < 15_000:
        raise base.BufferAutomationError(f"Downloaded media is unexpectedly small: {path.name}")


def download_entry(entry: dict[str, Any]) -> list[Path]:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    source_id = str(entry.get("source_item_id") or "item")
    paths: list[Path] = []
    if entry.get("format") == "reel":
        path = MEDIA_DIR / f"{source_id}.mp4"
        download(str(entry["media_url"]), path)
        paths.append(path)
    else:
        for index, url in enumerate(entry.get("slides") or [], 1):
            path = MEDIA_DIR / f"{source_id}-slide-{index:02d}.jpg"
            download(str(url), path)
            paths.append(path)
    return paths


def build_job(entry: dict[str, Any], slot: str, paths: list[Path]) -> dict[str, Any]:
    now = datetime.now(base.ROME)
    due = base.due_datetime(now.date(), slot)
    return {
        "id": f"f1-feed-{entry.get('source_item_id')}",
        "client_id": "f1-immobiliare",
        "created_by": CREATED_BY,
        "source_item_id": entry.get("source_item_id"),
        "source_feed_id": entry.get("id"),
        "source_feed_run_id": entry.get("source_run_id"),
        "title": entry.get("title"),
        "caption": entry.get("caption"),
        "cta": entry.get("cta"),
        "format": entry.get("format"),
        "media": [str(p.relative_to(ROOT)) for p in paths] if len(paths) > 1 else str(paths[0].relative_to(ROOT)),
        "scheduled_at": due.isoformat(),
        "platforms": [{"platform": service, "integration_id": "buffer"} for service in base.TARGET_SERVICES],
        "status": "buffer_pending",
        "buffer_posts": [],
        "buffer_scheduled_platforms": [],
        "approval_required": False,
        "manual_approval_required": False,
        "autonomous_publish": True,
        "production_source": "f1-feed-latest.json",
        "quality_gate_passed": True,
        "video_made_with_ai": bool(entry.get("format") == "reel" and entry.get("engine") == "revideo"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["auto", "morning", "evening"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now = datetime.now(base.ROME)
    slot = base.pick_slot(now, args.slot)
    if slot is None:
        print(f"NOOP: no F1 feed publication slot is due at {now.isoformat(timespec='minutes')}")
        return 0

    manifest = load_json(MANIFEST_PATH, {})
    entries = validate_manifest(manifest)
    queue = load_json(QUEUE_PATH, {"version": 6, "jobs": []})
    queue.setdefault("jobs", [])

    entry = choose_next(entries, queue)
    if entry is None:
        print("NOOP: all 28 F1 feed entries are already scheduled on all target channels")
        return 0

    source_id = str(entry.get("source_item_id"))
    job_id = f"f1-feed-{source_id}"
    existing = base.find_job(queue, job_id)
    paths: list[Path] = []

    try:
        paths = download_entry(entry)
        template = build_job(entry, slot, paths)
        if existing:
            preserved = {
                "buffer_posts": list(existing.get("buffer_posts", [])),
                "buffer_scheduled_platforms": list(existing.get("buffer_scheduled_platforms", [])),
                "cloudinary_assets": list(existing.get("cloudinary_assets", [])),
            }
            existing.clear()
            existing.update(template)
            existing.update(preserved)
            job = existing
        else:
            queue["jobs"].append(template)
            job = template

        api_key = os.getenv("BUFFER_API_KEY", "").strip()
        cloudinary_url = normalize_cloudinary_url(os.getenv("CLOUDINARY_URL", ""))
        missing = [name for name, value in (("BUFFER_API_KEY", api_key), ("CLOUDINARY_URL", cloudinary_url)) if not value]
        if missing:
            raise base.BufferAutomationError("Missing GitHub Actions Secrets: " + ", ".join(missing))

        organization_id, channels = base.discover_buffer_channels(api_key)
        job["buffer_organization_id"] = organization_id
        job["buffer_channels"] = channels
        hosted = base.ensure_cloudinary_assets(job, cloudinary_url)
        base.persist_queue(queue)

        if args.dry_run:
            job["status"] = "buffer_dry_run_ok"
            base.persist_queue(queue)
            print(json.dumps({
                "source_item_id": source_id,
                "format": job["format"],
                "status": job["status"],
                "slot": slot,
                "channels": channels,
                "cloudinary": [x.get("url") for x in hosted],
            }, ensure_ascii=False, indent=2))
            return 0

        scheduled = set(str(x) for x in job.get("buffer_scheduled_platforms", []))
        results: list[dict[str, Any]] = []
        for service in base.TARGET_SERVICES:
            if service in scheduled:
                continue
            try:
                channel = channels[service]
                result = base.create_buffer_post(
                    api_key,
                    str(channel["id"]),
                    service,
                    job,
                    hosted,
                    datetime.now(base.ROME),
                )
                job.setdefault("buffer_posts", []).append(result)
                job.setdefault("buffer_scheduled_platforms", []).append(service)
                scheduled.add(service)
                results.append({**result, "status": "scheduled"})
                base.persist_queue(queue)
            except Exception as exc:
                results.append({"service": service, "status": "error", "error": str(exc)})

        if set(base.TARGET_SERVICES).issubset(scheduled):
            job["status"] = "scheduled_in_buffer"
            job.pop("blocked_reason", None)
            code = 0
        elif scheduled:
            job["status"] = "buffer_partially_scheduled"
            job["blocked_reason"] = "Buffer retry required for remaining channels"
            code = 1
        else:
            job["status"] = "buffer_retry_required"
            job["blocked_reason"] = "Buffer did not schedule any target channel"
            code = 1

        base.persist_queue(queue)
        print(json.dumps({
            "source_item_id": source_id,
            "format": job["format"],
            "slot": slot,
            "status": job["status"],
            "results": results,
        }, ensure_ascii=False, indent=2))
        return code
    except Exception as exc:
        print(json.dumps({"status": "production_blocked", "source_item_id": source_id, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    finally:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
