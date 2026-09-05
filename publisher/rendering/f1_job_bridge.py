from __future__ import annotations

import re
from pathlib import Path
from typing import Any


GOLDEN_MASTER_VERSION = "F1_REFERENCE_FEED_V5"

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
    explicit = str(job.get("visual_family") or "").strip().lower()
    if explicit in {"property", "recruiting", "institutional"}:
        return explicit
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
        "camera", "bagno", "mq", "metr", "planimetr", "distribuzione", "moncalieri",
    )
    if any(term in haystack for term in recruiting):
        return "recruiting"
    if any(term in haystack for term in property_terms):
        return "property"
    return "institutional"


def _visual_variant(source_item_id: str, fmt: str, family: str) -> str:
    match = re.search(r"(\d+)", source_item_id or "")
    number = int(match.group(1)) if match else 1
    if family == "recruiting":
        variants = ("recruit_portrait", "recruit_split", "recruit_portrait")
    elif family == "property":
        variants = ("property_listing", "property_feature", "property_location", "property_plan")
    else:
        variants = ("institutional_split", "institutional_photo", "institutional_service")
    offset = 0 if fmt == "reel" else 1
    return variants[(number - 1 + offset) % len(variants)]


def _proofs(job: dict[str, Any], family: str) -> list[str]:
    keywords = [str(x).strip() for x in list(job.get("topic_keywords") or []) if str(x).strip()]
    if family == "property":
        defaults = ["AMBIENTI LUMINOSI", "ZONA COMODA E SERVITA", "SPAZI BEN DISTRIBUITI"]
    elif family == "recruiting":
        defaults = ["FORMAZIONE INTERNA", "TERRITORIO ASSEGNATO", "PERCORSO DI CRESCITA"]
    else:
        defaults = ["METODO F1", "TERRITORIO", "STRATEGIA"]
    values = keywords[:3] or defaults
    while len(values) < 3:
        values.append(defaults[len(values)])
    return [value.upper() for value in values[:3]]


def _first_cover_title(slides: list[dict[str, str]], title: str) -> str:
    raw = str(slides[0].get("title") if slides else title).strip() or title
    words = raw.replace("\n", " ").split()
    return raw if len(words) <= 7 else " ".join(words[:7])


def _short_cta(family: str) -> str:
    if family == "recruiting":
        return "CANDIDATI ORA"
    if family == "property":
        return "PRENOTA LA TUA VISITA"
    return "SCRIVI VALUTAZIONE"


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
        "template": "f1_reference_feed_reel_v5" if fmt == "reel" else "f1_reference_feed_carousel_v5",
        "brand": dict(F1_BRAND),
        "content": {
            "title": title,
            "cover_title": cover_title,
            "subtitle": subtitle,
            "body": str(job.get("caption") or ""),
            "cta": cta,
            "short_cta": _short_cta(family),
            "duration_s": float(job.get("reel_duration_seconds") or 28) if fmt == "reel" else 1,
            "slides": slides,
            "proofs": _proofs(job, family),
            "price": str(job.get("price") or ""),
            "location": str(job.get("location") or job.get("comune") or ""),
            "features": [str(x) for x in list(job.get("features") or [])[:6]],
        },
        "assets": {"images": [str(source_image)]},
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
            "headline_max_words": 7,
            "palette_locked": True,
            "logo_position": "top_left",
            "cta_position": "lower_panel",
            "reference_layout": "instagram_f1_reference_2026_09_05",
        },
        "output": {"quality": 95},
    }
