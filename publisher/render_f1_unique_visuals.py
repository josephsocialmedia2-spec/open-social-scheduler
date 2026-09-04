#!/usr/bin/env python3
"""Render the qualified 14-day F1 batch with one unique primary visual per content."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import render_f1_qualified_14d as base

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "qualified_14d_queue.json"
CACHE = ROOT / ".cache" / "f1-qualified-sources"


def cache_path(url: str) -> Path:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE / f"{key}.jpg"


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    jobs = list(data.get("jobs") or [])
    blocked = [j for j in jobs if j.get("gate_status") != "PASSED"]
    if blocked:
        raise RuntimeError(f"Refusing render: {len(blocked)} jobs have not PASSED producer gate")

    used: set[str] = set()
    reels = carousels = 0
    for job in jobs:
        urls = list(job.get("visual_asset_urls") or [])
        if len(urls) != 1:
            raise RuntimeError(f"{job.get('id')} must have exactly one primary visual URL")
        url = str(urls[0])
        if url in used:
            raise RuntimeError(f"Primary visual reused across contents: {url}")
        used.add(url)
        src = cache_path(url)
        if not src.exists() or src.stat().st_size < 20000:
            raise RuntimeError(f"Cached unique visual missing for {job.get('id')}: {src}")

        if job.get("format") == "reel":
            base.render_reel(job, [src])
            reels += 1
        elif job.get("format") == "carousel":
            base.render_carousel(job, [src])
            carousels += 1
        else:
            raise RuntimeError(f"Unsupported format {job.get('format')}")

        spec = dict(job.get("render_spec") or {})
        spec["source_policy"] = "one_unique_themed_primary_visual_per_content_no_reuse_14d"
        spec["unique_primary_visual_per_content"] = True
        spec["legacy_visuals_allowed"] = False
        job["render_spec"] = spec

    if len(used) != 28:
        raise RuntimeError(f"Expected 28 unique visuals, got {len(used)}")

    data["render_summary"] = {"reels": reels, "carousels": carousels, "total": reels + carousels}
    data["visual_source_policy"] = "28 contents = 28 different themed primary images; no primary visual reuse within 14 days"
    data["unique_visual_summary"] = {"contents": 28, "unique_primary_visuals": 28, "reuse": 0}
    QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("RENDERED UNIQUE F1 BATCH: 14 reels + 14 carousels; 28/28 distinct primary visuals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
