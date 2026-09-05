#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path

try:
    from .content_engine import generate_content
    from .f1_job_bridge import job_to_content_spec
except ImportError:
    from content_engine import generate_content
    from f1_job_bridge import job_to_content_spec

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "publisher" / "qualified_14d_queue.json"
OUT = ROOT / "renderer-v2-qualified-smoke"


def first(jobs: list[dict], fmt: str) -> dict:
    for job in jobs:
        if job.get("format") == fmt and job.get("gate_status") == "PASSED":
            return deepcopy(job)
    raise RuntimeError(f"No PASSED {fmt} job found")


def source(job: dict) -> str:
    urls = [str(x) for x in list(job.get("visual_asset_urls") or []) if str(x).startswith("http")]
    if not urls:
        raise RuntimeError(f"No remote visual for {job.get('id')}")
    return urls[0]


def assert_audio(path: Path) -> None:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name", "-of", "json", str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe audio failed")
    streams = (json.loads(proc.stdout or "{}") or {}).get("streams") or []
    if not streams:
        raise RuntimeError(f"Qualified Reel has no audio stream: {path}")


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    jobs = list(data.get("jobs") or [])
    reel = first(jobs, "reel")
    carousel = first(jobs, "carousel")
    OUT.mkdir(parents=True, exist_ok=True)

    reel_spec = job_to_content_spec(reel, source(reel))
    # Keep all real message frames but shorten the smoke render.
    reel_spec["content"]["duration_s"] = 7
    reel_spec["audio"]["voiceover_text"] = (
        "F1 Immobiliare. Prima i dati, poi la strategia, poi la vendita."
    )
    reel_result = generate_content(
        reel_spec,
        output=OUT / "qualified-reel.mp4",
        allow_fallback=False,
    )
    reel_path = Path(reel_result["outputs"][0])
    assert_audio(reel_path)

    carousel_spec = job_to_content_spec(carousel, source(carousel))
    carousel_result = generate_content(
        carousel_spec,
        output=OUT / "qualified-carousel.jpg",
        allow_fallback=False,
    )

    summary = {
        "status": "QUALIFIED_RENDERER_V2_SMOKE_OK",
        "reel": reel_result,
        "carousel": carousel_result,
        "source_jobs": [reel.get("id"), carousel.get("id")],
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
