#!/usr/bin/env python3
"""Render F1 Immobiliare with the binding light institutional brand system.

This module deliberately overrides the old generic F1 social-card composition.
The F1 output must visibly contain: institutional header/wordmark, black-green
slanted separator, relevant visual, three benefit boxes, contact block with QR,
and black institutional footer. If that signature is missing the run fails.

Real Media Pro continues to use render_photos_only unchanged.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import qrcode
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

import render_photos_only as renderer

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
HISTORY = ROOT / "publisher" / "image_history.json"
F1_CFG = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
SIZE = (1080, 1350)

_original_get_remote_image = renderer.get_remote_image
_request_count = 0

GREEN = "#4E9E15"
GREEN_DARK = "#2D760B"
BLACK = "#0A0D0A"
WHITE = "#FFFFFF"
SOFT = "#F5F7F3"
LINE = "#D7DDD3"
MUTED = "#555D55"

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
    candidates = []
    if condensed and bold:
        candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"]
    if italic:
        candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"]
    if bold:
        candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    else:
        candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
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
    if "apartment" in need:
        score += 8 if "apartment" in kinds else 0
    if "house" in need:
        score += 7 if "house" in kinds else 0
    if "townscape" in need:
        score += 8 if "townscape" in kinds else 0
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
        raise RuntimeError(f"F1 institutional renderer expected 5 jobs, got {len(jobs)}")

    sources = []
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
    if 1 <= position <= len(rows):
        return sorted(rows, key=lambda x: int(x.get("cycle_position", 0)))[position - 1]
    raise RuntimeError(f"Missing F1 job for position {position}")


def draw_f1_wordmark(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    # Roof/signature.
    draw.line((x + 8, y + 38, x + 105, y - 4, x + 185, y + 45), fill=GREEN, width=8, joint="curve")
    draw.line((x + 25, y + 28, x + 25, y + 62), fill=GREEN, width=6)
    draw.text((x, y + 28), "F", font=fnt(112, True, True), fill=BLACK)
    draw.text((x + 105, y + 28), "1", font=fnt(112, True, True), fill="#66C500")
    draw.text((x, y + 145), "IMMOBILIARE", font=fnt(32, True, True), fill=BLACK)
    draw.text((x + 2, y + 182), "C A S A   E   I M P R E S E", font=fnt(13, False), fill=BLACK)
    draw.line((x, y + 212, x + 345, y + 212), fill=GREEN, width=3)
    draw.text((x, y + 224), "LA TUA CASA, IL NOSTRO OBIETTIVO", font=fnt(11, False), fill=BLACK)


def draw_slanted_photo(canvas: Image.Image, image: Image.Image, box=(370, 195, 1080, 790)) -> None:
    x0, y0, x1, y1 = box
    photo = ImageOps.fit(image.convert("RGB"), (x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    layer = Image.new("RGB", SIZE, WHITE)
    layer.paste(photo, (x0, y0))
    mask = Image.new("L", SIZE, 0)
    md = ImageDraw.Draw(mask)
    md.polygon([(x0 + 120, y0), (x1, y0), (x1, y1), (x0, y1)], fill=255)
    canvas.paste(layer, (0, 0), mask)
    d = ImageDraw.Draw(canvas)
    d.polygon([(x0 + 92, y0), (x0 + 116, y0), (x0 - 2, y1), (x0 - 28, y1)], fill=BLACK)
    d.polygon([(x0 + 116, y0), (x0 + 132, y0), (x0 + 12, y1), (x0 - 2, y1)], fill=GREEN)


def fit_title(draw: ImageDraw.ImageDraw, text: str, width: int, max_lines: int = 4):
    words = " ".join(str(text or "").upper().split()).split()
    for size in range(56, 31, -2):
        f = fnt(size, True, True)
        lines, line = [], ""
        for w in words:
            test = (line + " " + w).strip()
            if draw.textbbox((0, 0), test, font=f)[2] <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = w
        if line:
            lines.append(line)
        if len(lines) <= max_lines:
            return f, lines
    return fnt(32, True, True), [" ".join(words)]


def service_copy(job: dict) -> tuple[str, list[tuple[str, str]], str]:
    sid = job.get("service_id")
    role = str(job.get("role") or "")
    if sid == "service_1_agent_pricing":
        return (
            "VALUTAZIONE PROFESSIONALE CON AGENT PRICING",
            [("DATI REALI", "Comparabili e mercato"), ("ANALISI PROFESSIONALE", "Microzona e domanda"), ("STRATEGIA DI PREZZO", "Una scelta motivata")],
            "RICHIEDI UNA VALUTAZIONE PROFESSIONALE",
        )
    if sid == "service_2_piano_vendita":
        return (
            "NON UN SEMPLICE ANNUNCIO: UN PIANO COSTRUITO PER LA TUA CASA",
            [("PRESENZA ONLINE", "Portali, sito e social"), ("MARKETING TERRITORIALE", "Fino a 2.500 volantini"), ("RETE F1", "Banca dati, WhatsApp, email")],
            "VUOI SAPERE COME VENDEREMMO LA TUA CASA?",
        )
    if sid == "service_3_bonus_casa":
        return (
            "INFORMAZIONI CASA: PRIMA LE FONTI UFFICIALI",
            [("FONTI UFFICIALI", "Agenzia delle Entrate"), ("DATI VERIFICATI", "Niente cifre inventate"), ("AGGIORNAMENTI", "Controllo prima del post")],
            "INFORMATI PRIMA DI COMPRARE",
        )
    if sid == "service_4_recruiting" and role == "coordinatrice":
        return (
            "UN RUOLO CENTRALE NELL'ORGANIZZAZIONE DELL'AGENZIA",
            [("FRONT OFFICE", "Clienti e telefonate"), ("BANCA DATI E AGENDA", "CRM e appuntamenti"), ("SUPPORTO ALLA SQUADRA", "Metodo e organizzazione")],
            "CANDIDATI",
        )
    if sid == "service_4_recruiting":
        return (
            "ANCHE ALLA PRIMA ESPERIENZA: FORMAZIONE, ZONA E CRESCITA",
            [("PRIMA ESPERIENZA", "Cerchiamo potenziale"), ("FORMAZIONE INTERNA", "Impari un metodo"), ("PERCORSO DI CRESCITA", "Da junior a responsabilità")],
            "CANDIDATI",
        )
    return (
        "F1 IMMOBILIARE · VALLE DI SUSA",
        [("TERRITORIO", "Conosciamo la zona"), ("METODO", "Processo strutturato"), ("PERSONE", "Rapporto diretto")],
        "CONTATTACI",
    )


def qr_image(size: int = 118) -> Image.Image:
    qr = qrcode.QRCode(version=3, box_size=5, border=1)
    qr.add_data("https://www.f1immobiliare.com")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((size, size), Image.Resampling.NEAREST)


def draw_three_boxes(draw: ImageDraw.ImageDraw, boxes: list[tuple[str, str]]) -> None:
    y0, y1 = 825, 995
    gap = 14
    x0 = 40
    total = 1000
    w = (total - 2 * gap) // 3
    for i, (title, body) in enumerate(boxes[:3]):
        x = x0 + i * (w + gap)
        draw.rounded_rectangle((x, y0, x + w, y1), radius=16, fill=WHITE, outline="#BFC8BA", width=2)
        draw.ellipse((x + 18, y0 + 27, x + 78, y0 + 87), outline=GREEN, width=4)
        # Simple service-neutral icon signature.
        draw.ellipse((x + 39, y0 + 48, x + 57, y0 + 66), fill=GREEN)
        draw.line((x + 48, y0 + 39, x + 48, y0 + 28), fill=GREEN, width=3)
        draw.text((x + 92, y0 + 26), title, font=fnt(19, True, True), fill=BLACK)
        draw.text((x + 92, y0 + 62), body, font=fnt(14, False), fill=MUTED)
        draw.line((x + 92, y0 + 96, x + w - 18, y0 + 96), fill=GREEN, width=2)
        draw.text((x + 92, y0 + 110), "F1 IMMOBILIARE", font=fnt(12, True), fill=GREEN_DARK)


def draw_contact_and_footer(canvas: Image.Image, cta: str, sid: str) -> None:
    d = ImageDraw.Draw(canvas)
    # Contact panel.
    d.rounded_rectangle((40, 1010, 1040, 1185), radius=18, fill=WHITE, outline="#AAB5A5", width=2)
    d.ellipse((62, 1034, 168, 1140), fill=GREEN)
    d.text((88, 1051), "☎", font=fnt(54, True), fill=WHITE)
    label = "Per info e candidature:" if sid == "service_4_recruiting" else "Per informazioni:"
    d.text((190, 1030), label, font=fnt(20, True), fill=BLACK)
    d.text((190, 1066), "371 370 8294", font=fnt(34, True, True), fill=GREEN_DARK)
    d.text((500, 1066), "371 424 6300", font=fnt(30, True, True), fill=GREEN_DARK)
    d.text((190, 1110), cta, font=fnt(14, True), fill=BLACK)
    qr = qr_image(118)
    canvas.paste(qr, (835, 1028))
    d.text((958, 1043), "VISITA", font=fnt(12, True), fill=BLACK)
    d.text((958, 1060), "IL SITO", font=fnt(12, True), fill=BLACK)
    d.text((958, 1077), "WEB", font=fnt(12, True), fill=GREEN_DARK)

    # Footer: same institutional geometry as approved F1 artwork.
    d.rectangle((0, 1200, 1080, 1350), fill="#0B100C")
    d.ellipse((32, 1232, 100, 1300), outline=WHITE, width=4)
    d.ellipse((55, 1250, 77, 1272), fill=WHITE)
    d.polygon([(66, 1292), (52, 1266), (80, 1266)], fill=WHITE)
    d.text((120, 1230), "Via Roma, 8", font=fnt(18, True), fill=WHITE)
    d.text((120, 1260), "Sant'Antonino di Susa (TO)", font=fnt(17), fill=WHITE)
    d.line((365, 1222, 365, 1326), fill="#8E968F", width=2)
    d.text((405, 1232), "F1", font=fnt(58, True, True), fill=WHITE)
    d.line((490, 1236, 555, 1209, 612, 1238), fill=GREEN, width=5, joint="curve")
    d.text((500, 1251), "IMMOBILIARE", font=fnt(22, True, True), fill=WHITE)
    d.text((503, 1283), "C A S A   E   I M P R E S E", font=fnt(10), fill=WHITE)
    d.line((500, 1305, 690, 1305), fill=GREEN, width=2)
    d.line((715, 1222, 715, 1326), fill="#8E968F", width=2)
    d.text((744, 1235), "www.f1immobiliare.com", font=fnt(17, True), fill=WHITE)
    for i, s in enumerate(("f", "◎", "▶", "in")):
        cx = 765 + i * 60
        d.ellipse((cx, 1274, cx + 38, 1312), fill=WHITE)
        d.text((cx + 9, 1281), s, font=fnt(13, True), fill=BLACK)
    d.text((995, 1228), "CASE", font=fnt(12, True), fill=WHITE)
    d.text((995, 1248), "PERSONE", font=fnt(12, True), fill=WHITE)
    d.text((995, 1268), "TERRITORIO", font=fnt(12, True), fill=WHITE)
    d.text((995, 1288), "FUTURO", font=fnt(12, True), fill=WHITE)


def institutional_f1_composition(image: Image.Image, title: str, position: int) -> Image.Image:
    job = current_job(position)
    sid = str(job.get("service_id") or "")
    subline, boxes, cta = service_copy(job)

    canvas = Image.new("RGB", SIZE, WHITE)
    d = ImageDraw.Draw(canvas)

    # Header identity.
    draw_f1_wordmark(d, 42, 18)
    d.text((735, 52), "Affidati a chi", font=fnt(24, False, italic=True), fill=BLACK)
    d.text((755, 82), "conosce il territorio", font=fnt(24, False, italic=True), fill=BLACK)
    d.line((760, 119, 1015, 92), fill=GREEN, width=4)

    # Main visual. Recruiting uses the real internal presenter assets, never generic stock.
    main_image = image
    if sid == "service_4_recruiting":
        presenter_name = "francesca" if str(job.get("role") or "") == "coordinatrice" else "joseph"
        try:
            main_image = renderer.load_presenter(presenter_name)
        except Exception:
            main_image = image
    draw_slanted_photo(canvas, main_image)
    d = ImageDraw.Draw(canvas)

    # Headline block on white left column.
    tf, lines = fit_title(d, title, 300, max_lines=5)
    y = 310
    green_words = {"DATI", "VALORE", "VENDITA", "PIANO", "TALENTO", "ESPERIENZA", "COORDINATRICE", "BONUS", "CASA", "F1"}
    for line in lines:
        words = line.split()
        cursor = 42
        for w in words:
            color = GREEN_DARK if any(k in w for k in green_words) else BLACK
            d.text((cursor, y), w, font=tf, fill=color)
            cursor += d.textbbox((0, 0), w + " ", font=tf)[2]
        y += int(getattr(tf, "size", 42) * 1.04)
    d.line((42, y + 6, 320, y + 6), fill=GREEN, width=3)

    sf, slines = fit_title(d, subline, 300, max_lines=5)
    # Use smaller subline regardless of title fitting.
    sf = fnt(min(24, max(18, int(getattr(sf, "size", 22) * 0.55))), True, True)
    sy = y + 28
    for line in slines[:5]:
        d.text((42, sy), line, font=sf, fill=MUTED)
        sy += int(getattr(sf, "size", 20) * 1.25)

    # Institutional service flag over image, not a generic badge.
    service_labels = {
        "service_1_agent_pricing": "VALUTAZIONE PROFESSIONALE",
        "service_2_piano_vendita": "PIANO DI VENDITA F1",
        "service_3_bonus_casa": "GUIDE E INFORMAZIONI CASA",
        "service_4_recruiting": "LAVORA CON F1 IMMOBILIARE",
    }
    flag = service_labels.get(sid, "F1 IMMOBILIARE")
    d.rounded_rectangle((690, 700, 1035, 770), radius=10, fill=BLACK)
    d.text((712, 717), flag, font=fnt(18, True, True), fill=WHITE)
    d.line((712, 751, 1005, 751), fill=GREEN, width=3)

    draw_three_boxes(d, boxes)
    draw_contact_and_footer(canvas, cta, sid)
    return canvas


def validate_f1_outputs() -> None:
    q = load_json(QUEUE, {"jobs": []})
    cycle = q.get("current_cycle")
    rows = [j for j in q.get("jobs", []) if j.get("cycle_key") == cycle and j.get("client_id") == "f1-immobiliare"]
    if len(rows) != 5:
        raise RuntimeError(f"Expected 5 F1 outputs, got {len(rows)}")
    for j in rows:
        if not j.get("service_id"):
            raise RuntimeError(f"Legacy/unclassified F1 job blocked: {j.get('id')}")
        rel = str(j.get("media") or "")
        path = Path(rel)
        if not path.exists():
            raise RuntimeError(f"Missing F1 rendered media: {rel}")
        im = Image.open(path).convert("RGB")
        if im.size != SIZE:
            raise RuntimeError(f"Wrong F1 canvas size for {rel}: {im.size}")
        # Visual signature: black institutional footer, white body and F1 green accents.
        footer = im.crop((0, 1200, 1080, 1350))
        body = im.crop((0, 0, 1080, 1190))
        fp = list(footer.getdata())
        bp = list(body.getdata())
        dark_ratio = sum(1 for r, g, b in fp if r < 45 and g < 55 and b < 45) / max(1, len(fp))
        white_ratio = sum(1 for r, g, b in bp if r > 235 and g > 235 and b > 230) / max(1, len(bp))
        green_ratio = sum(1 for r, g, b in bp if g > r * 1.25 and g > b * 1.25 and g > 90) / max(1, len(bp))
        if dark_ratio < 0.55 or white_ratio < 0.14 or green_ratio < 0.012:
            raise RuntimeError(
                f"F1 institutional visual gate failed for {rel}: footer={dark_ratio:.3f}, white={white_ratio:.3f}, green={green_ratio:.3f}"
            )
        j["institutional_render_v2"] = True
        j["visual_compliance"] = "F1_LIGHT_INSTITUTIONAL_V2"
        j["publication_ready"] = True
    save_json(QUEUE, q)
    print("F1 INSTITUTIONAL VISUAL GATE PASSED: 5/5")


renderer.get_remote_image = robust_local_get
renderer.configured_f1_local_candidates = smart_f1_candidates
renderer.f1_composition = institutional_f1_composition

if __name__ == "__main__":
    rc = renderer.main()
    if rc not in (None, 0):
        raise SystemExit(rc)
    validate_f1_outputs()
    raise SystemExit(0)
