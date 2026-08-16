#!/usr/bin/env python3
"""Render queued carousel-style content as 1080x1920 MP4 reels."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"
CLIENT_DIR = ROOT / "publisher" / "clients"
TITLE_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
BODY_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def client(client_id: str) -> dict[str, Any]:
    path = CLIENT_DIR / f"{client_id}.json"
    if not path.exists():
        raise RuntimeError(f"Unknown client: {client_id}")
    return load_json(path)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.exists():
        raise RuntimeError(f"Font not found: {path}")
    return ImageFont.truetype(str(path), size)


def fit_font(draw: ImageDraw.ImageDraw, lines: list[str], max_width: int, start: int = 92, minimum: int = 42) -> ImageFont.FreeTypeFont:
    size = start
    while size >= minimum:
        f = font(TITLE_FONT, size)
        widest = max((draw.textbbox((0, 0), line, font=f)[2] for line in lines), default=0)
        if widest <= max_width:
            return f
        size -= 2
    return font(TITLE_FONT, minimum)


def draw_centered_lines(draw: ImageDraw.ImageDraw, lines: list[str], y: int, f: ImageFont.FreeTypeFont, color: str, width: int, gap: int = 18) -> int:
    for line in lines:
        box = draw.textbbox((0, 0), line, font=f)
        w = box[2] - box[0]
        h = box[3] - box[1]
        draw.text(((width - w) / 2, y), line, font=f, fill=color)
        y += h + gap
    return y


def render_job(job: dict[str, Any], cfg: dict[str, Any]) -> Path:
    brand = cfg["brand"]
    reel = brand.get("reel", {})
    width = int(reel.get("width", 1080))
    height = int(reel.get("height", 1920))
    seconds = float(reel.get("seconds_per_slide", 2.8))
    slides = list(job.get("slides") or [])
    if not slides:
        raise RuntimeError(f"Job {job.get('id')} has no slides")

    output = ROOT / str(job["media"])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size > 10_000:
        return output
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to render reels")

    bg = brand.get("background", "#070907")
    bg_alt = brand.get("background_alt", bg)
    primary = brand.get("primary", "#F5F4EF")
    accent = brand.get("accent", "#39F28A")
    muted = brand.get("muted", "#AEB7B0")
    client_name = cfg.get("name", job.get("client_name", ""))

    with tempfile.TemporaryDirectory(prefix="oss-reel-") as tmp_raw:
        tmp = Path(tmp_raw)
        concat = tmp / "concat.txt"
        frames: list[Path] = []
        for idx, raw in enumerate(slides, 1):
            image = Image.new("RGB", (width, height), bg if idx % 2 else bg_alt)
            draw = ImageDraw.Draw(image)
            label_font = font(TITLE_FONT, 31)
            body_font = font(BODY_FONT, 36)

            # Brand label
            label_box = draw.textbbox((0, 0), client_name.upper(), font=label_font)
            label_w = label_box[2] - label_box[0]
            draw.rounded_rectangle((70, 70, 70 + label_w + 50, 136), radius=30, fill=accent)
            draw.text((95, 84), client_name.upper(), font=label_font, fill=bg)

            # Progress
            segment_w = (width - 140 - (len(slides) - 1) * 16) / len(slides)
            for p in range(len(slides)):
                x1 = 70 + p * (segment_w + 16)
                draw.rounded_rectangle((x1, 170, x1 + segment_w, 180), radius=5, fill=accent if p < idx else "#263128")

            lines = [line.strip() for line in str(raw).split("|") if line.strip()]
            title_font = fit_font(draw, lines, width - 160)
            start_y = 500 if len(lines) <= 3 else 420
            end_y = draw_centered_lines(draw, lines, start_y, title_font, accent if idx in (1, len(slides)) else primary, width)

            if idx == len(slides):
                cta = cfg.get("campaign", {}).get("cta", "")
                if cta:
                    cta_lines = [cta]
                    draw_centered_lines(draw, cta_lines, min(end_y + 110, 1320), body_font, primary, width, gap=12)

            draw.rounded_rectangle((70, height - 300, width - 70, height - 292), radius=4, fill=accent)
            count = f"{idx:02d} / {len(slides):02d}"
            draw.text((70, height - 245), count, font=font(TITLE_FONT, 30), fill=muted)
            campaign = cfg.get("campaign", {}).get("name", "")
            if campaign:
                campaign_short = campaign.upper()[:38]
                box = draw.textbbox((0, 0), campaign_short, font=font(TITLE_FONT, 27))
                draw.text((width - 70 - (box[2] - box[0]), height - 245), campaign_short, font=font(TITLE_FONT, 27), fill=accent)

            frame = tmp / f"slide_{idx:02d}.png"
            image.save(frame)
            frames.append(frame)

        with concat.open("w", encoding="utf-8") as fh:
            for frame in frames:
                fh.write(f"file '{frame.as_posix()}'\n")
                fh.write(f"duration {seconds}\n")
            fh.write(f"file '{frames[-1].as_posix()}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-profile:v", "high",
            "-level", "4.0", "-movflags", "+faststart", "-pix_fmt", "yuv420p", str(output),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if output.stat().st_size <= 10_000:
        raise RuntimeError(f"Rendered file is unexpectedly small: {output}")
    return output


def main() -> int:
    if not QUEUE_PATH.exists():
        print("Queue missing; nothing to render.")
        return 0
    queue = load_json(QUEUE_PATH)
    rendered = 0
    for job in queue.get("jobs", []):
        if not job.get("enabled", True):
            continue
        if job.get("status") in {"scheduled", "published", "disabled"}:
            continue
        if not job.get("client_id") or not job.get("slides") or not job.get("media"):
            continue
        path = ROOT / str(job["media"])
        if path.exists() and path.stat().st_size > 10_000:
            continue
        out = render_job(job, client(str(job["client_id"])))
        print(f"Rendered {job['id']} -> {out.relative_to(ROOT)}")
        rendered += 1
    print(f"Rendered {rendered} reel(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
