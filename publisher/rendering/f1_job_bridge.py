from __future__ import annotations

import re
from pathlib import Path
from typing import Any


GOLDEN_MASTER_VERSION = "F1_GOLDEN_MASTER_FEED_V4"

F1_BRAND = {
    "name": "F1 IMMOBILIARE",
    "descriptor": "CASA E IMPRESE",
    "tagline": "LA TUA CASA, IL NOSTRO OBIETTIVO",
    "script_tagline": "Affidati a chi conosce il territorio",
    "primary": "#4E9E15",
    "primary_bright": "#66C500",
    "secondary": "#0A0D0A",
    "background": "#FFFFFF",
    "foreground": "#111511",
    "muted": "#5D665D",
    "phone_primary": "+39 371 370 8294",
    "phone_secondary": "+39 371 424 6300",
    "site": "www.f1immobiliare.com",
    "address": "Via Roma, 8 · Sant'Antonino di Susa (TO)",
}


def _clean_slide(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        row = {str(k): str(v) for k, v in value.items() if v is not None}
        if "title" in row:
            row["title"] = row["title"].replace("|", "\n")
        return row
    text = str(value or "").strip().replace("|", "\n")
    return {"title": text}


def _family(job: dict[str, Any]) -> str:
    haystack = " ".join(
        str(job.get(key) or "")
        for key in ("title", "caption", "main_message", "visual_theme", "target_public")
    ).lower()
    recruiting = (
        "recruit", "candidat", "agente immobiliare", "coordinatrice", "coordinatore",
        "entra nella squadra", "lavora con noi", "carriera", "team leader",
    )
    property_terms = (
        "alloggio", "appartamento", "villa", "bilocale", "trilocale", "quadrilocale",
        "salone", "balcone", "terrazzo", "capannone", "locali commerciali", "in vendita",
        "camera", "bagno", "mq", "metr", "planimetr", "distribuzione",
    )
    if any(term in haystack for term in recruiting):
        return "recruiting"
    if any(term in haystack for term in property_terms) and str(job.get("lead_goal") or "") != "qualified_seller":
        return "property"
    return "institutional"


def _visual_variant(source_item_id: str, fmt: str, family: str) -> str:
    """Choose only layouts belonging to the locked Golden Master family."""
    match = re.search(r"(\d+)", source_item_id or "")
    number = int(match.group(1)) if match else 1
    if family == "recruiting":
        variants = ("recruit_split", "recruit_portrait")
    elif family == "property":
        variants = ("property_split", "property_photo")
    else:
        variants = ("institutional_split", "institutional_photo", "institutional_editorial")
    offset = 0 if fmt == "reel" else 1
    return variants[(number - 1 + offset) % len(variants)]


def _proofs(job: dict[str, Any]) -> list[str]:
    keywords = [str(x).strip() for x in list(job.get("topic_keywords") or []) if str(x).strip()]
    defaults = ["METODO F1", "TERRITORIO", "STRATEGIA"]
    values = keywords[:3] or defaults
    while len(values) < 3:
        values.append(defaults[len(values)])
    return [value.upper() for value in values[:3]]


def _first_cover_title(slides: list[dict[str, str]], title: str) -> str:
    raw = str(slides[0].get("title") if slides else title).strip()
    if not raw:
        raw = title
    words = raw.replace("\n", " ").split()
    if len(words) <= 8:
        return raw
    # The Golden Master requires covers readable at grid size: never dump a long headline into the tile.
    return " ".join(words[:8])


def job_to_content_spec(job: dict[str, Any], source_image: str | Path) -> dict[str, Any]:
    fmt = str(job.get("format") or "").lower()
    if fmt not in {"reel", "carousel"}:
        raise ValueError(f"Unsupported F1 qualified format for Renderer V2: {fmt!r}")

    slides = [_clean_slide(value) for value in list(job.get("slides") or [])]
    title = str(job.get("title") or (slides[0].get("title") if slides else "F1 IMMOBILIARE"))
    subtitle = str(job.get("main_message") or "")
    cta = str(job.get("cta") or "Scrivi VALUTAZIONE")
    source_item_id = str(job.get("source_item_id") or "")
    family = _family(job)
    variant = _visual_variant(source_item_id, fmt, family)
    cover_title = _first_cover_title(slides, title)

    return {
        "type": "reel" if fmt == "reel" else "carousel",
        "format": "9:16" if fmt == "reel" else "4:5",
        "template": "f1_golden_master_reel_v4" if fmt == "reel" else "f1_golden_master_carousel_v4",
        "brand": dict(F1_BRAND),
        "content": {
            "title": title,
            "cover_title": cover_title,
            "subtitle": subtitle,
            "body": str(job.get("caption") or ""),
            "cta": cta,
            "short_cta": "SCRIVI VALUTAZIONE",
            "duration_s": float(job.get("reel_duration_seconds") or 28) if fmt == "reel" else 1,
            "slides": slides,
            "proofs": _proofs(job),
        },
        "assets": {
            "images": [str(source_image)],
        },
        "audio": {
            "voiceover_text": str(job.get("voiceover") or ""),
            "rights": str(job.get("audio_rights") or ""),
        },
        "captions": {
            "enabled": bool(job.get("muted_view_comprehension_required", False)),
            "items": [],
        },
        "metadata": {
            "job_id": str(job.get("id") or ""),
            "source_item_id": source_item_id,
            "lead_goal": str(job.get("lead_goal") or ""),
            "safe_bottom_fraction": float(job.get("essential_content_safe_bottom_fraction") or 0.35),
            "unique_primary_visual": bool(job.get("unique_primary_visual", False)),
            "family": family,
            "variant": variant,
            "design_version": GOLDEN_MASTER_VERSION,
            "golden_master_version": GOLDEN_MASTER_VERSION,
            "locked_template": True,
            "feed_first": True,
            "feed_safe_square_px": 1080,
            "headline_max_words": 8,
            "palette_locked": True,
            "logo_position": "top_left",
            "cta_position": "lower_panel",
        },
        "output": {"quality": 94},
    }
