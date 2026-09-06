from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

from .engine_router import configured_engine_order

ROOT = Path(__file__).resolve().parents[2]


def check_module(name: str) -> dict[str, object]:
    try:
        importlib.import_module(name)
        return {"module": name, "ok": True}
    except Exception as exc:
        return {"module": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    modules = [
        "publisher.graphic_engines.base",
        "publisher.graphic_engines.comfyui_adapter",
        "publisher.graphic_engines.openai_adapter",
        "publisher.graphic_engines.http_image_adapter",
        "publisher.graphic_engines.local_renderer_adapter",
        "publisher.graphic_engines.engine_router",
        "publisher.rendering.content_engine",
    ]
    module_checks = [check_module(name) for name in modules]

    workflow_path = os.getenv("COMFYUI_WORKFLOW", "").strip()
    config = {
        "engine_order": configured_engine_order(),
        "comfyui": {
            "url_configured": bool(os.getenv("COMFYUI_URL", "").strip()),
            "workflow_configured": bool(workflow_path),
            "workflow_exists": bool(workflow_path and Path(workflow_path).exists()),
        },
        "openai": {"api_key_configured": bool(os.getenv("OPENAI_API_KEY", "").strip())},
        "http": {"url_configured": bool(os.getenv("F1_HTTP_GRAPHIC_URL", "").strip())},
        "local_renderer": {
            "content_engine_exists": (ROOT / "publisher" / "rendering" / "content_engine.py").exists()
        },
    }

    fatal = [row for row in module_checks if not row["ok"]]
    if not config["local_renderer"]["content_engine_exists"]:
        fatal.append({"module": "local_renderer", "ok": False, "error": "content_engine.py missing"})

    payload = {
        "status": "OK" if not fatal else "ERROR",
        "modules": module_checks,
        "configuration": config,
        "fatal": fatal,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not fatal else 1


if __name__ == "__main__":
    raise SystemExit(main())
