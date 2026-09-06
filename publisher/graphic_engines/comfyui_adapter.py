from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from .base import GraphicResult


class ComfyUIEngine:
    name = "comfyui"

    def __init__(self, base_url: str | None = None, workflow_path: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("COMFYUI_URL") or "").rstrip("/")
        self.workflow_path = workflow_path or os.getenv("COMFYUI_WORKFLOW")
        if not self.base_url:
            raise RuntimeError("COMFYUI_URL is not configured")
        if not self.workflow_path:
            raise RuntimeError("COMFYUI_WORKFLOW is not configured")

    def _load_workflow(self) -> dict[str, Any]:
        path = Path(self.workflow_path)
        if not path.exists():
            raise RuntimeError(f"ComfyUI workflow not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _inject_prompt(workflow: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        prompt = str(spec.get("prompt") or spec.get("headline") or "").strip()
        negative = str(spec.get("negative_prompt") or "").strip()
        seed = int(spec.get("seed") or 0)
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            title = str((node.get("_meta") or {}).get("title") or "").lower()
            class_type = str(node.get("class_type") or "").lower()
            if "positive" in title and "text" in inputs:
                inputs["text"] = prompt
            elif "negative" in title and "text" in inputs:
                inputs["text"] = negative
            elif "cliptextencode" in class_type and "text" in inputs and not inputs.get("text"):
                inputs["text"] = prompt
            if seed and "seed" in inputs:
                inputs["seed"] = seed
        return workflow

    def generate(self, spec: dict[str, Any], output_path: Path) -> GraphicResult:
        workflow = self._inject_prompt(self._load_workflow(), spec)
        client_id = str(uuid.uuid4())
        response = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=120,
        )
        response.raise_for_status()
        prompt_id = str(response.json()["prompt_id"])

        deadline = time.time() + int(spec.get("timeout_seconds") or 900)
        history: dict[str, Any] = {}
        while time.time() < deadline:
            r = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=60)
            r.raise_for_status()
            history = r.json()
            if prompt_id in history:
                break
            time.sleep(2)
        else:
            raise RuntimeError(f"ComfyUI generation timed out: {prompt_id}")

        outputs = (history.get(prompt_id) or {}).get("outputs") or {}
        image_info: dict[str, Any] | None = None
        for node_output in outputs.values():
            images = (node_output or {}).get("images") or []
            if images:
                image_info = images[0]
                break
        if not image_info:
            raise RuntimeError("ComfyUI returned no image output")

        params = {
            "filename": image_info["filename"],
            "subfolder": image_info.get("subfolder", ""),
            "type": image_info.get("type", "output"),
        }
        image = requests.get(f"{self.base_url}/view", params=params, timeout=120)
        image.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image.content)

        return GraphicResult(
            engine=self.name,
            output_path=output_path,
            metadata={"prompt_id": prompt_id, "source": image_info},
        )
