#!/usr/bin/env python3
"""Render the active 4-hour cycle with varied Pixabay photography.

Policy:
- every content uses 10 different source images;
- prefer images never used recently for that brand;
- F1 Reel 1 is driven by the query "case in Valle di Susa";
- F1 Reel 2 is dedicated to recruiting;
- F1 priority Reels change image exactly every 2 seconds: 10 images = 20 seconds;
- never go back to a fixed 10-image rotation;
- persist exact URLs and freshness statistics in GitHub memory.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont
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

F1_FALLBACK = [
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
]

OFFICE_FALLBACK = [
    "https://cdn.pixabay.com/photo/2017/06/26/12/57/laptop-2443749_1280.jpg",
    "https://cdn.pixabay.com/photo/2018/02/08/10/22/desk-3139127_1280.jpg",
    "https://cdn.pixabay.com/photo/2023/10/10/05/53/laptop-8305452_1280.jpg",
    "https://cdn.pixabay.com/photo/2015/01/08/18/25/desk-593327_1280.jpg",
    "https://cdn.pixabay.com/photo/2021/04/22/17/55/meeting-6200632_1280.jpg",
    "https://cdn.pixabay.com/photo/2017/08/02/01/01/people-2568603_1280.jpg",
    "https://cdn.pixabay.com/photo/2016/11/29/09/38/adult-1868750_1280.jpg",
    "https://cdn.pixabay.com/photo/2015/05/31/10/55/man-791049_1280.jpg",
    "https://cdn.pixabay.com/photo/2017/08/01/01/33/people-2562102_1280.jpg",
    "https://cdn.pixabay.com/photo/2016/03/09/09/17/meeting-1245776_1280.jpg",
]

RMP_FALLBACK = [
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
]


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


def _with_pixabay(query: str) -> str:
    q = str(query or "").strip()
    if not q:
        return ""
    return q if "pixabay" in q.lower() else f"{q} pixabay"


def search_queries(job: dict[str, Any]) -> list[str]:
    cid = str(job.get("client_id") or "")
    mode = str(job.get("visual_mode") or "")
    title = re.sub(r"[^A-Za-zÀ-ÿ0-9 ]+", " ", str(job.get("title") or "")).strip()
    territory = re.sub(r"[^A-Za-zÀ-ÿ0-9 ]+", " ", str(job.get("territory") or "")).strip()
    visuals = [str(x).strip() for x in job.get("visuals", []) if str(x).strip()]
    explicit = [str(x).strip() for x in job.get("search_queries", []) if str(x).strip()]
    override = str(job.get("search_query_override") or "").strip()

    queries: list[str] = []
    if override:
        queries.append(_with_pixabay(override))
    queries.extend(_with_pixabay(x) for x in explicit)

    if mode == "valle-di-susa-homes":
        queries.extend([
            "case in Valle di Susa pixabay",
            "casa montagna Piemonte pixabay",
            "villa alpina Piemonte pixabay",
            "casa pietra montagna Italia pixabay",
            "casa con giardino montagne Italia pixabay",
            "borgo alpino case pietra pixabay",
            "appartamento balcone montagne pixabay",
            "villa moderna montagne pixabay",
        ])
    elif mode == "f1-recruiting":
        queries.extend([
            "real estate agent office team pixabay",
            "real estate professional client meeting pixabay",
            "property consultant office pixabay",
            "business team training office pixabay",
            "real estate agent showing house pixabay",
            "professional team meeting client pixabay",
        ])
    elif cid == "f1-immobiliare":
        queries.extend([
            "modern house exterior residential architecture pixabay",
            "apartment living room bright interior pixabay",
            "modern kitchen residential interior pixabay",
            "villa garden residential exterior pixabay",
            "balcony terrace apartment home pixabay",
        ])
    else:
        queries.extend([
            "entrepreneur laptop modern office pixabay",
            "ecommerce online shop laptop smartphone pixabay",
            "digital marketing analytics workspace pixabay",
            "website design laptop business pixabay",
            "business team digital office pixabay",
        ])

    if title:
        queries.append(_with_pixabay(title))
    if territory and cid == "f1-immobiliare" and mode != "f1-recruiting":
        queries.append(_with_pixabay(f"residential home architecture {territory}"))
    queries.extend(_with_pixabay(x) for x in visuals)

    out: list[str] = []
    seen: set[str] = set()
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            out.append(q)
            seen.add(key)
    return out[:20]


def discover(job: dict[str, Any], max_urls: int = 120) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for query in search_queries(job):
        rows: list[dict[str, Any]] = []
        for attempt in range(2):
            try:
                with DDGS() as ddgs:
                    rows = list(ddgs.images(query, max_results=80) or [])
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


def fallback_for(job: dict[str, Any]) -> list[str]:
    cid = str(job.get("client_id") or "")
    mode = str(job.get("visual_mode") or "")
    if cid == "f1-immobiliare" and mode == "f1-recruiting":
        return OFFICE_FALLBACK
    if cid == "f1-immobiliare":
        return F1_FALLBACK
    return RMP_FALLBACK


def choose_urls(job: dict[str, Any], recent: set[str]) -> tuple[list[str], int]:
    cid = str(job.get("client_id") or "")
    session = SESSION_USED.setdefault(cid, set())
    discovered = discover(job)

    fresh_candidates: list[str] = []
    reuse_candidates: list[str] = []
    seen: set[str] = set()
    for url in discovered + fallback_for(job):
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

    consume(fresh_candidates, True)
    if len(selected) < 10:
        consume(reuse_candidates, False)

    if len(selected) < 10:
        raise RuntimeError(
            f"Visual source shortage for {job.get('id')}: only {len(selected)} unique usable Pixabay images found"
        )

    session.update(selected_keys)
    return selected[:10], fresh_count


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, minimum: int = 18) -> ImageFont.FreeTypeFont:
    size = start
    while size > minimum:
        font = ImageFont.truetype(str(rr.BOLD), size)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(str(rr.BOLD), minimum)


def apply_job_overrides(image: Image.Image, job: dict[str, Any], client: dict[str, Any]) -> Image.Image:
    if str(client.get("id") or "") != "f1-immobiliare":
        return image

    mode = str(job.get("visual_mode") or "")
    header_text = str(job.get("fixed_header_text") or "").strip()
    contact_text = str(job.get("fixed_contact_text") or "").strip()
    if mode != "f1-recruiting" and not contact_text:
        return image

    draw = ImageDraw.Draw(image, "RGBA")
    accent = client.get("brand", {}).get("accent", "#92C205")

    if mode == "f1-recruiting" and header_text:
        x1, y1, x2, y2 = 105, 270, image.width - 105, 345
        draw.rounded_rectangle((x1, y1, x2, y2), radius=22, fill=(255, 255, 255, 244))
        font = _fit_font(draw, header_text, x2 - x1 - 36, 34, 22)
        box = draw.textbbox((0, 0), header_text, font=font)
        draw.text(((image.width - (box[2] - box[0])) / 2, y1 + (y2 - y1 - (box[3] - box[1])) / 2 - 2), header_text, font=font, fill=accent)

    if contact_text:
        h = 104
        y = image.height - h - 24
        w = int(image.width * .88)
        x = (image.width - w) // 2
        draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=(255, 255, 255, 244), outline=accent, width=4)
        font = _fit_font(draw, contact_text, w - 55, 37, 20)
        box = draw.textbbox((0, 0), contact_text, font=font)
        draw.text(((image.width - (box[2] - box[0])) / 2, y + (h - (box[3] - box[1])) / 2 - 4), contact_text, font=font, fill="#0A0B0A")
    return image


def make_video_exact_change(frames: list[Path], voice: Path | None, music: Path, out: Path, seconds_per_image: float) -> None:
    """Hard cut to the next image at an exact interval, preserving audio mix."""
    n = len(frames)
    if n <= 0:
        raise RuntimeError("No frames supplied")
    target = n * seconds_per_image
    cmd = ["ffmpeg", "-y"]
    for path in frames:
        cmd += ["-loop", "1", "-t", f"{seconds_per_image:.3f}", "-i", str(path)]
    voice_index = None
    if voice:
        voice_index = n
        cmd += ["-i", str(voice)]
    music_index = n + (1 if voice else 0)
    cmd += ["-i", str(music)]

    filters: list[str] = []
    labels: list[str] = []
    for i in range(n):
        label = f"v{i}"
        labels.append(f"[{label}]")
        filters.append(
            f"[{i}:v]scale=1188:2112:force_original_aspect_ratio=increase,"
            f"crop=1188:2112,scale=1080:1920,fps=30,trim=duration={seconds_per_image:.3f},"
            f"setpts=PTS-STARTPTS,format=yuv420p[{label}]"
        )
    filters.append("".join(labels) + f"concat=n={n}:v=1:a=0[vout]")

    if voice_index is not None:
        filters.extend([
            f"[{voice_index}:a]volume=1.0,apad[voice]",
            f"[{music_index}:a]volume=0.055,apad[music]",
            "[voice][music]amix=inputs=2:duration=first:dropout_transition=1[aout]",
        ])
    else:
        filters.append(f"[{music_index}:a]volume=0.07,apad[aout]")

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-crf", "20",
        "-preset", "veryfast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-t", f"{target:.3f}",
        str(out),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def render_reel(job: dict[str, Any], client: dict[str, Any], urls: list[str], presenter_name: str | None) -> Path:
    out = ROOT / str(job["media"])
    out.parent.mkdir(parents=True, exist_ok=True)
    seconds_per_image = float(job.get("image_change_seconds") or 0)
    duration = float(job.get("reel_duration_seconds") or 60)

    with tempfile.TemporaryDirectory(prefix="oss-fresh-") as td:
        temp = Path(td)
        voice = rr.voice(job, temp)
        music = rr.music(temp / "music.wav", seconds=max(duration, 20))
        frames: list[Path] = []
        show_presenter = bool(job.get("show_presenter", True))
        who = presenter_name if show_presenter else None

        for i, url in enumerate(urls[:10]):
            path = temp / f"f{i:02d}.jpg"
            frame = rr.frame(client, url, 1080, 1920, "reel", who=who)
            frame = apply_job_overrides(frame, job, client)
            frame.save(path, "JPEG", quality=94, optimize=True)
            frames.append(path)

        if seconds_per_image > 0:
            make_video_exact_change(frames, voice, music, out, seconds_per_image)
        else:
            rr.make_video(frames, voice, music, out, duration)
    return out


def render_carousel(job: dict[str, Any], client: dict[str, Any], urls: list[str]) -> list[Path]:
    slides = (list(job.get("slides") or []) + [""] * 10)[:10]
    media = list(job.get("media") or [])
    if len(media) != 10:
        raise RuntimeError(f"Carousel {job.get('id')} must have exactly 10 media paths")
    outs: list[Path] = []
    for title, rel, url in zip(slides, media, urls[:10]):
        out = ROOT / str(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        rr.frame(client, url, 1080, 1350, "carousel", title=title).save(
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
    for job in sorted(jobs, key=lambda j: (str(j.get("client_id")), int(j.get("cycle_position", 0)))):
        cid = str(job.get("client_id") or "")
        brand_hist = history.setdefault("brands", {}).setdefault(cid, {"recent": []})
        recent_rows = list(brand_hist.get("recent", []))
        recent = {str(row.get("key") if isinstance(row, dict) else row) for row in recent_rows}

        urls, fresh_count = choose_urls(job, recent)
        job["visual_asset_urls"] = urls
        job["visual_source"] = "pixabay_dynamic_query_varied"
        job["visual_uniqueness"] = "10 unique source images inside this content"
        job["fresh_visual_count"] = fresh_count
        job["reused_visual_count"] = 10 - fresh_count

        client = rr.cfg(cid)
        if str(job.get("format") or "reel") == "carousel":
            render_carousel(job, client, urls)
        else:
            n = presenter_counts.get(cid, 0)
            presenter_name = ("joseph" if n % 2 == 0 else "francesca") if cid == "f1-immobiliare" else None
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

    queue["updated_by"] = "F1 2-second Reel + resilient Pixabay renderer"
    queue["visual_policy"] = (
        "10 different images per content; F1 priority reels change image every 2 seconds; prefer unseen history"
    )
    save(QUEUE, queue)
    history["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save(HISTORY, history)
    print(f"Rendered {rendered} current-cycle contents; F1 priority reels use exact 2-second image changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
