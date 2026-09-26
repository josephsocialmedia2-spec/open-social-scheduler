#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

from buffer_queue_publish import load_client, secret_for_client, verify_client
from buffer_twice_daily import ROME, create_buffer_post, ensure_cloudinary_assets, get_buffer_post

CLIENT_ID = "antica-cappella"
CHANNEL_ID = "6ab5cfc6ea19ca0bdedecef3"
IMAGE_URL = "https://www.anticacappella.it/wp-content/uploads/2024/09/IMG_5492-1024x768.jpg"
CAPTION = """Ogni occasione merita il suo tempo, il suo spazio, la sua tavola.

All'Antica Cappella accogliamo matrimoni, battesimi, comunioni, compleanni, ricorrenze ed eventi aziendali con sale ampie, menu personalizzabili e un servizio pensato per far stare bene gli ospiti.

📍 Via Maritano Lino 10, Avigliana
📞 011 931 11 55
🌐 anticacappella.it

#AnticaCappella #Avigliana #Matrimoni #Cerimonie #Eventi #Ristorante #ValleDiSusa"""


def main() -> int:
    verification = verify_client(CLIENT_ID)
    instagram = (verification.get("channels") or {}).get("instagram") or {}
    if not verification.get("ok") or instagram.get("channel_id") != CHANNEL_ID or instagram.get("name") != "anticacappella":
        raise SystemExit("ANTICA_CAPPELLA_ACCOUNT_MISMATCH: " + json.dumps(verification, ensure_ascii=False))

    client = load_client(CLIENT_ID)
    api_key = secret_for_client(client)
    cloudinary_url = os.getenv("CLOUDINARY_URL", "").strip()
    if not cloudinary_url:
        raise SystemExit("CLOUDINARY_URL_MISSING")

    parsed = urlparse(IMAGE_URL)
    if parsed.scheme != "https" or parsed.hostname not in {"www.anticacappella.it", "anticacappella.it"}:
        raise SystemExit("UNTRUSTED_MEDIA_HOST")

    response = requests.get(
        IMAGE_URL,
        headers={"User-Agent": "F1Social-AnticaCappella/1.0"},
        timeout=60,
    )
    response.raise_for_status()
    if not str(response.headers.get("content-type") or "").lower().startswith("image/"):
        raise SystemExit("OFFICIAL_MEDIA_NOT_IMAGE")
    if len(response.content) > 15 * 1024 * 1024:
        raise SystemExit("OFFICIAL_MEDIA_TOO_LARGE")

    media_path = Path("/tmp/antica-cappella-matrimoni.jpg")
    media_path.write_bytes(response.content)

    now = datetime.now(ROME)
    job = {
        "id": "antica-cappella-matrimoni-20260926",
        "client_id": CLIENT_ID,
        "client_name": "Antica Cappella",
        "title": "Matrimoni e cerimonie all'Antica Cappella",
        "caption": CAPTION,
        "format": "post",
        "media": [str(media_path)],
        "scheduled_at": (now - timedelta(seconds=1)).isoformat(),
        "platforms": ["instagram"],
        "provider": "buffer",
        "provider_channel_id": CHANNEL_ID,
        "source": "OFFICIAL_WEBSITE",
        "source_media_url": IMAGE_URL,
        "created_by": "antica-cappella-publish-now",
        "enabled": True,
        "status": "ready",
    }

    hosted = ensure_cloudinary_assets(job, cloudinary_url)
    created = create_buffer_post(api_key, CHANNEL_ID, "instagram", job, hosted, now)
    post_id = str(created.get("post_id") or "")
    if not post_id:
        raise SystemExit("BUFFER_POST_ID_MISSING")

    final = {}
    for _ in range(36):
        time.sleep(10)
        final = get_buffer_post(api_key, post_id)
        if final.get("external_link") or final.get("sent_at"):
            print(json.dumps({
                "status": "PUBLISHED_CONFIRMED",
                "client_id": CLIENT_ID,
                "account": "anticacappella",
                "channel_id": CHANNEL_ID,
                "post_id": post_id,
                "external_link": final.get("external_link"),
                "sent_at": final.get("sent_at"),
                "buffer_status": final.get("buffer_status"),
                "source_media_url": IMAGE_URL,
            }, ensure_ascii=False, indent=2))
            return 0

    print(json.dumps({
        "status": "BUFFER_ACCEPTED_NOT_YET_CONFIRMED",
        "client_id": CLIENT_ID,
        "account": "anticacappella",
        "channel_id": CHANNEL_ID,
        "post_id": post_id,
        "buffer_status": final.get("buffer_status"),
        "external_link": final.get("external_link"),
        "sent_at": final.get("sent_at"),
        "source_media_url": IMAGE_URL,
    }, ensure_ascii=False, indent=2))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
