#!/usr/bin/env python3
"""Build exactly 4 static-photo contents per 4-hour cycle: 2 per brand.

Cycle order:
1) F1 main image folder
2) F1 RIC LAVORO F1
3) Real Media Pro main image folder
4) Real Media Pro RIC LAVORO RMP

NO REELS / NO MP4. Queue history is preserved up to the existing 48-item cap.
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
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 9, "jobs": []}


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


def pick_two(candidates: list[dict], idx: int) -> list[dict]:
    if len(candidates) < 2:
        raise RuntimeError("Daily bank must expose at least 2 contents per brand")
    start = (idx * 2) % len(candidates)
    selected = [candidates[(start + n) % len(candidates)] for n in range(2)]
    return [copy.deepcopy(j) for j in selected]


def build_current_cycle() -> int:
    now = datetime.now(ROME)
    hour = cycle_hour(now)
    target = target_date(now)
    cycle_idx = CYCLE_HOURS.index(hour)
    cycle_key = f"{target.isoformat()}T{hour:02d}:00"

    queue = load(QUEUE)
    queue["version"] = max(int(queue.get("version", 1)), 9)
    jobs = [j for j in list(queue.get("jobs", [])) if str(j.get("cycle_key") or "") != cycle_key]

    if os.getenv("SOCIAL_RESET_LEGACY", "0").strip() == "1":
        jobs = [j for j in jobs if j.get("status") in {"published", "scheduled"} or j.get("cycle_key")]

    client_map = {c["id"]: c for c in base.clients()}
    added: list[dict] = []

    for cid in BRANDS:
        client = client_map.get(cid)
        if not client or not client.get("active", False):
            raise RuntimeError(f"Required brand is not active: {cid}")
        selected = pick_two(base.build_for_client(client, target), cycle_idx)
        for local_pos, job in enumerate(selected, start=1):
            minute = (0 if cid == "f1-immobiliare" else 30) + (local_pos - 1) * 8
            scheduled = datetime(target.year, target.month, target.day, hour, min(minute, 59), tzinfo=ROME)
            old_id = str(job.get("id") or f"content-{local_pos}")
            tail = old_id.split(f"{target.isoformat()}-", 1)[-1]
            job["id"] = f"{cid}-{target.isoformat()}-c{hour:02d}-{local_pos:02d}-{tail}"
            job["scheduled_at"] = scheduled.isoformat()
            job["cycle_key"] = cycle_key
            job["cycle_hour"] = hour
            job["cycle_index"] = cycle_idx
            job["cycle_position"] = local_pos
            job["production_mode"] = "folder-photos-4-every-4h"
            job["production_status"] = "PHOTO ONLY"
            job["format"] = "photo"
            job["media"] = photo_media(job, target, hour, local_pos)
            job["video_made_with_ai"] = False
            for key in ("image_change_seconds", "reel_duration_seconds", "target_reel_seconds"):
                job.pop(key, None)
            added.append(job)

    if len(added) != 4:
        raise RuntimeError(f"Cycle must contain exactly 4 photo posts, got {len(added)}")
    if any(str(j.get("format")) != "photo" for j in added):
        raise RuntimeError("PHOTO-ONLY policy violation")

    queue["jobs"] = jobs + added
    base.cap_queue(queue, base.MAX_QUEUE_ITEMS)
    queue["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    queue["updated_by"] = "Folder-driven photo cycle builder"
    queue["current_cycle"] = cycle_key
    queue["output_policy"] = "4 STATIC PHOTOS - MANUAL FOLDERS - NO REELS - NO MP4"
    save(QUEUE, queue)
    print(f"Built cycle {cycle_key}: 4 photo posts = F1 main + F1 recruiting + RMP main + RMP recruiting")
    return 0


def reconcile_only() -> int:
    queue = load(QUEUE)
    base.cap_queue(queue, base.MAX_QUEUE_ITEMS)
    queue["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    queue["output_policy"] = "4 STATIC PHOTOS - MANUAL FOLDERS - NO REELS - NO MP4"
    save(QUEUE, queue)
    print("Folder-driven photo queue preserved without approval reset")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reconcile-only", action="store_true")
    args = parser.parse_args()
    return reconcile_only() if args.reconcile_only else build_current_cycle()


if __name__ == "__main__":
    raise SystemExit(main())
