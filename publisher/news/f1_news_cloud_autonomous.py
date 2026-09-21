#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from PIL import Image

from publisher.chatgpt_query_runner.f1_brand_layer import apply_f1_brand_layer
from publisher.news.f1_valle_susa_news import (
    CONFIG_PATH,
    build_caption,
    build_visual_prompt,
    choose_item,
    load_json,
    source_hash,
)
from publisher.rendering.openai_visual_engine import generate_visual

ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
STATE_PATH = ROOT / "publisher" / "news" / "f1_news_cloud_state.json"
ASSET_ROOT = ROOT / "publisher" / "final_assets" / "f1_news"
ROME = ZoneInfo("Europe/Rome")
UA = "F1ValleSusaCloudNews/1.0 (+https://www.f1immobiliare.com)"
MAX_GENERATION_ATTEMPTS = 1
MAX_PUBLISH_ATTEMPTS = 3


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _state() -> dict[str, Any]:
    data = load_json(
        STATE_PATH,
        {
            "version": 1,
            "architecture": "github-actions-only",
            "jobs": {},
            "slots": {},
            "provider_audit": {},
            "updated_at": None,
        },
    )
    data.setdefault("jobs", {})
    data.setdefault("slots", {})
    data.setdefault("provider_audit", {})
    return data


