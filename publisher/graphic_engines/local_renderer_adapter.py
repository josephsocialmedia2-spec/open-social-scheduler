from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .base import GraphicResult, validate_final_asset


class LocalRendererEngine:
    name = "local-renderer"

    def generate(self, spec: dict[str, Any], output_path: Path) -> GraphicResult:
        from publisher.rendering.content_engine import generate_content

        local_spec = dict(spec)
        local_spec.setdefault("type", "static")
        local_spec.setdefault("format", "4:5")
        local_spec.setdefault("content", {})

        result = generate_content(local_spec, output=output_path, allow_fallback=True)
        candidates = result.get("outputs") or result.get("files") or []
        candidate = Path(str(candidates[0])) if candidates else output_path

        if candidate != output_path and candidate.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, output_path)

        asset_meta = validate_final_asset(output_path)
        return GraphicResult(
            engine=self.name,
            output_path=output_path,
            metadata={"renderer": result, "asset": asset_meta},
        )
