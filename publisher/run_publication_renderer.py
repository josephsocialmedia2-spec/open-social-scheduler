#!/usr/bin/env python3
"""Entrypoint for automatic social rendering.

F1 Immobiliare is never rendered when its client configuration is manual-only.
Other clients keep using the existing renderer.
"""
from __future__ import annotations

import json
from pathlib import Path

import render_photos_only as renderer

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
F1_CLIENT = ROOT / "publisher" / "clients" / "f1-immobiliare.json"


def f1_manual_only() -> bool:
    cfg = json.loads(F1_CLIENT.read_text(encoding="utf-8"))
    return (
        str(cfg.get("graphics_source") or "") == "manual_only"
        and cfg.get("publish_only") is True
        and cfg.get("automatic_rendering") is False
    )


def current_cycle_f1_jobs() -> list[dict]:
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    key = queue.get("current_cycle")
    return [
        job for job in queue.get("jobs", [])
        if job.get("cycle_key") == key and str(job.get("client_id") or "") == "f1-immobiliare"
    ]


if __name__ == "__main__":
    manual = f1_manual_only()
    f1_jobs = current_cycle_f1_jobs()
    if manual and f1_jobs:
        raise SystemExit(
            "F1 MANUAL PUBLISH ONLY violation: automatic F1 jobs reached the renderer"
        )

    f1_renderer = None
    if not manual:
        import f1_premium_renderer as f1_renderer
        f1_renderer.install()

    rc = renderer.main()
    if rc not in (None, 0):
        raise SystemExit(rc)

    if f1_renderer is not None:
        f1_renderer.validate_f1_outputs()

    print(f"AUTOMATIC_RENDER_COMPLETE F1_manual_only={manual} F1_auto_jobs={len(f1_jobs)}")
    raise SystemExit(0)
