from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import requests
from PIL import Image

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
OPENAI_EDITS_URL = "https://api.openai.com/v1/images/edits"
DEFAULT_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")


def _api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for OpenAI visual generation")
    return key


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_api_key()}"}


def build_prompt(spec: dict[str, Any]) -> str:
    brand = dict(spec.get("brand") or {})
    content = dict(spec.get("content") or {})
    metadata = dict(spec.get("metadata") or {})
    family = str(metadata.get("family") or "institutional")
    title = str(content.get("cover_title") or content.get("title") or "")
    subtitle = str(content.get("subtitle") or "")
    target = str(metadata.get("target") or content.get("target") or "")
    return (
        "Create the photographic hero asset only, without any text, logo, price, QR code or graphic frame. "
        "It will be inserted into a locked F1 Immobiliare social template. "
        f"Visual family: {family}. Content theme: {title}. Supporting idea: {subtitle}. Target: {target}. "
        "Photographic direction: premium but credible Italian real-estate advertising, natural daylight, clean composition, "
        "realistic materials and architecture, editorial commercial photography, no fantasy, no watermarks. "
        "Brand context uses white, black and bright F1 green, but the photo itself must remain natural. "
        "Leave useful negative space near the left edge when possible because copy sits there in the final layout. "
        "If a person is required, use a credible Italian real-estate professional in smart business clothing, friendly but not exaggerated, "
        "waist-up or three-quarter framing, realistic skin and anatomy."
    )


def _decode_image_response(payload: dict[str, Any], output: Path) -> Path:
    data = list(payload.get("data") or [])
    if not data:
        raise RuntimeError(f"OpenAI image response contains no data: {json.dumps(payload)[:800]}")
    row = data[0]
    if row.get("b64_json"):
        output.write_bytes(base64.b64decode(row["b64_json"]))
    elif row.get("url"):
        response = requests.get(str(row["url"]), timeout=120)
        response.raise_for_status()
        output.write_bytes(response.content)
    else:
        raise RuntimeError("OpenAI image response contains neither b64_json nor url")
    if output.stat().st_size < 20_000:
        raise RuntimeError(f"OpenAI generated image is unexpectedly small: {output}")
    return output


def generate_visual(spec: dict[str, Any], output: str | Path, *, reference_image: str | Path | None = None) -> Path:
    """Generate or edit one photographic hero asset with OpenAI Images.

    The final branded card is still rendered deterministically by the locked F1 renderer.
    Property listing photos should normally be supplied as factual source imagery and not regenerated.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(spec)
    model = os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_MODEL)

    if reference_image:
        ref = Path(reference_image)
        if not ref.exists():
            raise RuntimeError(f"Reference image not found: {ref}")
        with ref.open("rb") as image_handle:
            response = requests.post(
                OPENAI_EDITS_URL,
                headers=_headers(),
                data={"model": model, "prompt": prompt, "size": "1024x1536"},
                files={"image": (ref.name, image_handle, "image/jpeg")},
                timeout=240,
            )
    else:
        response = requests.post(
            OPENAI_IMAGES_URL,
            headers={**_headers(), "Content-Type": "application/json"},
            json={"model": model, "prompt": prompt, "size": "1024x1536"},
            timeout=240,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI image API failed {response.status_code}: {response.text[:1200]}")
    _decode_image_response(response.json(), output)

    # Normalize to JPEG/RGB so every downstream renderer consumes one predictable format.
    normalized = output.with_suffix(".jpg")
    with Image.open(output) as im:
        im.convert("RGB").save(normalized, "JPEG", quality=95)
    if normalized != output:
        output.unlink(missing_ok=True)
    return normalized
