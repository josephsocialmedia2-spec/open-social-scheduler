#!/usr/bin/env python3
"""Create deterministic local residential backdrops for F1 renderer.

The renderer checks its local cache before performing a remote download. This helper
pre-populates that cache using the exact configured photo-source URL hashes, so a
remote 403/429 cannot block preview or publication. No social publishing occurs here.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
CACHE = Path(os.getenv("SOCIAL_PHOTO_CACHE", str(ROOT / ".cache" / "social-photos")))
W, H = 1600, 2000


def lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def backdrop(seed: int) -> Image.Image:
    rng = random.Random(seed)
    top = (8 + rng.randrange(0, 8), 13 + rng.randrange(0, 8), 11 + rng.randrange(0, 7))
    bottom = (24 + rng.randrange(0, 18), 31 + rng.randrange(0, 20), 27 + rng.randrange(0, 16))
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        t = y / max(1, H - 1)
        c = tuple(lerp(top[i], bottom[i], t) for i in range(3))
        for x in range(W):
            n = rng.randrange(-3, 4)
            px[x, y] = tuple(max(0, min(255, v + n)) for v in c)

    d = ImageDraw.Draw(im, "RGBA")
    # Distant mountain / valley layers.
    d.polygon([(0, 930), (260, 690), (520, 880), (830, 610), (1130, 850), (1600, 640), (1600, 1230), (0, 1230)], fill=(32, 48, 41, 180))
    d.polygon([(0, 1120), (300, 960), (590, 1090), (960, 870), (1270, 1050), (1600, 920), (1600, 1380), (0, 1380)], fill=(18, 28, 24, 210))

    # Modern residence, varied per seed.
    bx = 170 + rng.randrange(0, 180)
    by = 920 + rng.randrange(-60, 80)
    bw = 1050 + rng.randrange(-120, 120)
    bh = 570 + rng.randrange(-50, 100)
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=24, fill=(14, 18, 17, 245), outline=(146, 194, 5, 190), width=6)
    roof_y = by - 155
    d.polygon([(bx - 50, by + 20), (bx + int(bw * .42), roof_y), (bx + bw + 70, by + 40)], fill=(10, 13, 12, 255), outline=(146, 194, 5, 160))

    warm = [(220, 177, 102, 210), (245, 223, 172, 205), (185, 205, 169, 190)]
    cols = 4
    gap = 45
    win_w = int((bw - gap * (cols + 1)) / cols)
    for i in range(cols):
        x1 = bx + gap + i * (win_w + gap)
        y1 = by + 105 + (i % 2) * 28
        y2 = by + bh - 90
        d.rounded_rectangle((x1, y1, x1 + win_w, y2), radius=10, fill=warm[(i + seed) % len(warm)], outline=(255, 255, 255, 55), width=3)
        d.line((x1 + win_w // 2, y1, x1 + win_w // 2, y2), fill=(30, 35, 32, 110), width=5)

    # Terrace / lawn and restrained F1 accent.
    d.rectangle((0, by + bh - 10, W, H), fill=(8, 14, 11, 155))
    d.line((90, 1700, 1510, 1700), fill=(146, 194, 5, 120), width=5)
    for _ in range(26):
        x = rng.randrange(0, W)
        y = rng.randrange(1450, H)
        r = rng.randrange(10, 34)
        d.ellipse((x-r, y-r, x+r, y+r), fill=(44, 77, 57, rng.randrange(35, 90)))

    # Soft vignette.
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((-350, -250, W + 350, H + 320), fill=220)
    mask = mask.filter(ImageFilter.GaussianBlur(170))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    inv = Image.eval(mask, lambda v: 255 - v)
    im = Image.composite(dark, im, inv.point(lambda v: int(v * 0.48)))
    return im


def main() -> int:
    data = json.loads(CLIENT.read_text(encoding="utf-8"))
    rows = data.get("brand", {}).get("photo_sources", [])
    urls = [str(r.get("url") or "").strip() for r in rows if isinstance(r, dict) and str(r.get("url") or "").strip()]
    if not urls:
        raise SystemExit("No F1 photo_sources configured")
    CACHE.mkdir(parents=True, exist_ok=True)
    created = []
    for url in urls:
        digest = hashlib.sha256(url.encode()).hexdigest()
        path = CACHE / f"{digest}.jpg"
        if not path.exists() or path.stat().st_size <= 12000:
            seed = int(digest[:12], 16)
            backdrop(seed).save(path, "JPEG", quality=94, optimize=True)
        created.append(str(path))
    print(json.dumps({"status": "PHOTO_CACHE_READY", "count": len(created), "cache": str(CACHE)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
