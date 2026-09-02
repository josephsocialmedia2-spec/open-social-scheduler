#!/usr/bin/env python3
"""Render the active cycle as 10 STATIC PUBLICATIONS.

F1 Immobiliare
- five publications per cycle;
- only configured, geographically coherent Valle di Susa / Piemonte imagery;
- never fall back to generic or foreign-looking property imagery;
- add the approved Francesca + Joseph brand footer.

Real Media Pro
- five publications per cycle;
- the ONLY visual reference is the official Shopify Theme Store URL stored on the job;
- Shopify theme screenshots/images are NEVER downloaded, copied, cropped or republished;
- generate an original ecommerce/site mockup from the stored Italian theme description;
- add the approved Francesca + Joseph brand footer.
"""
from __future__ import annotations

import base64
import json
import textwrap
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
HISTORY = ROOT / "publisher" / "image_history.json"
F1_CFG = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
ASSET_DIR = ROOT / "publisher" / "assets"
SIZE = (1080, 1350)
MAX_HISTORY = 1000
LOCAL_MARKERS = (
    "avigliana", "valle di susa", "val di susa", "susa", "almese", "sant'ambrogio",
    "oulx", "bardonecchia", "sauze", "condove", "villar dora", "bussoleno",
    "borgone", "chiusa di san michele", "piemonte",
)


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ] if bold else [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def fit_lines(draw: ImageDraw.ImageDraw, text: str, width_px: int, max_lines: int, start_size: int = 64, min_size: int = 28) -> tuple[ImageFont.ImageFont, list[str]]:
    clean = " ".join(str(text or "").upper().split())
    for size in range(start_size, min_size - 1, -2):
        f = font(size, True)
        rough = max(10, int(width_px / max(1, size * 0.56)))
        lines = textwrap.wrap(clean, width=rough)
        if len(lines) <= max_lines and all(draw.textbbox((0, 0), line, font=f)[2] <= width_px for line in lines):
            return f, lines
    f = font(min_size, True)
    return f, textwrap.wrap(clean, width=max(12, int(width_px / (min_size * 0.56))))[:max_lines]


def load_presenter(name: str) -> Image.Image:
    path = ASSET_DIR / f"{name}_presenter.jpg.b64"
    raw = base64.b64decode(path.read_text(encoding="utf-8"))
    return Image.open(BytesIO(raw)).convert("RGB")


def rounded_paste(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int], radius: int = 24) -> None:
    x0, y0, x1, y1 = box
    target = ImageOps.fit(image.convert("RGB"), (x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    mask = Image.new("L", target.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, target.width - 1, target.height - 1), radius=radius, fill=255)
    canvas.paste(target, (x0, y0), mask)


def presenter_footer(canvas: Image.Image, brand: str) -> None:
    draw = ImageDraw.Draw(canvas)
    top = 1035
    if brand == "f1":
        bg = "#FFFFFF"
        dark = "#081B33"
        accent = "#56A900"
        line = "#DCE5D2"
        brand_label = "F1 IMMOBILIARE"
        sub = "LA TUA CASA. IL NOSTRO METODO. RISULTATI REALI."
    else:
        bg = "#071A3A"
        dark = "#FFFFFF"
        accent = "#D4A536"
        line = "#355273"
        brand_label = "REAL MEDIA PRO"
        sub = "SITI WEB · ECOMMERCE · STRATEGIA DIGITALE"

    draw.rectangle((0, top, 1080, 1350), fill=bg)
    draw.line((0, top, 1080, top), fill=accent, width=6)

    francesca = load_presenter("francesca")
    joseph = load_presenter("joseph")
    rounded_paste(canvas, francesca, (35, top + 38, 215, 1305), radius=18)
    rounded_paste(canvas, joseph, (230, top + 38, 410, 1305), radius=18)

    draw.text((450, top + 35), brand_label, font=font(30, True), fill=dark)
    draw.text((450, top + 78), sub, font=font(14, False), fill=accent)
    draw.line((450, top + 112, 1030, top + 112), fill=line, width=2)

    draw.text((450, top + 135), "FRANCESCA AURIGEMMA", font=font(18, True), fill=dark)
    draw.text((450, top + 165), "Agente immobiliare", font=font(14), fill=dark)
    draw.text((450, top + 196), "+39 371 424 6300", font=font(20, True), fill=accent)

    draw.text((740, top + 135), "JOSEPH MALAFRONTE", font=font(18, True), fill=dark)
    draw.text((740, top + 165), "Digital Strategist", font=font(14), fill=dark)
    draw.text((740, top + 196), "+39 371 370 8294", font=font(20, True), fill=accent)

    if brand == "f1":
        draw.text((450, top + 244), "f1immobiliaresusa@outlook.it", font=font(15), fill=dark)
        draw.text((790, top + 244), "SCRIVI: VALUTAZIONE", font=font(15, True), fill=accent)
    else:
        draw.text((450, top + 244), "ANALISI STRATEGICA GRATUITA", font=font(17, True), fill=accent)
        draw.text((790, top + 244), "PARLIAMONE", font=font(17, True), fill=dark)


def configured_f1_local_candidates() -> list[str]:
    cfg = load_json(F1_CFG, {})
    rows: list[str] = []
    for item in cfg.get("brand", {}).get("photo_sources", []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        credit = str(item.get("credit") or "").lower()
        if url and any(marker in credit for marker in LOCAL_MARKERS):
            rows.append(url)
    if len(rows) < 5:
        raise RuntimeError("F1 requires at least five approved local Valle di Susa/Piemonte images")
    return rows


def get_remote_image(url: str) -> Image.Image:
    headers = {"User-Agent": "Mozilla/5.0 Open-Social-Scheduler/F1LocalVisuals"}
    r = requests.get(url, headers=headers, timeout=25)
    r.raise_for_status()
    image = Image.open(BytesIO(r.content)).convert("RGB")
    if image.width < 500 or image.height < 400:
        raise RuntimeError(f"Local image too small: {image.size}")
    return image


def f1_composition(image: Image.Image, title: str, position: int) -> Image.Image:
    canvas = Image.new("RGB", SIZE, "#FFFFFF")
    draw = ImageDraw.Draw(canvas)
    dark = "#081B33"
    green = "#56A900"

    draw.text((55, 42), "F1 IMMOBILIARE", font=font(25, True), fill=dark)
    draw.text((55, 78), "VALLE DI SUSA · VALUTAZIONE · VENDITA", font=font(14, True), fill=green)

    tf, lines = fit_lines(draw, title, 950, 3, start_size=64, min_size=38)
    y = 132
    for line in lines:
        split = line.split()
        if len(split) > 1:
            main = " ".join(split[:-1])
            last = split[-1]
            draw.text((55, y), main + " ", font=tf, fill=dark)
            x = 55 + draw.textbbox((0, 0), main + " ", font=tf)[2]
            draw.text((x, y), last, font=tf, fill=green)
        else:
            draw.text((55, y), line, font=tf, fill=dark)
        y += int(getattr(tf, "size", 44) * 1.15)

    photo = ImageOps.fit(image, (1080, 610), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    canvas.paste(photo, (0, 355))
    overlay = Image.new("RGBA", (1080, 610), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 430, 1080, 610), fill=(4, 20, 37, 185))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), Image.new("RGBA", SIZE, (0, 0, 0, 0)))
    canvas.alpha_composite(overlay, (0, 355))
    canvas = canvas.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    callouts = [
        "Hai un immobile da vendere? Prima valutazione gratuita.",
        "Il prezzo si verifica con dati, comparabili e domanda locale.",
        "Prima i dati. Poi la strategia. Poi la vendita.",
        "Via, piano, esposizione e contesto cambiano il valore.",
        "Comparabili · mercato · microzona · strategia.",
    ]
    draw.text((55, 815), callouts[max(0, min(4, position - 1))], font=font(23, True), fill="#FFFFFF")
    draw.rounded_rectangle((55, 900, 625, 990), radius=20, fill=green)
    draw.text((90, 924), "SCRIVI VALUTAZIONE", font=font(31, True), fill="#FFFFFF")
    presenter_footer(canvas, "f1")
    return canvas


