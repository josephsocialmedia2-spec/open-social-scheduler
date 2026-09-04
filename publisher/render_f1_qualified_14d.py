#!/usr/bin/env python3
"""Render F1 Qualified Seller 14-Day assets.

Reels: real MP4/H.264 1080x1920, 28 seconds, 7 message frames, readable muted,
with all essential copy above the bottom 35% safe area. Voiceover is attempted
with Edge TTS/Piper but the Reel remains fully understandable without sound.
Carousels: 1080x1350 JPGs, one distinct information unit per slide.
"""
from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import textwrap
import wave
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "qualified_14d_queue.json"
CLIENT = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
MANUAL = ROOT / "publisher" / "manual_images" / "f1-immobiliare" / "RIC LAVORO F1"
ASSETS = ROOT / "publisher" / "assets"
BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
REG = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
GREEN = "#92C205"
DARK = "#070907"
WHITE = "#F7F7F4"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ff(path: Path, size: int):
    return ImageFont.truetype(str(path), size)


def local_images() -> list[Path]:
    rows: list[Path] = []
    if MANUAL.exists():
        for p in sorted(MANUAL.iterdir()):
            if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            low = p.name.lower()
            if "certificato" in low or "readme" in low:
                continue
            if any(x in low for x in ("image-gen", "cortile", "chatgpt image")):
                rows.append(p)
    # Presenters are a stable last-resort source if the manual property bank is absent.
    if not rows:
        for name in ("joseph_presenter.jpg.b64", "francesca_presenter.jpg.b64"):
            if (ASSETS / name).exists():
                rows.append(ASSETS / name)
    return rows


def fallback_canvas(w: int, h: int, seed: int) -> Image.Image:
    im = Image.new("RGB", (w, h), DARK)
    d = ImageDraw.Draw(im)
    for y in range(h):
        k = y / max(1, h - 1)
        g = int(9 + 18 * (1 - k))
        d.line((0, y, w, y), fill=(5, g, 7))
    # simple architectural blocks; this is a fallback background, not a fake property listing.
    d.rectangle((int(w*.08), int(h*.42), int(w*.92), int(h*.78)), fill=(20, 30, 22))
    d.polygon([(int(w*.05), int(h*.43)), (int(w*.50), int(h*.25)), (int(w*.95), int(h*.43))], fill=(30, 43, 31))
    for x in (0.20, 0.43, 0.66):
        d.rectangle((int(w*x), int(h*.53), int(w*(x+.12)), int(h*.67)), fill=(50, 68, 52))
    return im


