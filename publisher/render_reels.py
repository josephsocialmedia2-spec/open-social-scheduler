#!/usr/bin/env python3
"""Render premium photo Reels and carousels for queued social content."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"
CLIENT_DIR = ROOT / "publisher" / "clients"
PHOTO_CACHE = Path(os.getenv("SOCIAL_PHOTO_CACHE", str(ROOT / ".cache" / "f1-photos")))
SERIF_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
SANS_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
_BG_CACHE: dict[str, Image.Image] = {}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def client(client_id: str) -> dict[str, Any]:
    path = CLIENT_DIR / f"{client_id}.json"
    if not path.exists():
        raise RuntimeError(f"Unknown client: {client_id}")
    return load_json(path)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def fit_font(draw: ImageDraw.ImageDraw, lines: list[str], max_width: int, start: int, minimum: int) -> ImageFont.FreeTypeFont:
    size = start
    while size >= minimum:
        f = font(SERIF_FONT, size)
        if max((draw.textbbox((0, 0), line, font=f)[2] for line in lines), default=0) <= max_width:
            return f
        size -= 2
    return font(SERIF_FONT, minimum)


def fallback_photo() -> Image.Image:
    """Deterministic fallback so an upstream image host can never stop publishing."""
    w, h = 1600, 1100
    image = Image.new("RGB", (w, h), "#0C1714")
    draw = ImageDraw.Draw(image)
    for y in range(h):
        t = y / h
        r = int(28 - 18 * t)
        g = int(63 - 38 * t)
        b = int(60 - 35 * t)
        draw.line((0, y, w, y), fill=(r, g, b))
    draw.polygon([(0, 760), (300, 390), (520, 610), (760, 270), (1030, 625), (1270, 360), (1600, 730), (1600, 1100), (0, 1100)], fill="#182B25")
    draw.polygon([(0, 855), (350, 590), (650, 805), (945, 520), (1240, 790), (1600, 570), (1600, 1100), (0, 1100)], fill="#0E201A")
    return image


def download_background(source: dict[str, Any]) -> Image.Image:
    url = str(source.get("url") or "")
    if not url:
        return fallback_photo()
    if url in _BG_CACHE:
        return _BG_CACHE[url].copy()

    PHOTO_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = PHOTO_CACHE / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".jpg")
    if cache_path.exists() and cache_path.stat().st_size > 20_000:
        image = Image.open(cache_path).convert("RGB")
        _BG_CACHE[url] = image
        return image.copy()

    headers = {
        "User-Agent": "F1-Immobiliare-Open-Social-Scheduler/1.0 (https://f1immobiliare.com/)",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    last_error = ""
    for attempt in range(4):
        try:
            response = requests.get(url, timeout=90, headers=headers)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else 4 * (attempt + 1)
                time.sleep(min(wait, 20))
                last_error = "HTTP 429"
                continue
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
            image.save(cache_path, "JPEG", quality=88, optimize=True)
            _BG_CACHE[url] = image
            return image.copy()
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2 * (attempt + 1))

    print(f"WARN photo unavailable after retries: {url} ({last_error}); using branded fallback.", file=sys.stderr)
    image = fallback_photo()
    _BG_CACHE[url] = image
    return image.copy()


def compose_photo(image: Image.Image, width: int, height: int) -> Image.Image:
    """Keep the real landscape photo visible while filling a vertical social canvas."""
    blurred = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=18))
    blurred = ImageEnhance.Brightness(blurred).enhance(0.55)
    canvas = blurred.convert("RGBA")

    featured_h = int(height * 0.53)
    featured = ImageOps.contain(image, (width, featured_h), method=Image.Resampling.LANCZOS)
    x = (width - featured.width) // 2
    y = int(height * 0.12)
    canvas.alpha_composite(featured.convert("RGBA"), (x, y))

    shade = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for py in range(height):
        if py < int(height * 0.30):
            alpha = 18
        else:
            alpha = min(150, int(18 + 155 * ((py / height - 0.30) / 0.70)))
        sd.line((0, py, width, py), fill=(0, 10, 5, max(0, alpha)))
    canvas.alpha_composite(shade)
    return canvas.convert("RGB")


def draw_logo(image: Image.Image, cfg: dict[str, Any], top: int, width_px: int) -> None:
    brand = cfg.get("brand", {})
    vectors = brand.get("logo_vectors", {})
    draw = ImageDraw.Draw(image)
    panel_w = width_px
    panel_h = int(width_px * 0.57)
    x0 = (image.width - panel_w) // 2
    y0 = top
    draw.rounded_rectangle((x0, y0, x0 + panel_w, y0 + panel_h), radius=42, fill="#050806", outline=brand.get("gold", "#C8A15A"), width=2)

    green = brand.get("accent", "#92C205")
    white = brand.get("primary", "#F7F7F4")
    scale = panel_w * 0.74 / 500.0
    ox = x0 + int(panel_w * 0.13)
    oy = y0 + int(panel_h * 0.01)
    for polygon in vectors.get("green", []):
        draw.polygon([(ox + int(x * scale), oy + int(y * scale)) for x, y in polygon], fill=green)
    for polygon in vectors.get("white", []):
        draw.polygon([(ox + int(x * scale), oy + int(y * scale)) for x, y in polygon], fill=white)

    label = "IMMOBILIARE"
    label_font = font(SANS_FONT, max(24, int(panel_w * 0.048)))
    box = draw.textbbox((0, 0), label, font=label_font)
    draw.text(((image.width - (box[2] - box[0])) / 2, y0 + panel_h - int(panel_h * 0.18)), label, font=label_font, fill=white)


def draw_premium_slide(raw: str, cfg: dict[str, Any], source: dict[str, Any], width: int, height: int, slide_no: int, slide_count: int, content_format: str) -> Image.Image:
    brand = cfg.get("brand", {})
    primary = brand.get("primary", "#F7F7F4")
    green = brand.get("accent", "#92C205")
    gold = brand.get("gold", "#C8A15A")
    muted = brand.get("muted", "#C7CDC8")
    bg = compose_photo(download_background(source), width, height)
    draw = ImageDraw.Draw(bg)

    logo_w = int(width * (0.47 if content_format == "reel" else 0.37))
    draw_logo(bg, cfg, top=int(height * 0.025), width_px=logo_w)

    lines = [line.strip() for line in str(raw).split("|") if line.strip()]
    panel_margin = int(width * 0.07)
    panel_top = int(height * (0.49 if content_format == "reel" else 0.50))
    panel_bottom = int(height * 0.91)
    draw.rounded_rectangle((panel_margin, panel_top, width - panel_margin, panel_bottom), radius=46, fill="#07130E", outline=gold, width=2)

    title_font = fit_font(draw, lines, width - panel_margin * 2 - 100, 94 if content_format == "reel" else 78, 44)
    line_gap = 16
    heights = [draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1] for line in lines]
    total_h = sum(heights) + max(0, len(lines) - 1) * line_gap
    y = panel_top + max(42, int((panel_bottom - panel_top - total_h) * 0.34))
    for i, line in enumerate(lines):
        box = draw.textbbox((0, 0), line, font=title_font)
        color = primary
        if len(lines) > 1 and i == len(lines) - 1:
            color = green if slide_no == slide_count else gold
        draw.text(((width - (box[2] - box[0])) / 2, y), line, font=title_font, fill=color)
        y += heights[i] + line_gap

    small_font = font(SANS_FONT, 30 if content_format == "reel" else 24)
    draw.text((panel_margin + 36, panel_bottom - 60), f"{slide_no:02d} / {slide_count:02d}", font=small_font, fill=muted)
    campaign = str(cfg.get("campaign", {}).get("name") or "F1 IMMOBILIARE").upper()[:34]
    cb = draw.textbbox((0, 0), campaign, font=small_font)
    draw.text((width - panel_margin - 36 - (cb[2] - cb[0]), panel_bottom - 60), campaign, font=small_font, fill=green)

    credit = str(source.get("credit") or "")
    if credit:
        credit_font = font(SANS_FONT, 18 if content_format == "reel" else 15)
        draw.text((24, height - 30), credit, font=credit_font, fill="#E6E6E6")
    return bg


def background_sources(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    sources = cfg.get("brand", {}).get("photo_sources", [])
    return list(sources) if sources else [{"url": "", "credit": "F1 Immobiliare"}]


def media_ready(job: dict[str, Any]) -> bool:
    media = job.get("media")
    values = media if isinstance(media, list) else [media]
    values = [str(v) for v in values if v]
    return bool(values) and all((ROOT / v).exists() and (ROOT / v).stat().st_size > 10_000 for v in values)


def synthesize_voice(job: dict[str, Any], cfg: dict[str, Any], output: Path) -> Path | None:
    voice_cfg = cfg.get("brand", {}).get("voice", {})
    text = str(job.get("voiceover") or "").strip()
    if not voice_cfg.get("enabled", False) or not text:
        return None
    model = str(voice_cfg.get("model") or "it_IT-paola-medium")
    data_dir = Path(os.getenv("PIPER_DATA_DIR", str(ROOT / ".cache" / "piper")))
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "piper", "-m", model, "--data-dir", str(data_dir), "-f", str(output), "--", text]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if not output.exists() or output.stat().st_size < 1_000:
        raise RuntimeError("Piper did not generate a valid voiceover")
    return output


def audio_duration(path: Path | None) -> float:
    if not path or not shutil.which("ffprobe"):
        return 0.0
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], check=True, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def render_reel(job: dict[str, Any], cfg: dict[str, Any]) -> Path:
    reel = cfg.get("brand", {}).get("reel", {})
    width, height = int(reel.get("width", 1080)), int(reel.get("height", 1920))
    slides = list(job.get("slides") or [])
    output = ROOT / str(job["media"])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size > 10_000:
        return output
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to render reels")

    sources = background_sources(cfg)
    with tempfile.TemporaryDirectory(prefix="oss-premium-reel-") as tmp_raw:
        tmp = Path(tmp_raw)
        voice = synthesize_voice(job, cfg, tmp / "voice.wav")
        duration = audio_duration(voice)
        seconds = max(2.25, (duration + 1.2) / len(slides)) if duration > 0 else float(reel.get("seconds_per_slide", 2.8))
        day_seed = int(str(job.get("scheduled_at") or "0000-00-00")[8:10] or 0)
        frames: list[Path] = []
        for idx, raw in enumerate(slides, 1):
            source = sources[(idx - 1 + day_seed) % len(sources)]
            frame = tmp / f"slide_{idx:02d}.jpg"
            draw_premium_slide(raw, cfg, source, width, height, idx, len(slides), "reel").save(frame, "JPEG", quality=91, optimize=True)
            frames.append(frame)

        concat = tmp / "concat.txt"
        with concat.open("w", encoding="utf-8") as fh:
            for frame in frames:
                fh.write(f"file '{frame.as_posix()}'\n")
                fh.write(f"duration {seconds:.3f}\n")
            fh.write(f"file '{frames[-1].as_posix()}'\n")

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat)]
        if voice:
            cmd += ["-i", str(voice)]
        cmd += ["-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-profile:v", "high", "-level", "4.0", "-movflags", "+faststart", "-pix_fmt", "yuv420p"]
        if voice:
            cmd += ["-c:a", "aac", "-b:a", "160k", "-af", "apad", "-shortest"]
        cmd += [str(output)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return output


def render_carousel(job: dict[str, Any], cfg: dict[str, Any]) -> list[Path]:
    slides = list(job.get("slides") or [])
    media = list(job.get("media") or [])
    if not slides or len(media) != len(slides):
        raise RuntimeError(f"Carousel {job.get('id')} media/slide count mismatch")
    carousel = cfg.get("brand", {}).get("carousel", {})
    width, height = int(carousel.get("width", 1080)), int(carousel.get("height", 1350))
    sources = background_sources(cfg)
    day_seed = int(str(job.get("scheduled_at") or "0000-00-00")[8:10] or 0)
    outputs: list[Path] = []
    for idx, (raw, rel) in enumerate(zip(slides, media), 1):
        output = ROOT / str(rel)
        output.parent.mkdir(parents=True, exist_ok=True)
        if not (output.exists() and output.stat().st_size > 10_000):
            source = sources[(idx - 1 + day_seed) % len(sources)]
            draw_premium_slide(raw, cfg, source, width, height, idx, len(slides), "carousel").save(output, "JPEG", quality=91, optimize=True)
        outputs.append(output)
    return outputs


def main() -> int:
    if not QUEUE_PATH.exists():
        print("Queue missing; nothing to render.")
        return 0
    queue = load_json(QUEUE_PATH)
    rendered = 0
    for job in queue.get("jobs", []):
        if not job.get("enabled", True) or job.get("status") in {"scheduled", "published", "disabled"}:
            continue
        if not job.get("client_id") or not job.get("slides") or not job.get("media") or media_ready(job):
            continue
        cfg = client(str(job["client_id"]))
        if str(job.get("format") or "reel") == "carousel":
            outputs = render_carousel(job, cfg)
            print(f"Rendered {job['id']} -> {len(outputs)} carousel slide(s)")
        else:
            output = render_reel(job, cfg)
            print(f"Rendered {job['id']} -> {output.relative_to(ROOT)}")
        rendered += 1
    print(f"Rendered {rendered} social asset set(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
