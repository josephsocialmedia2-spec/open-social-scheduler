#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

OLLAMA_URL = os.getenv("F1_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("F1_OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = int(os.getenv("F1_OLLAMA_TIMEOUT", "45"))
OLLAMA_STRICT = os.getenv("F1_OLLAMA_STRICT", "0").strip().lower() in {"1", "true", "yes", "on"}

ALLOWED_FAMILIES = {"property", "acquisition", "recruiting", "territory", "valuation"}
ALLOWED_VISUALS = {
    "residential_interior",
    "residential_exterior",
    "apartment_building",
    "villa",
    "local_territory",
    "professional_real_estate_team",
}


def _fallback(query_item: dict[str, Any]) -> dict[str, Any]:
    family = str(query_item.get("family") or "property").strip().lower()
    if family not in ALLOWED_FAMILIES:
        family = "property"
    visual = {
        "property": "residential_exterior",
        "acquisition": "residential_interior",
        "recruiting": "professional_real_estate_team",
        "territory": "local_territory",
        "valuation": "residential_interior",
    }[family]
    return {
        "query": str(query_item.get("query") or "").strip(),
        "family": family,
        "headline": str(query_item.get("headline") or query_item.get("query") or "").strip(),
        "subheadline": str(query_item.get("subheadline") or "").strip(),
        "cta": str(query_item.get("cta") or "CONTATTACI").strip(),
        "visual_type": visual,
        "layout": "left_overlay",
        "ollama_used": False,
    }


def enrich_query(query_item: dict[str, Any]) -> dict[str, Any]:
    """Enrich one selected query without ever replacing the original query."""
    original_query = str(query_item.get("query") or "").strip()
    if not original_query:
        raise ValueError("Query vuota")

    system = (
        "Sei il planner grafico di F1 Immobiliare. Devi analizzare una query GIA SCELTA dall'utente. "
        "NON cambiare, NON riscrivere e NON sostituire la query originale. Restituisci solo JSON valido. "
        "Scegli family tra property, acquisition, recruiting, territory, valuation. "
        "Scegli visual_type solo tra residential_interior, residential_exterior, apartment_building, villa, "
        "local_territory, professional_real_estate_team. Sono vietati animali, gufi, uccelli, cibo, auto, "
        "oggetti casuali e immagini non immobiliari. Mantieni headline, subheadline e CTA forniti se coerenti."
    )
    user = {
        "query": original_query,
        "family_hint": query_item.get("family"),
        "headline": query_item.get("headline"),
        "subheadline": query_item.get("subheadline"),
        "cta": query_item.get("cta"),
        "required_output": {
            "query": original_query,
            "family": "property|acquisition|recruiting|territory|valuation",
            "headline": "string",
            "subheadline": "string",
            "cta": "string",
            "visual_type": "allowed visual type",
            "layout": "left_overlay|photo_top|split|bottom_overlay"
        }
    }
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "options": {"temperature": 0.1},
    }

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body.get("message", {}).get("content", "")
        result = json.loads(content)

        # Hard guarantee: Ollama cannot alter the selected query.
        result["query"] = original_query
        family = str(result.get("family") or query_item.get("family") or "property").lower()
        if family not in ALLOWED_FAMILIES:
            family = _fallback(query_item)["family"]
        result["family"] = family
        visual = str(result.get("visual_type") or "")
        if visual not in ALLOWED_VISUALS:
            visual = _fallback(query_item)["visual_type"]
        result["visual_type"] = visual
        result["headline"] = str(result.get("headline") or query_item.get("headline") or original_query).strip()
        result["subheadline"] = str(result.get("subheadline") or query_item.get("subheadline") or "").strip()
        result["cta"] = str(result.get("cta") or query_item.get("cta") or "CONTATTACI").strip()
        result["ollama_used"] = True
        return result
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError, KeyError, TypeError) as exc:
        if OLLAMA_STRICT:
            raise RuntimeError(f"Ollama non disponibile o risposta non valida: {exc}") from exc
        fallback = _fallback(query_item)
        fallback["ollama_error"] = str(exc)
        return fallback


def enrich_queries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_query(item) for item in items]
