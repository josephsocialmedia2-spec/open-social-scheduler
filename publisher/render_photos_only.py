#!/usr/bin/env python3
"""Render the active cycle as STATIC PHOTOS ONLY.

Produces exactly one 1080x1350 JPG per job. No MP4, no audio, no voiceover.
Priority order:
1) photos manually uploaded to publisher/manual_images/<brand>/;
2) fresh Pixabay photography;
3) reusable Pixabay fallback.
Manual photos are tracked in image_history.json so the engine avoids repeating them
inside the same cycle and prefers unused uploads first.
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
MANUAL_ROOT = ROOT / "publisher" / "manual_images"
SIZE = (1080, 1350)
MAX_HISTORY = 500
ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}


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


def source_key(source: str) -> str:
    return source if source.startswith("manual://") else fv.photo_key(source)


def recent_keys(history: dict, cid: str) -> set[str]:
    rows = history.get("brands", {}).get(cid, {}).get("recent", [])
    return {str(row.get("key") or "") for row in rows if isinstance(row, dict) and row.get("key")}


def manual_candidates(cid: str) -> list[tuple[str, Path]]:
    folder = MANUAL_ROOT / cid
    if not folder.exists():
        return []
    rows: list[tuple[str, Path]] = []
    for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED:
            continue
        rel = path.relative_to(ROOT).as_posix()
        rows.append((f"manual://{rel}", path))
    return rows


def open_manual(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.width < 500 or image.height < 500:
        raise RuntimeError(f"manual image too small: {path} = {image.size}")
    return image


def choose_one(job: dict, history: dict, session: set[str]) -> tuple[str, Image.Image, bool, str]:
    cid = str(job.get("client_id") or "")
    recent = recent_keys(history, cid)

    # 1) USER UPLOADS: always preferred over internet discovery.
    manual = manual_candidates(cid)
    manual_reuse: list[tuple[str, Path]] = []
    for source, path in manual:
        key = source_key(source)
        if key in session:
            continue
        if key in recent:
            manual_reuse.append((source, path))
            continue
        try:
            return source, open_manual(path), True, "manual-upload"
        except Exception as exc:
            print(f"WARN manual photo rejected {path}: {exc}")

    # If all user photos were already used historically, keep prioritizing them
    # before going back to Pixabay, but never duplicate one inside the same cycle.
    for source, path in manual_reuse:
        key = source_key(source)
        if key in session:
            continue
        try:
            return source, open_manual(path), False, "manual-upload"
        except Exception as exc:
            print(f"WARN reusable manual photo rejected {path}: {exc}")

    # 2) PIXABAY / DISCOVERY FALLBACK.
    candidates = fv.discover(job, max_urls=100) + fv.fallback_for(job)
    seen: set[str] = set()
    reusable: list[str] = []

    for url in candidates:
        key = source_key(url)
        if key in seen:
            continue
        seen.add(key)
        if key in recent or key in session:
            reusable.append(url)
            continue
        try:
            return url, fv.direct_get_image(url), True, "pixabay-fresh-static-photo"
        except Exception as exc:
            print(f"WARN photo rejected {url}: {exc}")

    for url in reusable:
        key = source_key(url)
        if key in session:
            continue
        try:
            return url, fv.direct_get_image(url), False, "pixabay-reused-static-photo"
        except Exception as exc:
            print(f"WARN reusable photo rejected {url}: {exc}")

    raise RuntimeError(f"No usable static photo found for {job.get('id')}")


def record(history: dict, cid: str, source: str, job_id: str, source_type: str) -> None:
    brands = history.setdefault("brands", {})
    brand = brands.setdefault(cid, {"recent": []})
    rows = list(brand.get("recent", []))
    key = source_key(source)
    rows = [r for r in rows if str(r.get("key") or "") != key]
    rows.append({
        "key": key,
        "url": source,
        "used_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "job_id": job_id,
        "output_type": "static-photo",
        "source_type": source_type,
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
        source_id, source, fresh, source_type = choose_one(job, history, session.setdefault(cid, set()))
        key = source_key(source_id)
        session[cid].add(key)
        out = ROOT / str(job["media"])
        out.parent.mkdir(parents=True, exist_ok=True)
        center_crop(source).save(out, "JPEG", quality=94, optimize=True, progressive=True)
        if not out.exists() or out.stat().st_size < 20000:
            raise RuntimeError(f"Static photo was not rendered correctly: {out}")

        job["visual_asset_urls"] = [source_id]
        job["visual_source"] = source_type
        job["visual_count"] = 1
        job["fresh_visual_count"] = 1 if fresh else 0
        job["reused_visual_count"] = 0 if fresh else 1
        job["production_status"] = "PHOTO READY"
        job["publication_ready"] = True
        job["output_type"] = "static-photo"
        job["no_video"] = True
        job["no_audio"] = True
        record(history, cid, source_id, str(job.get("id") or ""), source_type)
        print(f"PHOTO READY {cid}: {out} <- {source_type}: {source_id}")

    history["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    q["output_policy"] = "STATIC PHOTOS ONLY - USER UPLOADS FIRST - JPG/PNG - NO REELS - NO MP4"
    q["manual_upload_folders"] = {
        "f1-immobiliare": "publisher/manual_images/f1-immobiliare/",
        "real-media-pro": "publisher/manual_images/real-media-pro/",
    }
    q["updated_by"] = "Photo-only renderer with manual image priority"
    save_json(HISTORY, history)
    save_json(QUEUE, q)
    print("DONE: 6 static JPG photos rendered; user uploads have priority; zero reels/mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
