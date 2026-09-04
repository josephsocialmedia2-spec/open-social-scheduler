#!/usr/bin/env python3
"""Build the F1 14-day qualified-seller content queue.

This is intentionally separate from the legacy static-photo queue. It creates
14 Reels + 14 carousels from the canonical qualified-seller plan and never
invents a best publication time when Instagram Insights are unavailable.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "publisher" / "content_bank" / "f1-qualified-14d.json"
OUT = ROOT / "publisher" / "qualified_14d_queue.json"
POLICY = ROOT / "publisher" / "instagram_distribution_policy.json"
CREATORS = ROOT / "publisher" / "instagram_creators_best_practices.json"
ROME = ZoneInfo("Europe/Rome")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def media_for(item: dict, day: date) -> str | list[str]:
    base = f"publisher/media/generated/f1-qualified-14d/{day.isoformat()}"
    safe = item["id"].lower()
    if item["format"] == "reel":
        return f"{base}/{safe}.mp4"
    return [f"{base}/{safe}/slide-{n:02d}.jpg" for n in range(1, len(item.get("slides") or []) + 1)]


def build(end_date: date) -> dict:
    plan = load(PLAN)
    policy = load(POLICY)
    creators = load(CREATORS)
    items = list(plan.get("items") or [])
    reels = [x for x in items if x.get("format") == "reel"]
    carousels = [x for x in items if x.get("format") == "carousel"]
    if len(reels) != 14 or len(carousels) != 14:
        raise RuntimeError(f"Plan must contain 14 reels + 14 carousels; got {len(reels)} + {len(carousels)}")

    jobs = []
    start = end_date - timedelta(days=13)
    for i in range(14):
        day = start + timedelta(days=i)
        for item in (reels[i], carousels[i]):
            # Times below are ordering labels only. They are NOT claimed to be optimal publish times.
            hh, mm = (10, 0) if item["format"] == "reel" else (18, 0)
            ordering_time = datetime(day.year, day.month, day.day, hh, mm, tzinfo=ROME)
            fmt = item["format"]
            job = {
                "id": f"f1-qualified-{day.isoformat()}-{item['id'].lower()}",
                "source_item_id": item["id"],
                "client_id": "f1-immobiliare",
                "client_name": "F1 Immobiliare",
                "regeneration_batch": "qualified-14d",
                "content_date": day.isoformat(),
                "scheduled_at": ordering_time.isoformat(),
                "scheduled_at_role": "production_order_only",
                "publication_time_verified": False,
                "recommended_publish_day": None,
                "recommended_publish_window": None,
                "insights_status": "NOT_AVAILABLE",
                "format": fmt,
                "title": item["title"],
                "caption": item["caption"],
                "voiceover": item.get("voiceover", ""),
                "slides": list(item.get("slides") or []),
                "main_message": item["main_message"],
                "topic_keywords": list(item.get("topic_keywords") or []),
                "target_public": plan["target_public"],
                "post_objective": plan["objective"],
                "lead_goal": "qualified_seller",
                "lead_keyword": plan["qualification"]["keyword"],
                "lead_qualification_required_fields": list(plan["qualification"]["required_fields"]),
                "lead_qualification_optional_fields": list(plan["qualification"].get("optional_fields") or []),
                "cta": plan["cta"],
                "media": media_for(item, day),
                "enabled": True,
                "status": "gate_pending",
                "gate_status": "PENDING",
                "gate_reasons": [],
                "manual_approval_required": True,
                "publish_automatically": False,
                "instagram_policy_required": True,
                "instagram_policy_version": policy.get("version"),
                "instagram_policy_source": "publisher/instagram_distribution_policy.json",
                "instagram_creators_policy_version": creators.get("version"),
                "instagram_creators_policy_source": "publisher/instagram_creators_best_practices.json",
                "instagram_format": fmt,
                "muted_view_comprehension_required": fmt == "reel",
                "essential_content_safe_bottom_fraction": 0.35 if fmt == "reel" else None,
                "reel_width": 1080 if fmt == "reel" else None,
                "reel_height": 1920 if fmt == "reel" else None,
                "reel_duration_seconds": 28 if fmt == "reel" else None,
                "first_hook_seconds": 3 if fmt == "reel" else None,
                "audio_rights": "generated_original_bed_plus_tts" if fmt == "reel" else None,
                "business_kpi_priority": ["qualified_seller_dm", "valuation_request", "appointment", "mandate"],
            }
            jobs.append(job)

    out = {
        "version": 1,
        "name": "F1 Qualified Seller 14-Day Queue",
        "generated_at": datetime.now(ROME).isoformat(timespec="seconds"),
        "window_start": start.isoformat(),
        "window_end": end_date.isoformat(),
        "goal": "qualified_seller_leads",
        "count": len(jobs),
        "formats": {"reel": 14, "carousel": 14},
        "publication_time_policy": "NO_BEST_TIME_WITHOUT_REAL_INSIGHTS",
        "manual_approval_required": True,
        "jobs": jobs,
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", help="Last day in the 14-day window, YYYY-MM-DD")
    args = parser.parse_args()
    end = date.fromisoformat(args.end_date) if args.end_date else datetime.now(ROME).date()
    data = build(end)
    save(OUT, data)
    print(f"BUILT F1 QUALIFIED 14D: {data['count']} assets ({data['formats']['reel']} reels + {data['formats']['carousel']} carousels), {data['window_start']} -> {data['window_end']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
