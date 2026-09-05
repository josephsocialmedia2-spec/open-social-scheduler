from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

GOLDEN_MASTER_VERSION = "F1_GOLDEN_MASTER_FEED_V4"
EXPECTED_GREEN = "#4E9E15"
EXPECTED_DARK = "#0A0D0A"
EXPECTED_BACKGROUND = "#FFFFFF"
ALLOWED_FAMILIES = {"property", "recruiting", "institutional"}


def _rgb_stats(path: Path, *, crop_feed_square: bool) -> dict[str, float]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        if crop_feed_square:
            side = min(rgb.width, rgb.height, 1080)
            rgb = rgb.crop((0, 0, min(1080, rgb.width), side))
        rgb.thumbnail((180, 180))
        pixels = list(rgb.getdata())
    if not pixels:
        raise RuntimeError(f"No pixels available for visual compliance: {path}")
    total = float(len(pixels))
    white = sum(1 for r, g, b in pixels if r >= 232 and g >= 232 and b >= 232) / total
    dark = sum(1 for r, g, b in pixels if r <= 52 and g <= 56 and b <= 52) / total
    green = sum(1 for r, g, b in pixels if g >= 78 and g >= r * 1.20 and g >= b * 1.20) / total
    luminance = sum((0.2126 * r + 0.7152 * g + 0.0722 * b) for r, g, b in pixels) / total
    return {
        "white_ratio": round(white, 4),
        "dark_ratio": round(dark, 4),
        "green_ratio": round(green, 4),
        "mean_luminance": round(luminance, 2),
    }


def _assert_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = dict(spec.get("metadata") or {})
    brand = dict(spec.get("brand") or {})
    checks: list[dict[str, Any]] = []

    required = {
        "golden_master_version": metadata.get("golden_master_version") == GOLDEN_MASTER_VERSION,
        "design_version": metadata.get("design_version") == GOLDEN_MASTER_VERSION,
        "locked_template": metadata.get("locked_template") is True,
        "feed_first": metadata.get("feed_first") is True,
        "feed_safe_square_px": int(metadata.get("feed_safe_square_px") or 0) == 1080,
        "headline_max_words": int(metadata.get("headline_max_words") or 0) == 8,
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
    checks.append({"name": "locked_golden_master_contract", "passed": not failed, "failed": failed})
    if failed:
        raise RuntimeError("Golden Master structural FAIL: " + ", ".join(failed))
    return checks


def _assert_frame(path: Path, *, label: str) -> dict[str, Any]:
    stats = _rgb_stats(path, crop_feed_square=True)
    critical = {
        "white_field": stats["white_ratio"] >= 0.08,
        "f1_green_present": stats["green_ratio"] >= 0.002,
        "dark_brand_present": stats["dark_ratio"] >= 0.004,
        "not_dark_feed_cover": stats["mean_luminance"] >= 92.0,
    }
    failed = [name for name, passed in critical.items() if not passed]
    row = {"name": label, "passed": not failed, "stats": stats, "failed": failed}
    if failed:
        raise RuntimeError(f"Golden Master visual FAIL for {path}: {', '.join(failed)} stats={stats}")
    return row


def _video_cover(video: Path) -> Path:
    handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    handle.close()
    frame = Path(handle.name)
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", "1.0", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(frame),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not frame.exists() or frame.stat().st_size < 5000:
        frame.unlink(missing_ok=True)
        raise RuntimeError(f"Unable to extract Reel cover for visual compliance: {video}: {proc.stderr.strip()}")
    return frame


def visual_compliance_gate(paths: list[Path], spec: dict[str, Any]) -> dict[str, Any]:
    checks = _assert_spec(spec)
    kind = str(spec.get("type") or "")
    if kind in {"static", "photo", "carousel"}:
        for index, path in enumerate(paths, 1):
            checks.append(_assert_frame(path, label=f"feed_cover_static_{index:02d}"))
    else:
        frame = _video_cover(paths[0])
        try:
            checks.append(_assert_frame(frame, label="feed_cover_reel_at_1s"))
        finally:
            frame.unlink(missing_ok=True)

    # Critical checks are PASS/FAIL; a passing deterministic locked template scores 100.
    return {
        "passed": True,
        "score": 100,
        "golden_master": GOLDEN_MASTER_VERSION,
        "checks": checks,
    }
