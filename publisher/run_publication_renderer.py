#!/usr/bin/env python3
"""F1 Immobiliare premium social renderer.

The GitHub Actions workflow remains the orchestration engine. This module only
owns the F1 visual system. Real Media Pro keeps using render_photos_only.

Design direction: premium real-estate social creative, large property/territory
photo, one strong headline, F1 green accents, compact CTA and compact footer.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import qrcode
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

import render_photos_only as renderer

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
HISTORY = ROOT / "publisher" / "image_history.json"
F1_CFG = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
SIZE = (1080, 1350)

_original_get_remote_image = renderer.get_remote_image
_request_count = 0

# F1 official operational data.
F1_PHONE_PRIMARY = "371 370 8294"
F1_PHONE_SECONDARY = "371 424 6300"
F1_ADDRESS = "Via Umberto I, 96"
F1_CITY = "Sant'Antonino di Susa (TO)"
F1_WEBSITE = "www.f1immobiliare.com"
F1_WEBSITE_URL = "https://www.f1immobiliare.com"

GREEN = "#92C205"
GREEN_DARK = "#6F9E00"
BLACK = "#070907"
BLACK_SOFT = "#101610"
WHITE = "#F7F7F4"
MUTED = "#C7CDC8"
GOLD = "#C8A15A"

LOCAL_MARKERS = (
    "avigliana", "valle di susa", "val di susa", "susa", "almese", "sant'ambrogio",
    "oulx", "bardonecchia", "sauze", "condove", "villar dora", "bussoleno",
    "borgone", "chiusa di san michele", "piemonte", "torino",
)
RESIDENTIAL_MARKERS = (
    "residen", "appart", "villa", "villetta", "house", "home", "casa", "palazzina",
    "building", "abitaz", "architecture", "architettura",
)
TOWNSCAPE_MARKERS = (
    "centro storico", "borgo", "street", "piazza", "town", "village", "quartiere",
)
FORBIDDEN_MARKERS = (
    "owl", "gufo", "bird", "uccello", "cat", "gatto", "dog", "cane", "animal", "animale",
    "food", "cibo", "car", "auto", "motor", "portrait", "ritratto",
)


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fnt(size: int, bold: bool = False, condensed: bool = False, italic: bool = False):
    candidates: list[str] = []
    if condensed and bold:
        candidates.append("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf")
    if italic:
        candidates.append("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf")
    if bold:
        candidates.append("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    else:
        candidates.append("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def source_text(item: dict) -> str:
    return (str(item.get("credit") or "") + " " + str(item.get("url") or "")).lower()


def source_kind(item: dict) -> set[str]:
    text = source_text(item)
    kinds: set[str] = set()
    if any(x in text for x in RESIDENTIAL_MARKERS):
        kinds.add("residential")
    if any(x in text for x in ("villa", "villetta", "house", "home", "casa")):
        kinds.add("house")
    if any(x in text for x in ("appart", "palazzina", "condominio")):
        kinds.add("apartment")
    if any(x in text for x in TOWNSCAPE_MARKERS):
        kinds.add("townscape")
    if any(x in text for x in LOCAL_MARKERS):
        kinds.add("local")
    return kinds


def job_need(job: dict) -> set[str]:
    text = (str(job.get("title") or "") + " " + str(job.get("caption") or "")).lower()
    if job.get("service_id") == "service_4_recruiting":
        return {"local"}
    need = {"residential"}
    if "appartament" in text:
        need.add("apartment")
    if any(x in text for x in ("villa", "villetta", "casa", "abitazione")):
        need.add("house")
    if any(x in text for x in ("microzona", "zona", "mercato", "territorio")):
        need.add("townscape")
    return need


def recent_usage_penalty(url: str, history: dict) -> int:
    rows = history.get("brands", {}).get("f1-immobiliare", {}).get("recent", [])
    key = url.strip().lower()
    matching = [r for r in rows if str(r.get("url") or r.get("key") or "").strip().lower() == key]
    if not matching:
        return 0
    try:
        used = datetime.fromisoformat(str(matching[-1].get("used_at") or "").replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - used).total_seconds() / 3600
    except Exception:
        return 3
    if age_hours < 4:
        return 12
    if age_hours < 12:
        return 7
    if age_hours < 24:
        return 4
    if age_hours < 72:
        return 2
    return 0


def semantic_score(job: dict, item: dict, history: dict) -> int:
    text = source_text(item)
    if any(x in text for x in FORBIDDEN_MARKERS):
        return -10000
    kinds = source_kind(item)
    need = job_need(job)
    score = 0
    if "local" in kinds:
        score += 15
    if "residential" in kinds:
        score += 12
    if "apartment" in need and "apartment" in kinds:
        score += 8
    if "house" in need and "house" in kinds:
        score += 7
    if "townscape" in need and "townscape" in kinds:
        score += 8
    score -= recent_usage_penalty(str(item.get("url") or ""), history)
    return score


def smart_f1_candidates() -> list[str]:
    cfg = load_json(F1_CFG, {})
    queue = load_json(QUEUE, {"jobs": []})
    history = load_json(HISTORY, {"brands": {}})
    cycle = queue.get("current_cycle")
    jobs = sorted(
        [j for j in queue.get("jobs", []) if j.get("cycle_key") == cycle and j.get("client_id") == "f1-immobiliare"],
        key=lambda j: int(j.get("cycle_position", 0)),
    )
    if len(jobs) != 5:
        raise RuntimeError(f"F1 premium renderer expected 5 jobs, got {len(jobs)}")

    sources: list[dict] = []
    for item in cfg.get("brand", {}).get("photo_sources", []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        text = source_text(item)
        if not url or any(x in text for x in FORBIDDEN_MARKERS):
            continue
        kinds = source_kind(item)
        if "local" in kinds or "residential" in kinds:
            sources.append(item)
    if len(sources) < 5:
        raise RuntimeError("F1 requires at least five approved local/residential sources")

    unused = list(sources)
    ordered: list[str] = []
    for job in jobs:
        ranked = sorted(unused, key=lambda item: semantic_score(job, item, history), reverse=True)
        best = ranked[0]
        if semantic_score(job, best, history) < 0:
            raise RuntimeError(f"No coherent F1 image for {job.get('id')}")
        ordered.append(str(best["url"]))
        unused.remove(best)
    ordered.extend(str(item["url"]) for item in unused)
    return ordered


def robust_local_get(url: str):
    global _request_count
    if _request_count:
        time.sleep(3)
    _request_count += 1
    last_error: Exception | None = None
    for extra_wait in (0, 10, 20):
        if extra_wait:
            time.sleep(extra_wait)
        try:
            return _original_get_remote_image(url)
        except requests.HTTPError as exc:
            last_error = exc
            if getattr(exc.response, "status_code", None) != 429:
                raise
        except Exception as exc:
            last_error = exc
            raise
    raise last_error or RuntimeError("F1 image download failed")


def current_job(position: int) -> dict:
    q = load_json(QUEUE, {"jobs": []})
    cycle = q.get("current_cycle")
    rows = [j for j in q.get("jobs", []) if j.get("cycle_key") == cycle and j.get("client_id") == "f1-immobiliare"]
    for j in rows:
        if int(j.get("cycle_position", 0)) == int(position):
            return j
    rows = sorted(rows, key=lambda x: int(x.get("cycle_position", 0)))
    if 1 <= position <= len(rows):
        return rows[position - 1]
    raise RuntimeError(f"Missing F1 job for position {position}")


def fit_lines(draw: ImageDraw.ImageDraw, text: str, width: int, max_lines: int = 4, start: int = 76, minimum: int = 38):
    words = " ".join(str(text or "").upper().split()).split()
    for size in range(start, minimum - 1, -2):
        font = fnt(size, True, True)
        lines: list[str] = []
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if draw.textbbox((0, 0), test, font=font)[2] <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        if len(lines) <= max_lines:
            return font, lines
    return fnt(minimum, True, True), [" ".join(words)]


def draw_brand(draw: ImageDraw.ImageDraw, x: int, y: int, dark: bool = True) -> None:
    fg = WHITE if dark else BLACK
    draw.text((x, y), "F1", font=fnt(66, True, True), fill=fg)
    draw.line((x + 8, y + 7, x + 62, y - 16, x + 113, y + 8), fill=GREEN, width=5, joint="curve")
    draw.text((x + 118, y + 12), "IMMOBILIARE", font=fnt(24, True, True), fill=fg)
    draw.text((x + 119, y + 43), "CASA E IMPRESE", font=fnt(12, True), fill=GREEN)


def service_copy(job: dict) -> tuple[str, list[str], str]:
    sid = str(job.get("service_id") or "")
    role = str(job.get("role") or "")
    if sid == "service_1_agent_pricing":
        return "VALUTAZIONE PROFESSIONALE", ["Comparabili reali", "Microzona e domanda", "Strategia di prezzo"], "RICHIEDI LA VALUTAZIONE"
    if sid == "service_2_piano_vendita":
        return "PIANO DI VENDITA F1", ["Portali, sito e social", "Marketing territoriale", "Rete e banca dati F1"], "SCOPRI COME VENDEREMMO CASA"
    if sid == "service_3_bonus_casa":
        return "GUIDE E INFORMAZIONI CASA", ["Fonti ufficiali", "Dati verificati", "Aggiornamenti prima del post"], "INFORMATI PRIMA DI COMPRARE"
    if sid == "service_4_recruiting" and role == "coordinatrice":
        return "LAVORA CON F1", ["Front office", "CRM e appuntamenti", "Supporto alla squadra"], "CANDIDATI"
    if sid == "service_4_recruiting":
        return "LAVORA CON F1", ["Anche prima esperienza", "Formazione interna", "Percorso di crescita"], "CANDIDATI"
    return "F1 IMMOBILIARE · VALLE DI SUSA", ["Territorio", "Metodo", "Rapporto diretto"], "CONTATTACI"


def qr_image(size: int = 104) -> Image.Image:
    qr = qrcode.QRCode(version=3, box_size=5, border=1)
    qr.add_data(F1_WEBSITE_URL)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB").resize((size, size), Image.Resampling.NEAREST)


def prepare_photo(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    photo = ImageOps.fit(image.convert("RGB"), size, Image.Resampling.LANCZOS)
    photo = ImageEnhance.Contrast(photo).enhance(1.06)
    photo = ImageEnhance.Color(photo).enhance(0.96)
    return photo


def dark_gradient(size: tuple[int, int], horizontal: bool = True) -> Image.Image:
    w, h = size
    grad = Image.new("L", size, 0)
    px = grad.load()
    if horizontal:
        for x in range(w):
            alpha = int(max(0, min(220, 220 * (1 - x / max(1, w * 0.75)))))
            for y in range(h):
                px[x, y] = alpha
    else:
        for y in range(h):
            alpha = int(max(0, min(235, 235 * ((y / max(1, h)) ** 1.8))))
            for x in range(w):
                px[x, y] = alpha
    overlay = Image.new("RGBA", size, (7, 9, 7, 0))
    overlay.putalpha(grad)
    return overlay


def draw_headline(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, width: int, max_lines: int = 4, start: int = 74) -> int:
    font, lines = fit_lines(draw, text, width, max_lines=max_lines, start=start, minimum=38)
    green_words = {"CASA", "VENDERE", "VENDITA", "VALORE", "DATI", "PREZZO", "F1", "TERRITORIO", "CRESCITA", "ESPERIENZA"}
    yy = y
    for line in lines:
        cursor = x
        for word in line.split():
            color = GREEN if any(key in word for key in green_words) else WHITE
            draw.text((cursor, yy), word, font=font, fill=color)
            cursor += draw.textbbox((0, 0), word + " ", font=font)[2]
        yy += int(getattr(font, "size", 54) * 1.03)
    return yy


def draw_cta(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, width: int = 500) -> None:
    h = 64
    draw.rounded_rectangle((x, y, x + width, y + h), radius=18, fill=GREEN)
    font = fnt(22, True, True)
    label = text[:42]
    bbox = draw.textbbox((0, 0), label, font=font)
    tx = x + max(18, (width - (bbox[2] - bbox[0])) // 2)
    draw.text((tx, y + 18), label, font=font, fill=BLACK)


def draw_bullets(draw: ImageDraw.ImageDraw, bullets: list[str], x: int, y: int, max_width: int = 500) -> int:
    yy = y
    for item in bullets[:3]:
        draw.ellipse((x, yy + 8, x + 12, yy + 20), fill=GREEN)
        draw.text((x + 26, yy), item, font=fnt(21, True), fill=WHITE)
        yy += 38
    return yy


def draw_footer(canvas: Image.Image) -> None:
    d = ImageDraw.Draw(canvas)
    y0 = 1165
    d.rectangle((0, y0, 1080, 1350), fill=BLACK)
    d.rectangle((0, y0, 1080, y0 + 6), fill=GREEN)
    draw_brand(d, 42, 1194, dark=True)
    d.text((390, 1200), F1_ADDRESS, font=fnt(18, True), fill=WHITE)
    d.text((390, 1230), F1_CITY, font=fnt(17), fill=MUTED)
    d.text((390, 1275), F1_PHONE_PRIMARY, font=fnt(22, True), fill=GREEN)
    d.text((565, 1275), F1_PHONE_SECONDARY, font=fnt(19, True), fill=WHITE)
    d.text((760, 1203), F1_WEBSITE, font=fnt(18, True), fill=WHITE)
    qr = qr_image(100)
    canvas.paste(qr, (930, 1200))
    d.text((760, 1243), "NON A SENSAZIONE.", font=fnt(15, True), fill=MUTED)
    d.text((760, 1266), "CON I DATI.", font=fnt(18, True), fill=GREEN)


def variant_left_overlay(image: Image.Image, title: str, label: str, bullets: list[str], cta: str) -> Image.Image:
    canvas = prepare_photo(image, SIZE)
    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(dark_gradient(SIZE, horizontal=True))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((38, 36, 445, 128), radius=16, fill=(7, 9, 7, 218), outline=GREEN, width=2)
    draw_brand(d, 58, 49, dark=True)
    d.text((58, 205), label, font=fnt(20, True, True), fill=GREEN)
    y = draw_headline(d, title, 58, 250, 560, max_lines=5, start=70)
    d.line((58, y + 12, 430, y + 12), fill=GREEN, width=4)
    draw_bullets(d, bullets, 62, y + 42)
    draw_cta(d, cta, 58, 1010, 510)
    out = canvas.convert("RGB")
    draw_footer(out)
    return out


def variant_photo_top(image: Image.Image, title: str, label: str, bullets: list[str], cta: str) -> Image.Image:
    canvas = Image.new("RGB", SIZE, BLACK)
    photo = prepare_photo(image, (1080, 760))
    canvas.paste(photo, (0, 0))
    shade = Image.new("RGBA", (1080, 760), (0, 0, 0, 0))
    shade.alpha_composite(dark_gradient((1080, 760), horizontal=False))
    canvas.paste(shade.convert("RGB"), (0, 0), shade.getchannel("A"))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((38, 34, 445, 126), radius=16, fill=BLACK_SOFT, outline=GREEN, width=2)
    draw_brand(d, 58, 47, dark=True)
    d.text((58, 700), label, font=fnt(20, True, True), fill=GREEN)
    y = draw_headline(d, title, 58, 760, 920, max_lines=3, start=64)
    draw_bullets(d, bullets, 60, min(y + 18, 1020))
    draw_cta(d, cta, 630, 1060, 390)
    draw_footer(canvas)
    return canvas


def variant_split(image: Image.Image, title: str, label: str, bullets: list[str], cta: str) -> Image.Image:
    canvas = Image.new("RGB", SIZE, BLACK)
    photo = prepare_photo(image, (650, 1165))
    canvas.paste(photo, (430, 0))
    d = ImageDraw.Draw(canvas)
    d.polygon([(410, 0), (510, 0), (390, 1165), (290, 1165)], fill=GREEN)
    d.polygon([(380, 0), (445, 0), (325, 1165), (260, 1165)], fill=BLACK)
    draw_brand(d, 48, 48, dark=True)
    d.text((50, 220), label, font=fnt(19, True, True), fill=GREEN)
    y = draw_headline(d, title, 50, 265, 360, max_lines=6, start=56)
    draw_bullets(d, bullets, 52, y + 25, 340)
    draw_cta(d, cta, 50, 1035, 340)
    draw_footer(canvas)
    return canvas


def variant_bottom_overlay(image: Image.Image, title: str, label: str, bullets: list[str], cta: str) -> Image.Image:
    canvas = prepare_photo(image, SIZE).convert("RGBA")
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, 1080, 145), fill=(7, 9, 7, 205))
    od.rectangle((0, 650, 1080, 1165), fill=(7, 9, 7, 220))
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.2))
    canvas.alpha_composite(overlay)
    d = ImageDraw.Draw(canvas)
    draw_brand(d, 48, 38, dark=True)
    d.text((58, 700), label, font=fnt(20, True, True), fill=GREEN)
    y = draw_headline(d, title, 58, 750, 900, max_lines=4, start=68)
    draw_bullets(d, bullets, 62, min(y + 16, 1035))
    draw_cta(d, cta, 650, 1060, 370)
    out = canvas.convert("RGB")
    draw_footer(out)
    return out


def premium_f1_composition(image: Image.Image, title: str, position: int) -> Image.Image:
    job = current_job(position)
    sid = str(job.get("service_id") or "")
    label, bullets, cta = service_copy(job)

    main_image = image
    if sid == "service_4_recruiting":
        presenter_name = "francesca" if str(job.get("role") or "") == "coordinatrice" else "joseph"
        try:
            main_image = renderer.load_presenter(presenter_name)
        except Exception:
            main_image = image

    variant = (int(position) - 1) % 4
    if variant == 0:
        return variant_left_overlay(main_image, title, label, bullets, cta)
    if variant == 1:
        return variant_photo_top(main_image, title, label, bullets, cta)
    if variant == 2:
        return variant_split(main_image, title, label, bullets, cta)
    return variant_bottom_overlay(main_image, title, label, bullets, cta)


def validate_f1_outputs() -> None:
    q = load_json(QUEUE, {"jobs": []})
    cycle = q.get("current_cycle")
    rows = [j for j in q.get("jobs", []) if j.get("cycle_key") == cycle and j.get("client_id") == "f1-immobiliare"]
    if len(rows) != 5:
        raise RuntimeError(f"Expected 5 F1 outputs, got {len(rows)}")

    for job in rows:
        if not job.get("service_id"):
            raise RuntimeError(f"Legacy/unclassified F1 job blocked: {job.get('id')}")
        rel = str(job.get("media") or "")
        path = Path(rel)
        if not path.exists():
            raise RuntimeError(f"Missing F1 rendered media: {rel}")
        im = Image.open(path).convert("RGB")
        if im.size != SIZE:
            raise RuntimeError(f"Wrong F1 canvas size for {rel}: {im.size}")

        footer = im.crop((0, 1165, 1080, 1350))
        pixels = list(footer.getdata())
        dark_ratio = sum(1 for r, g, b in pixels if r < 40 and g < 45 and b < 40) / max(1, len(pixels))
        green_ratio = sum(1 for r, g, b in pixels if g > r * 1.35 and g > b * 1.25 and g > 90) / max(1, len(pixels))
        if dark_ratio < 0.55 or green_ratio < 0.004:
            raise RuntimeError(f"F1 premium visual gate failed for {rel}: dark={dark_ratio:.3f}, green={green_ratio:.3f}")

        job["premium_render_v3"] = True
        job["visual_compliance"] = "F1_PREMIUM_SOCIAL_V3"
        job["publication_ready"] = True

    save_json(QUEUE, q)
    print("F1 PREMIUM VISUAL GATE PASSED: 5/5")


renderer.get_remote_image = robust_local_get
renderer.configured_f1_local_candidates = smart_f1_candidates
renderer.f1_composition = premium_f1_composition

if __name__ == "__main__":
    rc = renderer.main()
    if rc not in (None, 0):
        raise SystemExit(rc)
    validate_f1_outputs()
    raise SystemExit(0)