def theme_palette(profile: str) -> tuple[str, str, str, str]:
    palettes = {
        "creative_modular": ("#0B1E44", "#4D67FF", "#F5EEE5", "#161A23"),
        "mobile_speed": ("#071A3A", "#D4A536", "#F4F5F7", "#0A234A"),
        "premium": ("#0A1220", "#C79A4A", "#EEE7DD", "#191919"),
        "brand_story": ("#12243B", "#C69B43", "#F4EFE8", "#18243A"),
        "catalog_discovery": ("#0A2540", "#276EF1", "#F5F7FA", "#132238"),
    }
    return palettes.get(profile, palettes["mobile_speed"])


def feature_labels(profile: str) -> list[str]:
    return {
        "creative_modular": ["Sezioni modulari", "Quick buy", "Confronto prodotti", "Percorso chiaro"],
        "mobile_speed": ["Mobile first", "Velocità", "CTA visibili", "Upsell"],
        "premium": ["Design premium", "Prestazioni", "Accessibilità", "Valore percepito"],
        "brand_story": ["Brand identity", "Visual storytelling", "Catalogo chiaro", "Conversione"],
        "catalog_discovery": ["Filtri", "Ricerca", "Collezioni", "Scoperta prodotti"],
    }.get(profile, ["Mobile first", "Struttura chiara", "Prodotti", "Conversione"])


