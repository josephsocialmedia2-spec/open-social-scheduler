#!/usr/bin/env python3
"""Apply enrich_queue only to the current 4-hour cycle without rewriting older content."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import enrich_queue as enrich

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"


def load() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    full = load()
    current = str(full.get("current_cycle") or "")
    if not current:
        raise SystemExit("current_cycle is missing")
    subset_jobs = [copy.deepcopy(j) for j in full.get("jobs", []) if str(j.get("cycle_key") or "") == current]
    if len(subset_jobs) != 6:
        raise SystemExit(f"Expected 6 current-cycle jobs, got {len(subset_jobs)}")

    working = {
        "version": full.get("version", 7),
        "jobs": subset_jobs,
        "current_cycle": current,
    }
    save(working)
    try:
        rc = enrich.main()
        enriched = load()
    finally:
        # Merge the enriched jobs back into the untouched full queue.
        pass

    by_id = {str(j.get("id")): j for j in enriched.get("jobs", [])}
    merged = []
    for job in full.get("jobs", []):
        merged.append(by_id.get(str(job.get("id")), job))
    full["jobs"] = merged
    full["updated_by"] = "4-hour cycle enrichment"
    save(full)
    print(f"Enriched {len(by_id)} jobs for {current}")
    return int(rc or 0)


if __name__ == "__main__":
    raise SystemExit(main())