def image_from_source(path: Path, w: int, h: int, seed: int) -> Image.Image:
    try:
        if path.suffix.lower() == ".b64":
            raw = base64.b64decode(path.read_text(encoding="utf-8").strip())
            src = Image.open(BytesIO(raw)).convert("RGB")
        else:
            src = Image.open(path).convert("RGB")
        src = ImageEnhance.Contrast(src).enhance(1.04)
        return ImageOps.fit(src, (w, h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    except Exception:
        return fallback_canvas(w, h, seed)


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int = 4) -> list[str]:
    words = str(text).replace("|", " ").split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = (cur + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
            if len(lines) >= max_lines - 1:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def branded_background(path: Path, w: int, h: int, seed: int) -> Image.Image:
    im = image_from_source(path, w, h, seed)
    over = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    od.rectangle((0, 0, w, h), fill=(0, 0, 0, 80))
    od.rectangle((0, 0, w, int(h*.18)), fill=(0, 0, 0, 85))
    od.rectangle((0, int(h*.65), w, h), fill=(0, 0, 0, 38))
    base = im.convert("RGBA")
    base.alpha_composite(over)
    return base.convert("RGB")


def brand_header(im: Image.Image, compact: bool = False) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    size = 34 if compact else 42
    f = ff(BOLD, size)
    text = "F1 IMMOBILIARE"
    box = d.textbbox((0, 0), text, font=f)
    tw = box[2] - box[0]
    x = (im.width - tw) // 2
    y = 58 if compact else 82
    d.rounded_rectangle((x-24, y-15, x+tw+24, y+size+18), radius=22, fill=(7,9,7,225), outline=GREEN, width=3)
    d.text((x, y), text, font=f, fill=WHITE)


def reel_frame(path: Path, slide: str, index: int, total: int, job: dict) -> Image.Image:
    w, h = 1080, 1920
    im = branded_background(path, w, h, index)
    brand_header(im)
    d = ImageDraw.Draw(im, "RGBA")

    # Instagram safe-area rule: essential text stays above 65% height (=1248 px).
    safe_end = int(h * 0.65)
    panel_top = 300
    panel_bottom = 910
    d.rounded_rectangle((70, panel_top, w-70, panel_bottom), radius=44, fill=(5,10,6,210), outline=(146,194,5,225), width=4)

    first = index == 0
    font_size = 76 if first else 68
    f = ff(BOLD, font_size)
    lines = wrap_lines(d, slide, f, w-190, 4)
    line_h = int(font_size * 1.18)
    total_h = max(1, len(lines)) * line_h
    y = panel_top + (panel_bottom-panel_top-total_h)//2
    for line in lines:
        b = d.textbbox((0, 0), line, font=f)
        x = (w - (b[2]-b[0])) // 2
        d.text((x, y), line, font=f, fill=WHITE)
        y += line_h

    # Qualifying CTA is visible without sound and remains above the bottom 35%.
    if index == total - 1:
        cta = "SCRIVI VALUTAZIONE"
        sub = "COMUNE · TIPOLOGIA · MQ · QUANDO VUOI VENDERE"
    else:
        cta = "PROPRIETARI · VALLE DI SUSA"
        sub = "PRIMA I DATI. POI LA STRATEGIA. POI LA VENDITA."
    cf = ff(BOLD, 42)
    sf = ff(REG, 28)
    cbox = d.textbbox((0,0), cta, font=cf)
    ctw = cbox[2]-cbox[0]
    cy = 1010
    d.rounded_rectangle((65, cy-24, w-65, 1195), radius=32, fill=(247,247,244,235))
    d.text(((w-ctw)//2, cy), cta, font=cf, fill=GREEN)
    sbox = d.textbbox((0,0), sub, font=sf)
    d.text(((w-(sbox[2]-sbox[0]))//2, cy+72), sub, font=sf, fill="#111111")

    # progress marker is non-essential but also kept above safe boundary.
    pf = ff(BOLD, 24)
    ptxt = f"{index+1}/{total}"
    d.text((w-120, safe_end-55), ptxt, font=pf, fill=(255,255,255,190))
    return im


def carousel_frame(path: Path, slide: str, index: int, total: int) -> Image.Image:
    w, h = 1080, 1350
    im = branded_background(path, w, h, index)
    brand_header(im, compact=True)
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle((70, 265, w-70, 955), radius=44, fill=(5,10,6,218), outline=(146,194,5,220), width=4)
    f = ff(BOLD, 66 if index else 72)
    lines = wrap_lines(d, slide, f, w-190, 4)
    lh = int((66 if index else 72)*1.2)
    th = len(lines)*lh
    y = 265 + (690-th)//2
    for line in lines:
        b = d.textbbox((0,0), line, font=f)
        d.text(((w-(b[2]-b[0]))//2, y), line, font=f, fill=WHITE)
        y += lh
    footer = "SCRIVI VALUTAZIONE" if index == total-1 else "F1 · NON A SENSAZIONE. CON I DATI."
    sf = ff(BOLD, 32)
    b = d.textbbox((0,0), footer, font=sf)
    d.rounded_rectangle((90, 1040, w-90, 1150), radius=30, fill=(247,247,244,235))
    d.text(((w-(b[2]-b[0]))//2, 1076), footer, font=sf, fill=GREEN)
    pf = ff(BOLD, 22)
    d.text((w-110, 1210), f"{index+1}/{total}", font=pf, fill=WHITE)
    return im


async def edge_save(text: str, out: Path) -> None:
    import edge_tts
    await edge_tts.Communicate(text=text, voice="it-IT-IsabellaNeural", rate="-2%", volume="+0%").save(str(out))


def voice(job: dict, temp: Path) -> Path | None:
    text = str(job.get("voiceover") or "").strip()
    if not text:
        return None
    out = temp / "voice.mp3"
    try:
        asyncio.run(edge_save(text, out))
        if out.exists() and out.stat().st_size > 1000:
            return out
    except Exception as exc:
        print(f"WARN edge_tts {job.get('id')}: {exc}", file=sys.stderr)
    wav = temp / "voice.wav"
    data = Path(os.getenv("PIPER_DATA_DIR", str(ROOT / ".cache" / "piper")))
    try:
        subprocess.run([sys.executable, "-m", "piper", "-m", "it_IT-paola-medium", "--data-dir", str(data), "-f", str(wav), "--", text], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return wav if wav.exists() and wav.stat().st_size > 1000 else None
    except Exception as exc:
        print(f"WARN piper {job.get('id')}: {exc}", file=sys.stderr)
        return None


def music(out: Path, seconds: float) -> Path:
    sr = 22050
    notes = [196.0, 246.94, 293.66, 392.0, 220.0, 277.18, 329.63, 440.0]
    total = int(sr * seconds)
    with wave.open(str(out), "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        for i in range(total):
            t = i / sr
            f0 = notes[int(t / 2.0) % len(notes)]
            sample = (math.sin(2*math.pi*f0*t)*0.50 + math.sin(2*math.pi*f0*0.5*t)*0.22) * 0.07
            wf.writeframes(struct.pack("<h", max(-32767, min(32767, int(sample*32767)))))
    return out


def make_video(frames: list[Path], voice_path: Path | None, music_path: Path, out: Path, target: float) -> None:
    n = len(frames)
    tr = 0.35
    dur = (target + (n-1)*tr) / n
    cmd = ["ffmpeg", "-y"]
    for p in frames:
        cmd += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(p)]
    vi = None
    if voice_path:
        vi = n
        cmd += ["-i", str(voice_path)]
    mi = n + (1 if voice_path else 0)
    cmd += ["-i", str(music_path)]
    filters = []
    for i in range(n):
        filters.append(f"[{i}:v]scale=1080:1920,format=yuv420p[v{i}]")
    cur = "v0"
    for i in range(1, n):
        label = f"x{i}"
        filters.append(f"[{cur}][v{i}]xfade=transition=fade:duration={tr}:offset={i*(dur-tr):.3f}[{label}]")
        cur = label
    if vi is not None:
        filters += [f"[{vi}:a]volume=1.0,apad[voice]", f"[{mi}:a]volume=0.045,apad[music]", "[voice][music]amix=inputs=2:duration=longest:dropout_transition=2[aout]"]
    else:
        filters += [f"[{mi}:a]volume=0.065,apad[aout]"]
    cmd += ["-filter_complex", ";".join(filters), "-map", f"[{cur}]", "-map", "[aout]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{target:.3f}", str(out)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def render_reel(job: dict, sources: list[Path]) -> None:
    slides = [str(x) for x in job.get("slides") or []]
    if not 6 <= len(slides) <= 8:
        raise RuntimeError(f"Reel slide count invalid: {job.get('id')} {len(slides)}")
    out = ROOT / str(job["media"])
    out.parent.mkdir(parents=True, exist_ok=True)
    target = float(job.get("reel_duration_seconds") or 28)
    with tempfile.TemporaryDirectory(prefix="f1q-reel-") as td:
        t = Path(td)
        frames: list[Path] = []
        for i, slide in enumerate(slides):
            src = sources[(i + abs(hash(job["id"])) % len(sources)) % len(sources)] if sources else Path("missing")
            p = t / f"frame-{i:02d}.jpg"
            reel_frame(src, slide, i, len(slides), job).save(p, "JPEG", quality=93, optimize=True)
            frames.append(p)
        v = voice(job, t)
        m = music(t / "music.wav", target + 2)
        make_video(frames, v, m, out, target)
    job["render_status"] = "RENDERED_REEL_MP4"
    job["render_spec"] = {"width": 1080, "height": 1920, "duration_seconds": target, "muted_view": True, "safe_bottom_fraction": 0.35}


def render_carousel(job: dict, sources: list[Path]) -> None:
    slides = [str(x) for x in job.get("slides") or []]
    media = list(job.get("media") or [])
    if len(slides) != len(media) or not 7 <= len(slides) <= 10:
        raise RuntimeError(f"Carousel mismatch: {job.get('id')} slides={len(slides)} media={len(media)}")
    for i, (slide, rel) in enumerate(zip(slides, media)):
        src = sources[(i + abs(hash(job["id"])) % len(sources)) % len(sources)] if sources else Path("missing")
        out = ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        carousel_frame(src, slide, i, len(slides)).save(out, "JPEG", quality=93, optimize=True)
    job["render_status"] = "RENDERED_CAROUSEL_JPG"
    job["render_spec"] = {"width": 1080, "height": 1350, "slides": len(slides)}


def main() -> int:
    data = load(QUEUE)
    jobs = list(data.get("jobs") or [])
    blocked = [j for j in jobs if j.get("gate_status") != "PASSED"]
    if blocked:
        raise RuntimeError(f"Refusing render: {len(blocked)} jobs have not PASSED producer gate")
    sources = local_images()
    print(f"F1 QUALIFIED RENDER sources={len(sources)}")
    reels = carousels = 0
    for job in jobs:
        if job.get("format") == "reel":
            render_reel(job, sources); reels += 1
        elif job.get("format") == "carousel":
            render_carousel(job, sources); carousels += 1
        else:
            raise RuntimeError(f"Unsupported format {job.get('format')}")
    data["render_summary"] = {"reels": reels, "carousels": carousels, "total": reels+carousels}
    QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RENDERED F1 QUALIFIED 14D: reels={reels} carousels={carousels}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