def draw_product(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, accent: str, kind: int) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=16, fill=fill, outline="#D9DEE7", width=2)
    cx = (x0 + x1) // 2
    if kind % 4 == 0:
        draw.ellipse((cx - 42, y0 + 24, cx + 42, y0 + 108), fill=accent)
        draw.rectangle((cx - 16, y0 + 102, cx + 16, y0 + 160), fill=accent)
    elif kind % 4 == 1:
        draw.rounded_rectangle((cx - 48, y0 + 30, cx + 48, y0 + 132), radius=24, fill=accent)
        draw.rectangle((cx - 28, y0 + 128, cx + 28, y0 + 164), fill=accent)
    elif kind % 4 == 2:
        draw.ellipse((cx - 52, y0 + 42, cx + 52, y0 + 122), fill=accent)
        draw.rectangle((cx - 18, y0 + 20, cx + 18, y0 + 48), fill=accent)
    else:
        draw.polygon([(cx - 52, y0 + 130), (cx, y0 + 28), (cx + 52, y0 + 130)], fill=accent)
        draw.rectangle((cx - 38, y0 + 128, cx + 38, y0 + 160), fill=accent)
    draw.rectangle((x0 + 18, y1 - 54, x1 - 18, y1 - 40), fill="#D8DEE8")
    draw.rectangle((x0 + 18, y1 - 31, x0 + 78, y1 - 20), fill=accent)


