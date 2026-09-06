from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .base import GraphicResult


class LocalRendererEngine:
    name = "local-renderer"

    def generate(self, spec: dict[str, Any], output_path: Path) -> GraphicResult:
        from publisher.rendering.content_engine import generateContent

        local_spec = dict(spec)
        local_spec.setdefault("type", "static")
        local_spec.setdefault("format", "4:5")
        local_spec.setdefault("outputs", [str(output_path)])
        result = generateContent(local_spec, allow_fallback=True)

        candidates = result.get("outputs") or result.get("files") or []
        candidate = Path(str(candidates[0])) if candidates else output_path
        if candidate != output_path and candidate.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, output_path)
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Local renderer did not create the requested output")
        return GraphicResult(engine=self.name, output_path=output_path, metadata={"renderer": result})
