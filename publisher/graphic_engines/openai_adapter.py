from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GraphicResult


class OpenAIVisualEngine:
    """Thin adapter over the existing F1 OpenAI visual engine.

    Kept behind the common graphic-engine interface so it can be replaced
    without touching the queue or publisher.
    """

    name = "openai"

    def generate(self, spec: dict[str, Any], output_path: Path) -> GraphicResult:
        from publisher.rendering import openai_visual_engine

        fn = getattr(openai_visual_engine, "generate_visual", None)
        if fn is None:
            fn = getattr(openai_visual_engine, "generate_image", None)
        if fn is None:
            raise RuntimeError("Existing OpenAI visual engine exposes no supported generate function")

        result = fn(spec, output_path)
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("OpenAI visual engine did not create the requested output")
        return GraphicResult(
            engine=self.name,
            output_path=output_path,
            metadata={"wrapped_result": result},
        )
