from __future__ import annotations

from pathlib import Path
from typing import Any


F1_BRAND = {
    "name": "F1 IMMOBILIARE",
    "tagline": "CASA E IMPRESE · VALLE DI SUSA",
    "primary": "#66C500",
    "secondary": "#0A0D0A",
    "background": "#F7F8F5",
    "foreground": "#111511",
    "phone_primary": "+39 371 370 8294",
    "phone_secondary": "+39 371 424 6300",
    "site": "https://www.f1immobiliare.com",
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


def job_to_content_spec(job: dict[str, Any], source_image: str | Path) -> dict[str, Any]:
    fmt = str(job.get("format") or "").lower()
    if fmt not in {"reel", "carousel"}:
        raise ValueError(f"Unsupported F1 qualified format for Renderer V2: {fmt!r}")

    slides = [_clean_slide(value) for value in list(job.get("slides") or [])]
    title = str(job.get("title") or (slides[0].get("title") if slides else "F1 IMMOBILIARE"))
    subtitle = str(job.get("main_message") or "")
    cta = str(job.get("cta") or "Scrivi VALUTAZIONE")

    return {
        "type": "reel" if fmt == "reel" else "carousel",
        "format": "9:16" if fmt == "reel" else "4:5",
        "template": "f1_qualified_reel_v2" if fmt == "reel" else "f1_qualified_carousel_v2",
        "brand": dict(F1_BRAND),
        "content": {
            "title": title,
            "subtitle": subtitle,
            "body": str(job.get("caption") or ""),
            "cta": cta,
            "duration_s": float(job.get("reel_duration_seconds") or 28) if fmt == "reel" else 1,
            "slides": slides,
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
            "source_item_id": str(job.get("source_item_id") or ""),
            "lead_goal": str(job.get("lead_goal") or ""),
            "safe_bottom_fraction": float(job.get("essential_content_safe_bottom_fraction") or 0.35),
            "unique_primary_visual": bool(job.get("unique_primary_visual", False)),
        },
        "output": {"quality": 94},
    }
