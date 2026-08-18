#!/usr/bin/env python3
"""Archive user-validated queue jobs into the persistent GitHub content memory.

Validation can be supplied with VALIDATED_JOB_IDS (comma-separated IDs) or by setting
validation_status=approved on queue jobs. Re-running is idempotent by job ID.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
MEMORY = ROOT / "publisher" / "content_memory.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(job: dict, approved_at: str) -> dict:
    return {
        "id": job.get("id"),
        "brand": job.get("client_id"),
        "type": job.get("format"),
        "title": job.get("title"),
        "research_query": job.get("research_query"),
        "caption": job.get("caption"),
        "voiceover": job.get("voiceover"),
        "cta": job.get("cta"),
        "territory": job.get("territory"),
        "cycle_key": job.get("cycle_key"),
        "approved_at": approved_at,
        "visual_asset_urls": job.get("visual_asset_urls", []),
        "visual_source": job.get("visual_source"),
        "media": job.get("media"),
        "template_profile": "publisher/reference_models.json",
        "status": "approved"
    }


def main() -> int:
    queue = load(QUEUE)
    memory = load(MEMORY)
    explicit = {x.strip() for x in os.getenv("VALIDATED_JOB_IDS", "").split(",") if x.strip()}
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changed = 0
    for job in queue.get("jobs", []):
        jid = str(job.get("id") or "")
        approved = jid in explicit or str(job.get("validation_status") or "").lower() == "approved"
        if not approved:
            continue
        brand = str(job.get("client_id") or "")
        bucket = memory.setdefault("approved", {}).setdefault(brand, [])
        if any(str(row.get("id")) == jid for row in bucket if isinstance(row, dict)):
            continue
        bucket.append(record(job, stamp))
        job["validation_status"] = "approved"
        job["validated_at"] = stamp
        changed += 1
    if changed:
        memory["updated_at"] = stamp
        save(MEMORY, memory)
        save(QUEUE, queue)
    print(f"Archived {changed} validated content(s) into GitHub memory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
