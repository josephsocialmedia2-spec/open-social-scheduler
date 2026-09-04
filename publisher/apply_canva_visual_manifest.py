#!/usr/bin/env python3
"""Bind 28 unique themed visuals to the F1 qualified-seller producer.

Each content receives one primary photographic source that cannot be reused by
another content in the same 14-day batch. Unsplash landing pages are resolved
to their Open Graph image once and cached for the renderer. Legacy F1 creative
is physically removed from the ephemeral Actions workspace.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

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


def og_image(text: str) -> str | None:
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'"image"\s*:\s*"(https:[^"\\]+)"',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return html.unescape(m.group(1).replace("\\u0026", "&"))
    return None


def resolve_and_cache(landing_url: str) -> tuple[Path, str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = cached_path(landing_url)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; F1ImmobiliareContentQA/2.0)",
        "Accept": "text/html,image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    page = requests.get(landing_url, headers=headers, timeout=35, allow_redirects=True)
    page.raise_for_status()
    ctype = str(page.headers.get("content-type") or "").lower()
    resolved = landing_url
    raw = page.content
    if "image/" not in ctype:
        resolved = og_image(page.text) or ""
        if not resolved:
            raise RuntimeError(f"No og:image found for {landing_url}")
        img = requests.get(resolved, headers={**headers, "Accept": "image/*,*/*;q=0.8"}, timeout=35, allow_redirects=True)
        img.raise_for_status()
        raw = img.content
    im = Image.open(BytesIO(raw)).convert("RGB")
    if im.width < 600 or im.height < 500:
        raise RuntimeError(f"Visual too small {im.size}: {landing_url}")
    im.save(dest, "JPEG", quality=94, optimize=True)
    return dest, resolved


def main() -> int:
    manifest = load(MANIFEST)
    client = load(CLIENT)
    queue = load(QUEUE)
    sources = list(manifest.get("visual_sources") or [])
    jobs = list(queue.get("jobs") or [])

    if len(sources) != 28 or len(jobs) != 28:
        raise RuntimeError(f"Expected 28 visual sources and 28 jobs; got {len(sources)} / {len(jobs)}")
    ids = [str(x.get("source_item_id") or "") for x in sources]
    urls = [str(x.get("landing_url") or "").strip() for x in sources]
    if len(set(ids)) != 28 or len(set(urls)) != 28:
        raise RuntimeError("Visual manifest contains duplicate source_item_id or landing_url")

    if LEGACY.exists():
        shutil.rmtree(LEGACY)

    resolved_by_id: dict[str, dict] = {}
    for src in sources:
        item_id = str(src["source_item_id"])
        landing = str(src["landing_url"]).strip()
        path, resolved = resolve_and_cache(landing)
        resolved_by_id[item_id] = {
            "landing_url": landing,
            "resolved_url": resolved,
            "theme": str(src.get("theme") or ""),
            "cache_path": str(path.relative_to(ROOT)),
        }
        print(f"VISUAL {item_id}: {src.get('theme')} -> {resolved}")

    resolved_urls = [v["resolved_url"] for v in resolved_by_id.values()]
    if len(set(resolved_urls)) != 28:
        raise RuntimeError("Resolved visual duplication detected: 28 contents must have 28 different primary images")

    brand = client.setdefault("brand", {})
    brand["photo_sources"] = [
        {"url": x["landing_url"], "source": "f1_unique_visual_manifest", "approved": True}
        for x in resolved_by_id.values()
    ]
    brand["visual_source_of_truth"] = "publisher/canva_visual_manifest.json"
    brand["legacy_visuals_allowed"] = False
    brand["unique_primary_visual_per_content"] = True

    assigned: list[str] = []
    for job in jobs:
        item_id = str(job.get("source_item_id") or "")
        src = resolved_by_id.get(item_id)
        if not src:
            raise RuntimeError(f"No visual source mapped to {item_id}")
        assigned.append(src["landing_url"])
        job["canva_visual_source"] = True
        job["canva_manifest"] = "publisher/canva_visual_manifest.json"
        job["visual_asset_urls"] = [src["landing_url"]]
        job["resolved_visual_url"] = src["resolved_url"]
        job["visual_theme"] = src["theme"]
        job["visual_cache_path"] = src["cache_path"]
        job["unique_primary_visual"] = True
        job["legacy_visuals_allowed"] = False

        fmt = str(job.get("format") or "")
        cfg = manifest["reels"] if fmt == "reel" else manifest["carousels"]
        try:
            n = int(re.sub(r"\D", "", item_id) or "1")
        except ValueError:
            n = 1
        per = int(cfg["pages_per_item"])
        job["canva_design_id"] = cfg.get("design_id")
        job["canva_edit_url"] = cfg.get("edit_url")
        job["canva_page_start"] = (n - 1) * per + 1
        job["canva_page_end"] = job["canva_page_start"] + per - 1

    if len(set(assigned)) != len(jobs):
        raise RuntimeError("A primary visual was assigned to more than one content")

    queue["visual_source"] = "canva_unique_manifest"
    queue["canva_manifest"] = "publisher/canva_visual_manifest.json"
    queue["legacy_visuals_allowed"] = False
    queue["unique_visual_summary"] = {
        "contents": len(jobs),
        "unique_primary_visuals": len(set(assigned)),
        "reuse": 0,
    }
    save(CLIENT, client)
    save(QUEUE, queue)
    print("UNIQUE VISUAL POLICY PASSED: 28 contents -> 28 distinct themed images; legacy workspace removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
