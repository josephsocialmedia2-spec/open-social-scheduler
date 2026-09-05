#!/usr/bin/env python3
"""Render the qualified 14-day F1 batch with one unique primary visual per content.

Migration contract:
- `F1_RENDERER_ENGINE=v2` routes visuals through Renderer V2;
- the exact legacy renderer remains an explicit fallback while migration is staged;
- `F1_RENDERER_V2_STRICT=1` disables legacy fallback and is used by migration CI.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import render_f1_qualified_14d as base
from rendering.content_engine import generate_content
from rendering.f1_job_bridge import job_to_content_spec

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "qualified_14d_queue.json"
CACHE = ROOT / ".cache" / "f1-qualified-sources"


def cache_path(url: str) -> Path:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE / f"{key}.jpg"


def relative(path: str | Path) -> str:
    return str(Path(path).resolve().relative_to(ROOT.resolve()))


def v2_output(job: dict) -> Path:
    fmt = str(job.get("format") or "")
    if fmt == "reel":
        return ROOT / str(job["media"])
    media = [str(x) for x in list(job.get("media") or [])]
    if not media:
        raise RuntimeError(f"Carousel has no output media: {job.get('id')}")
    first = ROOT / media[0]
    stem = re.sub(r"-\d+$", "", first.stem)
    return first.with_name(stem + first.suffix)


def render_v2(job: dict, src: Path) -> dict:
    spec = job_to_content_spec(job, src)
    result = generate_content(spec, output=v2_output(job), allow_fallback=False)
    outputs = [relative(path) for path in result.get("outputs") or []]
    if job.get("format") == "reel":
        if len(outputs) != 1 or not outputs[0].endswith(".mp4"):
            raise RuntimeError(f"Renderer V2 reel output mismatch: {job.get('id')} {outputs}")
        job["media"] = outputs[0]
        job["render_status"] = "RENDERED_REEL_MP4_V2"
    else:
        expected = len(list(job.get("slides") or []))
        if len(outputs) != expected:
            raise RuntimeError(
                f"Renderer V2 carousel output mismatch: {job.get('id')} expected={expected} got={len(outputs)}"
            )
        job["media"] = outputs
        job["render_status"] = "RENDERED_CAROUSEL_JPG_V2"
    job["renderer_v2"] = {
        "engine": result.get("engine"),
        "primary_engine": result.get("primary_engine"),
        "fallback_used": bool(result.get("fallback_used")),
        "audio": result.get("audio"),
        "quality_gate": result.get("quality_gate"),
        "visual_compliance": result.get("visual_compliance"),
    }
    return result


def render_legacy(job: dict, src: Path) -> None:
    if job.get("format") == "reel":
        base.render_reel(job, [src])
    elif job.get("format") == "carousel":
        base.render_carousel(job, [src])
    else:
        raise RuntimeError(f"Unsupported format {job.get('format')}")
    job["renderer_v2"] = {
        "engine": "legacy-pillow-ffmpeg",
        "primary_engine": None,
        "fallback_used": True,
    }


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    jobs = list(data.get("jobs") or [])
    blocked = [j for j in jobs if j.get("gate_status") != "PASSED"]
    if blocked:
        raise RuntimeError(f"Refusing render: {len(blocked)} jobs have not PASSED producer gate")

    engine = os.getenv("F1_RENDERER_ENGINE", "legacy").strip().lower()
    strict_v2 = os.getenv("F1_RENDERER_V2_STRICT", "0") == "1"
    if engine not in {"legacy", "v2"}:
        raise RuntimeError(f"Unsupported F1_RENDERER_ENGINE={engine!r}")

    used: set[str] = set()
    content_hashes: set[str] = set()
    reels = carousels = v2_count = legacy_count = 0
    for job in jobs:
        urls = list(job.get("visual_asset_urls") or [])
        if len(urls) != 1:
            raise RuntimeError(f"{job.get('id')} must have exactly one primary visual URL")
        url = str(urls[0])
        if url in used:
            raise RuntimeError(f"Primary visual reused across contents: {url}")
        used.add(url)
        visual_hash = str(job.get("visual_content_sha256") or "").strip()
        if not visual_hash:
            raise RuntimeError(f"Missing verified visual content hash for {job.get('id')}")
        if visual_hash in content_hashes:
            raise RuntimeError(f"Actual image content reused across contents: {visual_hash}")
        content_hashes.add(visual_hash)

        src = cache_path(url)
        if not src.exists() or src.stat().st_size < 20000:
            raise RuntimeError(f"Cached unique visual missing for {job.get('id')}: {src}")

        if engine == "v2":
            try:
                render_v2(job, src)
                v2_count += 1
            except Exception as exc:
                if strict_v2:
                    raise RuntimeError(f"Renderer V2 strict failure for {job.get('id')}: {exc}") from exc
                print(f"WARN Renderer V2 failed for {job.get('id')}; exact legacy fallback: {exc}")
                render_legacy(job, src)
                legacy_count += 1
        else:
            render_legacy(job, src)
            legacy_count += 1

        if job.get("format") == "reel":
            reels += 1
        elif job.get("format") == "carousel":
            carousels += 1
        else:
            raise RuntimeError(f"Unsupported format {job.get('format')}")

        spec = dict(job.get("render_spec") or {})
        spec["source_policy"] = "one_unique_themed_primary_visual_per_content_no_reuse_14d"
        spec["unique_primary_visual_per_content"] = True
        spec["visual_content_hash_verified"] = True
        spec["legacy_visuals_allowed"] = False
        spec["renderer_migration"] = "v2" if job.get("renderer_v2", {}).get("engine") != "legacy-pillow-ffmpeg" else "legacy_fallback"
        visual = (job.get("renderer_v2") or {}).get("visual_compliance") or {}
        spec["golden_master"] = visual.get("golden_master")
        spec["visual_compliance_score"] = visual.get("score")
        spec["visual_compliance_passed"] = visual.get("passed") is True
        job["render_spec"] = spec

    if len(used) != 28 or len(content_hashes) != 28:
        raise RuntimeError(f"Expected 28 unique URLs and 28 unique content hashes, got {len(used)} / {len(content_hashes)}")

    data["render_summary"] = {
        "reels": reels,
        "carousels": carousels,
        "total": reels + carousels,
        "renderer_v2": v2_count,
        "legacy": legacy_count,
        "requested_engine": engine,
        "strict_v2": strict_v2,
        "golden_master": "F1_GOLDEN_MASTER_FEED_V4",
        "visual_compliance_required": True,
    }
    data["visual_source_policy"] = "28 contents = 28 different themed primary images; URL and normalized pixel hash uniqueness required"
    data["unique_visual_summary"] = {
        "contents": 28,
        "unique_primary_visuals": 28,
        "unique_content_hashes": 28,
        "reuse": 0,
    }
    QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"RENDERED UNIQUE F1 BATCH: reels={reels} carousels={carousels} "
        f"renderer_v2={v2_count} legacy={legacy_count}; reuse=0; golden_master=V4"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
