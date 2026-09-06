from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import requests

from .base import GraphicResult, validate_final_asset


class HTTPImageEngine:
    """Generic JSON-over-HTTP image generator adapter.

    Expected request body: the full F1 graphic spec as JSON.
    Supported responses:
      {"image_base64": "..."}
      {"image_url": "https://..."}

    Configure with F1_HTTP_GRAPHIC_URL and optionally F1_HTTP_GRAPHIC_TOKEN.
    This adapter exists so a future FLUX/InvokeAI/custom service can be swapped in
    without changing the rest of the F1 pipeline.
    """

    name = "http"

    def __init__(self) -> None:
        self.url = os.getenv("F1_HTTP_GRAPHIC_URL", "").strip()
        self.token = os.getenv("F1_HTTP_GRAPHIC_TOKEN", "").strip()
        if not self.url:
            raise RuntimeError("F1_HTTP_GRAPHIC_URL is not configured")

    def generate(self, spec: dict[str, Any], output_path: Path) -> GraphicResult:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        response = requests.post(self.url, json=spec, headers=headers, timeout=300)
        response.raise_for_status()
        payload = response.json()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if payload.get("image_base64"):
            output_path.write_bytes(base64.b64decode(payload["image_base64"]))
        elif payload.get("image_url"):
            image = requests.get(str(payload["image_url"]), timeout=180)
            image.raise_for_status()
            output_path.write_bytes(image.content)
        else:
            raise RuntimeError("HTTP graphic engine returned neither image_base64 nor image_url")

        asset_meta = validate_final_asset(output_path)
        return GraphicResult(
            engine=self.name,
            output_path=output_path,
            metadata={"remote_metadata": payload.get("metadata") or {}, "asset": asset_meta},
        )
