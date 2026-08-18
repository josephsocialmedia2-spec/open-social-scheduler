#!/usr/bin/env python3
"""Emergency renderer using direct Pixabay CDN assets only.

GitHub runners must never scrape Pixabay photo pages: those pages can answer 403.
This wrapper injects already-resolved CDN asset URLs, retries direct downloads,
and then delegates the actual Deluxe render to render_reels.py.
"""
from __future__ import annotations

import hashlib
import time
from io import BytesIO

import requests
from PIL import Image

import render_reels as rr

# Direct licensed Pixabay media URLs. No HTML/page scraping.
rr.F1 = [
    "https://cdn.pixabay.com/photo/2025/08/29/17/52/modern-villa-exterior-9804538_1280.jpg",
    "https://cdn.pixabay.com/photo/2025/08/29/17/52/luxury-villa-facade-9804536_1280.jpg",
    "https://cdn.pixabay.com/photo/2025/08/25/10/19/living-room-9795892_1280.jpg",
    "https://cdn.pixabay.com/photo/2017/09/15/15/22/modern-2752472_1280.jpg",
    "https://cdn.pixabay.com/photo/2023/12/11/06/20/real-estate-8442802_1280.jpg",
    "https://cdn.pixabay.com/photo/2024/03/27/10/34/apartment-8658767_1280.jpg",
    "https://cdn.pixabay.com/photo/2023/09/18/12/05/kitchen-8260437_1280.jpg",
    "https://cdn.pixabay.com/photo/2024/02/06/07/01/bathroom-8556101_1280.jpg",
    "https://cdn.pixabay.com/photo/2023/12/04/01/27/real-estate-8428506_1280.jpg",
    "https://cdn.pixabay.com/photo/2024/02/14/07/08/bedroom-8572584_1280.jpg",
]

rr.RMP = [
    "https://cdn.pixabay.com/photo/2017/06/26/12/57/laptop-2443749_1280.jpg",
    "https://cdn.pixabay.com/photo/2018/02/08/10/22/desk-3139127_1280.jpg",
    "https://cdn.pixabay.com/photo/2023/10/10/05/53/laptop-8305452_1280.jpg",
    "https://cdn.pixabay.com/photo/2015/01/08/18/25/desk-593327_1280.jpg",
    "https://cdn.pixabay.com/photo/2019/07/13/10/25/payment-4334491_1280.jpg",
    "https://cdn.pixabay.com/photo/2017/10/29/17/31/online-2900303_640.jpg",
    "https://cdn.pixabay.com/photo/2017/08/07/19/45/ecommerce-2607114_640.jpg",
    "https://cdn.pixabay.com/photo/2022/07/06/03/41/business-7304257_640.jpg",
    "https://cdn.pixabay.com/photo/2019/06/15/16/06/online-4275963_1280.jpg",
    "https://cdn.pixabay.com/photo/2018/07/31/14/52/ecommerce-3575280_1280.jpg",
]


def direct_get_image(url: str) -> Image.Image:
    rr.CACHE.mkdir(parents=True, exist_ok=True)
    cache = rr.CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".jpg")
    if cache.exists() and cache.stat().st_size > 12000:
        return Image.open(cache).convert("RGB")

    last: Exception | None = None
    headers = {
        "User-Agent": "Mozilla/5.0 Open-Social-Scheduler/DeluxeFast",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://pixabay.com/",
    }
    for attempt in range(5):
        try:
            response = requests.get(url, headers=headers, timeout=45)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
            image.save(cache, "JPEG", quality=94, optimize=True)
            return image
        except Exception as exc:
            last = exc
            time.sleep(2 + attempt * 2)
    raise RuntimeError(f"Direct premium image download failed after retries: {url}: {last}")


rr.get_image = direct_get_image

if __name__ == "__main__":
    raise SystemExit(rr.main())
