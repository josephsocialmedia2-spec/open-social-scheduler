#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

import f1_premium_renderer as f1
from ollama_graphics_bridge import enrich_queries

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "publisher" / "github_graphics" / "queries.json"
OUTPUT_DIR = ROOT / "property-preview"
META = OUTPUT_DIR / "meta.json"
README = OUTPUT_DIR / "README.md"
SIZE = (1080, 1350)
MAX_COUNT = 10

FORBIDDEN = (
    "owl", "gufo", "bird", "uccello", "cat", "gatto", "dog", "cane",
    "food", "cibo", "car", "auto", "animal", "animale"
)
REAL_ESTATE_MARKERS = (
    "house", "home", "residential", "apartment", "villa", "building",
    "interior", "estate", "property", "immobil", "casa", "local", "territory"
)


def font(size: int, bold: bool = False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, width: int, size: int, max_lines: int, bold: bool = True):
    words = str(text or "").split()
    for s in range(size, 25, -2):
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


def _source_text(item: dict) -> str:
    return " ".join(str(v) for v in item.values()).lower()


def valid_source(item: dict, visual_type: str) -> bool:
    text = _source_text(item)
    if any(marker in text for marker in FORBIDDEN):
        return False
    if not any(marker in text for marker in REAL_ESTATE_MARKERS):
        return False
    if visual_type == "professional_real_estate_team":
        return any(x in text for x in ("team", "office", "agent", "professional", "person", "presenter"))
    if visual_type == "local_territory":
        return any(x in text for x in ("local", "territory", "valle", "susa", "avigliana", "town", "landscape"))
    return True


def choose_image(brief: dict, index: int) -> Image.Image:
    cfg = f1.load_json(f1.F1_CFG, {})
    sources = [x for x in cfg.get("brand", {}).get("photo_sources", []) if isinstance(x, dict) and x.get("url")]
    visual = str(brief.get("visual_type") or "residential_exterior")
    candidates = [x for x in sources if valid_source(x, visual)]
    if not candidates:
        candidates = [x for x in sources if not any(m in _source_text(x) for m in FORBIDDEN)]
    if not candidates:
        raise RuntimeError("Nessuna sorgente fotografica immobiliare valida configurata")

    errors = []
    for offset in range(len(candidates)):
        item = candidates[(index + offset) % len(candidates)]
        try:
            return f1.robust_local_get(str(item["url"]))
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("Nessuna immagine caricabile: " + " | ".join(errors[-3:]))


def render(brief: dict, image: Image.Image, index: int) -> Image.Image:
    canvas = ImageOps.fit(image.convert("RGB"), SIZE, Image.Resampling.LANCZOS)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.05)

    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, 1080, 175), fill=(7, 9, 7, 224))
    od.rectangle((0, 610, 1080, 1165), fill=(7, 9, 7, 238))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(canvas)

    f1.draw_brand(d, 48, 48)
    d.rounded_rectangle((805, 52, 1025, 104), radius=14, fill=f1.GREEN)
    d.text((840, 67), f"QUERY {index:02d}", font=font(18, True), fill=f1.BLACK)

    family = str(brief.get("family") or "property").upper()
    d.text((58, 650), family, font=font(24, True), fill=f1.GREEN)

    headline = str(brief.get("headline") or brief.get("query") or "").strip()
    ft, lines = wrap(d, headline.upper(), 930, 63, 3, True)
    y = 700
    for line in lines:
        d.text((58, y), line, font=ft, fill=f1.WHITE)
        y += int(getattr(ft, "size", 50) * 1.06)

    sub = str(brief.get("subheadline") or "").strip()
    if sub:
        fs, sub_lines = wrap(d, sub, 900, 30, 3, False)
        y += 14
        for line in sub_lines:
            d.text((58, y), line, font=fs, fill=f1.MUTED)
            y += int(getattr(fs, "size", 28) * 1.25)

    cta = str(brief.get("cta") or "CONTATTACI").strip().upper()
    d.rounded_rectangle((58, 1015, 530, 1082), radius=18, fill=f1.GREEN)
    cta_font, cta_lines = wrap(d, cta, 420, 26, 1, True)
    d.text((82, 1035), cta_lines[0], font=cta_font, fill=f1.BLACK)

    # Audit trail: the exact user-selected query is printed without reinterpretation.
    query = str(brief.get("query") or "").strip()
    fq, qlines = wrap(d, f"Query: {query}", 930, 18, 2, False)
    qy = 1100
    for line in qlines:
        d.text((58, qy), line, font=fq, fill=f1.MUTED)
        qy += 22

    f1.draw_footer(canvas)
    return canvas


def main() -> int:
    payload = json.loads(QUERIES.read_text(encoding="utf-8"))
    selected = payload.get("queries") or []
    if not selected:
        raise RuntimeError("queries.json non contiene query selezionate")
    if len(selected) > MAX_COUNT:
        selected = selected[:MAX_COUNT]

    # Ollama enriches the selected queries, but the bridge hard-locks the original query text.
    briefs = enrich_queries(selected)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("[0-9][0-9].jpg"):
        old.unlink()

    outputs = []
    for i, brief in enumerate(briefs, 1):
        image = choose_image(brief, i - 1)
        out = OUTPUT_DIR / f"{i:02d}.jpg"
        render(brief, image, i).save(out, "JPEG", quality=94, optimize=True)
        outputs.append({
            "index": i,
            "id": selected[i - 1].get("id"),
            "query": selected[i - 1].get("query"),
            "brief": brief,
            "output": str(out.relative_to(ROOT)),
        })

    shutil.copyfile(OUTPUT_DIR / "01.jpg", OUTPUT_DIR / "latest.jpg")
    META.write_text(json.dumps({
        "batch": payload.get("batch"),
        "count": len(outputs),
        "size": SIZE,
        "source": "publisher/github_graphics/queries.json",
        "outputs": outputs,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    repo = "https://raw.githubusercontent.com/josephsocialmedia2-spec/open-social-scheduler/main/property-preview"
    lines = [
        "# F1 · Grafiche generate dalle query selezionate",
        "",
        "Ogni JPG corrisponde, nello stesso ordine, a una query presente in `publisher/github_graphics/queries.json`.",
        "Ollama può arricchire il brief ma non può modificare la query originale.",
        "",
    ]
    for item in outputs:
        i = item["index"]
        lines += [f"## {i:02d} · {item['query']}", "", f"![Query {i:02d}]({repo}/{i:02d}.jpg)", ""]
    README.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"F1 QUERY PREVIEWS READY: {len(outputs)}")
    for item in outputs:
        print(f"{item['index']:02d} | {item['query']} | ollama={item['brief'].get('ollama_used')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
