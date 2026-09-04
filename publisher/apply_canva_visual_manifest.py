#!/usr/bin/env python3
"""Bind 28 unique themed photographic visuals to the F1 seller-lead producer.

Every content receives exactly one direct image URL. The file is downloaded,
validated as an actual image, normalized and hashed. The batch is rejected if
URLs OR normalized pixel hashes are duplicated. Legacy F1 creative is removed
from the ephemeral Actions workspace before rendering.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "publisher" / "canva_visual_manifest.json"
CLIENT = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
QUEUE = ROOT / "publisher" / "qualified_14d_queue.json"
LEGACY = ROOT / "publisher" / "manual_images" / "f1-immobiliare" / "RIC LAVORO F1"
CACHE = ROOT / ".cache" / "f1-qualified-sources"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cached_path(url: str) -> Path:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE / f"{key}.jpg"


def normalized_pixel_hash(im: Image.Image) -> str:
    # Normalize size/orientation so the uniqueness test checks image content,
    # not just URL parameters or file metadata.
    sample = ImageOps.fit(im.convert("RGB"), (256, 256), method=Image.Resampling.LANCZOS)
    return hashlib.sha256(sample.tobytes()).hexdigest()


def download_and_cache(image_url: str) -> tuple[Path, str, tuple[int, int]]:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = cached_path(image_url)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; F1ImmobiliareVisualProducer/3.0)",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.pexels.com/",
    }
    last: Exception | None = None
    raw: bytes | None = None
    for attempt, wait in enumerate((0, 2, 5), start=1):
        if wait:
            time.sleep(wait)
        try:
            r = requests.get(image_url, headers=headers, timeout=40, allow_redirects=True)
            r.raise_for_status()
            ctype = str(r.headers.get("content-type") or "").lower()
            if "image" not in ctype and len(r.content) < 50000:
                raise RuntimeError(f"not an image response: {ctype}")
            raw = r.content
            break
        except Exception as exc:
            last = exc
            print(f"WARN image attempt {attempt}: {image_url}: {exc}")
    if raw is None:
        raise RuntimeError(f"Unable to download visual {image_url}: {last}")

    im = Image.open(BytesIO(raw)).convert("RGB")
    if im.width < 600 or im.height < 500:
        raise RuntimeError(f"Visual too small {im.size}: {image_url}")
    pixel_hash = normalized_pixel_hash(im)
    im.save(dest, "JPEG", quality=94, optimize=True)
    if dest.stat().st_size < 20000:
        raise RuntimeError(f"Cached visual unexpectedly small: {dest}")
    return dest, pixel_hash, (im.width, im.height)


def main() -> int:
    manifest = load(MANIFEST)
    client = load(CLIENT)
    queue = load(QUEUE)
    sources = list(manifest.get("visual_sources") or [])
    jobs = list(queue.get("jobs") or [])

    if len(sources) != 28 or len(jobs) != 28:
        raise RuntimeError(f"Expected 28 visual sources and 28 jobs; got {len(sources)} / {len(jobs)}")
    ids = [str(x.get("source_item_id") or "") for x in sources]
    urls = [str(x.get("image_url") or "").strip() for x in sources]
    if len(set(ids)) != 28 or any(not x for x in urls) or len(set(urls)) != 28:
        raise RuntimeError("Visual manifest must contain 28 unique source_item_id values and 28 unique direct image_url values")

    if LEGACY.exists():
        shutil.rmtree(LEGACY)

    resolved_by_id: dict[str, dict] = {}
    hashes: list[str] = []
    for src in sources:
        item_id = str(src["source_item_id"])
        image_url = str(src["image_url"]).strip()
        path, pixel_hash, dimensions = download_and_cache(image_url)
        hashes.append(pixel_hash)
        resolved_by_id[item_id] = {
            "image_url": image_url,
            "theme": str(src.get("theme") or ""),
            "cache_path": str(path.relative_to(ROOT)),
            "pixel_sha256": pixel_hash,
            "dimensions": list(dimensions),
        }
        print(f"VISUAL {item_id}: {src.get('theme')} -> {dimensions[0]}x{dimensions[1]} hash={pixel_hash[:12]}")

    if len(set(hashes)) != 28:
        duplicates = sorted({h for h in hashes if hashes.count(h) > 1})
        raise RuntimeError(f"Actual image-content duplication detected. Unique hashes={len(set(hashes))}/28; duplicates={duplicates}")

    brand = client.setdefault("brand", {})
    brand["photo_sources"] = [
        {"url": x["image_url"], "source": "f1_unique_visual_manifest", "approved": True}
        for x in resolved_by_id.values()
    ]
    brand["visual_source_of_truth"] = "publisher/canva_visual_manifest.json"
    brand["legacy_visuals_allowed"] = False
    brand["unique_primary_visual_per_content"] = True
    brand["visual_content_hash_uniqueness_required"] = True

    assigned_urls: list[str] = []
    assigned_hashes: list[str] = []
    for job in jobs:
        item_id = str(job.get("source_item_id") or "")
        src = resolved_by_id.get(item_id)
        if not src:
            raise RuntimeError(f"No visual source mapped to {item_id}")
        assigned_urls.append(src["image_url"])
        assigned_hashes.append(src["pixel_sha256"])
        job["canva_visual_source"] = True
        job["canva_manifest"] = "publisher/canva_visual_manifest.json"
        job["visual_asset_urls"] = [src["image_url"]]
        job["resolved_visual_url"] = src["image_url"]
        job["visual_theme"] = src["theme"]
        job["visual_cache_path"] = src["cache_path"]
        job["visual_content_sha256"] = src["pixel_sha256"]
        job["visual_dimensions"] = src["dimensions"]
        job["unique_primary_visual"] = True
        job["legacy_visuals_allowed"] = False

        fmt = str(job.get("format") or "")
        cfg = manifest["reels"] if fmt == "reel" else manifest["carousels"]
        n = int(re.sub(r"\D", "", item_id) or "1")
        per = int(cfg["pages_per_item"])
        job["canva_design_id"] = cfg.get("design_id")
        job["canva_edit_url"] = cfg.get("edit_url")
        job["canva_page_start"] = (n - 1) * per + 1
        job["canva_page_end"] = job["canva_page_start"] + per - 1

    if len(set(assigned_urls)) != 28 or len(set(assigned_hashes)) != 28:
        raise RuntimeError("Primary visual uniqueness invariant failed after assignment")

    queue["visual_source"] = "direct_cdn_unique_manifest"
    queue["canva_manifest"] = "publisher/canva_visual_manifest.json"
    queue["legacy_visuals_allowed"] = False
    queue["unique_visual_summary"] = {
        "contents": 28,
        "unique_primary_visuals": 28,
        "unique_content_hashes": 28,
        "reuse": 0
    }
    save(CLIENT, client)
    save(QUEUE, queue)
    print("UNIQUE VISUAL POLICY PASSED: 28 contents -> 28 URLs -> 28 distinct pixel hashes -> reuse 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
