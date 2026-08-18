#!/usr/bin/env python3
"""Render the active 4-hour cycle with varied Pixabay photography.

Policy:
- every single Reel/carousel must contain 10 different source images;
- prefer images never used recently for that brand;
- never go back to a fixed 10-image rotation;
- if search supply is temporarily limited, allow controlled reuse across DIFFERENT
  contents rather than failing the whole production, while still keeping the 10
  frames inside each content unique;
- persist exact URLs and freshness statistics in GitHub memory.
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
MAX_HISTORY_PER_BRAND = 500
SESSION_USED: dict[str, set[str]] = {
    "f1-immobiliare": set(),
    "real-media-pro": set(),
}

# Known-good direct Pixabay assets. They are ONLY a safety net after dynamic
# discovery. They are not used as the normal repeating visual set.
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def photo_key(url: str) -> str:
    path = str(url).split("?", 1)[0]
    return re.sub(
        r"_(?:340|640|960|1280|1920)\.(jpg|jpeg|png|webp)$",
        r".\1",
        path,
        flags=re.I,
    )


def candidate_url(item: dict[str, Any]) -> str | None:
    image = str(item.get("image") or item.get("thumbnail") or "").strip()
    if not image:
        return None
    if "cdn.pixabay.com/" in image:
        return image
    if "pixabay.com/" in image and "/get/" in image:
        return image
    return None


def search_queries(job: dict[str, Any]) -> list[str]:
    cid = str(job.get("client_id") or "")
    title = re.sub(r"[^A-Za-zÀ-ÿ0-9 ]+", " ", str(job.get("title") or "")).strip()
    territory = re.sub(r"[^A-Za-zÀ-ÿ0-9 ]+", " ", str(job.get("territory") or "")).strip()
    visuals = [str(x).strip() for x in job.get("visuals", []) if str(x).strip()]

    if cid == "f1-immobiliare":
        anchors = [
            "modern house exterior residential architecture",
            "apartment living room bright interior",
            "modern kitchen residential interior",
            "bedroom apartment interior",
            "bathroom modern home interior",
            "villa garden residential exterior",
            "balcony terrace apartment home",
        ]
    else:
        anchors = [
            "entrepreneur laptop modern office",
            "ecommerce online shop laptop smartphone",
            "digital marketing analytics workspace",
            "website design laptop business",
            "online shopping checkout smartphone",
            "business team digital office",
            "small business owner laptop",
        ]

    queries: list[str] = []
    if title:
        queries.append(f"{title} pixabay")
    if territory and cid == "f1-immobiliare":
        queries.append(f"residential home architecture {territory} pixabay")
    for visual in visuals:
        queries.append(f"{visual} pixabay")
    queries.extend(f"{x} pixabay" for x in anchors)

    out: list[str] = []
    seen: set[str] = set()
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            out.append(q)
            seen.add(key)
    return out[:15]


def discover(job: dict[str, Any], max_urls: int = 90) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for query in search_queries(job):
        rows: list[dict[str, Any]] = []
        for attempt in range(2):
            try:
                with DDGS() as ddgs:
                    rows = list(ddgs.images(query, max_results=70) or [])
                break
            except Exception as exc:
                print(f"WARN image search attempt {attempt + 1} failed: {query}: {exc}")
                time.sleep(1.5 + attempt)
        for row in rows:
            url = candidate_url(row)
            if not url:
                continue
            key = photo_key(url)
            if key in seen:
                continue
            seen.add(key)
            found.append(url)
            if len(found) >= max_urls:
                return found
    return found


def direct_get_image(url: str) -> Image.Image:
    rr.CACHE.mkdir(parents=True, exist_ok=True)
    cache = rr.CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".jpg")
    if cache.exists() and cache.stat().st_size > 12000:
        return Image.open(cache).convert("RGB")

    headers = {
        "User-Agent": "Mozilla/5.0 Open-Social-Scheduler/FreshVisuals",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://pixabay.com/",
    }
    last: Exception | None = None
    for attempt in range(4):
        try:
            response = requests.get(url, headers=headers, timeout=35)
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


def choose_urls(job: dict[str, Any], recent: set[str]) -> tuple[list[str], int]:
    """Return 10 unique images for this content and number that are fully fresh."""
    cid = str(job.get("client_id") or "")
    session = SESSION_USED.setdefault(cid, set())
    discovered = discover(job)

    fresh_candidates: list[str] = []
    reuse_candidates: list[str] = []
    seen: set[str] = set()
    for url in discovered + FALLBACK.get(cid, []):
        key = photo_key(url)
        if key in seen:
            continue
        seen.add(key)
        if key not in recent and key not in session:
            fresh_candidates.append(url)
        else:
            reuse_candidates.append(url)

    selected: list[str] = []
    selected_keys: set[str] = set()
    fresh_count = 0

    def consume(rows: list[str], mark_fresh: bool) -> None:
        nonlocal fresh_count
        for url in rows:
            if len(selected) >= 10:
                return
            key = photo_key(url)
            if key in selected_keys:
                continue
            try:
                direct_get_image(url)
            except Exception as exc:
                print(f"WARN rejecting image {url}: {exc}")
                continue
            selected.append(url)
            selected_keys.add(key)
            if mark_fresh:
                fresh_count += 1

    # Strong preference: new images not seen in recent history and not already
    # used by another content in this cycle.
    consume(fresh_candidates, True)

    # Reliability fallback: controlled reuse across different contents is allowed
    # only if necessary. Inside this content the ten frames remain all different.
    if len(selected) < 10:
        consume(reuse_candidates, False)

    if len(selected) < 10:
        raise RuntimeError(
            f"Visual source shortage for {job.get('id')}: only {len(selected)} unique usable Pixabay images found"
        )

    session.update(selected_keys)
    return selected[:10], fresh_count


def render_reel(job: dict[str, Any], c: dict[str, Any], urls: list[str], presenter_name: str | None) -> Path:
    out = ROOT / str(job["media"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="oss-fresh-") as td:
        t = Path(td)
        voice = rr.voice(job, t)
        music = rr.music(t / "music.wav")
        frames: list[Path] = []
        for i, url in enumerate(urls[:10]):
            p = t / f"f{i:02d}.jpg"
            rr.frame(c, url, 1080, 1920, "reel", who=presenter_name).save(
                p, "JPEG", quality=94, optimize=True
            )
            frames.append(p)
        rr.make_video(frames, voice, music, out, 60)
    return out


def render_carousel(job: dict[str, Any], c: dict[str, Any], urls: list[str]) -> list[Path]:
    slides = (list(job.get("slides") or []) + [""] * 10)[:10]
    media = list(job.get("media") or [])
    if len(media) != 10:
        raise RuntimeError(f"Carousel {job.get('id')} must have exactly 10 media paths")
    outs: list[Path] = []
    for title, rel, url in zip(slides, media, urls[:10]):
        out = ROOT / str(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        rr.frame(c, url, 1080, 1350, "carousel", title=title).save(
            out, "JPEG", quality=94, optimize=True
        )
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

    presenter_counts: dict[str, int] = {}
    rendered = 0
    for job in sorted(
        jobs,
        key=lambda j: (str(j.get("client_id")), int(j.get("cycle_position", 0))),
    ):
        cid = str(job.get("client_id") or "")
        brand_hist = history.setdefault("brands", {}).setdefault(cid, {"recent": []})
        recent_rows = list(brand_hist.get("recent", []))
        recent = {
            str(row.get("key") if isinstance(row, dict) else row)
            for row in recent_rows
        }

        urls, fresh_count = choose_urls(job, recent)
        job["visual_asset_urls"] = urls
        job["visual_source"] = "pixabay_dynamic_varied"
        job["visual_uniqueness"] = "10 unique source images inside this content"
        job["fresh_visual_count"] = fresh_count
        job["reused_visual_count"] = 10 - fresh_count

        client = rr.cfg(cid)
        if str(job.get("format") or "reel") == "carousel":
            render_carousel(job, client, urls)
        else:
            n = presenter_counts.get(cid, 0)
            presenter_name = (
                "joseph" if n % 2 == 0 else "francesca"
            ) if cid == "f1-immobiliare" else None
            presenter_counts[cid] = n + 1
            job["_presenter"] = presenter_name or ""
            render_reel(job, client, urls, presenter_name)

        rendered += 1
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for url in urls:
            recent_rows.append({
                "key": photo_key(url),
                "url": url,
                "used_at": stamp,
                "job_id": job.get("id"),
            })
        brand_hist["recent"] = recent_rows[-MAX_HISTORY_PER_BRAND:]

    queue["updated_by"] = "Resilient fresh Pixabay renderer"
    queue["visual_policy"] = (
        "10 different images per content; prefer unseen history; controlled cross-content reuse only on source shortage"
    )
    save(QUEUE, queue)
    history["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save(HISTORY, history)
    print(f"Rendered {rendered} current-cycle contents with varied Pixabay visuals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
