from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class RevideoAdapter:
    name = "revideo"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.node_dir = root / "publisher" / "rendering" / "node"

    def render(self, spec: dict[str, Any], output: Path) -> list[Path]:
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        ) as handle:
            json.dump(spec, handle, ensure_ascii=False)
            spec_path = Path(handle.name)
        try:
            cmd = [
                "npm",
                "run",
                "render:video",
                "--",
                "--spec",
                str(spec_path),
                "--output",
                str(output),
            ]
            proc = subprocess.run(
                cmd,
                cwd=self.node_dir,
                text=True,
                capture_output=True,
                check=False,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    "Revideo renderer failed: "
                    + (proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
                )
            if not output.exists():
                raise RuntimeError(f"Revideo completed without creating {output}")
            return [output]
        finally:
            spec_path.unlink(missing_ok=True)
