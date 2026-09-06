from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from PIL import Image


@dataclass
class GraphicResult:
    engine: str
    output_path: Path
    metadata: dict[str, Any]


class GraphicEngine(Protocol):
    name: str

    def generate(self, spec: dict[str, Any], output_path: Path) -> GraphicResult:
        ...


def validate_final_asset(path: str | Path, *, minimum_bytes: int = 10_000) -> dict[str, Any]:
    asset = Path(path)
    if not asset.exists():
        raise RuntimeError(f"Graphic engine did not create the requested output: {asset}")
    size = asset.stat().st_size
    if size < minimum_bytes:
        raise RuntimeError(f"Generated asset is unexpectedly small: {asset} ({size} bytes)")

    metadata: dict[str, Any] = {
        "bytes": size,
        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
        "suffix": asset.suffix.lower(),
    }

    if asset.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
        with Image.open(asset) as image:
            metadata["dimensions"] = [int(image.width), int(image.height)]
            metadata["mode"] = image.mode
            if image.width < 900 or image.height < 900:
                raise RuntimeError(
                    f"Generated visual resolution is too small: {image.size}; expected social-ready output"
                )

    return metadata
