#!/usr/bin/env python3
"""Prepare the active 4-post cycle from USER-UPLOADED STATIC PHOTOS ONLY.

Each job reads only its assigned ``manual_folder``. The engine does not invent or
download a replacement image for automatic publication. If a folder is empty, the
job stays ``awaiting_manual_image`` and nothing is posted.

Output: one 1080x1350 JPG per ready job. No MP4, no audio, no voiceover.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
HISTORY = ROOT / "publisher" / "image_history.json"
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


def source_key(path: Path) -> str:
    return "manual://" + path.relative_to(ROOT).as_posix()


def recent_keys(history: dict, cid: str) -> set[str]:
    rows = history.get("brands", {}).get(cid, {}).get("recent", [])
    return {
        str(row.get("key") or "")
        for row in rows
        if isinstance(row, dict) and row.get("key")
    }


def assigned_candidates(job: dict) -> list[Path]:
    rel = str(job.get("manual_folder") or "").strip()
    if not rel:
        return []
    folder = ROOT / rel
    if not folder.exists() or not folder.is_dir():
        return []
    return [
        path
        for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold())
        if path.is_file() and path.suffix.lower() in ALLOWED
    ]


def open_manual(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.width < 500 or image.height < 500:
        raise RuntimeError(f"manual image too small: {path} = {image.size}")
    return image


def choose_manual(job: dict, history: dict, session: set[str]) -> tuple[Path, Image.Image, bool] | None:
    cid = str(job.get("client_id") or "")
    recent = recent_keys(history, cid)
    candidates = assigned_candidates(job)
    reusable: list[Path] = []

    for path in candidates:
        key = source_key(path)
        if key in session:
            continue
        if key in recent:
            reusable.append(path)
            continue
        try:
            return path, open_manual(path), True
        except Exception as exc:
            print(f"WARN manual photo rejected {path}: {exc}")

    for path in reusable:
        key = source_key(path)
        if key in session:
            continue
        try:
            return path, open_manual(path), False
        except Exception as exc:
            print(f"WARN reusable manual photo rejected {path}: {exc}")
    return None


def record(history: dict, cid: str, path: Path, job_id: str) -> None:
    brands = history.setdefault("brands", {})
    brand = brands.setdefault(cid, {"recent": []})
    rows = list(brand.get("recent", []))
    key = source_key(path)
    rows = [r for r in rows if str(r.get("key") or "") != key]
    rows.append({
        "key": key,
        "url": key,
        "used_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "job_id": job_id,
        "output_type": "static-photo",
        "source_type": "manual-upload",
    })
    brand["recent"] = rows[-MAX_HISTORY:]


def main() -> int:
    q = load_json(QUEUE, {"jobs": []})
    cycle = q.get("current_cycle")
    jobs = [j for j in q.get("jobs", []) if j.get("cycle_key") == cycle]
    if len(jobs) != 4:
        raise RuntimeError(f"Expected 4 current-cycle jobs, got {len(jobs)}")
    if any(j.get("format") != "photo" for j in jobs):
        raise RuntimeError("PHOTO-ONLY renderer received a non-photo job")

    history = load_json(HISTORY, {"version": 1, "brands": {}})
    session: dict[str, set[str]] = {"f1-immobiliare": set(), "real-media-pro": set()}
    ready = 0
    waiting = 0

    for job in jobs:
        cid = str(job.get("client_id") or "")
        selected = choose_manual(job, history, session.setdefault(cid, set()))
        out = ROOT / str(job["media"])

        if selected is None:
            if out.exists():
                out.unlink()
            job["visual_asset_urls"] = []
            job["visual_source"] = "manual-folder-empty"
            job["visual_count"] = 0
            job["fresh_visual_count"] = 0
            job["reused_visual_count"] = 0
            job["production_status"] = "WAITING FOR USER PHOTO"
            job["publication_ready"] = False
            job["auto_publish_ready"] = False
            job["status"] = "awaiting_manual_image"
            job["blocked_reason"] = f"nessuna immagine caricata in {job.get('manual_folder')}"
            waiting += 1
            print(f"WAITING {job.get('id')}: {job.get('manual_folder')}")
            continue

        path, source, fresh = selected
        key = source_key(path)
        session[cid].add(key)
        out.parent.mkdir(parents=True, exist_ok=True)
        center_crop(source).save(out, "JPEG", quality=94, optimize=True, progressive=True)
        if not out.exists() or out.stat().st_size < 20000:
            raise RuntimeError(f"Static photo was not rendered correctly: {out}")

        job["visual_asset_urls"] = [key]
        job["visual_source"] = "manual-upload"
        job["visual_count"] = 1
        job["fresh_visual_count"] = 1 if fresh else 0
        job["reused_visual_count"] = 0 if fresh else 1
        job["production_status"] = "PHOTO READY - AUTO PUBLISH"
        job["publication_ready"] = True
        job["auto_publish_ready"] = True
        job["output_type"] = "static-photo"
        job["no_video"] = True
        job["no_audio"] = True
        job["status"] = "ready"
        job.pop("blocked_reason", None)
        record(history, cid, path, str(job.get("id") or ""))
        ready += 1
        print(f"READY {cid}: {out} <- {key}")

    history["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    q["output_policy"] = "4 USER-UPLOADED PHOTOS ONLY - AUTOMATIC SOCIAL PUBLISHING"
    q["manual_upload_folders"] = {
        "f1-main": "publisher/manual_images/f1-immobiliare/",
        "f1-recruiting": "publisher/manual_images/f1-immobiliare/RIC LAVORO F1/",
        "rmp-main": "publisher/manual_images/real-media-pro/",
        "rmp-recruiting": "publisher/manual_images/real-media-pro/RIC LAVORO RMP/",
    }
    q["auto_publish_policy"] = {
        "manual_images_only": True,
        "ready_jobs": ready,
        "waiting_jobs": waiting,
        "platforms": ["facebook", "instagram", "linkedin", "pinterest"],
        "excluded_photo_platforms": ["tiktok", "youtube"],
    }
    q["updated_by"] = "Manual-folder photo renderer + automatic publisher gate"
    save_json(HISTORY, history)
    save_json(QUEUE, q)
    print(f"DONE: {ready} ready for automatic publication; {waiting} waiting for user images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
