#!/usr/bin/env python3
"""Build automatic static-photo publications for clients that allow rendering.

F1 Immobiliare can be configured as manual-publish-only. In that mode this
builder MUST NOT create F1 jobs or media. Other active clients continue to use
the legacy automatic cycle unchanged.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

import build_daily_queue as base

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
ROME = ZoneInfo("Europe/Rome")
CYCLE_HOURS = (0, 4, 8, 12, 16, 20)
BRANDS = ("f1-immobiliare", "real-media-pro")
POSTS_PER_BRAND = 5
HISTORY_DAYS = max(1, int(os.getenv("SOCIAL_HISTORY_DAYS", "14") or 14))
QUEUE_HISTORY_LIMIT = max(120, int(os.getenv("SOCIAL_HISTORY_LIMIT", str(10 * len(CYCLE_HOURS) * HISTORY_DAYS)) or 840))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 10, "jobs": []}


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cycle_hour(now: datetime) -> int:
    raw = os.getenv("SOCIAL_CYCLE_HOUR", "").strip()
    if raw:
        hour = int(raw)
        if hour not in CYCLE_HOURS:
            raise SystemExit(f"SOCIAL_CYCLE_HOUR must be one of {CYCLE_HOURS}")
        return hour
    return max(h for h in CYCLE_HOURS if h <= now.hour)


def target_date(now: datetime) -> date:
    raw = os.getenv("SOCIAL_DATE", "").strip()
    return date.fromisoformat(raw) if raw else now.date()


def photo_media(job: dict, target: date, hour: int, position: int) -> str:
    cid = str(job["client_id"])
    base_dir = f"publisher/media/generated/{cid}/{target.isoformat()}/cycle-{hour:02d}"
    slug = str(job.get("id") or "content").split("-", 4)[-1]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in slug).strip("-") or f"content-{position}"
    return f"{base_dir}/{position:02d}-{safe}.jpg"


def pick_five(candidates: list[dict], idx: int) -> list[dict]:
    if len(candidates) < POSTS_PER_BRAND:
        raise RuntimeError(f"Daily bank must expose at least {POSTS_PER_BRAND} contents per brand")
    start = (idx * POSTS_PER_BRAND) % len(candidates)
    selected = [candidates[(start + n) % len(candidates)] for n in range(POSTS_PER_BRAND)]
    return [copy.deepcopy(j) for j in selected]


def automatic_rendering_enabled(client: dict) -> bool:
    if not client.get("active", False):
        return False
    if str(client.get("graphics_source") or "") == "manual_only":
        return False
    if client.get("publish_only") is True:
        return False
    if client.get("automatic_rendering") is False:
        return False
    return True


def _preserve_job_during_reset(job: dict) -> bool:
    status = str(job.get("status") or "")
    if status in {"published", "scheduled"}:
        return True
    if str(job.get("source") or "") == "SUPABASE_CONTENT_HUB":
        return True
    if job.get("cycle_key"):
        if (
            str(job.get("client_id") or "") == "f1-immobiliare"
            and status not in {"published", "scheduled"}
        ):
            return False
        return True
    return False


def build_current_cycle() -> int:
    now = datetime.now(ROME)
    hour = cycle_hour(now)
    target = target_date(now)
    cycle_idx = CYCLE_HOURS.index(hour)
    cycle_key = f"{target.isoformat()}T{hour:02d}:00"

    queue = load(QUEUE)
    queue["version"] = max(int(queue.get("version", 1)), 10)
    jobs = [j for j in list(queue.get("jobs", [])) if str(j.get("cycle_key") or "") != cycle_key]

    if os.getenv("SOCIAL_RESET_LEGACY", "0").strip() == "1":
        jobs = [j for j in jobs if _preserve_job_during_reset(j)]

    client_map = {c["id"]: c for c in base.clients()}
    eligible_brands: list[str] = []
    for cid in BRANDS:
        client = client_map.get(cid)
        if not client:
            raise RuntimeError(f"Missing client config: {cid}")
        if automatic_rendering_enabled(client):
            eligible_brands.append(cid)

    added: list[dict] = []
    for cid in eligible_brands:
        client = client_map[cid]
        selected = pick_five(base.build_for_client(client, target), cycle_idx)
        for local_pos, job in enumerate(selected, start=1):
            minute = (0 if cid == "f1-immobiliare" else 30) + (local_pos - 1) * 6
            scheduled = datetime(target.year, target.month, target.day, hour, min(minute, 59), tzinfo=ROME)
            old_id = str(job.get("id") or f"content-{local_pos}")
            tail = old_id.split(f"{target.isoformat()}-", 1)[-1]
            job["id"] = f"{cid}-{target.isoformat()}-c{hour:02d}-{local_pos:02d}-{tail}"
            job["scheduled_at"] = scheduled.isoformat()
            job["cycle_key"] = cycle_key
            job["cycle_hour"] = hour
            job["cycle_index"] = cycle_idx
            job["cycle_position"] = local_pos
            job["production_mode"] = "automatic-static-photo-cycle"
            job["production_status"] = "PHOTO ONLY"
            job["format"] = "photo"
            job["media"] = photo_media(job, target, hour, local_pos)
            job["video_made_with_ai"] = False
            for key in ("image_change_seconds", "reel_duration_seconds", "target_reel_seconds"):
                job.pop(key, None)
            added.append(job)

    expected = POSTS_PER_BRAND * len(eligible_brands)
    if len(added) != expected:
        raise RuntimeError(f"Cycle expected {expected} automatic photo posts, got {len(added)}")
    if any(str(j.get("format")) != "photo" for j in added):
        raise RuntimeError("PHOTO-ONLY policy violation")
    if any(str(j.get("client_id") or "") == "f1-immobiliare" for j in added):
        f1 = client_map.get("f1-immobiliare") or {}
        if not automatic_rendering_enabled(f1):
            raise RuntimeError("F1 manual-only policy violation: automatic F1 job created")

    queue["jobs"] = jobs + added
    base.reconcile(queue, client_map)
    removed = base.cap_queue(queue, QUEUE_HISTORY_LIMIT)
    queue["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    queue["updated_by"] = "automatic photo cycle builder · F1 manual-only aware"
    queue["current_cycle"] = cycle_key
    queue["history_days"] = HISTORY_DAYS
    queue["history_limit"] = QUEUE_HISTORY_LIMIT

    f1_client = client_map.get("f1-immobiliare") or {}
    f1_manual = not automatic_rendering_enabled(f1_client)
    queue["output_policy"] = (
        "F1 MANUAL PUBLISH ONLY + 5 RMP STATIC PHOTOS"
        if f1_manual and eligible_brands == ["real-media-pro"]
        else f"AUTOMATIC STATIC PHOTOS: {', '.join(eligible_brands) or 'NONE'}"
    )
    save(QUEUE, queue)
    print(
        f"Built cycle {cycle_key}: automatic={len(added)} "
        f"brands={eligible_brands}; F1_manual_only={f1_manual}; "
        f"history={len(queue['jobs'])}/{QUEUE_HISTORY_LIMIT}, removed={removed}"
    )
    return 0


def reconcile_only() -> int:
    queue = load(QUEUE)
    client_map = {c["id"]: c for c in base.clients()}
    base.reconcile(queue, client_map)
    removed = base.cap_queue(queue, QUEUE_HISTORY_LIMIT)
    queue["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    queue["history_days"] = HISTORY_DAYS
    queue["history_limit"] = QUEUE_HISTORY_LIMIT
    f1_client = client_map.get("f1-immobiliare") or {}
    queue["f1_manual_publish_only"] = not automatic_rendering_enabled(f1_client)
    save(QUEUE, queue)
    print(
        f"Automatic cycle queue reconciled; F1_manual_only={queue['f1_manual_publish_only']}; "
        f"history={len(queue.get('jobs', []))}/{QUEUE_HISTORY_LIMIT}, removed={removed}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reconcile-only", action="store_true")
    args = parser.parse_args()
    return reconcile_only() if args.reconcile_only else build_current_cycle()


if __name__ == "__main__":
    raise SystemExit(main())
