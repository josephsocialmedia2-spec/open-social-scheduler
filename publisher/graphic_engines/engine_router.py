from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import GraphicResult
from .comfyui_adapter import ComfyUIEngine
from .local_renderer_adapter import LocalRendererEngine
from .openai_adapter import OpenAIVisualEngine

ENGINE_ORDER_DEFAULT = ["comfyui", "openai", "local-renderer"]


def _build_engine(name: str):
    key = name.strip().lower()
    if key == "comfyui":
        return ComfyUIEngine()
    if key == "openai":
        return OpenAIVisualEngine()
    if key in {"local", "local-renderer", "svg"}:
        return LocalRendererEngine()
    raise ValueError(f"Unsupported graphic engine: {name}")


def generate_final_visual(spec: dict[str, Any], output_path: str | Path) -> GraphicResult:
    output = Path(output_path)
    configured = os.getenv("F1_GRAPHIC_ENGINE_ORDER", "").strip()
    order = [x.strip() for x in configured.split(",") if x.strip()] or ENGINE_ORDER_DEFAULT
    errors: list[str] = []

    for name in order:
        try:
            engine = _build_engine(name)
            result = engine.generate(spec, output)
            result.metadata.setdefault("engine_order", order)
            result.metadata.setdefault("fallback_used", name != order[0])
            return result
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    raise RuntimeError("All graphic engines failed: " + " | ".join(errors))
