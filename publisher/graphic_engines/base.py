from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass
class GraphicResult:
    engine: str
    output_path: Path
    metadata: dict[str, Any]


class GraphicEngine(Protocol):
    name: str

    def generate(self, spec: dict[str, Any], output_path: Path) -> GraphicResult:
        ...
