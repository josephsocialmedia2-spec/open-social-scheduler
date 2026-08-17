#!/usr/bin/env python3
"""Collect fresh public research signals for the daily social-content engine.

This script deliberately avoids scraping protected Facebook/Instagram feeds or
copying third-party creatives. It uses public web/news signals and official
Meta/Shopify guidance as research inputs, then stores links/titles so the
content generator can explain what influenced the day's candidates.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "publisher" / "research" / "latest.json"
UA = "Open-Social-Scheduler/1.0 (+https://github.com/josephsocialmedia2-spec/open-social-scheduler)"

OFFICIAL = {
    "meta_reels": "https://www.facebook.com/business/ads/facebook-instagram-reels-ads",
    "meta_creative": "https://www.facebook.com/business/ads/ad-creative",
    "shopify_content": "https://www.shopify.com/it/blog/topics/content-marketing",
    "shopify_conversion": "https://www.shopify.com/blog/topics/conversion",
    "shopify_editions": "https://www.shopify.com/it/editions/spring2026",
}

QUERIES = {
    "f1-immobiliare": [
        "mercato immobiliare Torino prezzi case",
        "Val di Susa immobili vendita case",
        "Torino provincia mercato casa vendite immobiliari",
    ],
    "real-media-pro": [
        "Shopify ecommerce conversion site speed product page",
        "ecommerce customer acquisition conversion marketing 2026",
        "Instagram Reels ecommerce creative performance",
    ],
}

PROVEN_FORMATS = {
    "f1-immobiliare": [
        "domanda diretta sul valore della casa",
        "errore comune sul prezzo",
        "checklist semplice prima della vendita",
        "immobile/casa come visual principale",
    ],
    "real-media-pro": [
        "domanda diagnostica sul sito",
        "checklist conversione ecommerce",
        "errore semplice da correggere",
        "dimostrazione visiva di sito/mobile/product page",
    ],
}


def get(url: str, timeout: int = 20) -> requests.Response:
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9,en;q=0.7"}, timeout=timeout)
    r.raise_for_status()
    return r


def news_search(query: str, limit: int = 6) -> list[dict[str, str]]:
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=it&gl=IT&ceid=IT:it"
    )
    try:
        root = ET.fromstring(get(url).content)
    except Exception:
        return []
    out: list[dict[str, str]] = []
    for item in root.findall("./channel/item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        date = (item.findtext("pubDate") or "").strip()
        if title and link:
            out.append({"title": title, "url": link, "published": date, "source": "Google News RSS"})
    return out


def official_probe(name: str, url: str) -> dict[str, str]:
    try:
        text = get(url).text[:500000]
        m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else name
        return {"name": name, "url": url, "status": "ok", "title": title}
    except Exception as exc:
        return {"name": name, "url": url, "status": "unavailable", "error": str(exc)[:180]}


def main() -> int:
    payload: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "policy": {
            "copy_third_party_creatives": False,
            "download_reupload_protected_media": False,
            "research_only": True,
            "allowed_media": ["owned", "generated", "licensed", "explicitly reusable"],
        },
        "official_sources": [official_probe(name, url) for name, url in OFFICIAL.items()],
        "brands": {},
    }

    for brand, queries in QUERIES.items():
        seen: set[str] = set()
        signals: list[dict[str, str]] = []
        for query in queries:
            for item in news_search(query):
                key = item["title"].lower()
                if key in seen:
                    continue
                seen.add(key)
                signals.append(item)
                if len(signals) >= 10:
                    break
            if len(signals) >= 10:
                break
        payload["brands"][brand] = {
            "queries": queries,
            "signals": signals,
            "proven_simple_formats": PROVEN_FORMATS[brand],
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved daily public research signals to {OUT.relative_to(ROOT)}")
    for brand, data in payload["brands"].items():
        print(f"{brand}: {len(data['signals'])} fresh signal(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
