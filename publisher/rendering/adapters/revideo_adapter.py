from __future__ import annotations

import base64
import json
import mimetypes
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import requests


class RevideoAdapter:
    name = "revideo"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.node_dir = root / "publisher" / "rendering" / "node"

    def _hydrate_images(self, spec: dict[str, Any]) -> dict[str, Any]:
        clone = json.loads(json.dumps(spec))
        assets = clone.setdefault("assets", {})
        hydrated: list[str] = []
        for raw in list(assets.get("images") or [])[:8]:
            value = str(raw or "").strip()
            if not value:
                continue
            if value.startswith("data:"):
                hydrated.append(value)
                continue
            if value.startswith("https://") or value.startswith("http://"):
                response = requests.get(
                    value,
                    timeout=35,
                    allow_redirects=True,
                    headers={"User-Agent": "F1-Renderer-V2/1.0"},
                )
                response.raise_for_status()
                content_type = str(response.headers.get("content-type") or "").split(";", 1)[0]
                if not content_type.startswith("image/"):
                    raise RuntimeError(f"Remote asset is not an image: {value} ({content_type})")
                payload = base64.b64encode(response.content).decode("ascii")
                hydrated.append(f"data:{content_type};base64,{payload}")
                continue
            path = Path(value)
            if not path.is_absolute():
                path = self.root / path
            if not path.exists():
                raise FileNotFoundError(path)
            content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            payload = base64.b64encode(path.read_bytes()).decode("ascii")
            hydrated.append(f"data:{content_type};base64,{payload}")
        assets["images"] = hydrated
        return clone

    def render(self, spec: dict[str, Any], output: Path) -> list[Path]:
        output.parent.mkdir(parents=True, exist_ok=True)
        hydrated = self._hydrate_images(spec)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        ) as handle:
            json.dump(hydrated, handle, ensure_ascii=False)
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
