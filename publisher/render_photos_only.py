#!/usr/bin/env python3
"""Render the active cycle as STATIC PHOTOS ONLY.

Produces exactly one 1080x1350 JPG per job. No MP4, no audio, no voiceover.
Uses fresh Pixabay photography, preferring images not present in image_history.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

import render_fresh_visuals as fv

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
HISTORY = ROOT / "publisher" / "image_history.json"
SIZE = (1080, 1350)
MAX_HISTORY = 500


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def center_crop(image: Image.Image, size: tuple[int, int] = SIZE) -> Image.Image:
    image = image.convert("RGB")
    tw, th = size
    target_ratio = tw / th
    ratio = image.width / image.height
    if ratio > target_ratio:
        new_w = int(image.height * target_ratio)
        left = max(0, (image.width - new_w) // 2)
        image = image.crop((left, 0, left + new_w, image.height))
    else:
        new_h = int(image.width / target_ratio)
        top = max(0, (image.height - new_h) // 2)
        image = image.crop((0, top, image.width, top + new_h))
    return image.resize(size, Image.Resampling.LANCZOS)


def recent_keys(history: dict, cid: str) -> set[str]:
    rows = history.get("brands", {}).get(cid, {}).get("recent", [])
    return {str(row.get("key") or "") for row in rows if isinstance(row, dict) and row.get("key")}


def choose_one(job: dict, history: dict, session: set[str]) -> tuple[str, Image.Image, bool]:
    cid = str(job.get("client_id") or "")
    recent = recent_keys(history, cid)
    candidates = fv.discover(job, max_urls=100) + fv.fallback_for(job)
    seen: set[str] = set()
    reusable: list[str] = []

    for url in candidates:
        key = fv.photo_key(url)
        if key in seen:
            continue
        seen.add(key)
        if key in recent or key in session:
            reusable.append(url)
            continue
        try:
            return url, fv.direct_get_image(url), True
        except Exception as exc:
            print(f"WARN photo rejected {url}: {exc}")

    for url in reusable:
        key = fv.photo_key(url)
        if key in session:
            continue
        try:
            return url, fv.direct_get_image(url), False
        except Exception as exc:
            print(f"WARN reusable photo rejected {url}: {exc}")

    raise RuntimeError(f"No usable static photo found for {job.get('id')}")


def record(history: dict, cid: str, url: str, job_id: str) -> None:
    brands = history.setdefault("brands", {})
    brand = brands.setdefault(cid, {"recent": []})
    rows = list(brand.get("recent", []))
    key = fv.photo_key(url)
    rows = [r for r in rows if str(r.get("key") or "") != key]
    rows.append({
        "key": key,
        "url": url,
        "used_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "job_id": job_id,
        "output_type": "static-photo",
    })
    brand["recent"] = rows[-MAX_HISTORY:]


def main() -> int:
    q = load_json(QUEUE, {"jobs": []})
    cycle = q.get("current_cycle")
    jobs = [j for j in q.get("jobs", []) if j.get("cycle_key") == cycle]
    if len(jobs) != 6:
        raise RuntimeError(f"Expected 6 current-cycle jobs, got {len(jobs)}")
    if any(j.get("format") != "photo" for j in jobs):
        raise RuntimeError("PHOTO-ONLY renderer received a non-photo job")

    history = load_json(HISTORY, {"version": 1, "brands": {}})
    session: dict[str, set[str]] = {"f1-immobiliare": set(), "real-media-pro": set()}

    for job in jobs:
        cid = str(job.get("client_id") or "")
        url, source, fresh = choose_one(job, history, session.setdefault(cid, set()))
        key = fv.photo_key(url)
        session[cid].add(key)
        out = ROOT / str(job["media"])
        out.parent.mkdir(parents=True, exist_ok=True)
        center_crop(source).save(out, "JPEG", quality=94, optimize=True, progressive=True)
        if not out.exists() or out.stat().st_size < 20000:
            raise RuntimeError(f"Static photo was not rendered correctly: {out}")

        job["visual_asset_urls"] = [url]
        job["visual_source"] = "pixabay-fresh-static-photo"
        job["visual_count"] = 1
        job["fresh_visual_count"] = 1 if fresh else 0
        job["reused_visual_count"] = 0 if fresh else 1
        job["production_status"] = "PHOTO READY"
        job["publication_ready"] = True
        job["output_type"] = "static-photo"
        job["no_video"] = True
        job["no_audio"] = True
        record(history, cid, url, str(job.get("id") or ""))
        print(f"PHOTO READY {cid}: {out}")

    history["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    q["output_policy"] = "STATIC PHOTOS ONLY - JPG/PNG - NO REELS - NO MP4"
    q["updated_by"] = "Photo-only renderer"
    save_json(HISTORY, history)
    save_json(QUEUE, q)
    print("DONE: 6 static JPG photos rendered; zero reels/mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
