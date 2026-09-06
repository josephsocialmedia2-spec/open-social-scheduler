from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
QUERY_FILE = ROOT / "publisher" / "github_graphics" / "queries.json"
OUTPUT_DIR = ROOT / "publisher" / "final_assets" / "github_generated"
MANIFEST = OUTPUT_DIR / "manifest.json"

W, H = 1080, 1350
GREEN = "#4E9E15"
GREEN_BRIGHT = "#64C800"
DARK = "#0A0D0A"
WHITE = "#FFFFFF"
LIGHT = "#F4F6F2"
MID = "#DCE5D7"


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_house_scene(draw: ImageDraw.ImageDraw, family: str, variant: int):
    x0, y0, x1, y1 = 520, 180, 1030, 1010
    draw.rounded_rectangle((x0, y0, x1, y1), radius=36, fill="#E9EFE5")
    # sky
    draw.rectangle((x0, y0, x1, 520), fill="#DDEBDD")
    # mountains
    peaks = [(520, 500), (625, 350), (730, 500), (820, 325), (930, 505), (1030, 410), (1030, 560), (520, 560)]
    draw.polygon(peaks, fill="#AFC5AA")
    draw.polygon([(520, 545),(650,420),(760,545),(865,400),(980,545),(1030,480),(1030,610),(520,610)], fill="#89A884")
    if family == "recruiting":
        # office/team visual
        draw.rectangle((575, 565, 980, 915), fill="#D5DDD1")
        draw.rectangle((610, 610, 945, 870), fill=WHITE)
        for i, cx in enumerate((670, 785, 895)):
            draw.ellipse((cx-38, 650, cx+38, 726), fill=GREEN if i == 1 else DARK)
            draw.rounded_rectangle((cx-54, 722, cx+54, 835), radius=24, fill=GREEN if i == 1 else "#2B332A")
        draw.rectangle((635, 840, 920, 860), fill=GREEN)
    else:
        # apartment block
        body = (590, 520, 970, 900)
        draw.rounded_rectangle(body, radius=18, fill="#E3D6C2")
        draw.rectangle((590, 520, 970, 575), fill=DARK)
        for row in range(3):
            for col in range(4):
                wx = 625 + col * 78
                wy = 610 + row * 82
                draw.rectangle((wx, wy, wx+48, wy+48), fill="#A9D1DF", outline=DARK, width=3)
                draw.rectangle((wx-5, wy+52, wx+53, wy+60), fill=GREEN)
        draw.rectangle((745, 785, 815, 900), fill="#6D5844")
        # foreground lawn
        draw.rectangle((520, 900, 1030, 1010), fill="#B9D7A8")
    # decorative ribbon
    draw.polygon([(520, 180),(700,180),(630,250),(520,250)], fill=GREEN)
    draw.text((548, 197), "SUSA", font=font(31, True), fill=WHITE)


def render(item: dict, index: int) -> Path:
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    # top diagonal identity
    draw.polygon([(0,0),(450,0),(340,105),(0,105)], fill=GREEN)
    draw.polygon([(405,0),(520,0),(410,105),(335,105)], fill=DARK)
    draw.text((58, 32), "F1", font=font(66, True), fill=WHITE)
    draw.text((165, 37), "IMMOBILIARE", font=font(36, True), fill=DARK if index % 2 else WHITE)

    # left copy field
    family = item.get("family", "property")
    draw.text((58, 185), "F1 CASA E IMPRESE", font=font(24, True), fill=GREEN)
    headline_font = font(72 if len(item["headline"]) < 28 else 58, True)
    lines = wrap(draw, item["headline"], headline_font, 420)
    y = 245
    for line in lines[:4]:
        draw.text((58, y), line, font=headline_font, fill=DARK)
        y += headline_font.size + 5
    sub_font = font(33, False)
    y += 28
    for line in wrap(draw, item["subheadline"], sub_font, 420)[:5]:
        draw.text((58, y), line, font=sub_font, fill="#303630")
        y += 46

    # content chips
    chips = [
        ("TERRITORIO", "Conoscenza locale"),
        ("METODO", "Comunicazione mirata"),
        ("SUPPORTO", "Assistenza concreta") if family != "recruiting" else ("CRESCITA", "Formazione e affiancamento"),
    ]
    cy = 720
    for label, value in chips:
        draw.ellipse((58, cy, 110, cy+52), fill=GREEN)
        draw.text((76, cy+8), "•", font=font(28, True), fill=WHITE)
        draw.text((126, cy-1), label, font=font(21, True), fill=DARK)
        draw.text((126, cy+25), value, font=font(20), fill="#4A5048")
        cy += 83

    draw_house_scene(draw, family, index)

    # CTA
    cta_y = 1060
    draw.rounded_rectangle((58, cta_y, 690, cta_y+92), radius=26, fill=GREEN_BRIGHT)
    draw.text((92, cta_y+25), item["cta"], font=font(31, True), fill=WHITE)
    draw.text((720, cta_y+28), "→", font=font(40, True), fill=DARK)

    # footer
    draw.rectangle((0, 1190, W, H), fill=DARK)
    draw.text((58, 1228), "+39 371 370 8294", font=font(31, True), fill=WHITE)
    draw.text((58, 1274), "+39 371 424 6300", font=font(25), fill="#D5D8D4")
    draw.text((555, 1232), "www.f1immobiliare.com", font=font(28, True), fill=WHITE)
    draw.text((555, 1279), "VALLE DI SUSA", font=font(23, True), fill=GREEN_BRIGHT)

    # right edge branding anchor
    draw.rectangle((1005, 1080, 1030, 1190), fill=GREEN)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{index+1:02d}_{item['id'].lower()}_{item['family']}.png"
    out = OUTPUT_DIR / filename
    img.save(out, "PNG", optimize=True)
    return out


def main():
    payload = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    generated = []
    for index, item in enumerate(payload["queries"]):
        out = render(item, index)
        generated.append({"id": item["id"], "query": item["query"], "asset": str(out.relative_to(ROOT)), "bytes": out.stat().st_size})
    MANIFEST.write_text(json.dumps({"batch": payload["batch"], "generated": generated}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "OK", "generated": generated}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