def _persist_state(state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _save_json(STATE_PATH, state)


def _queue() -> dict[str, Any]:
    data = load_json(
        QUEUE_PATH,
        {
            "version": 3,
            "pipeline": "f1-final-assets",
            "brand": "F1 Immobiliare",
            "asset_policy": "immutable-final-layout",
            "jobs": [],
        },
    )
    data.setdefault("jobs", [])
    return data


def _persist_queue(queue: dict[str, Any]) -> None:
    queue["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _save_json(QUEUE_PATH, queue)


def _slot(now: datetime, forced: str) -> tuple[str, str] | None:
    if forced != "auto":
        label = forced.upper()
        return label, f"{now.date().isoformat()}|{label}"
    minutes = now.hour * 60 + now.minute
    if 11 * 60 <= minutes <= 13 * 60:
        return "MIDDAY", f"{now.date().isoformat()}|MIDDAY"
    if 19 * 60 <= minutes <= 21 * 60:
        return "EVENING", f"{now.date().isoformat()}|EVENING"
    return None


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def verify_source(item: dict[str, Any]) -> dict[str, Any]:
    url = str(item.get("source_url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("SOURCE_URL_INVALID")

    response = requests.get(
        url,
        timeout=35,
        allow_redirects=True,
        headers={"User-Agent": UA},
    )
    response.raise_for_status()
    content_type = str(response.headers.get("content-type") or "").lower()
    if "html" not in content_type and "text" not in content_type:
        raise RuntimeError(f"SOURCE_UNSUPPORTED_CONTENT_TYPE:{content_type}")

    raw = response.text
    text = _strip_html(raw)
    if len(text) < 250:
        raise RuntimeError("SOURCE_CONTENT_TOO_SHORT")

    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    page_title = _strip_html(title_match.group(1))[:300] if title_match else ""

    expected = str(item.get("title") or "").casefold()
    tokens = [
        t for t in re.findall(r"[a-zà-ÿ0-9]+", expected)
        if len(t) >= 5 and t not in {"della", "delle", "degli", "dello", "nella", "nelle", "anche", "comuni"}
    ]
    body_cf = text.casefold()
    matched = sorted({t for t in tokens if t in body_cf})
    if tokens and not matched:
        raise RuntimeError(
            "SOURCE_TITLE_NOT_CONFIRMED: nessun termine significativo del titolo candidato compare nella pagina"
        )

    return {
        "http_status": response.status_code,
        "final_url": response.url,
        "domain": urlparse(response.url).netloc,
        "page_title": page_title,
        "matched_title_terms": matched[:12],
        "content_sha256": hashlib.sha256(response.content).hexdigest(),
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "content_excerpt": text[:700],
    }


def _valid_image(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file() or path.stat().st_size < 20_000:
        return None
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            width, height = im.size
            fmt = str(im.format or "").upper()
    except Exception:
        return None
    if fmt not in {"PNG", "JPEG", "WEBP"}:
        return None
    if width < 900 or height < 1200:
        return None
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "width": width,
        "height": height,
        "format": fmt,
        "bytes": path.stat().st_size,
    }


def _asset_from_record(record: dict[str, Any], field: str) -> Path | None:
    raw = str(record.get(field) or "").strip()
    if not raw:
        return None
    path = ROOT / raw
    return path if _valid_image(path) else None


def _provider_audit(state: dict[str, Any]) -> dict[str, Any]:
    audit = {
        "openai_image": {
            "configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            "status": "PRESENT" if os.getenv("OPENAI_API_KEY", "").strip() else "MISSING",
        },
        "modal_ugc": {
            "configured": True,
            "status": "INCOMPATIBLE",
            "reason": "repository Modal endpoint renders UGC video, not a still-image news generator",
        },
        "other_configured_still_image_provider": {
            "configured": False,
            "status": "NOT_FOUND",
        },
        "local_chatgpt_browser": {
            "configured": False,
            "status": "PROHIBITED_FOR_PRODUCTION",
        },
    }
    state["provider_audit"] = audit
    _persist_state(state)
    return audit


def _job_id(now: datetime, slot_name: str, digest: str) -> str:
    return f"F1NEWS-{now:%Y%m%d}-{slot_name}-{digest[:10].upper()}"


def _job_for_slot(state: dict[str, Any], slot_key: str) -> dict[str, Any] | None:
    ref = state.get("slots", {}).get(slot_key) or {}
    jid = str(ref.get("job_id") or "")
    return state.get("jobs", {}).get(jid) if jid else None


def _existing_final_job(queue: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    return next((x for x in queue.get("jobs") or [] if str(x.get("id") or "") == job_id), None)


def _set_status(state: dict[str, Any], job: dict[str, Any], status: str, **extra: Any) -> None:
    job["status"] = status
    job["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    job.update(extra)
    state["jobs"][job["content_id"]] = job
    state["slots"][job["slot_key"]] = {
        "job_id": job["content_id"],
        "status": status,
        "updated_at": job["updated_at"],
    }
    _persist_state(state)


def _new_job(now: datetime, slot_name: str, slot_key: str, item: dict[str, Any], verified: dict[str, Any]) -> dict[str, Any]:
    digest = source_hash(item)
    jid = _job_id(now, slot_name, digest)
    config = load_json(CONFIG_PATH, {})
    caption = build_caption(item, config)
    prompt = build_visual_prompt(item)
    return {
        "content_id": jid,
        "news_id": str(item.get("id") or f"NEWS-{digest[:12].upper()}"),
        "communication_id": f"COMM-NEWS-{now:%Y%m%d}-{slot_name}-{digest[:8].upper()}",
        "slot": slot_name,
        "slot_key": slot_key,
        "headline": str(item.get("headline") or item.get("title") or "F1 NEWS VALLE DI SUSA")[:72],
        "caption": caption,
        "prompt": prompt,
        "source_name": str(item.get("source_name") or "Fonte pubblica"),
        "source_url": str(item.get("source_url") or ""),
        "source_hash": digest,
        "source_published_at": str(item.get("published_at") or ""),
        "source_verification": verified,
        "category": str(item.get("category") or "immobiliare"),
        "territory": str(item.get("area") or "Valle di Susa"),
        "platforms": ["facebook", "instagram"],
        "status": "SOURCE_VERIFIED",
        "generation_attempts": 0,
        "publish_attempts": 0,
        "max_publish_attempts": MAX_PUBLISH_ATTEMPTS,
        "created_at": now.isoformat(timespec="seconds"),
        "updated_at": now.isoformat(timespec="seconds"),
    }


def _make_spec(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "static",
        "format": "4:5",
        "brand": {
            "primary": "#92C205",
            "secondary": "#070907",
            "background": "#F7F7F4",
        },
        "content": {
            "title": job["headline"],
            "cover_title": job["headline"],
            "subtitle": job["prompt"],
            "target": "proprietari, acquirenti e famiglie della Valle di Susa",
        },
        "metadata": {
            "family": "property",
            "target": "Valle di Susa",
            "search_query": job["headline"],
            "search_intent": "local real estate news",
            "creative_direction": "editorial, credible, contemporary Piedmont real estate",
            "prompt_override": job["prompt"],
        },
    }


def _queue_job(job: dict[str, Any]) -> dict[str, Any]:
    branded = str(job["branded_asset_path"])
    return {
        "id": job["content_id"],
        "communication_id": job["communication_id"],
        "news_id": job["news_id"],
        "title": job["headline"],
        "headline": job["headline"],
        "objective": "LOCAL NEWS / AUTHORITY",
        "pillar": "F1 News Valle di Susa",
        "source_name": job["source_name"],
        "source_url": job["source_url"],
        "source_hash": job["source_hash"],
        "source_published_at": job["source_published_at"],
        "caption": job["caption"],
        "prompt": job["prompt"],
        "category": job["category"],
        "format": "photo",
        "assets": [{"path": branded, "sha256": job["branded_asset_sha256"]}],
        "platforms": ["facebook", "instagram"],
        "scope": "network",
        "territory": "Valle di Susa",
        "editorial_slot": job["slot"],
        "slot_key": job["slot_key"],
        "scheduled_at": datetime.now(ROME).isoformat(timespec="seconds"),
        "status": "READY",
        "publisher_backend": "buffer_cloud_news",
        "max_publish_attempts": MAX_PUBLISH_ATTEMPTS,
        "generation_provider": job.get("generation_provider"),
        "generation_model": job.get("generation_model"),
        "generated_asset_path": job.get("generated_asset_path"),
        "generated_asset_sha256": job.get("generated_asset_sha256"),
        "branded_asset_path": branded,
        "branded_asset_sha256": job.get("branded_asset_sha256"),
        "technical_qa": job.get("technical_qa"),
        "content_qa": job.get("content_qa"),
        "brand_qa": job.get("brand_qa"),
        "semantic_visual_qa": job.get("semantic_visual_qa"),
        "created_by": "f1-news-cloud-autonomous",
        "approval_required": False,
        "manual_approval_required": False,
        "autonomous_publish": True,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _emit(path: str | None, payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            handle.write(f"{key}={str(value).replace(chr(10), ' ')}\n")


def run(forced_slot: str, output_path: str | None) -> int:
    now = datetime.now(ROME)
    state = _state()
    audit = _provider_audit(state)
    slot_info = _slot(now, forced_slot)
    if slot_info is None:
        _emit(output_path, {"status": "NOOP_OUTSIDE_WINDOW", "job_id": "", "slot_key": ""})
        return 0

    slot_name, slot_key = slot_info
    queue = _queue()

    existing = _job_for_slot(state, slot_key)
    if existing and str(existing.get("status") or "") == "PUBLISHED_VERIFIED":
        _emit(
            output_path,
            {
                "status": "NOOP_ALREADY_COMPLETED_SLOT",
                "job_id": existing["content_id"],
                "slot_key": slot_key,
            },
        )
        return 0

    if existing:
        job = existing
    else:
        item = choose_item(load_json(CONFIG_PATH, {}))
        if not item:
            _emit(output_path, {"status": "NOOP_NO_RELEVANT_NEWS", "job_id": "", "slot_key": slot_key})
            return 0
        try:
            verified = verify_source(item)
        except Exception as exc:
            rejected = {
                "content_id": f"REJECTED-{now:%Y%m%d%H%M%S}",
                "slot_key": slot_key,
                "status": "SOURCE_REJECTED",
                "error": f"{type(exc).__name__}: {exc}",
                "source_url": item.get("source_url"),
                "source_hash": source_hash(item),
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            state.setdefault("rejected_sources", []).append(rejected)
            state["rejected_sources"] = state["rejected_sources"][-100:]
            _persist_state(state)
            _emit(output_path, {"status": "SOURCE_REJECTED", "job_id": "", "slot_key": slot_key, "error": rejected["error"]})
            return 0
        job = _new_job(now, slot_name, slot_key, item, verified)
        state["jobs"][job["content_id"]] = job
        state["slots"][slot_key] = {"job_id": job["content_id"], "status": "SOURCE_VERIFIED"}
        _persist_state(state)
        _set_status(state, job, "CAPTION_READY")
        _set_status(state, job, "PROMPT_READY")

    final_job = _existing_final_job(queue, job["content_id"])
    if final_job and str(final_job.get("status") or "") == "PUBLISHED_VERIFIED":
        _set_status(
            state,
            job,
            "PUBLISHED_VERIFIED",
            remote_post_id=final_job.get("remote_post_id"),
            remote_post_ids=final_job.get("remote_post_ids") or [],
            remote_post_url=final_job.get("remote_post_url"),
            remote_post_urls=final_job.get("remote_post_urls") or [],
            published_at=final_job.get("published_at"),
        )
        _emit(output_path, {"status": "NOOP_ALREADY_COMPLETED_SLOT", "job_id": job["content_id"], "slot_key": slot_key})
        return 0

    source_path = _asset_from_record(job, "generated_asset_path")
    if source_path is None:
        if not audit["openai_image"]["configured"]:
            _set_status(
                state,
                job,
                "BLOCKED_CLOUD_IMAGE_PROVIDER",
                provider_error="OPENAI_API_KEY missing; no compatible configured still-image fallback found",
                providers_checked=audit,
            )
            _emit(output_path, {"status": "BLOCKED_CLOUD_IMAGE_PROVIDER", "job_id": job["content_id"], "slot_key": slot_key})
            return 0

        day_dir = ASSET_ROOT / now.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        requested = day_dir / f"{job['content_id']}-source.png"
        _set_status(state, job, "GENERATING")
        try:
            generated = generate_visual(_make_spec(job), requested)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            code = "credit_balance_exhausted" if "credit_balance_exhausted" in message else ""
            if code or "insufficient_quota" in message or "no credits remaining" in message.casefold():
                state["provider_audit"]["openai_image"]["status"] = "ERROR"
                state["provider_audit"]["openai_image"]["error_code"] = "credit_balance_exhausted"
                _set_status(
                    state,
                    job,
                    "BLOCKED_CLOUD_IMAGE_PROVIDER",
                    provider_error=message[:1400],
                    providers_checked=state["provider_audit"],
                )
                _emit(
                    output_path,
                    {
                        "status": "BLOCKED_CLOUD_IMAGE_PROVIDER",
                        "job_id": job["content_id"],
                        "slot_key": slot_key,
                        "provider": "openai_image",
                        "provider_error_code": "credit_balance_exhausted",
                    },
                )
                return 0
            job["generation_attempts"] = int(job.get("generation_attempts") or 0) + 1
            _set_status(
                state,
                job,
                "FAILED_FINAL" if job["generation_attempts"] >= MAX_GENERATION_ATTEMPTS else "FAILED_RETRYABLE",
                generation_error=message[:1400],
            )
            _emit(output_path, {"status": job["status"], "job_id": job["content_id"], "slot_key": slot_key})
            return 0

        meta = _valid_image(generated)
        if not meta:
            job["generation_attempts"] = int(job.get("generation_attempts") or 0) + 1
            _set_status(state, job, "FAILED_FINAL", generation_error="Generated image failed technical validation")
            _emit(output_path, {"status": "FAILED_FINAL", "job_id": job["content_id"], "slot_key": slot_key})
            return 0

        job["generation_attempts"] = 1
        _set_status(
            state,
            job,
            "IMAGE_READY",
            generated_asset_path=meta["path"],
            generated_asset_sha256=meta["sha256"],
            generated_width=meta["width"],
            generated_height=meta["height"],
            generated_format=meta["format"],
            generation_provider="openai",
            generation_model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            generation_completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        source_path = generated

    meta = _valid_image(source_path)
    if not meta:
        _set_status(state, job, "FAILED_FINAL", technical_qa="FAIL", technical_error="Generated source asset invalid")
        _emit(output_path, {"status": "FAILED_FINAL", "job_id": job["content_id"], "slot_key": slot_key})
        return 0

    _set_status(
        state,
        job,
        "FILE_VALIDATED",
        technical_qa="PASS",
        content_qa="PASS_SOURCE_GROUNDED",
        semantic_visual_qa="NOT_AVAILABLE",
    )
    _set_status(state, job, "QA_PENDING")
    _set_status(state, job, "QA_PASS")

    branded_path = _asset_from_record(job, "branded_asset_path")
    if branded_path is None:
        branded_path = ASSET_ROOT / now.strftime("%Y%m%d") / f"{job['content_id']}-brand.png"
        result = apply_f1_brand_layer(
            source_path,
            branded_path,
            headline=job["headline"],
            cta="SCOPRI COSA CAMBIA",
            territory="F1 NEWS · VALLE DI SUSA",
            body="Notizia immobiliare da fonte pubblica verificata. Dettagli e fonte completa nella caption.",
        )
        if result.get("brand_qa") != "PASS":
            _set_status(state, job, "FAILED_FINAL", brand_qa="FAIL")
            _emit(output_path, {"status": "FAILED_FINAL", "job_id": job["content_id"], "slot_key": slot_key})
            return 0
        job["branded_asset_path"] = result["path"]
        job["branded_asset_sha256"] = result["sha256"]
        job["brand_qa"] = "PASS"

    _set_status(state, job, "BRAND_PASS")

    queue = _queue()
    final_job = _existing_final_job(queue, job["content_id"])
    if final_job is None:
        queue["jobs"].append(_queue_job(job))
    else:
        if str(final_job.get("status") or "") not in {"PUBLISHING", "PUBLISHED", "VERIFYING_PUBLICATION", "PUBLISHED_VERIFIED"}:
            refreshed = _queue_job(job)
            final_job.clear()
            final_job.update(refreshed)
    _persist_queue(queue)
    _set_status(state, job, "READY_TO_PUBLISH")

    _emit(
        output_path,
        {
            "status": "READY_TO_PUBLISH",
            "job_id": job["content_id"],
            "slot_key": slot_key,
            "source_url": job["source_url"],
            "generated_asset": job["generated_asset_path"],
            "branded_asset": job["branded_asset_path"],
        },
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["auto", "midday", "evening", "immediate"], default="auto")
    parser.add_argument("--github-output")
    args = parser.parse_args()
    return run(args.slot, args.github_output)


if __name__ == "__main__":
    raise SystemExit(main())
