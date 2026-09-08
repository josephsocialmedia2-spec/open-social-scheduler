#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import random
import shutil
from pathlib import Path

import requests
from ddgs import DDGS
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

import f1_premium_renderer as f1
from ollama_graphics_bridge import enrich_queries

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "publisher" / "github_graphics" / "queries.json"
OUTPUT_DIR = ROOT / "property-preview"
META = OUTPUT_DIR / "meta.json"
README = OUTPUT_DIR / "README.md"
INDEX = OUTPUT_DIR / "index.html"
SIZE = (1080, 1350)
MAX_COUNT = 10
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
FORBIDDEN = ("owl", "gufo", "bird", "uccello", "cat", "gatto", "dog", "cane", "food", "cibo", "car", "auto", "animal", "animale")


def font(size: int, bold: bool = False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def wrap(draw, text, width, size, max_lines, bold=True):
    words = str(text or "").split()
    for s in range(size, 24, -2):
        ft = font(s, bold)
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            if draw.textbbox((0, 0), test, font=ft)[2] <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        if len(lines) <= max_lines:
            return ft, lines
    return font(26, bold), [" ".join(words)]


def extract_commune(item: dict) -> str:
    if item.get("commune"):
        return str(item["commune"]).strip()
    q = str(item.get("query") or "")
    marker = "immobili in vendita a "
    return q.split(marker, 1)[1].strip() if marker in q else q


def download_image(url: str) -> Image.Image:
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"}, timeout=18)
    r.raise_for_status()
    if len(r.content) < 30000:
        raise RuntimeError("immagine troppo piccola")
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    if im.width < 700 or im.height < 500:
        raise RuntimeError("risoluzione insufficiente")
    return im


def search_commune_home(commune: str, index: int):
    searches = [
        f'"{commune}" Piemonte casa abitazione villa',
        f'"{commune}" Torino case borgata abitazioni',
        f'"{commune}" Piemonte residential house',
    ]
    errors = []
    for query in searches:
        try:
            results = list(DDGS().images(query, region="it-it", safesearch="moderate", max_results=18))
        except Exception as exc:
            errors.append(str(exc))
            continue
        random.Random(20260908 + index).shuffle(results)
        for row in results:
            text = " ".join(str(row.get(k, "")) for k in ("title", "url", "image", "source")).lower()
            if any(x in text for x in FORBIDDEN):
                continue
            url = row.get("image") or row.get("url")
            if not url or not str(url).startswith("http"):
                continue
            try:
                return download_image(str(url)), {"search_query": query, "source_url": str(url), "source_title": row.get("title", "")}
            except Exception as exc:
                errors.append(str(exc))
    # deterministic real-estate fallback from configured F1 sources
    cfg = f1.load_json(f1.F1_CFG, {})
    sources = [x for x in cfg.get("brand", {}).get("photo_sources", []) if isinstance(x, dict) and x.get("url")]
    for item in sources:
        text = " ".join(str(v) for v in item.values()).lower()
        if any(x in text for x in FORBIDDEN):
            continue
        try:
            return f1.robust_local_get(str(item["url"])), {"search_query": "fallback F1", "source_url": str(item["url"]), "source_title": str(item.get("credit", ""))}
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("Nessuna immagine immobiliare valida: " + " | ".join(errors[-4:]))


def twilightize(image: Image.Image) -> Image.Image:
    base = ImageOps.fit(image.convert("RGB"), SIZE, Image.Resampling.LANCZOS)
    base = ImageEnhance.Contrast(base).enhance(1.10)
    base = ImageEnhance.Color(base).enhance(0.92)
    dark = ImageEnhance.Brightness(base).enhance(0.72).convert("RGBA")

    tint = Image.new("RGBA", SIZE, (22, 46, 82, 75))
    dark = Image.alpha_composite(dark, tint)

    # warm sunset gradient in the upper half
    grad = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(0, 680):
        t = y / 680
        alpha = int(92 * (1 - t))
        gd.line((0, y, 1080, y), fill=(255, 126, 58, alpha), width=1)
    dark = Image.alpha_composite(dark, grad)

    # turn existing highlights into warm window/street-light glow
    lum = base.convert("L")
    mask = lum.point(lambda p: 255 if p > 188 else 0).filter(ImageFilter.GaussianBlur(10))
    glow = Image.new("RGBA", SIZE, (255, 176, 72, 0))
    glow.putalpha(mask.point(lambda p: int(p * 0.58)))
    dark = Image.alpha_composite(dark, glow)
    return dark.convert("RGB")


def draw_location_badge(d, commune):
    x1, y1, x2, y2 = 735, 50, 1030, 126
    d.rounded_rectangle((x1, y1, x2, y2), radius=16, fill=(7, 9, 7))
    d.ellipse((760, 68, 786, 94), outline=(200, 161, 90), width=4)
    d.ellipse((769, 77, 777, 85), fill=(200, 161, 90))
    ft, lines = wrap(d, commune.upper(), 205, 25, 2, True)
    yy = 63
    for line in lines:
        d.text((805, yy), line, font=ft, fill=f1.WHITE)
        yy += int(getattr(ft, "size", 22) * 1.03)


def render(brief: dict, image: Image.Image, index: int, commune: str) -> Image.Image:
    canvas = twilightize(image)
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, 1080, 150), fill=(4, 7, 7, 205))
    od.rectangle((0, 555, 1080, 1350), fill=(4, 7, 7, 180))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(canvas)

    f1.draw_brand(d, 44, 38)
    draw_location_badge(d, commune)

    d.text((58, 625), "CERCHI CASA A", font=font(34, False), fill=f1.WHITE)
    ft, lines = wrap(d, commune.upper() + "?", 920, 74, 2, True)
    y = 668
    for line in lines:
        d.text((58, y), line, font=ft, fill=(210, 172, 96))
        y += int(getattr(ft, "size", 60) * 1.02)

    d.text((58, y + 12), "Scopri le opportunità nel territorio e ricevi", font=font(28), fill=f1.WHITE)
    d.text((58, y + 50), "foto, prezzi e planimetrie delle case disponibili.", font=font(28), fill=f1.WHITE)

    benefits = [("NATURA E TRANQUILLITÀ", 865), ("SERVIZI A PORTATA DI MANO", 920), ("CASE SELEZIONATE", 975)]
    for txt, yy in benefits:
        d.ellipse((62, yy, 90, yy + 28), outline=(210, 172, 96), width=3)
        d.text((108, yy - 1), txt, font=font(20, True), fill=f1.WHITE)

    d.rounded_rectangle((58, 1050, 670, 1133), radius=18, fill=(200, 161, 90))
    d.text((87, 1070), "SCRIVI CASA SU WHATSAPP", font=font(28, True), fill=f1.BLACK)

    query = str(brief.get("query") or "").strip()
    fq, qlines = wrap(d, "QUERY: " + query, 920, 17, 2, False)
    qy = 1155
    for line in qlines:
        d.text((60, qy), line, font=fq, fill=(205, 211, 206))
        qy += 22

    f1.draw_footer(canvas)
    return canvas