def ecommerce_browser(profile: str, cycle_index: int = 0) -> Image.Image:
    bg, accent, soft, dark = theme_palette(profile)
    browser = Image.new("RGB", (640, 610), "#FFFFFF")
    draw = ImageDraw.Draw(browser)
    draw.rounded_rectangle((0, 0, 639, 609), radius=24, fill="#FFFFFF", outline="#CBD2DC", width=3)
    draw.rectangle((0, 0, 640, 55), fill="#F8FAFC")
    draw.ellipse((18, 20, 30, 32), fill="#FF6B6B")
    draw.ellipse((38, 20, 50, 32), fill="#FFD166")
    draw.ellipse((58, 20, 70, 32), fill="#06D6A0")
    draw.text((95, 17), "SHOP   COLLEZIONI   NOVITÀ   CONTATTI", font=font(11, True), fill=dark)

    if profile == "catalog_discovery":
        draw.rectangle((18, 78, 162, 365), fill="#F3F6FA")
        draw.text((35, 95), "FILTRI", font=font(15, True), fill=dark)
        for i, label in enumerate(["Categoria", "Prezzo", "Colore", "Materiale"]):
            y = 135 + i * 48
            draw.rectangle((35, y, 49, y + 14), outline=accent, width=2)
            draw.text((60, y - 2), label, font=font(12), fill=dark)
        hero_x = 185
    else:
        hero_x = 18

    hero_w = 604 - hero_x
    draw.rounded_rectangle((hero_x, 78, 622, 275), radius=20, fill=bg)
    draw.text((hero_x + 26, 104), "Essenziale. Chiaro. Tuo.", font=font(25, True), fill="#FFFFFF")
    draw.text((hero_x + 26, 145), "Un percorso progettato per capire\nil prodotto e arrivare all'azione.", font=font(13), fill="#FFFFFF")
    draw.rounded_rectangle((hero_x + 26, 210, hero_x + 175, 250), radius=10, fill=accent)
    draw.text((hero_x + 47, 222), "SCOPRI ORA", font=font(12, True), fill="#FFFFFF")
    # Original decorative product shapes; no external assets.
    draw.ellipse((500, 105, 575, 180), fill=soft)
    draw.rounded_rectangle((470, 150, 520, 238), radius=16, fill=accent)

    cols = 3 if profile == "catalog_discovery" else 4
    available_x0 = hero_x
    gap = 12
    total_w = 604 - hero_x
    card_w = int((total_w - gap * (cols - 1)) / cols)
    for i in range(cols):
        x0 = available_x0 + i * (card_w + gap)
        draw_product(draw, (x0, 300, x0 + card_w, 505), "#FFFFFF", accent if i % 2 == 0 else dark, i + cycle_index)
    draw.text((hero_x, 530), "SPEDIZIONE CHIARA   •   PAGAMENTI SICURI   •   SUPPORTO", font=font(11, True), fill=dark)
    return browser


def rmp_composition(job: dict) -> Image.Image:
    profile = str(job.get("layout_profile") or "mobile_speed")
    bg, accent, soft, dark = theme_palette(profile)
    canvas = Image.new("RGB", SIZE, "#FFFFFF")
    draw = ImageDraw.Draw(canvas)

    draw.text((55, 42), "REAL MEDIA PRO", font=font(29, True), fill=dark)
    draw.text((55, 82), "ECOMMERCE · SHOPIFY · DIGITAL STRATEGY", font=font(14, True), fill=accent)

    title = str(job.get("title") or "SHOPIFY · SITO ORIGINALE")
    tf, lines = fit_lines(draw, title, 420, 4, start_size=54, min_size=34)
    y = 145
    for idx, line in enumerate(lines):
        draw.text((55, y), line, font=tf, fill=accent if idx == len(lines) - 1 else dark)
        y += int(getattr(tf, "size", 40) * 1.12)

    draw.text((55, 395), f"Ispirato ai principi del tema Shopify {job.get('theme_name','')}", font=font(17, True), fill=dark)
    draw.text((55, 428), "Layout e immagini completamente originali · nessuna copia", font=font(14), fill="#4D5A6B")

    features = feature_labels(profile)
    for i, label in enumerate(features):
        yy = 482 + i * 62
        draw.ellipse((58, yy, 88, yy + 30), fill=accent)
        draw.text((101, yy + 2), label, font=font(17, True), fill=dark)

    mock = ecommerce_browser(profile, int(job.get("cycle_index", 0)))
    rounded_paste(canvas, mock, (430, 130, 1040, 710), radius=28)

    desc = str(job.get("theme_description_it") or "")
    draw.rounded_rectangle((55, 760, 1025, 950), radius=24, fill=soft)
    draw.text((85, 790), "DAL TEMA ALLA STRATEGIA", font=font(16, True), fill=accent)
    wrapped = textwrap.wrap(desc, width=84)[:4]
    yy = 828
    for line in wrapped:
        draw.text((85, yy), line, font=font(17), fill=dark)
        yy += 29
    draw.rounded_rectangle((55, 965, 590, 1020), radius=16, fill=accent)
    draw.text((82, 980), "ANALISI STRATEGICA GRATUITA", font=font(19, True), fill="#FFFFFF")

    presenter_footer(canvas, "rmp")
    return canvas


