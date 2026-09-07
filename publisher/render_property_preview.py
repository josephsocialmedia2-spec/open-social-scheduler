#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import f1_premium_renderer as f1

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "publisher" / "property_job_preview.json"
OUTPUT_DIR = ROOT / "property-preview"
OUTPUT = OUTPUT_DIR / "latest.jpg"
META = OUTPUT_DIR / "meta.json"
SIZE = (1080, 1350)


def font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
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


def choose_preview_image(job: dict) -> Image.Image:
    cfg = f1.load_json(f1.F1_CFG, {})
    sources = [x for x in cfg.get("brand", {}).get("photo_sources", []) if isinstance(x, dict) and x.get("url")]
    # Prefer a generic residential source for the preview so the graphic does not imply
    # that the stock photo is the actual property in Rivoli.
    ranked = sorted(sources, key=lambda x: ("residential" not in f1.source_kind(x), "local" not in f1.source_kind(x)))
    last = None
    for item in ranked:
        try:
            return f1.robust_local_get(str(item["url"]))
        except Exception as exc:
            last = exc
    raise RuntimeError(f"No preview image available: {last}")


def render(job: dict) -> Image.Image:
    prop = job.get("property") or {}
    image = choose_preview_image(job)
    canvas = ImageOps.fit(image.convert("RGB"), SIZE, Image.Resampling.LANCZOS)

    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, 1080, 190), fill=(7, 9, 7, 220))
    od.rectangle((0, 670, 1080, 1165), fill=(7, 9, 7, 232))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(canvas)

    f1.draw_brand(d, 48, 48)
    d.rounded_rectangle((780, 52, 1025, 104), radius=14, fill=f1.GREEN)
    d.text((808, 67), "ANTEPRIMA GRAFICA", font=font(18, True), fill=f1.BLACK)

    d.text((58, 700), str(job.get("title") or "IMMOBILE IN VENDITA").upper(), font=font(24, True), fill=f1.GREEN)

    title = str(prop.get("title") or "Immobile in vendita")
    ft, lines = wrap(d, title.upper(), 900, 64, 2, True)
    y = 748
    for line in lines:
        d.text((58, y), line, font=ft, fill=f1.WHITE)
        y += int(getattr(ft, "size", 50) * 1.04)

    desc = str(prop.get("description") or "")
    if desc:
        fd, dlines = wrap(d, desc, 900, 31, 2, False)
        y += 12
        for line in dlines:
            d.text((58, y), line, font=fd, fill=f1.MUTED)
            y += int(getattr(fd, "size", 28) * 1.25)

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

    d.text((58, 1130), "Immagine di esempio per validare il layout. Sostituire con la foto reale dell'immobile prima della pubblicazione.", font=font(15), fill=f1.MUTED)

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
    image = render(job)
    image.save(OUTPUT, "JPEG", quality=94, optimize=True)
    META.write_text(json.dumps({"job": job, "output": str(OUTPUT.relative_to(ROOT)), "size": SIZE}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PROPERTY PREVIEW READY: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
