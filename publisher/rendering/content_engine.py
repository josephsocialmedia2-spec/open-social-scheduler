#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from PIL import Image

try:
    from .adapters.audio_adapter import AudioAdapter
    from .adapters.pillow_fallback_adapter import PillowFallbackAdapter
    from .adapters.revideo_adapter import RevideoAdapter
    from .adapters.static_svg_adapter import StaticSvgAdapter
    from .visual_compliance import visual_compliance_gate
except ImportError:
    from adapters.audio_adapter import AudioAdapter
    from adapters.pillow_fallback_adapter import PillowFallbackAdapter
    from adapters.revideo_adapter import RevideoAdapter
    from adapters.static_svg_adapter import StaticSvgAdapter
    from visual_compliance import visual_compliance_gate

ROOT = Path(__file__).resolve().parents[2]
STATIC_TYPES = {"static", "photo", "carousel"}
VIDEO_TYPES = {"reel", "video", "story", "ugc"}

DEFAULT_BRAND = {
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


class ContentSpecError(ValueError):
    pass


def normalize_spec(raw: dict[str, Any]) -> dict[str, Any]:
    spec = deepcopy(raw)
    kind = str(spec.get("type") or "").strip().lower()
    if kind not in STATIC_TYPES | VIDEO_TYPES:
        raise ContentSpecError(f"Unsupported content type: {kind!r}")
    spec["type"] = kind
    if not isinstance(spec.get("content"), dict):
        raise ContentSpecError("content must be an object")
    brand = dict(DEFAULT_BRAND)
    brand.update(spec.get("brand") or {})
    spec["brand"] = brand
    spec.setdefault("assets", {})
    spec.setdefault("audio", {})
    spec.setdefault("captions", {"enabled": False, "items": []})
    if not spec.get("format"):
        spec["format"] = "9:16" if kind in VIDEO_TYPES else "4:5"
    return spec


def default_output(spec: dict[str, Any]) -> Path:
    kind = spec["type"]
    base = ROOT / "publisher" / "media" / "generated" / "renderer-v2"
    base.mkdir(parents=True, exist_ok=True)
    if kind == "carousel":
        return base / "carousel.jpg"
    if kind in VIDEO_TYPES:
        return base / f"{kind}.mp4"
    return base / f"{kind}.jpg"


def quality_gate(paths: list[Path], spec: dict[str, Any]) -> dict[str, Any]:
    if not paths:
        raise RuntimeError("Renderer returned no assets")
    kind = spec["type"]
    checks: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            raise RuntimeError(f"Missing rendered file: {path}")
        size = path.stat().st_size
        minimum = 12_000 if kind in STATIC_TYPES else 40_000
        if size < minimum:
            raise RuntimeError(f"Rendered file is unexpectedly small: {path} ({size} bytes)")
        row: dict[str, Any] = {"path": str(path), "bytes": size}
        if kind in STATIC_TYPES:
            with Image.open(path) as image:
                row["dimensions"] = list(image.size)
                expected = (1080, 1350)
                if image.size != expected:
                    raise RuntimeError(f"Wrong static dimensions for {path}: {image.size}; expected {expected}")
        else:
            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height,duration,codec_name",
                    "-of", "json", str(path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if probe.returncode != 0:
                raise RuntimeError(f"ffprobe failed for {path}: {probe.stderr.strip()}")
            payload = json.loads(probe.stdout or "{}")
            streams = payload.get("streams") or []
            if not streams:
                raise RuntimeError(f"No video stream in {path}")
            stream = streams[0]
            row["video"] = stream
            if int(stream.get("width") or 0) != 1080 or int(stream.get("height") or 0) != 1920:
                raise RuntimeError(f"Wrong video dimensions for {path}: {stream}")
        checks.append(row)
    return {"passed": True, "checks": checks}


def _apply_audio(paths: list[Path], spec: dict[str, Any]) -> dict[str, Any]:
    if spec["type"] not in VIDEO_TYPES or not paths:
        return {"applied": False, "engine": None}
    return AudioAdapter(ROOT).apply(paths[0], spec)


def generate_content(
    content_spec: dict[str, Any],
    *,
    output: str | Path | None = None,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    spec = normalize_spec(content_spec)
    out = Path(output) if output else default_output(spec)
    if not out.is_absolute():
        out = ROOT / out
    primary = StaticSvgAdapter(ROOT) if spec["type"] in STATIC_TYPES else RevideoAdapter(ROOT)
    fallback = PillowFallbackAdapter(ROOT)
    fallback_used = False
    primary_error = None
    audio_info: dict[str, Any] = {"applied": False, "engine": None}
    try:
        paths = primary.render(spec, out)
        audio_info = _apply_audio(paths, spec)
        engine = primary.name
    except Exception as exc:
        primary_error = f"{type(exc).__name__}: {exc}"
        if not allow_fallback or os.getenv("RENDERER_V2_NO_FALLBACK") == "1":
            raise
        paths = fallback.render(spec, out)
        audio_info = _apply_audio(paths, spec)
        engine = fallback.name
        fallback_used = True
    gate = quality_gate(paths, spec)
    visual_gate = visual_compliance_gate(paths, spec)
    return {
        "status": "RENDERER_V2_OK",
        "engine": engine,
        "primary_engine": primary.name,
        "fallback_used": fallback_used,
        "primary_error": primary_error,
        "type": spec["type"],
        "format": spec["format"],
        "outputs": [str(path) for path in paths],
        "audio": audio_info,
        "quality_gate": gate,
        "visual_compliance": visual_gate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="F1 Renderer V2 facade")
    parser.add_argument("--spec", required=True, help="ContentSpec JSON file")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--no-fallback", action="store_true")
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    result = generate_content(spec, output=args.output, allow_fallback=not args.no_fallback)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
