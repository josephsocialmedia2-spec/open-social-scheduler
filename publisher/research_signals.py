#!/usr/bin/env python3
"""Collect fresh Google query suggestions and keep a durable anti-duplicate history."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "publisher" / "research" / "latest.json"
HISTORY = ROOT / "publisher" / "query_history.json"
UA = "Mozilla/5.0 Open-Social-Scheduler/Deluxe-Premium"

BASE_QUERIES = {
    "f1-immobiliare": "agenzia delle entrate vendere comprare casa",
    "real-media-pro": "perché i social fanno crescere la tua azienda con i fatturati e le vendite",
}

FALLBACKS = {
    "f1-immobiliare": [
        "agenzia delle entrate valori immobiliari",
        "agenzia delle entrate consultazione valori immobiliari dichiarati",
        "agenzia delle entrate atti di vendita immobili",
        "agenzia delle entrate tasse vendita casa ereditata",
        "agenzia delle entrate plusvalenza vendita casa",
        "agenzia delle entrate prezzo valore compravendita",
        "agenzia delle entrate rendita catastale vendita casa",
        "agenzia delle entrate prima casa vendita riacquisto",
        "agenzia delle entrate imposte acquisto casa",
        "agenzia delle entrate guida acquisto casa",
        "agenzia delle entrate valore dichiarato immobile",
        "agenzia delle entrate omi quotazioni immobiliari",
    ],
    "real-media-pro": [
        "perché i social aumentano le vendite aziendali",
        "social media lead generation aziende",
        "social media e fatturato aziendale",
        "come trasformare follower in clienti",
        "sito web conversioni e vendite",
        "shopify aumentare vendite ecommerce",
        "ecommerce mobile conversioni",
        "contenuti social che generano contatti",
        "social proof fiducia clienti",
        "marketing digitale crescita aziendale",
        "reel per aziende e vendite",
        "funnel social sito vendita",
    ],
}

OFFICIAL = {
    "f1-immobiliare": [
        "https://www.agenziaentrate.gov.it/portale/web/guest/schede/fabbricatiterreni/omi",
        "https://www.agenziaentrate.gov.it/portale/web/guest/cittadini/acquisto-o-vendita-di-un-immobile",
    ],
    "real-media-pro": [
        "https://www.facebook.com/business/ads/facebook-instagram-reels-ads",
        "https://www.facebook.com/business/ads/ad-creative",
        "https://www.shopify.com/it/blog/topics/content-marketing",
        "https://www.shopify.com/blog/topics/conversion",
    ],
}


def get_json(url: str, timeout: int = 20) -> Any:
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def normalise(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return text


def google_suggest(query: str) -> list[str]:
    url = "https://suggestqueries.google.com/complete/search?client=firefox&hl=it&q=" + quote_plus(query)
    try:
        data = get_json(url)
        rows = data[1] if isinstance(data, list) and len(data) > 1 else []
        return [str(x).strip() for x in rows if str(x).strip()]
    except Exception as exc:
        print(f"WARN Google suggestions unavailable for {query!r}: {exc}")
        return []


def load_history() -> dict[str, Any]:
    if not HISTORY.exists():
        return {"version": 1, "items": []}
    try:
        data = json.loads(HISTORY.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "items": []}
        data.setdefault("version", 1)
        data.setdefault("items", [])
        return data
    except Exception:
        return {"version": 1, "items": []}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fresh_queries(brand: str, base: str, used: set[str], wanted: int = 10) -> list[str]:
    pool: list[str] = []
    seeds = [base]
    seeds.extend(google_suggest(base)[:8])
    for seed in seeds:
        for item in google_suggest(seed):
            key = normalise(item)
            if key and key not in used and key not in {normalise(x) for x in pool}:
                pool.append(item)
                if len(pool) >= wanted:
                    return pool
    for item in FALLBACKS[brand]:
        key = normalise(item)
        if key and key not in used and key not in {normalise(x) for x in pool}:
            pool.append(item)
            if len(pool) >= wanted:
                return pool
    variants = ["spiegazione", "errori", "guida", "checklist", "cosa sapere", "come funziona"]
    for seed in FALLBACKS[brand]:
        for suffix in variants:
            item = f"{seed} {suffix}"
            key = normalise(item)
            if key not in used and key not in {normalise(x) for x in pool}:
                pool.append(item)
                if len(pool) >= wanted:
                    return pool
    return pool


def main() -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    history = load_history()
    items = [x for x in history.get("items", []) if isinstance(x, dict)]
    used_by_brand = {
        brand: {normalise(x.get("query", "")) for x in items if x.get("brand") == brand}
        for brand in BASE_QUERIES
    }
    payload: dict[str, Any] = {
        "generated_at": now,
        "policy": {
            "query_source": "Google autocomplete suggestions",
            "avoid_duplicates": True,
            "copy_third_party_creatives": False,
            "allowed_media": ["owned", "generated", "Pixabay licensed", "Canva/client assets"],
        },
        "brands": {},
    }
    for brand, base in BASE_QUERIES.items():
        selected = fresh_queries(brand, base, used_by_brand[brand], wanted=10)
        payload["brands"][brand] = {
            "base_query": base,
            "fresh_queries": selected,
            "official_sources": OFFICIAL[brand],
        }
        for q in selected:
            items.append({
                "brand": brand,
                "query_base": base,
                "query": q,
                "used_at": now,
                "status": "reserved_for_content",
            })
    history["items"] = items[-2000:]
    save_json(HISTORY, history)
    save_json(OUT, payload)
    for brand, data in payload["brands"].items():
        print(f"{brand}: {len(data['fresh_queries'])} fresh query(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
