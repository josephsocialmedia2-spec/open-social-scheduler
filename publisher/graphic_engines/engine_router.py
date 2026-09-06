from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import GraphicResult
from .comfyui_adapter import ComfyUIEngine
from .http_image_adapter import HTTPImageEngine
from .local_renderer_adapter import LocalRendererEngine
from .openai_adapter import OpenAIVisualEngine

ENGINE_ORDER_DEFAULT = ["comfyui", "openai", "http", "local-renderer"]


def _build_engine(name: str):
    key = name.strip().lower()
    if key == "comfyui":
        return ComfyUIEngine()
    if key == "openai":
        return OpenAIVisualEngine()
    if key in {"http", "remote", "flux", "invokeai"}:
        return HTTPImageEngine()
    if key in {"local", "local-renderer", "svg"}:
        return LocalRendererEngine()
    raise ValueError(f"Unsupported graphic engine: {name}")


def configured_engine_order() -> list[str]:
    configured = os.getenv("F1_GRAPHIC_ENGINE_ORDER", "").strip()
    return [x.strip() for x in configured.split(",") if x.strip()] or list(ENGINE_ORDER_DEFAULT)


def generate_final_visual(spec: dict[str, Any], output_path: str | Path) -> GraphicResult:
    output = Path(output_path)
    order = configured_engine_order()
    errors: list[str] = []

    for index, name in enumerate(order):
        try:
            engine = _build_engine(name)
            result = engine.generate(spec, output)
            result.metadata.setdefault("engine_order", order)
            result.metadata.setdefault("fallback_used", index > 0)
            result.metadata.setdefault("selected_engine", result.engine)
            if errors:
                result.metadata.setdefault("previous_errors", errors)
            return result
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    raise RuntimeError("All graphic engines failed: " + " | ".join(errors))
