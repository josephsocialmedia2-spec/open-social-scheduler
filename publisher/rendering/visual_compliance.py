from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

GOLDEN_MASTER_VERSION = "F1_REFERENCE_FEED_V5"
EXPECTED_GREEN = "#4E9E15"
EXPECTED_DARK = "#0A0D0A"
EXPECTED_BACKGROUND = "#FFFFFF"
ALLOWED_FAMILIES = {"property", "recruiting", "institutional"}


def _stats(image: Image.Image) -> dict[str, float]:
    rgb = image.convert("RGB")
    rgb.thumbnail((220, 220))
    pixels = list(rgb.getdata())
    total = float(len(pixels) or 1)
    white = sum(1 for r, g, b in pixels if r >= 232 and g >= 232 and b >= 232) / total
    dark = sum(1 for r, g, b in pixels if r <= 58 and g <= 62 and b <= 58) / total
    green = sum(1 for r, g, b in pixels if g >= 75 and g >= r * 1.18 and g >= b * 1.18) / total
    luminance = sum((0.2126 * r + 0.7152 * g + 0.0722 * b) for r, g, b in pixels) / total
    # crude visual entropy proxy: count coarse RGB buckets
    buckets = len({(r // 32, g // 32, b // 32) for r, g, b in pixels})
    return {
        "white_ratio": round(white, 4),
        "dark_ratio": round(dark, 4),
        "green_ratio": round(green, 4),
        "mean_luminance": round(luminance, 2),
        "color_buckets": float(buckets),
    }


def _rgb_stats(path: Path) -> dict[str, dict[str, float]]:
    with Image.open(path) as source:
        rgb = source.convert("RGB")
        square_h = min(1080, rgb.height)
        square = rgb.crop((0, 0, min(1080, rgb.width), square_h))
        w, h = square.size
        regions = {
            "full": square,
            "top": square.crop((0, 0, w, max(1, int(h * 0.22)))),
            "left": square.crop((0, int(h * 0.18), max(1, int(w * 0.52)), h)),
            "right": square.crop((int(w * 0.44), int(h * 0.18), w, h)),
            "bottom": square.crop((0, int(h * 0.82), w, h)),
        }
        return {name: _stats(region) for name, region in regions.items()}


def _assert_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = dict(spec.get("metadata") or {})
    brand = dict(spec.get("brand") or {})
    required = {
        "golden_master_version": metadata.get("golden_master_version") == GOLDEN_MASTER_VERSION,
        "design_version": metadata.get("design_version") == GOLDEN_MASTER_VERSION,
        "reference_layout": metadata.get("reference_layout") == "instagram_f1_reference_2026_09_05",
        "locked_template": metadata.get("locked_template") is True,
        "feed_first": metadata.get("feed_first") is True,
        "feed_safe_square_px": int(metadata.get("feed_safe_square_px") or 0) == 1080,
        "headline_max_words": int(metadata.get("headline_max_words") or 0) <= 7,
        "palette_locked": metadata.get("palette_locked") is True,
        "family": str(metadata.get("family") or "") in ALLOWED_FAMILIES,
        "logo_position": metadata.get("logo_position") == "top_left",
        "cta_position": metadata.get("cta_position") == "lower_panel",
        "brand_green": str(brand.get("primary") or "").upper() == EXPECTED_GREEN,
        "brand_dark": str(brand.get("secondary") or "").upper() == EXPECTED_DARK,
        "brand_background": str(brand.get("background") or "").upper() == EXPECTED_BACKGROUND,
        "primary_phone": str(brand.get("phone_primary") or "") == "+39 371 370 8294",
        "secondary_phone": str(brand.get("phone_secondary") or "") == "+39 371 424 6300",
        "site": str(brand.get("site") or "").replace("https://", "").replace("http://", "").rstrip("/") == "www.f1immobiliare.com",
    }
    failed = [name for name, passed in required.items() if not passed]
    row = {"name": "locked_reference_contract", "passed": not failed, "failed": failed}
    if failed:
        raise RuntimeError("Reference feed structural FAIL: " + ", ".join(failed))
    return [row]


def _assert_frame(path: Path, *, label: str) -> dict[str, Any]:
    stats = _rgb_stats(path)
    full, top, left, right, bottom = (stats[k] for k in ("full", "top", "left", "right", "bottom"))
    critical = {
        "bright_feed_cover": full["mean_luminance"] >= 108.0,
        "white_brand_field": top["white_ratio"] >= 0.28,
        "f1_green_present": full["green_ratio"] >= 0.004,
        "dark_brand_present": full["dark_ratio"] >= 0.01,
        "left_copy_field": left["white_ratio"] >= 0.16,
        "right_hero_visual": right["color_buckets"] >= 18,
        "bottom_brand_anchor": bottom["dark_ratio"] >= 0.006 or bottom["green_ratio"] >= 0.004,
    }
    failed = [name for name, passed in critical.items() if not passed]
    row = {"name": label, "passed": not failed, "stats": stats, "failed": failed}
    if failed:
        raise RuntimeError(f"Reference feed visual FAIL for {path}: {', '.join(failed)}")
    return row


def _video_cover(video: Path) -> Path:
    handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    handle.close()
    frame = Path(handle.name)
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.2", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(frame)],
        text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0 or not frame.exists() or frame.stat().st_size < 5000:
        frame.unlink(missing_ok=True)
        raise RuntimeError(f"Unable to extract Reel cover: {video}: {proc.stderr.strip()}")
    return frame


def visual_compliance_gate(paths: list[Path], spec: dict[str, Any]) -> dict[str, Any]:
    checks = _assert_spec(spec)
    kind = str(spec.get("type") or "")
    if kind in {"static", "photo", "carousel"}:
        for index, path in enumerate(paths, 1):
            checks.append(_assert_frame(path, label=f"reference_static_{index:02d}"))
    else:
        frame = _video_cover(paths[0])
        try:
            checks.append(_assert_frame(frame, label="reference_reel_cover"))
        finally:
            frame.unlink(missing_ok=True)
    return {
        "passed": True,
        "score": 100,
        "golden_master": GOLDEN_MASTER_VERSION,
        "checks": checks,
    }