def record(history: dict, cid: str, source: str, job_id: str, source_type: str) -> None:
    brands = history.setdefault("brands", {})
    brand = brands.setdefault(cid, {"recent": []})
    rows = list(brand.get("recent", []))
    key = source.strip().lower()
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
    if len(jobs) != 10:
        raise RuntimeError(f"Expected 10 current-cycle jobs, got {len(jobs)}")
    if sum(j.get("client_id") == "f1-immobiliare" for j in jobs) != 5:
        raise RuntimeError("Expected exactly five F1 jobs")
    if sum(j.get("client_id") == "real-media-pro" for j in jobs) != 5:
        raise RuntimeError("Expected exactly five RMP jobs")
    if any(j.get("format") != "photo" for j in jobs):
        raise RuntimeError("PHOTO-ONLY renderer received a non-photo job")

    history = load_json(HISTORY, {"version": 1, "brands": {}})
    local_urls = configured_f1_local_candidates()
    f1_used: set[str] = set()

    for job in jobs:
        cid = str(job.get("client_id") or "")
        pos = int(job.get("cycle_position", 1))
        out = ROOT / str(job["media"])
        out.parent.mkdir(parents=True, exist_ok=True)

        if cid == "f1-immobiliare":
            source_url = ""
            image = None
            # rotate through approved local sources and never use any fallback.
            for offset in range(len(local_urls)):
                candidate = local_urls[(pos - 1 + offset) % len(local_urls)]
                if candidate in f1_used:
                    continue
                try:
                    image = get_remote_image(candidate)
                    source_url = candidate
                    f1_used.add(candidate)
                    break
                except Exception as exc:
                    print(f"WARN local F1 image rejected {candidate}: {exc}")
            if image is None:
                raise RuntimeError(f"F1 local visual policy blocked {job.get('id')}: no approved Valle di Susa image was usable")
            final = f1_composition(image, str(job.get("title") or ""), pos)
            source_type = "f1-approved-local-valle-susa"
            transform = "f1-local-photo-plus-presenter-footer"
            source_id = source_url

        elif cid == "real-media-pro":
            theme_url = str(job.get("theme_source_url") or "").strip()
            host = urlsplit(theme_url).netloc.lower()
            if host != "themes.shopify.com":
                raise RuntimeError(f"RMP source policy violation: {theme_url!r} is not themes.shopify.com")
            if not bool(job.get("shopify_theme_store_only", False)) or bool(job.get("copy_shopify_images", True)):
                raise RuntimeError("RMP source policy violation: Theme Store only + zero copied images required")
            final = rmp_composition(job)
            source_type = "shopify-theme-store-description-only"
            transform = "original-generated-ecommerce-mockup-plus-presenter-footer"
            source_id = theme_url
        else:
            raise RuntimeError(f"Unexpected client in strict publication renderer: {cid}")

        final.save(out, "JPEG", quality=94, optimize=True, progressive=True)
        if not out.exists() or out.stat().st_size < 20000:
            raise RuntimeError(f"Static publication was not rendered correctly: {out}")

        job["visual_asset_urls"] = [source_id]
        job["visual_source"] = source_type
        job["visual_transform"] = transform
        job["visual_count"] = 1
        job["fresh_visual_count"] = 1
        job["reused_visual_count"] = 0
        job["production_status"] = "PHOTO READY"
        job["publication_ready"] = True
        job["output_type"] = "static-photo"
        job["no_video"] = True
        job["no_audio"] = True
        job["no_reel"] = True
        record(history, cid, source_id, str(job.get("id") or ""), source_type)
        print(f"PHOTO READY {cid}: {out} <- {source_type}: {source_id}")

    history["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    q["output_policy"] = "10 STATIC PUBLICATIONS - F1 LOCAL + PRESENTER FOOTER - RMP SHOPIFY THEME STORE DESCRIPTION ONLY + ORIGINAL MOCKUPS"
    q["updated_by"] = "Approved 5+5 publication renderer"
    save_json(HISTORY, history)
    save_json(QUEUE, q)
    print("DONE: 5 F1 + 5 RMP; local F1 visuals; zero copied Shopify theme images; presenter footer on every graphic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
