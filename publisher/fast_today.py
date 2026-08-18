#!/usr/bin/env python3
"""Keep only one immediate Reel per brand for the emergency same-day fast lane."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
BRANDS = ("f1-immobiliare", "real-media-pro")


def load() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    data = load()
    target = os.getenv("SOCIAL_DATE", "").strip() or datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    jobs = list(data.get("jobs", []))
    selected = []
    for brand in BRANDS:
        candidates = [
            j for j in jobs
            if str(j.get("client_id")) == brand
            and str(j.get("scheduled_at", ""))[:10] == target
            and str(j.get("format", "reel")).lower() == "reel"
            and j.get("status") not in {"published", "disabled"}
        ]
        candidates.sort(key=lambda j: (str(j.get("scheduled_at", "")), str(j.get("id", ""))))
        if not candidates:
            raise SystemExit(f"No Reel candidate found for {brand} on {target}")
        job = candidates[0]
        job["scheduled_at"] = datetime.now(ZoneInfo("Europe/Rome")).replace(microsecond=0).isoformat()
        job["production_status"] = "FAST TODAY - PRIORITA IMMEDIATA"
        job["publish_decision"] = "manual"
        selected.append(job)
    data["jobs"] = selected
    data["version"] = max(int(data.get("version", 1)), 6)
    data["updated_by"] = "Emergency Fast Lane 1+1"
    save(data)
    print("Fast lane prepared: 1 F1 Reel + 1 Real Media Pro Reel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
