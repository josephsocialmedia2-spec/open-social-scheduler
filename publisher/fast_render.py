#!/usr/bin/env python3
"""Resilient emergency renderer wrapper for the 1+1 same-day fast lane."""
from __future__ import annotations

import html
import re
import time
from typing import Any

import requests

import render_reels as rr


def robust_resolve_pixabay(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Open-Social-Scheduler/DeluxeFast",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
    }
    last: Exception | None = None
    for attempt in range(5):
        try:
            r = requests.get(url, headers=headers, timeout=35)
            r.raise_for_status()
            text = r.text
            patterns = (
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                r'(https://cdn\.pixabay\.com/photo/[^"\'<> ]+?_(?:1280|1920)\.(?:jpg|jpeg|png|webp))',
                r'(https://cdn\.pixabay\.com/photo/[^"\'<> ]+?\.(?:jpg|jpeg|png|webp))',
            )
            for pat in patterns:
                m = re.search(pat, text, re.I)
                if m:
                    return html.unescape(m.group(1)).replace("\\u002F", "/")
            raise RuntimeError(f"No usable Pixabay image URL found in page: {url}")
        except Exception as exc:
            last = exc
            time.sleep(2 + attempt * 2)
    raise RuntimeError(f"Pixabay resolution failed after retries: {url}: {last}")


def resilient_get_image(url: str):
    pools: list[list[str]] = []
    if url in rr.F1:
        pools = [rr.F1]
    elif url in rr.RMP:
        pools = [rr.RMP]
    else:
        pools = [[url]]

    errors: list[str] = []
    for pool in pools:
        start = pool.index(url) if url in pool else 0
        for offset in range(len(pool)):
            candidate = pool[(start + offset) % len(pool)]
            try:
                direct = robust_resolve_pixabay(candidate) if "pixabay.com/" in candidate and "cdn.pixabay.com/" not in candidate else candidate
                return _download_direct(direct)
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")
                continue
    raise RuntimeError("No usable premium image source. " + " | ".join(errors[-4:]))


def _download_direct(direct: str):
    from io import BytesIO
    import hashlib
    from PIL import Image

    rr.CACHE.mkdir(parents=True, exist_ok=True)
    p = rr.CACHE / (hashlib.sha256(direct.encode()).hexdigest() + ".jpg")
    if p.exists() and p.stat().st_size > 12000:
        return Image.open(p).convert("RGB")
    r = requests.get(
        direct,
        headers={"User-Agent": "Mozilla/5.0 Open-Social-Scheduler/DeluxeFast", "Accept": "image/*"},
        timeout=45,
    )
    r.raise_for_status()
    im = Image.open(BytesIO(r.content)).convert("RGB")
    im.save(p, "JPEG", quality=94, optimize=True)
    return im


rr.resolve_pixabay = robust_resolve_pixabay
rr.get_image = resilient_get_image

if __name__ == "__main__":
    raise SystemExit(rr.main())