def build_index(outputs):
    cards = []
    for item in outputs:
        i = item["index"]
        cards.append(f'''<article><img src="{i:02d}.jpg" alt="{item['query']}"><h2>{i:02d}. {item['query']}</h2><a href="{i:02d}.jpg" target="_blank">Apri grafica</a></article>''')
    html = '''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>F1 · 10 grafiche query</title><style>body{margin:0;background:#070907;color:#f7f7f4;font-family:Arial,sans-serif}header{padding:28px 5vw;border-bottom:1px solid #c8a15a}h1{margin:0;color:#c8a15a}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:22px;padding:28px 5vw}article{background:#101610;padding:14px;border:1px solid #2d382d;border-radius:18px}img{width:100%;border-radius:12px;display:block}h2{font-size:16px;line-height:1.35}a{display:inline-block;background:#c8a15a;color:#070907;padding:10px 14px;border-radius:10px;text-decoration:none;font-weight:700}</style></head><body><header><h1>F1 IMMOBILIARE · ANTEPRIMA 10 GRAFICHE</h1><p>Query bloccate: cambia solo il nome del comune. Immagini ricercate sul web e trasformate in atmosfera tramonto/luci accese.</p></header><main class="grid">''' + "".join(cards) + '''</main></body></html>'''
    INDEX.write_text(html, encoding="utf-8")


def main() -> int:
    payload = json.loads(QUERIES.read_text(encoding="utf-8"))
    selected = (payload.get("queries") or [])[:MAX_COUNT]
    if not selected:
        raise RuntimeError("queries.json non contiene query selezionate")
    briefs = enrich_queries(selected)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("[0-9][0-9].jpg"):
        old.unlink()

    outputs = []
    for i, brief in enumerate(briefs, 1):
        original = selected[i - 1]
        commune = extract_commune(original)
        image, source = search_commune_home(commune, i)
        out = OUTPUT_DIR / f"{i:02d}.jpg"
        render(brief, image, i, commune).save(out, "JPEG", quality=94, optimize=True)
        outputs.append({"index": i, "id": original.get("id"), "commune": commune, "query": original.get("query"), "brief": brief, "source": source, "output": str(out.relative_to(ROOT))})

    shutil.copyfile(OUTPUT_DIR / "01.jpg", OUTPUT_DIR / "latest.jpg")
    META.write_text(json.dumps({"batch": payload.get("batch"), "count": len(outputs), "size": SIZE, "source": "publisher/github_graphics/queries.json", "visual_rule": "web residence -> sunset -> lights on", "outputs": outputs}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    repo = "https://raw.githubusercontent.com/josephsocialmedia2-spec/open-social-scheduler/main/property-preview"
    lines = ["# F1 · 10 grafiche query", "", "Le query sono bloccate: cambia soltanto il nome del comune.", ""]
    for item in outputs:
        i = item["index"]
        lines += [f"## {i:02d} · {item['query']}", "", f"![Query {i:02d}]({repo}/{i:02d}.jpg)", ""]
    README.write_text("\n".join(lines) + "\n", encoding="utf-8")
    build_index(outputs)
    print(f"F1 QUERY PREVIEWS READY: {len(outputs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
