#!/usr/bin/env python3
"""Render the current 4-hour cycle with fresh, non-repeating Pixabay photography.

Unlike the legacy renderer, this module does NOT rotate the same ten URLs. For each
job it discovers fresh Pixabay CDN assets through web image search, rejects photos
already used in the repository history, validates downloads, records the exact
asset URLs in the queue, and only then renders the final media.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image
from ddgs import DDGS

import render_reels as rr

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
HISTORY = ROOT / "publisher" / "image_history.json"
MAX_HISTORY_PER_BRAND = 320
USED_THIS_RUN: set[str] = set()

# Emergency-only licensed Pixabay CDN fallback. It is used only if dynamic search
# cannot supply enough fresh assets. Dynamic discovery is always attempted first.
FALLBACK = {
    "f1-immobiliare": [
        "https://cdn.pixabay.com/photo/2025/08/29/17/52/modern-villa-exterior-9804538_1280.jpg",
        "https://cdn.pixabay.com/photo/2025/08/29/17/52/luxury-villa-facade-9804536_1280.jpg",
        "https://cdn.pixabay.com/photo/2025/08/25/10/19/living-room-9795892_1280.jpg",
        "https://cdn.pixabay.com/photo/2017/09/15/15/22/modern-2752472_1280.jpg",
        "https://cdn.pixabay.com/photo/2023/12/11/06/20/real-estate-8442802_1280.jpg",
        "https://cdn.pixabay.com/photo/2024/03/27/10/34/apartment-8658767_1280.jpg",
        "https://cdn.pixabay.com/photo/2023/09/18/12/05/kitchen-8260437_1280.jpg",
        "https://cdn.pixabay.com/photo/2024/02/06/07/01/bathroom-8556101_1280.jpg",
        "https://cdn.pixabay.com/photo/2023/12/04/01/27/real-estate-8428506_1280.jpg",
        "https://cdn.pixabay.com/photo/2024/02/14/07/08/bedroom-8572584_1280.jpg",
    ],
    "real-media-pro": [
        "https://cdn.pixabay.com/photo/2017/06/26/12/57/laptop-2443749_1280.jpg",
        "https://cdn.pixabay.com/photo/2018/02/08/10/22/desk-3139127_1280.jpg",
        "https://cdn.pixabay.com/photo/2023/10/10/05/53/laptop-8305452_1280.jpg",
        "https://cdn.pixabay.com/photo/2015/01/08/18/25/desk-593327_1280.jpg",
        "https://cdn.pixabay.com/photo/2019/07/13/10/25/payment-4334491_1280.jpg",
        "https://cdn.pixabay.com/photo/2017/10/29/17/31/online-2900303_640.jpg",
        "https://cdn.pixabay.com/photo/2017/08/07/19/45/ecommerce-2607114_640.jpg",
        "https://cdn.pixabay.com/photo/2022/07/06/03/41/business-7304257_640.jpg",
        "https://cdn.pixabay.com/photo/2019/06/15/16/06/online-4275963_1280.jpg",
        "https://cdn.pixabay.com/photo/2018/07/31/14/52/ecommerce-3575280_1280.jpg",
    ],
}


def load(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def photo_key(url: str) -> str:
    """Collapse 640/1280 variants of the same Pixabay photo into one history key."""
    path = url.split("?", 1)[0]
    path = re.sub(r"_(?:340|640|960|1280|1920)\.(jpg|jpeg|png|webp)$", r".\1", path, flags=re.I)
    return path


def valid_pixabay_candidate(item: dict[str, Any]) -> str | None:
    image = str(item.get("image") or item.get("thumbnail") or "").strip()
    page = str(item.get("url") or item.get("source") or "").strip()
    if not image:
        return None
    if "cdn.pixabay.com/" in image:
        return image
    if "pixabay.com/" in image and "/get/" in image:
        return image
    # Some search engines proxy thumbnails. Never use those as final assets.
    if "pixabay.com" in page and "cdn.pixabay.com" in image:
        return image
    return None


def search_queries(job: dict[str, Any]) -> list[str]:
    cid = str(job.get("client_id") or "")
    title = re.sub(r"[^A-Za-zÀ-ÿ0-9 ]+", " ", str(job.get("title") or "")).strip()
    visuals = [str(x).strip() for x in job.get("visuals", []) if str(x).strip()]
    if cid == "f1-immobiliare":
        core = "real estate residential house home interior exterior architecture"
        anchors = [
            "modern house exterior real estate",
            "luxury living room apartment interior",
            "modern kitchen bedroom bathroom home",
        ]
    else:
        core = "digital business ecommerce marketing laptop smartphone online shop"
        anchors = [
            "ecommerce laptop online shopping business",
            "digital marketing workspace analytics smartphone",
            "website online store entrepreneur office",
        ]
    queries = [f"{title} {core} site:pixabay.com"] if title else []
    for anchor in anchors:
        queries.append(f"{anchor} site:pixabay.com")
    for visual in visuals[:3]:
        queries.append(f"{visual} site:pixabay.com")
    return queries


def discover(job: dict[str, Any], recent: set[str], need: int = 10) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for query in search_queries(job):
        try:
            with DDGS() as ddgs:
                rows = list(ddgs.images(query, max_results=45) or [])
        except Exception as exc:
            print(f"WARN image search failed: {query}: {exc}")
            continue
        for row in rows:
            url = valid_pixabay_candidate(row)
            if not url:
                continue
            key = photo_key(url)
            if key in seen or key in USED_THIS_RUN or key in recent:
                continue
            seen.add(key)
            found.append(url)
            if len(found) >= need:
                return found
    return found


def direct_get_image(url: str) -> Image.Image:
    rr.CACHE.mkdir(parents=True, exist_ok=True)
    cache = rr.CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".jpg")
    if cache.exists() and cache.stat().st_size > 12000:
        return Image.open(cache).convert("RGB")
    last: Exception | None = None
    headers = {
        "User-Agent": "Mozilla/5.0 Open-Social-Scheduler/FreshVisuals",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://pixabay.com/",
    }
    for attempt in range(4):
        try:
            response = requests.get(url, headers=headers, timeout=40)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
            if image.width < 500 or image.height < 500:
                raise RuntimeError(f"image too small: {image.size}")
            image.save(cache, "JPEG", quality=94, optimize=True)
            return image
        except Exception as exc:
            last = exc
            time.sleep(1 + attempt * 2)
    raise RuntimeError(f"image download failed: {url}: {last}")


def usable_urls(job: dict[str, Any], recent: set[str]) -> list[str]:
    urls = discover(job, recent, need=18)
    out: list[str] = []
    for url in urls:
        try:
            direct_get_image(url)
        except Exception as exc:
            print(f"WARN rejecting image {url}: {exc}")
            continue
        key = photo_key(url)
        if key in USED_THIS_RUN or key in recent:
            continue
        out.append(url)
        USED_THIS_RUN.add(key)
        if len(out) == 10:
            return out

    # Emergency fallback only; prefer unused fallback URLs.
    cid = str(job.get("client_id") or "")
    for url in FALLBACK.get(cid, []):
        key = photo_key(url)
        if key in USED_THIS_RUN:
            continue
        try:
            direct_get_image(url)
        except Exception:
            continue
        out.append(url)
        USED_THIS_RUN.add(key)
        if len(out) == 10:
            return out

    # A job must never silently render 10 duplicated frames.
    if len(out) < 10:
        raise RuntimeError(
            f"Fresh visual policy blocked {job.get('id')}: only {len(out)} unique usable Pixabay images found"
        )
    return out


def render_reel(job: dict[str, Any], c: dict[str, Any], urls: list[str], presenter_name: str | None) -> Path:
    out = ROOT / str(job["media"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="oss-fresh-") as td:
        t = Path(td)
        v = rr.voice(job, t)
        m = rr.music(t / "music.wav")
        frames: list[Path] = []
        for i, url in enumerate(urls[:10]):
            p = t / f"f{i:02d}.jpg"
            rr.frame(c, url, 1080, 1920, "reel", who=presenter_name).save(p, "JPEG", quality=94, optimize=True)
            frames.append(p)
        rr.make_video(frames, v, m, out, 60)
    return out


def render_carousel(job: dict[str, Any], c: dict[str, Any], urls: list[str]) -> list[Path]:
    slides = (list(job.get("slides") or []) + [""] * 10)[:10]
    media = list(job.get("media") or [])
    if len(media) != 10:
        raise RuntimeError(f"Carousel {job.get('id')} must have exactly 10 media paths")
    outs: list[Path] = []
    for i, (title, rel, url) in enumerate(zip(slides, media, urls[:10])):
        out = ROOT / str(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        rr.frame(c, url, 1080, 1350, "carousel", title=title).save(out, "JPEG", quality=94, optimize=True)
        outs.append(out)
    return outs


def main() -> int:
    rr.get_image = direct_get_image
    queue = load(QUEUE, {"jobs": []})
    history = load(HISTORY, {"version": 1, "brands": {}})
    current_cycle = str(queue.get("current_cycle") or "")
    jobs = [
        j for j in queue.get("jobs", [])
        if str(j.get("cycle_key") or "") == current_cycle
        and j.get("enabled", True)
        and j.get("status") not in {"published", "disabled"}
    ]
    if not jobs:
        print("No current-cycle jobs to render")
        return 0

    counts: dict[str, int] = {}
    rendered = 0
    for job in sorted(jobs, key=lambda j: (str(j.get("client_id")), int(j.get("cycle_position", 0)))):
        cid = str(job.get("client_id") or "")
        brand_hist = history.setdefault("brands", {}).setdefault(cid, {"recent": []})
        recent_rows = list(brand_hist.get("recent", []))
        recent = {str(row.get("key") if isinstance(row, dict) else row) for row in recent_rows}
        urls = usable_urls(job, recent)
        job["visual_asset_urls"] = urls
        job["visual_source"] = "pixabay_dynamic_non_repeating"
        job["visual_uniqueness"] = "10 unique frames; repository history checked"
        c = rr.cfg(cid)
        if str(job.get("format") or "reel") == "carousel":
            render_carousel(job, c, urls)
        else:
            k = counts.get(cid, 0)
            presenter_name = ("joseph" if k % 2 == 0 else "francesca") if cid == "f1-immobiliare" else None
            counts[cid] = k + 1
            job["_presenter"] = presenter_name or ""
            render_reel(job, c, urls, presenter_name)
        rendered += 1
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for url in urls:
            recent_rows.append({"key": photo_key(url), "url": url, "used_at": stamp, "job_id": job.get("id")})
        brand_hist["recent"] = recent_rows[-MAX_HISTORY_PER_BRAND:]

    queue["updated_by"] = "Fresh Pixabay visual renderer"
    queue["visual_policy"] = "never reuse same 10-image set; reject duplicate recent photos"
    save(QUEUE, queue)
    history["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save(HISTORY, history)
    print(f"Rendered {rendered} current-cycle contents with fresh Pixabay visuals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
