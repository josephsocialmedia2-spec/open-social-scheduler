#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

import f1_premium_renderer as f1

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "publisher" / "property_job_preview.json"
OUTPUT_DIR = ROOT / "property-preview"
META = OUTPUT_DIR / "meta.json"
README = OUTPUT_DIR / "README.md"
SIZE = (1080, 1350)
COUNT = 10


def font(size: int, bold: bool = False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, width: int, size: int, max_lines: int, bold: bool = True):
    words = str(text or "").split()
    for s in range(size, 27, -2):
        ft = font(s, bold)
        lines, line = [], ""
        for w in words:
            test = (line + " " + w).strip()
            if draw.textbbox((0, 0), test, font=ft)[2] <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = w
        if line:
            lines.append(line)
        if len(lines) <= max_lines:
            return ft, lines
    return font(28, bold), [" ".join(words)]


def choose_preview_images() -> list[Image.Image]:
    cfg = f1.load_json(f1.F1_CFG, {})
    sources = [x for x in cfg.get("brand", {}).get("photo_sources", []) if isinstance(x, dict) and x.get("url")]
    ranked = sorted(sources, key=lambda x: ("residential" not in f1.source_kind(x), "local" not in f1.source_kind(x)))
    loaded: list[Image.Image] = []
    errors = []
    for item in ranked:
        try:
            loaded.append(f1.robust_local_get(str(item["url"])))
        except Exception as exc:
            errors.append(str(exc))
    if not loaded:
        raise RuntimeError("No preview image available: " + " | ".join(errors[-3:]))
    return [loaded[i % len(loaded)].copy() for i in range(COUNT)]


def render(job: dict, image: Image.Image, index: int) -> Image.Image:
    prop = job.get("property") or {}
    canvas = ImageOps.fit(image.convert("RGB"), SIZE, Image.Resampling.LANCZOS)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.02 + (index % 3) * 0.02)

    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Alternate the visual rhythm while preserving the F1 identity.
    if index % 2:
        od.rectangle((0, 0, 1080, 165), fill=(7, 9, 7, 218))
        od.rectangle((0, 620, 1080, 1165), fill=(7, 9, 7, 234))
    else:
        od.rectangle((0, 0, 1080, 190), fill=(7, 9, 7, 225))
        od.rectangle((0, 680, 1080, 1165), fill=(7, 9, 7, 236))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(canvas)

    f1.draw_brand(d, 48, 48)
    d.rounded_rectangle((810, 52, 1025, 104), radius=14, fill=f1.GREEN)
    d.text((838, 67), f"PROPOSTA {index:02d}", font=font(18, True), fill=f1.BLACK)

    top_y = 655 if index % 2 else 705
    d.text((58, top_y), str(job.get("title") or "IMMOBILE IN VENDITA").upper(), font=font(24, True), fill=f1.GREEN)

    title = str(prop.get("title") or "Immobile in vendita")
    ft, lines = wrap(d, title.upper(), 900, 64, 2, True)
    y = top_y + 48
    for line in lines:
        d.text((58, y), line, font=ft, fill=f1.WHITE)
        y += int(getattr(ft, "size", 50) * 1.04)

    desc = str(prop.get("description") or "")
    if desc:
        fd, dlines = wrap(d, desc, 900, 30, 2, False)
        y += 10
        for line in dlines:
            d.text((58, y), line, font=fd, fill=f1.MUTED)
            y += int(getattr(fd, "size", 28) * 1.22)

    price = str(prop.get("price") or "")
    if price:
        d.text((58, 930), price, font=font(54, True), fill=f1.GREEN)

    specs = [
        f"{prop.get('mq')} m²" if prop.get("mq") else "",
        f"{prop.get('locali')} locali" if prop.get("locali") else "",
        f"{prop.get('bagni')} bagni" if prop.get("bagni") else "",
        str(prop.get("box") or ""),
    ]
    specs = [x for x in specs if x]
    sx = 58
    for item in specs[:4]:
        box_w = max(145, d.textbbox((0, 0), item, font=font(20, True))[2] + 44)
        d.rounded_rectangle((sx, 1010, sx + box_w, 1062), radius=13, fill=(20, 28, 20), outline=f1.GREEN, width=2)
        d.text((sx + 20, 1025), item, font=font(20, True), fill=f1.WHITE)
        sx += box_w + 14

    location = str(prop.get("location") or "")
    if location:
        d.text((58, 1092), location, font=font(22, True), fill=f1.WHITE)

    d.text((58, 1130), "Mockup grafico: sostituire con la fotografia reale dell'immobile prima della pubblicazione.", font=font(15), fill=f1.MUTED)
    f1.draw_footer(canvas)
    return canvas


def main() -> int:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    jobs = payload.get("jobs") or []
    if len(jobs) != 1:
        raise RuntimeError("Property preview expects exactly one job")
    job = jobs[0]
    prop = job.get("property") or {}
    required = ["title", "description", "mq", "locali", "bagni", "price", "location"]
    missing = [k for k in required if not prop.get(k)]
    if missing:
        raise RuntimeError(f"Missing property fields: {', '.join(missing)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    images = choose_preview_images()
    outputs = []
    for i, source in enumerate(images, 1):
        out = OUTPUT_DIR / f"{i:02d}.jpg"
        render(job, source, i).save(out, "JPEG", quality=94, optimize=True)
        outputs.append(str(out.relative_to(ROOT)))

    shutil.copyfile(OUTPUT_DIR / "01.jpg", OUTPUT_DIR / "latest.jpg")
    META.write_text(json.dumps({"job": job, "outputs": outputs, "count": COUNT, "size": SIZE}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    repo = "https://raw.githubusercontent.com/josephsocialmedia2-spec/open-social-scheduler/main/property-preview"
    lines = ["# F1 · 10 proposte grafiche generate dal nuovo Python", "", "Tutte le immagini sono 1080 × 1350 e derivano dal JSON immobile corrente.", ""]
    for i in range(1, COUNT + 1):
        lines += [f"## Proposta {i:02d}", "", f"![Proposta {i:02d}]({repo}/{i:02d}.jpg)", ""]
    README.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PROPERTY PREVIEWS READY: {COUNT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
