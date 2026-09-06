from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .base import GraphicResult, validate_final_asset


class OpenAIVisualEngine:
    """Adapter over the existing F1 OpenAI visual engine."""

    name = "openai"

    def generate(self, spec: dict[str, Any], output_path: Path) -> GraphicResult:
        from publisher.rendering import openai_visual_engine

        fn = getattr(openai_visual_engine, "generate_visual", None)
        if fn is None:
            fn = getattr(openai_visual_engine, "generate_image", None)
        if fn is None:
            raise RuntimeError("Existing OpenAI visual engine exposes no supported generate function")

        produced = fn(spec, output_path)
        produced_path = Path(produced) if produced else output_path

        if produced_path != output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(produced_path, output_path)

        asset_meta = validate_final_asset(output_path)
        return GraphicResult(
            engine=self.name,
            output_path=output_path,
            metadata={"source_output": str(produced_path), "asset": asset_meta},
        )
