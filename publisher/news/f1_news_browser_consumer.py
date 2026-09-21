#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = ROOT / "publisher" / "news" / "f1_news_browser_queue.json"
DEFAULT_OUTPUT = ROOT / "publisher" / "news" / "f1_news_current.local.json"
ROME = ZoneInfo("Europe/Rome")


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_slot(now: datetime, requested: str) -> tuple[str, str] | None:
    if requested == "midday":
        return "MIDDAY", f"{now.date().isoformat()}|MIDDAY"
    if requested == "evening":
        return "EVENING", f"{now.date().isoformat()}|EVENING"
    if requested == "immediate":
        return "IMMEDIATE", f"{now.date().isoformat()}|IMMEDIATE"

    minutes = now.hour * 60 + now.minute
    if 10 * 60 + 45 <= minutes <= 13 * 60:
        return "MIDDAY", f"{now.date().isoformat()}|MIDDAY"
    if 18 * 60 + 45 <= minutes <= 21 * 60:
        return "EVENING", f"{now.date().isoformat()}|EVENING"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["auto", "midday", "evening", "immediate"], default="auto")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--queue", default=str(QUEUE_PATH))
    args = parser.parse_args()

    now = datetime.now(ROME)
    slot_info = resolve_slot(now, args.slot)
    if slot_info is None:
        print(json.dumps({"status": "NOOP_OUTSIDE_PUBLICATION_WINDOW"}, ensure_ascii=False))
        return 4
    slot_name, slot_key = slot_info
    queue = load_json(Path(args.queue), {"items": []})

    candidates = [
        row
        for row in queue.get("items") or []
        if str(row.get("slot_key") or "") == slot_key
        and str(row.get("status") or "") not in {"PUBLISHED_VERIFIED", "FAILED_FINAL", "CANCELLED"}
    ]
    candidates.sort(key=lambda row: str(row.get("created_at") or ""))
    if not candidates:
        print(json.dumps({"status": "NOOP_NO_QUEUED_JOB", "slot_key": slot_key}, ensure_ascii=False))
        return 4

    row = candidates[0]
    payload = {
        "batch": "f1-news-valle-susa-github-to-browser-v1",
        "backend": "chatgpt_browser",
        "strategy": "F1 NEWS VALLE DI SUSA",
        "queries": [
            {
                "id": row["id"],
                "query": row.get("query") or row.get("headline") or "",
                "communication": row.get("communication") or row.get("caption") or "",
                "caption": row.get("caption") or row.get("communication") or "",
                "prompt": row.get("prompt") or "",
                "client": row.get("client") or "F1 Immobiliare",
                "territory": row.get("territory") or "Valle di Susa",
                "scope": row.get("scope") or "network",
                "platforms": row.get("platforms") or ["facebook", "instagram"],
                "source": row.get("source") or "f1-news-browser-control",
                "news_id": row.get("news_id") or "",
                "headline": row.get("headline") or "",
                "cta": row.get("cta") or "SCOPRI COSA CAMBIA",
                "category": row.get("category") or "immobiliare",
                "source_name": row.get("source_name") or "",
                "source_url": row.get("source_url") or "",
                "source_hash": row.get("source_hash") or "",
                "source_published_at": row.get("source_published_at") or "",
                "editorial_slot": row.get("editorial_slot") or slot_name.lower(),
                "slot_key": row.get("slot_key") or slot_key,
                "publication_status": row.get("status") or "QUEUED_FOR_PC",
            }
        ],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "JOB_READY_FOR_BROWSER",
                "job_id": row["id"],
                "slot_key": slot_key,
                "query_file": output.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
