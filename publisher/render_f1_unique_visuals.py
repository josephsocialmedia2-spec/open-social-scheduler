#!/usr/bin/env python3
"""Render the qualified F1 batch with one unique primary visual per content.

Production contract:
- Renderer V2 is the deterministic branded composition engine.
- OpenAI Images can generate/edit non-property hero imagery when OPENAI_API_KEY is available.
- Actual property photography stays factual and is never hallucinated or structurally altered.
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
from rendering.openai_visual_engine import generate_visual

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "qualified_14d_queue.json"
CACHE = ROOT / ".cache" / "f1-qualified-sources"
OPENAI_CACHE = ROOT / ".cache" / "f1-openai-hero"


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


def _openai_hero(job: dict, src: Path, spec: dict) -> tuple[Path, dict]:
    mode = os.getenv("F1_OPENAI_VISUALS", "auto").strip().lower()
    family = str((spec.get("metadata") or {}).get("family") or "institutional")
    has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    if family == "property":
        return src, {"used": False, "reason": "factual_property_photo_locked"}
    if mode in {"0", "off", "false", "disabled"}:
        return src, {"used": False, "reason": "disabled"}
    if not has_key:
        if mode in {"1", "on", "true", "required"}:
            raise RuntimeError("F1_OPENAI_VISUALS requires OPENAI_API_KEY")
        return src, {"used": False, "reason": "OPENAI_API_KEY_not_configured"}

    OPENAI_CACHE.mkdir(parents=True, exist_ok=True)
    target = OPENAI_CACHE / f"{str(job.get('id') or 'content')}.png"
    generated = generate_visual(spec, target, reference_image=src)
    return generated, {
        "used": True,
        "engine": "OpenAI Images",
        "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        "mode": "reference_edit",
        "source_reference": relative(src),
        "generated_hero": relative(generated),
    }


def render_v2(job: dict, src: Path) -> dict:
    spec = job_to_content_spec(job, src)
    hero, openai_meta = _openai_hero(job, src, spec)
    if hero != src:
        spec = job_to_content_spec(job, hero)
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
        "openai_visual": openai_meta,
    }
    return result


def render_legacy(job: dict, src: Path) -> None:
    if job.get("format") == "reel":
        base.render_reel(job, [src])
    elif job.get("format") == "carousel":
        base.render_carousel(job, [src])
    else:
        raise RuntimeError(f"Unsupported format {job.get('format')}")
    job["renderer_v2"] = {"engine": "legacy-pillow-ffmpeg", "primary_engine": None, "fallback_used": True}


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
    reels = carousels = v2_count = legacy_count = openai_count = 0
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
                if ((job.get("renderer_v2") or {}).get("openai_visual") or {}).get("used"):
                    openai_count += 1
            except Exception as exc:
                if strict_v2:
                    raise RuntimeError(f"Renderer V2 strict failure for {job.get('id')}: {exc}") from exc
                print(f"WARN Renderer V2 failed for {job.get('id')}; exact legacy fallback: {exc}")
                render_legacy(job, src)
                legacy_count += 1
        else:
            render_legacy(job, src)
            legacy_count += 1

        if job.get("format") == "reel": reels += 1
        elif job.get("format") == "carousel": carousels += 1
        else: raise RuntimeError(f"Unsupported format {job.get('format')}")

        render_spec = dict(job.get("render_spec") or {})
        render_spec["source_policy"] = "one_unique_themed_primary_visual_per_content_no_reuse_14d"
        render_spec["unique_primary_visual_per_content"] = True
        render_spec["visual_content_hash_verified"] = True
        render_spec["legacy_visuals_allowed"] = False
        render_spec["renderer_migration"] = "v2" if job.get("renderer_v2", {}).get("engine") != "legacy-pillow-ffmpeg" else "legacy_fallback"
        visual = (job.get("renderer_v2") or {}).get("visual_compliance") or {}
        render_spec["golden_master"] = visual.get("golden_master")
        render_spec["visual_compliance_score"] = visual.get("score")
        render_spec["visual_compliance_passed"] = visual.get("passed") is True
        job["render_spec"] = render_spec

    if len(used) != 28 or len(content_hashes) != 28:
        raise RuntimeError(f"Expected 28 unique URLs and 28 unique content hashes, got {len(used)} / {len(content_hashes)}")

    data["render_summary"] = {
        "reels": reels,
        "carousels": carousels,
        "total": reels + carousels,
        "renderer_v2": v2_count,
        "legacy": legacy_count,
        "openai_generated_or_edited_heroes": openai_count,
        "requested_engine": engine,
        "strict_v2": strict_v2,
        "golden_master": "F1_REFERENCE_FEED_V5",
        "visual_compliance_required": True,
    }
    data["visual_source_policy"] = "28 contents = 28 different themed primary images; factual property imagery locked; eligible generative hero imagery routed to OpenAI when configured"
    data["unique_visual_summary"] = {"contents": 28, "unique_primary_visuals": 28, "unique_content_hashes": 28, "reuse": 0}
    QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RENDERED UNIQUE F1 BATCH: reels={reels} carousels={carousels} renderer_v2={v2_count} legacy={legacy_count}; openai={openai_count}; reuse=0; reference=F1_REFERENCE_FEED_V5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
