#!/usr/bin/env python3
"""Bind the F1 Canva visual manifest to the qualified-seller producer.

The Canva designs are the editable visual source of truth. This script injects
only clean photographic sources from the Canva manifest into the renderer and
adds Canva traceability to every queue job. Legacy manual creative is not used
when manifest images are available.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "publisher" / "canva_visual_manifest.json"
CLIENT = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
QUEUE = ROOT / "publisher" / "qualified_14d_queue.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def item_number(job: dict) -> int:
    raw = str(job.get("source_item_id") or job.get("id") or "1")
    m = re.search(r"(\d+)", raw)
    return max(1, int(m.group(1)) if m else 1)


def main() -> int:
    manifest = load(MANIFEST)
    client = load(CLIENT)
    queue = load(QUEUE)
    images = [str(x).strip() for x in manifest.get("cover_images") or [] if str(x).strip()]
    if len(images) < 6:
        raise RuntimeError(f"Canva visual manifest needs at least 6 clean image sources; got {len(images)}")

    brand = client.setdefault("brand", {})
    brand["photo_sources"] = [
        {"url": url, "source": "canva_visual_manifest", "approved": True}
        for url in images
    ]
    brand["visual_source_of_truth"] = "publisher/canva_visual_manifest.json"
    brand["legacy_visuals_allowed"] = False

    for job in queue.get("jobs") or []:
        n = item_number(job)
        fmt = str(job.get("format") or "")
        cfg = manifest["reels"] if fmt == "reel" else manifest["carousels"]
        per = int(cfg["pages_per_item"])
        start = (n - 1) * per + 1
        job["canva_visual_source"] = True
        job["canva_manifest"] = "publisher/canva_visual_manifest.json"
        job["canva_design_id"] = cfg["design_id"]
        job["canva_edit_url"] = cfg["edit_url"]
        job["canva_page_start"] = start
        job["canva_page_end"] = start + per - 1
        job["visual_asset_urls"] = [images[(n * 3 + (1 if fmt == "carousel" else 0)) % len(images)]]
        job["legacy_visuals_allowed"] = False

    queue["visual_source"] = "canva"
    queue["canva_manifest"] = "publisher/canva_visual_manifest.json"
    queue["legacy_visuals_allowed"] = False
    save(CLIENT, client)
    save(QUEUE, queue)
    print(f"CANVA VISUALS APPLIED: {len(images)} clean sources -> {len(queue.get('jobs') or [])} jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
