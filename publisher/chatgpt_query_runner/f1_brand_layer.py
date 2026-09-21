from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
CLIENT_PATH = ROOT / "publisher" / "clients" / "f1-immobiliare.json"

W, H = 1080, 1350
GREEN = "#92C205"
DARK = "#070907"
WHITE = "#F7F7F4"
MUTED = "#D7DBD7"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _fit_cover(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    src_ratio = image.width / image.height
    dst_ratio = W / H
    if src_ratio > dst_ratio:
        new_h = H
        new_w = round(new_h * src_ratio)
    else:
        new_w = W
        new_h = round(new_w / src_ratio)
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - W) // 2)
    top = max(0, (new_h - H) // 2)
    return resized.crop((left, top, left + W, top + H))


def _draw_logo(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 0.22) -> None:
    # Deterministic simplified F1 wordmark. Exact text remains outside the AI image.
    f1 = _font(round(155 * scale), bold=True)
    brand = _font(round(66 * scale), bold=True)
    draw.text((x, y), "F1", font=f1, fill=GREEN)
    draw.text((x, y + round(120 * scale)), "IMMOBILIARE", font=brand, fill=WHITE)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        box = draw.textbbox((0, 0), trial, font=font)
        if box[2] - box[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def apply_f1_brand_layer(
    source: Path,
    destination: Path,
    *,
    headline: str,
    cta: str,
    territory: str = "VALLE DI SUSA",
    phone: str = "371 370 8294",
    url: str = "www.f1immobiliare.com",
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as raw:
        base = _fit_cover(raw)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Dark left panel with soft fade approximation. This mirrors the supplied F1 brand references:
    # property photography remains protagonist, copy sits on a strong black/green system.
    od.rectangle((0, 0, 610, H), fill=(7, 9, 7, 220))
    for x in range(610, 780, 10):
        alpha = max(0, int(210 * (780 - x) / 170))
        od.rectangle((x, 0, x + 10, H), fill=(7, 9, 7, alpha))
    base = Image.alpha_composite(base.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(base)
    _draw_logo(draw, 64, 56, 1.0)

    small = _font(34, bold=True)
    draw.text((64, 220), territory.upper(), font=small, fill=MUTED)
    draw.rectangle((64, 270, 166, 278), fill=GREEN)

    title_font = _font(82, bold=True)
    lines = _wrap(draw, headline.upper(), title_font, 510)
    y = 330
    for line in lines[:4]:
        # Highlight the key term "VALE" when present.
        if "VALE" in line:
            parts = line.split("VALE", 1)
            x = 64
            if parts[0]:
                draw.text((x, y), parts[0], font=title_font, fill=WHITE)
                x += draw.textlength(parts[0], font=title_font)
            draw.text((x, y), "VALE", font=title_font, fill=GREEN)
            x += draw.textlength("VALE", font=title_font)
            if parts[1]:
                draw.text((x, y), parts[1], font=title_font, fill=WHITE)
        else:
            draw.text((64, y), line, font=title_font, fill=WHITE)
        y += 96

    body_font = _font(37, bold=False)
    body = "Scopri il valore reale del tuo immobile con una valutazione professionale e senza impegno."
    by = min(y + 36, 780)
    for line in _wrap(draw, body, body_font, 500)[:5]:
        draw.text((64, by), line, font=body_font, fill=WHITE)
        by += 50

    cta_y = 1010
    draw.rounded_rectangle((64, cta_y, 560, cta_y + 108), radius=28, fill=GREEN)
    cta_font = _font(34, bold=True)
    cta_text = cta.upper()
    bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    tx = 64 + (496 - (bbox[2] - bbox[0])) / 2
    draw.text((tx, cta_y + 31), cta_text, font=cta_font, fill=DARK)

    foot = _font(28, bold=False)
    draw.text((64, 1180), f"☎ {phone}", font=foot, fill=WHITE)
    draw.text((64, 1224), url, font=foot, fill=WHITE)
    draw.text((64, 1270), "NON A SENSAZIONE. CON I DATI.", font=_font(25, bold=True), fill=GREEN)

    rgb = base.convert("RGB")
    rgb.save(destination, format="PNG", optimize=True)

    with Image.open(destination) as check:
        check.verify()
    with Image.open(destination) as check:
        width, height = check.size
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return {
        "path": destination.relative_to(ROOT).as_posix(),
        "sha256": digest,
        "width": width,
        "height": height,
        "brand_qa": "PASS" if (width, height) == (W, H) else "FAIL",
        "visual_qa": "TECHNICAL_PASS",
    }
