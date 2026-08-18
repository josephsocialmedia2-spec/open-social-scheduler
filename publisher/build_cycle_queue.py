#!/usr/bin/env python3
"""Build exactly 6 fresh contents per 4-hour cycle: 2 Reel + 1 carousel per brand.

The cycle queue is append-only across the day (up to the repository 48-item cap) so a
new cycle never destroys the previous cycle. Old legacy non-final drafts can be
removed once with SOCIAL_RESET_LEGACY=1.
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


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 7, "jobs": []}


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


def remap_media(job: dict, target: date, hour: int, position: int) -> None:
    cid = str(job["client_id"])
    base_dir = f"publisher/media/generated/{cid}/{target.isoformat()}/cycle-{hour:02d}"
    slug = str(job.get("id") or "content").split("-", 4)[-1]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in slug).strip("-") or f"content-{position}"
    if str(job.get("format") or "reel") == "carousel":
        job["media"] = [f"{base_dir}/{position:02d}-{safe}/slide-{n:02d}.jpg" for n in range(1, 11)]
    else:
        job["media"] = f"{base_dir}/{position:02d}-{safe}.mp4"


def pick_three(candidates: list[dict], idx: int) -> list[dict]:
    reels = [j for j in candidates if str(j.get("format") or "reel") == "reel"]
    cars = [j for j in candidates if str(j.get("format") or "") == "carousel"]
    if len(reels) < 2 or not cars:
        raise RuntimeError("Daily bank must expose at least 2 reels and 1 carousel per brand")
    chosen = [reels[(idx * 2) % len(reels)], reels[(idx * 2 + 1) % len(reels)], cars[idx % len(cars)]]
    return [copy.deepcopy(j) for j in chosen]


def build_current_cycle() -> int:
    now = datetime.now(ROME)
    hour = cycle_hour(now)
    target = target_date(now)
    cycle_idx = CYCLE_HOURS.index(hour)
    cycle_key = f"{target.isoformat()}T{hour:02d}:00"

    queue = load(QUEUE)
    queue["version"] = max(int(queue.get("version", 1)), 7)
    jobs = list(queue.get("jobs", []))

    # Remove only a rerun of this exact cycle. Preserve every previous cycle and final job.
    jobs = [j for j in jobs if str(j.get("cycle_key") or "") != cycle_key]

    # One-time cleanup of stale pre-cycle drafts, never delete published/scheduled content.
    if os.getenv("SOCIAL_RESET_LEGACY", "0").strip() == "1":
        jobs = [
            j for j in jobs
            if j.get("status") in {"published", "scheduled"}
            or j.get("cycle_key")
        ]

    all_clients = base.clients()
    client_map = {c["id"]: c for c in all_clients}
    position = 0
    added: list[dict] = []

    for cid in BRANDS:
        client = client_map.get(cid)
        if not client or not client.get("active", False):
            raise RuntimeError(f"Required brand is not active: {cid}")
        daily = base.build_for_client(client, target)
        selected = pick_three(daily, cycle_idx)
        for local_pos, job in enumerate(selected):
            position += 1
            minute = (0 if cid == "f1-immobiliare" else 30) + local_pos * 8
            minute = min(minute, 59)
            scheduled = datetime(target.year, target.month, target.day, hour, minute, tzinfo=ROME)
            old_id = str(job.get("id") or f"content-{position}")
            tail = old_id.split(f"{target.isoformat()}-", 1)[-1]
            job["id"] = f"{cid}-{target.isoformat()}-c{hour:02d}-{local_pos + 1:02d}-{tail}"
            job["scheduled_at"] = scheduled.isoformat()
            job["cycle_key"] = cycle_key
            job["cycle_hour"] = hour
            job["cycle_index"] = cycle_idx
            job["cycle_position"] = local_pos + 1
            job["production_mode"] = "6-every-4h"
            job["production_status"] = "DELUXE PREMIUM - FRESH VISUALS"
            remap_media(job, target, hour, local_pos + 1)
            added.append(job)

    # 6 exact items = 3 per brand = 4 reels + 2 carousels.
    if len(added) != 6:
        raise RuntimeError(f"Cycle must contain exactly 6 jobs, got {len(added)}")
    if sum(str(j.get("format")) == "reel" for j in added) != 4:
        raise RuntimeError("Cycle must contain exactly 4 reels")
    if sum(str(j.get("format")) == "carousel" for j in added) != 2:
        raise RuntimeError("Cycle must contain exactly 2 carousels")

    queue["jobs"] = jobs + added
    base.reconcile(queue, client_map)
    base.cap_queue(queue, base.MAX_QUEUE_ITEMS)
    queue["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    queue["updated_by"] = "4-hour Deluxe cycle builder"
    queue["current_cycle"] = cycle_key
    save(QUEUE, queue)
    print(f"Built cycle {cycle_key}: 6 contents = 4 reels + 2 carousels")
    return 0


def reconcile_only() -> int:
    queue = load(QUEUE)
    client_map = {c["id"]: c for c in base.clients()}
    base.reconcile(queue, client_map)
    base.cap_queue(queue, base.MAX_QUEUE_ITEMS)
    queue["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    save(QUEUE, queue)
    print("Cycle queue reconciled after rendering")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reconcile-only", action="store_true")
    args = parser.parse_args()
    return reconcile_only() if args.reconcile_only else build_current_cycle()


if __name__ == "__main__":
    raise SystemExit(main())
