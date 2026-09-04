#!/usr/bin/env python3
"""Autonomous F1 Meta publisher: exactly two daily publications on Facebook + Instagram.

Morning slot: carousel post.
Evening slot: Reel.
No approval gate, no Postiz, no paid scheduler. The workflow renders and publishes in
one GitHub Actions run using the official Meta APIs implemented in direct_api_publish.py.

The job IDs are deterministic, so retries are idempotent: a slot already published is
never published a second time. Failed/credential-blocked jobs are kept out of the
legacy direct publisher and are retried only by this autonomous workflow.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import direct_api_publish as core
import render_reels as renderer

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"
CLIENT_PATH = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
BANK_PATH = ROOT / "publisher" / "content_bank" / "f1-immobiliare.json"
ROME = ZoneInfo("Europe/Rome")
CLIENT_ID = "f1-immobiliare"
PLATFORMS = ["facebook", "instagram"]
SLOTS = {
    "morning": time(10, 30),
    "evening": time(18, 30),
}


def load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return fallback or {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def replace_tokens(value: Any, tokens: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, replacement in tokens.items():
            value = value.replace("{" + key + "}", replacement)
        return value
    if isinstance(value, list):
        return [replace_tokens(item, tokens) for item in value]
    if isinstance(value, dict):
        return {k: replace_tokens(v, tokens) for k, v in value.items()}
    return value


def normalize_hashtags(tags: list[Any]) -> list[str]:
    out: list[str] = []
    for raw in tags:
        tag = str(raw or "").strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag.replace(" ", "")
        if tag not in out:
            out.append(tag)
    return out


def caption_with_hashtags(caption: str, hashtags: list[str]) -> str:
    base = str(caption or "").strip()
    existing = {part for part in base.split() if part.startswith("#")}
    extra = [tag for tag in hashtags if tag not in existing]
    return base if not extra else base + "\n\n" + " ".join(extra)


def pick_slot(now: datetime, requested: str) -> str | None:
    if requested in SLOTS:
        return requested
    if requested != "auto":
        raise ValueError(f"Unsupported slot: {requested}")

    current = now.timetz().replace(tzinfo=None)
    # Scheduled workflow runs at :45 around the two local target windows. An early
    # DST companion run simply exits; the next companion run retries automatically.
    if SLOTS["evening"] <= current <= time(21, 30):
        return "evening"
    if SLOTS["morning"] <= current <= time(14, 30):
        return "morning"
    return None


def target_date(raw: str | None, now: datetime) -> date:
    return date.fromisoformat(raw) if raw else now.date()


def build_job(client: dict[str, Any], bank: dict[str, Any], day: date, slot: str) -> dict[str, Any]:
    slot_index = 0 if slot == "morning" else 1
    ordinal = day.toordinal()
    categories = ["data", "error", "proof"]
    category = categories[(ordinal + slot_index) % len(categories)]
    items = list(bank.get(category) or [])
    if not items:
        raise RuntimeError(f"Content bank category is empty: {category}")

    item = dict(items[(ordinal * 2 + slot_index) % len(items)])
    campaign = client.get("campaign", {})
    territories = list(campaign.get("territories") or [""])
    territory = str(territories[ordinal % len(territories)])
    tokens = {
        "territory": territory,
        "cta": str(campaign.get("cta") or ""),
        "client": str(client.get("name") or CLIENT_ID),
        "phone": str(campaign.get("phone") or ""),
    }
    item = replace_tokens(item, tokens)

    format_name = "carousel" if slot == "morning" else "reel"
    slug = str(item.get("slug") or f"{slot}-{category}").strip()
    hhmm = SLOTS[slot]
    scheduled = datetime(day.year, day.month, day.day, hhmm.hour, hhmm.minute, tzinfo=ROME)
    base = f"publisher/media/generated/meta-twice/{day.isoformat()}/{slot}-{slug}"

    if format_name == "carousel":
        slides = list(item.get("slides") or [])
        slide_count = 10
        media: Any = [f"{base}/slide-{n:02d}.jpg" for n in range(1, slide_count + 1)]
    else:
        slides = list(item.get("slides") or [])
        media = f"{base}.mp4"

    hashtag_sets = [row for row in campaign.get("hashtag_sets", []) if isinstance(row, list) and row]
    hashtags = normalize_hashtags(hashtag_sets[(ordinal + slot_index) % len(hashtag_sets)]) if hashtag_sets else []
    raw_caption = str(item.get("caption") or "").strip()
    caption = caption_with_hashtags(raw_caption, hashtags)

    return {
        "id": f"{CLIENT_ID}-meta-{day.isoformat()}-{slot}",
        "client_id": CLIENT_ID,
        "client_name": client.get("name", "F1 Immobiliare"),
        "category": category,
        "editorial_role": category,
        "campaign": str(campaign.get("name") or "F1 Meta Auto"),
        "format": format_name,
        "title": str(item.get("title") or ""),
        "caption": caption,
        "hashtags": hashtags,
        "voiceover": str(item.get("voiceover") or raw_caption or item.get("title") or ""),
        "slides": slides,
        "visuals": list(item.get("visuals") or []),
        "cta": item.get("cta", campaign.get("cta", "")),
        "media": media,
        "scheduled_at": scheduled.isoformat(),
        "territory": territory,
        "property_focus": campaign.get("property_focus", {}),
        "platforms": [
            {"platform": "facebook", "integration_id": "direct-api"},
            {"platform": "instagram", "integration_id": "direct-api"},
        ],
        "enabled": True,
        "status": "ready",
        "published_platforms": [],
        "direct_api_results": [],
        "video_made_with_ai": format_name == "reel",
        "approval_required": False,
        "manual_approval_required": False,
        "autonomous_publish": True,
        "created_by": "meta-twice-daily",
    }


def find_job(queue: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    for job in queue.get("jobs", []):
        if str(job.get("id")) == job_id:
            return job
    return None


def configure_owned_photo_sources(client: dict[str, Any]) -> None:
    """Use only the explicitly reusable F1 sources in client configuration.

    This deliberately bypasses the renderer's legacy Pixabay page URLs, which can
    reject unattended requests with HTTP 403. Wikimedia Special:Redirect/file URLs
    resolve directly to the reusable/public-domain/CC0 assets already documented in
    the F1 client configuration.
    """
    rows = client.get("brand", {}).get("photo_sources", [])
    sources = [
        str(row.get("url") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("url") or "").strip()
    ]
    if not sources:
        raise RuntimeError("F1 reusable photo_sources are not configured")
    repeat = (10 + len(sources) - 1) // len(sources)
    renderer.F1 = (sources * repeat)[:10]


def render_job(job: dict[str, Any], client: dict[str, Any]) -> None:
    configure_owned_photo_sources(client)
    if str(job.get("format")) == "carousel":
        renderer.render_carousel(job, client)
    elif str(job.get("format")) == "reel":
        job["_presenter"] = "joseph"
        try:
            renderer.render_reel(job, client)
        finally:
            job.pop("_presenter", None)
    else:
        raise RuntimeError(f"Unsupported format: {job.get('format')}")


def cleanup_media(job: dict[str, Any]) -> None:
    raw = job.get("media")
    if isinstance(raw, list):
        parent = (ROOT / str(raw[0])).parent if raw else None
        if parent and parent.exists():
            shutil.rmtree(parent, ignore_errors=True)
    elif raw:
        path = ROOT / str(raw)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def prune_meta_history(queue: dict[str, Any], keep: int = 120) -> None:
    jobs = list(queue.get("jobs", []))
    meta = [j for j in jobs if str(j.get("created_by")) == "meta-twice-daily"]
    if len(meta) <= keep:
        return
    meta_sorted = sorted(meta, key=lambda j: str(j.get("scheduled_at") or ""), reverse=True)
    keep_ids = {str(j.get("id")) for j in meta_sorted[:keep]}
    queue["jobs"] = [
        j for j in jobs
        if str(j.get("created_by")) != "meta-twice-daily" or str(j.get("id")) in keep_ids
    ]


def record_result(job: dict[str, Any], results: list[dict[str, Any]], dry_run: bool) -> None:
    job.setdefault("direct_api_results", []).append(
        {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dry_run": dry_run,
            "results": results,
            "source": "meta-twice-daily",
        }
    )


def persist_queue(queue: dict[str, Any]) -> None:
    queue["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prune_meta_history(queue)
    save_json(QUEUE_PATH, queue)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["auto", "morning", "evening"], default="auto")
    parser.add_argument("--date", help="Europe/Rome calendar date YYYY-MM-DD; default today")
    parser.add_argument("--dry-run", action="store_true", help="Render/check credentials but do not publish")
    args = parser.parse_args()

    now = datetime.now(ROME)
    slot = pick_slot(now, args.slot)
    if slot is None:
        print(f"NOOP: no F1 Meta slot is due at {now.isoformat(timespec='minutes')}")
        return 0

    day = target_date(args.date, now)
    if args.slot == "auto" and day != now.date():
        print("NOOP: automatic scheduler only publishes today's local-date slots")
        return 0

    client = load_json(CLIENT_PATH)
    bank = load_json(BANK_PATH)
    queue = load_json(QUEUE_PATH, {"version": 6, "jobs": []})
    queue.setdefault("jobs", [])

    template = build_job(client, bank, day, slot)
    existing = find_job(queue, template["id"])
    if existing:
        published = {str(x) for x in existing.get("published_platforms", [])}
        if existing.get("status") == "published" or set(PLATFORMS).issubset(published):
            print(f"NOOP: {template['id']} already published on Facebook + Instagram")
            return 0
        preserved = {
            "published_platforms": list(existing.get("published_platforms", [])),
            "direct_api_results": list(existing.get("direct_api_results", [])),
        }
        existing.clear()
        existing.update(template)
        existing.update(preserved)
        existing["status"] = "partially_published" if preserved["published_platforms"] else "ready"
        job = existing
    else:
        queue["jobs"].append(template)
        job = template

    # Fail early and explicitly before doing expensive rendering. The workflow stays
    # fully autonomous: as soon as the secrets exist, the next scheduled companion
    # run will proceed without any approval step.
    missing: list[str] = []
    for platform in PLATFORMS:
        for name in core.required_secrets(platform, client):
            if name not in missing:
                missing.append(name)
    if missing:
        results = [{"platform": "meta", "status": "blocked", "missing": missing}]
        job["status"] = "awaiting_credentials"
        job["blocked_reason"] = "missing GitHub Actions Secrets: " + ", ".join(missing)
        record_result(job, results, args.dry_run)
        persist_queue(queue)
        print(json.dumps({"job_id": job["id"], "slot": slot, "results": results}, ensure_ascii=False, indent=2))
        return 2

    try:
        try:
            render_job(job, client)
        except Exception as exc:
            results = [{"platform": "renderer", "status": "error", "error": str(exc)}]
            job["status"] = "render_failed"
            job["blocked_reason"] = str(exc)
            record_result(job, results, args.dry_run)
            persist_queue(queue)
            print(json.dumps({"job_id": job["id"], "slot": slot, "results": results}, ensure_ascii=False, indent=2))
            return 1

        results, ok = core.publish_job(job, set(PLATFORMS), args.dry_run)
        record_result(job, results, args.dry_run)
        if not ok:
            published = {str(x) for x in job.get("published_platforms", [])}
            if published:
                job["status"] = "partially_published"
            elif any(str(row.get("status")) == "blocked" for row in results):
                job["status"] = "awaiting_credentials"
            else:
                job["status"] = "retry_required"
            if job.get("status") != "partially_published":
                job["blocked_reason"] = "automatic Meta publication requires retry"
        else:
            job.pop("blocked_reason", None)
        persist_queue(queue)
        print(json.dumps({"job_id": job["id"], "slot": slot, "results": results}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    finally:
        cleanup_media(job)


if __name__ == "__main__":
    raise SystemExit(main())
