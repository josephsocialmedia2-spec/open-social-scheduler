#!/usr/bin/env python3
"""Overwrite current Real Media Pro reels with original Shopify-Theme-Store-inspired visuals.

No Shopify theme screenshot is copied. The Theme Store is used only as a high-level
reference for clean ecommerce composition: generous whitespace, product-led hero,
mobile-first hierarchy, collection cards, trust strip and clear CTA.

The actual imagery comes from the reusable/licensed image URLs already selected by the
fresh-visual renderer. Every reel is 10 frames x 2 seconds = 20 seconds.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps

import render_reels as rr
import render_fresh_visuals as fresh

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
CREAM = "#F7F3EC"
INK = "#111512"
MUTED = "#657067"
GREEN = "#365B35"
LINE = "#DDD8CF"
WHITE = "#FFFFFF"
REFERENCE = "https://themes.shopify.com/?locale=it"

HEADLINES = [
    "Modern essentials. Built to convert.",
    "Beauty products. Clear shopping.",
    "Timeless pieces. Easy discovery.",
    "Beautiful spaces. Simple choices.",
    "Thoughtful products. Strong presentation.",
    "Premium gear. Seamless experience.",
    "Products worth discovering.",
    "Tools for creators. Content that connects.",
    "A cleaner path to checkout.",
    "Your ecommerce, built to grow.",
]

KICKERS = [
    "CURATED COLLECTION", "CLEAN BEAUTY", "REFINED ESSENTIALS", "HOME & LIVING",
    "NEW ARRIVALS", "TECH EDIT", "FEATURED PRODUCTS", "CREATOR TOOLS",
    "CONVERSION FIRST", "REAL MEDIA PRO",
]


def load_queue() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save_queue(data: dict) -> None:
    QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def f(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def cover(img: Image.Image, size: tuple[int, int], centering=(0.5, 0.5)) -> Image.Image:
    return ImageOps.fit(img.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=centering)


def rounded_paste(base: Image.Image, img: Image.Image, box: tuple[int, int, int, int], radius: int = 24) -> None:
    x1, y1, x2, y2 = box
    fitted = cover(img, (x2 - x1, y2 - y1))
    mask = Image.new("L", fitted.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, fitted.width - 1, fitted.height - 1), radius=radius, fill=255)
    base.paste(fitted, (x1, y1), mask)


def text_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int, max_lines: int = 3) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        candidate = (cur + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
            if len(lines) >= max_lines - 1:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def product_crop(img: Image.Image, variant: int) -> Image.Image:
    w, h = img.size
    centers = [(0.35, 0.5), (0.65, 0.45), (0.5, 0.62)]
    return cover(img, (260, 250), centers[variant % len(centers)])


def shopify_inspired_frame(urls: list[str], index: int) -> Image.Image:
    """Create an original ecommerce design board, not a copied theme screenshot."""
    base = Image.new("RGB", (1080, 1920), CREAM)
    d = ImageDraw.Draw(base)
    hero = fresh.direct_get_image(urls[index % len(urls)])
    p2 = fresh.direct_get_image(urls[(index + 1) % len(urls)])
    p3 = fresh.direct_get_image(urls[(index + 2) % len(urls)])
    p4 = fresh.direct_get_image(urls[(index + 3) % len(urls)])

    # Top navigation: no browser chrome and no Shopify marks.
    d.text((70, 48), "REAL MEDIA PRO", font=f(rr.BOLD, 29), fill=INK)
    nav = "SHOP     COLLECTIONS     ABOUT     CONTACT"
    d.text((510, 56), nav, font=f(rr.SANS, 15), fill=MUTED)
    d.line((65, 105, 1015, 105), fill=LINE, width=2)

    # Hero block.
    d.text((72, 165), KICKERS[index % len(KICKERS)], font=f(rr.BOLD, 18), fill=GREEN)
    title_font = f(rr.BOLD, 54)
    y = 205
    for line in text_lines(d, HEADLINES[index % len(HEADLINES)], title_font, 420, 3):
        d.text((72, y), line, font=title_font, fill=INK)
        y += 66
    d.text((72, y + 18), "Design pulito, percorso chiaro e una struttura pensata per accompagnare l'acquisto.", font=f(rr.SANS, 22), fill=MUTED)
    d.rounded_rectangle((72, y + 92, 300, y + 154), radius=10, fill=GREEN)
    d.text((111, y + 111), "SCOPRI DI PIÙ", font=f(rr.BOLD, 17), fill=WHITE)
    rounded_paste(base, hero, (540, 150, 1010, 650), 26)

    # Trust strip.
    d.rounded_rectangle((65, 690, 1015, 820), radius=22, fill=WHITE, outline=LINE, width=2)
    features = [("MOBILE", "Ottimizzato"), ("FIDUCIA", "Più chiarezza"), ("CHECKOUT", "Meno attriti"), ("DATI", "Misurabile")]
    for i, (a, b) in enumerate(features):
        x = 92 + i * 235
        d.ellipse((x, 724, x + 34, 758), outline=GREEN, width=3)
        d.text((x + 48, 715), a, font=f(rr.BOLD, 16), fill=INK)
        d.text((x + 48, 744), b, font=f(rr.SANS, 15), fill=MUTED)

    # Editorial/product section.
    d.text((70, 880), "COLLEZIONE IN EVIDENZA", font=f(rr.BOLD, 20), fill=INK)
    d.text((850, 883), "VEDI TUTTO", font=f(rr.BOLD, 15), fill=GREEN)
    cards = [(p2, "BEST SELLER"), (p3, "NEW IN"), (p4, "EDITOR'S PICK")]
    for i, (img, label) in enumerate(cards):
        x = 70 + i * 318
        d.rounded_rectangle((x, 930, x + 286, 1320), radius=22, fill=WHITE, outline=LINE, width=2)
        crop = product_crop(img, i)
        mask = Image.new("L", crop.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, crop.width - 1, crop.height - 1), radius=16, fill=255)
        base.paste(crop, (x + 13, 944), mask)
        d.text((x + 18, 1210), label, font=f(rr.BOLD, 14), fill=GREEN)
        d.text((x + 18, 1244), ["Prodotto essenziale", "Scelta premium", "Design contemporaneo"][i], font=f(rr.BOLD, 18), fill=INK)
        d.text((x + 18, 1280), "Scopri ora  →", font=f(rr.SANS, 16), fill=MUTED)

    # Conversion section.
    d.rounded_rectangle((65, 1370, 1015, 1680), radius=26, fill=WHITE, outline=LINE, width=2)
    d.text((95, 1410), "NON SOLO BELLO.", font=f(rr.BOLD, 18), fill=GREEN)
    d.text((95, 1450), "Un sito deve rendere semplice capire, fidarsi e agire.", font=f(rr.BOLD, 34), fill=INK)
    bullets = ["proposta chiara", "esperienza mobile", "pagina prodotto", "checkout", "misurazione"]
    for i, item in enumerate(bullets):
        yy = 1530 + (i % 3) * 48
        xx = 95 + (i // 3) * 390
        d.ellipse((xx, yy + 4, xx + 19, yy + 23), fill=GREEN)
        d.text((xx + 32, yy), item.upper(), font=f(rr.BOLD, 16), fill=MUTED)

    # Fixed footer for publication-ready Reel.
    d.rounded_rectangle((62, 1770, 1018, 1870), radius=50, fill=WHITE, outline="#67E8C4", width=4)
    footer = "SITI • ECOMMERCE • SHOPIFY   |   371 370 8294"
    fb = f(rr.BOLD, 25)
    box = d.textbbox((0, 0), footer, font=fb)
    d.text(((1080 - (box[2] - box[0])) / 2, 1801), footer, font=fb, fill=INK)
    return base


def render_job(job: dict) -> Path:
    urls = list(job.get("visual_asset_urls") or [])[:10]
    if len(urls) != 10:
        raise RuntimeError(f"{job.get('id')}: expected 10 source images before Shopify composition")
    out = ROOT / str(job["media"])
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="oss-rmp-shopify-") as td:
        temp = Path(td)
        voice = rr.voice(job, temp)
        music = rr.music(temp / "music.wav", seconds=20)
        frames: list[Path] = []
        for i in range(10):
            p = temp / f"rmp-{i:02d}.jpg"
            shopify_inspired_frame(urls, i).save(p, "JPEG", quality=94, optimize=True)
            frames.append(p)
        fresh.make_video_exact_change(frames, voice, music, out, 2.0)
    return out


def main() -> int:
    rr.get_image = fresh.direct_get_image
    data = load_queue()
    current = str(data.get("current_cycle") or "")
    reels = [
        j for j in data.get("jobs", [])
        if str(j.get("cycle_key") or "") == current
        and str(j.get("client_id") or "") == "real-media-pro"
        and str(j.get("format") or "") == "reel"
        and j.get("enabled", True)
        and j.get("status") not in {"published", "disabled"}
    ]
    if len(reels) != 2:
        raise SystemExit(f"Expected 2 current RMP reels, got {len(reels)}")

    for job in reels:
        if str(job.get("visual_mode") or "") != "shopify-theme-inspired-original":
            raise RuntimeError(f"RMP job is not locked to Shopify-inspired original mode: {job.get('id')}")
        render_job(job)
        job["visual_source"] = "original_shopify_theme_store_inspired_composition_from_licensed_photos"
        job["design_reference_url"] = REFERENCE
        job["copyright_policy"] = "original composition; no copied Shopify theme screenshots"
        job["image_change_seconds"] = 2
        job["reel_duration_seconds"] = 20
        job["publication_ready"] = True
        job["caption_ready"] = bool(str(job.get("caption") or "").strip())

    data["updated_by"] = "Original Shopify-inspired RMP renderer"
    save_queue(data)
    print("Rendered 2 publication-ready RMP reels: original Shopify-inspired visuals, 10 x 2 seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
