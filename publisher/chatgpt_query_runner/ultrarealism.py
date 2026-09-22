from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

MASTER_PREFIX = (
    "Create an ultra-realistic, highly photorealistic editorial real-estate photograph, "
    "visually indistinguishable from a professionally shot property photograph. "
    "Use natural physically plausible lighting, authentic Italian residential architecture, "
    "realistic materials and textures, natural human proportions, realistic skin texture, "
    "anatomically correct hands and faces, credible optical depth of field and physically "
    "coherent perspective. The result must look like a real photograph captured by a "
    "professional real-estate photographer, not AI-generated artwork. "
)

MASTER_SUFFIX = (
    " Natural photographic imperfections are allowed and encouraged when they increase realism. "
    "Avoid overly perfect symmetry, artificial staging, synthetic surfaces and exaggerated cinematic effects. "
    "Maintain believable Italian/Piedmont residential architecture, realistic furniture scale, physically "
    "coherent windows, doors, walls, reflections, shadows and perspective. "
    "No illustration, no drawing, no painting, no digital art, no cartoon, no anime, no 3D render, "
    "no architectural render, no CGI, no synthetic-image look, no impossible architecture, no impossible "
    "perspective, no warped walls, no malformed or duplicated windows, no floating or distorted furniture, "
    "no impossible reflections, no incorrect shadows, no excessive HDR, no oversaturation, no plastic materials, "
    "no plastic or waxy skin, no mannequin people, no malformed faces, no asymmetrical artificial eyes, "
    "no distorted bodies, no deformed hands, no extra/missing/fused fingers, no duplicated limbs, "
    "no unnatural posture, no random text, no letters, no captions, no watermark, no signature, "
    "no fake logos, no generated signage, no stock-photo smile and no artificial stock-photo look. "
    "Do not render logos, headlines, CTA, phone numbers, URLs or readable promotional text inside the image."
)

REQUIRED_SCORES = {
    "photorealism_score": 90,
    "architecture_score": 85,
    "lighting_score": 85,
    "materials_score": 85,
    "perspective_score": 85,
    "artifact_free_score": 90,
}

HARD_FAIL_KEYS = (
    "random_text",
    "watermark",
    "fake_logo",
    "major_artifacts",
)


def enforce_ultrarealism_prompt(prompt: str) -> str:
    raw = " ".join(str(prompt or "").split())
    if "visually indistinguishable from a professionally shot property photograph" in raw:
        return raw
    return MASTER_PREFIX + raw + MASTER_SUFFIX


def technical_image_qa(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"technical_pass": False, "reason": "missing_file"}
    try:
        with Image.open(path) as image:
            image = image.convert("RGB")
            width, height = image.size
            stat = ImageStat.Stat(image)
            extrema = image.getextrema()
            dynamic_ranges = [hi - lo for lo, hi in extrema]
            mean_dynamic_range = sum(dynamic_ranges) / max(1, len(dynamic_ranges))
            channel_std = sum(stat.stddev) / max(1, len(stat.stddev))
    except Exception as exc:
        return {"technical_pass": False, "reason": f"invalid_image:{type(exc).__name__}"}

    file_size = path.stat().st_size
    failures = []
    if width < 900 or height < 900:
        failures.append("resolution_too_low")
    if file_size < 20_000:
        failures.append("file_too_small")
    if mean_dynamic_range < 35:
        failures.append("insufficient_dynamic_range")
    if channel_std < 12:
        failures.append("image_too_flat")

    return {
        "technical_pass": not failures,
        "width": width,
        "height": height,
        "file_size": file_size,
        "mean_dynamic_range": round(mean_dynamic_range, 2),
        "channel_stddev": round(channel_std, 2),
        "failures": failures,
    }


def normalize_visual_qa(payload: dict[str, Any], *, people_expected: bool | None = None) -> dict[str, Any]:
    result = dict(payload or {})
    for key in (
        "photorealism_score",
        "anatomy_score",
        "architecture_score",
        "lighting_score",
        "materials_score",
        "perspective_score",
        "artifact_free_score",
        "real_estate_quality_score",
    ):
        try:
            result[key] = int(result.get(key)) if result.get(key) is not None else None
        except Exception:
            result[key] = None

    for key in HARD_FAIL_KEYS:
        result[key] = bool(result.get(key, False))

    failures = list(result.get("qa_failure_reasons") or [])
    for key, minimum in REQUIRED_SCORES.items():
        score = result.get(key)
        if score is None or score < minimum:
            failures.append(f"{key}<{minimum}")

    if people_expected is not False:
        anatomy = result.get("anatomy_score")
        if anatomy is not None and anatomy < 90:
            failures.append("anatomy_score<90")

    for key in HARD_FAIL_KEYS:
        if result.get(key):
            failures.append(key)

    result["qa_failure_reasons"] = sorted(set(str(x) for x in failures if str(x).strip()))
    result["ultrarealism_pass"] = not result["qa_failure_reasons"]
    result["qa_method"] = str(result.get("qa_method") or "chatgpt_browser_vision")
    return result


def ultrarealism_gate(
    image_path: Path,
    visual_qa: dict[str, Any] | None,
    *,
    people_expected: bool | None = None,
) -> dict[str, Any]:
    technical = technical_image_qa(image_path)
    if not technical.get("technical_pass"):
        return {
            "technical_qa": technical,
            "visual_qa": visual_qa or {},
            "ultrarealism_pass": False,
            "qa_failure_reasons": list(technical.get("failures") or [technical.get("reason") or "technical_fail"]),
        }

    if not visual_qa:
        return {
            "technical_qa": technical,
            "visual_qa": {},
            "ultrarealism_pass": False,
            "qa_failure_reasons": ["semantic_visual_qa_missing"],
        }

    normalized = normalize_visual_qa(visual_qa, people_expected=people_expected)
    return {
        "technical_qa": technical,
        "visual_qa": normalized,
        "ultrarealism_pass": bool(normalized.get("ultrarealism_pass")),
        "qa_failure_reasons": normalized.get("qa_failure_reasons") or [],
        "photorealism_score": normalized.get("photorealism_score"),
    }


def qa_prompt(content_id: str, brief: str, people_expected: bool | None = None) -> str:
    people_rule = (
        "If people are visible, inspect face, eyes, hands, fingers, limbs and posture very strictly."
        if people_expected is not False
        else "People are not required; do not penalize the image for having no person."
    )
    schema = {
        "photorealism_score": 0,
        "anatomy_score": 0,
        "architecture_score": 0,
        "lighting_score": 0,
        "materials_score": 0,
        "perspective_score": 0,
        "artifact_free_score": 0,
        "real_estate_quality_score": 0,
        "random_text": False,
        "watermark": False,
        "fake_logo": False,
        "major_artifacts": False,
        "qa_failure_reasons": [],
    }
    return (
        f"F1 VISUAL QA. CONTENT_ID={content_id}. Evaluate ONLY the attached/generated image, not the prompt. "
        "Be strict. Determine whether it is visually indistinguishable from a professional Italian real-estate "
        "editorial photograph. Check photographic realism, Italian/Piedmont architectural plausibility, perspective, "
        "lighting physics, materials, windows, doors, furniture geometry, reflections, shadows and obvious AI artifacts. "
        + people_rule + " Check for random text, watermark or invented logos. "
        f"Creative brief: {brief}. Return exactly one line beginning F1_QA_RESULT followed by valid JSON matching this schema: "
        + json.dumps(schema, separators=(",", ":"))
    )
