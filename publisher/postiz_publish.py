#!/usr/bin/env python3
"""Publish/schedule queued social posts through Postiz with tenant isolation."""

from __future__ import annotations

import json
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = Path(os.getenv("SOCIAL_QUEUE", ROOT / "publisher" / "queue.json"))
CLIENT_DIR = ROOT / "publisher" / "clients"
API_BASE = os.getenv("POSTIZ_API_URL", "https://api.postiz.com/public/v1").rstrip("/")
API_KEY = os.getenv("POSTIZ_API_KEY", "").strip()
ALLOW_LEGACY_HINTS = os.getenv("ALLOW_LEGACY_ACCOUNT_HINTS", "false").lower() == "true"

ALIASES = {
    "facebook": {"facebook"},
    "instagram": {"instagram", "instagram-standalone"},
    "linkedin": {"linkedin"},
    "linkedin-page": {"linkedin-page"},
    "tiktok": {"tiktok"},
    "youtube": {"youtube"},
    "pinterest": {"pinterest"},
}


def headers() -> dict[str, str]:
    return {"Authorization": API_KEY}


def api(method: str, path: str, **kwargs: Any) -> requests.Response:
    response = requests.request(method, f"{API_BASE}{path}", headers=headers(), timeout=120, **kwargs)
    if not response.ok:
        raise RuntimeError(f"Postiz {method} {path} failed: {response.status_code} {response.text[:1000]}")
    return response


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_queue() -> dict[str, Any]:
    if not QUEUE_PATH.exists():
        return {"version": 2, "jobs": []}
    data = load_json(QUEUE_PATH)
    if not isinstance(data.get("jobs"), list):
        raise ValueError("queue.json must contain a jobs array")
    return data


def save_queue(data: dict[str, Any]) -> None:
    tmp = QUEUE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(QUEUE_PATH)


def load_client(client_id: str) -> dict[str, Any]:
    path = CLIENT_DIR / f"{client_id}.json"
    if not path.exists():
        raise RuntimeError(f"Unknown client_id: {client_id}")
    return load_json(path)


def get_integrations() -> list[dict[str, Any]]:
    payload = api("GET", "/integrations").json()
    if isinstance(payload, list):
        return payload
    for key in ("integrations", "data", "items"):
        if isinstance(payload.get(key), list):
            return payload[key]
    raise RuntimeError(f"Unexpected integrations response: {payload}")


def integration_kind(item: dict[str, Any]) -> str:
    for key in ("identifier", "provider", "type", "providerIdentifier"):
        if item.get(key):
            return str(item[key]).lower()
    return ""


def integration_name(item: dict[str, Any]) -> str:
    for key in ("name", "displayName", "profile", "username", "identifier"):
        if item.get(key):
            return str(item[key])
    return str(item.get("id", ""))


def verify_exact_integration(integrations: list[dict[str, Any]], platform: str, integration_id: str) -> dict[str, Any]:
    allowed = ALIASES.get(platform, {platform})
    matches = [item for item in integrations if str(item.get("id")) == integration_id]
    if not matches:
        raise RuntimeError(f"Configured integration ID for {platform} does not exist: {integration_id}")
    item = matches[0]
    kind = integration_kind(item)
    if kind not in allowed:
        raise RuntimeError(f"Integration {integration_id} is '{kind}', not '{platform}'")
    if item.get("disabled") is True:
        raise RuntimeError(f"Integration {integration_id} ({integration_name(item)}) is disabled")
    return item


def legacy_select(integrations: list[dict[str, Any]], platform: str, account_hint: str | None) -> dict[str, Any]:
    if not ALLOW_LEGACY_HINTS:
        raise RuntimeError("Production publishing requires an explicit integration_id per tenant/platform")
    allowed = ALIASES.get(platform, {platform})
    candidates = [i for i in integrations if integration_kind(i) in allowed and i.get("disabled") is not True]
    if account_hint:
        hint = account_hint.lower()
        candidates = [i for i in candidates if hint in integration_name(i).lower()]
    if len(candidates) != 1:
        raise RuntimeError(f"Legacy lookup for {platform} is ambiguous or empty; configure integration_id")
    return candidates[0]


def resolve_integration(job: dict[str, Any], platform_spec: Any, integrations: list[dict[str, Any]]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    overrides: dict[str, Any] = {}
    integration_id = ""
    account_hint = None
    if isinstance(platform_spec, str):
        platform = platform_spec.lower()
    else:
        platform = str(platform_spec.get("platform") or "").lower()
        integration_id = str(platform_spec.get("integration_id") or "").strip()
        overrides = dict(platform_spec.get("settings") or {})
        account_hint = platform_spec.get("account_hint")
    if not platform:
        raise RuntimeError("Platform specification is missing platform")

    client_id = str(job.get("client_id") or "").strip()
    if client_id:
        cfg = load_client(client_id)
        tenant_cfg = cfg.get("integrations", {}).get(platform, {})
        tenant_id = str(tenant_cfg.get("id") or "").strip()
        if integration_id and tenant_id and integration_id != tenant_id:
            raise RuntimeError(f"Tenant isolation mismatch for {client_id}/{platform}")
        integration_id = integration_id or tenant_id
        if platform == "pinterest" and tenant_cfg.get("board") and "board" not in overrides:
            overrides["board"] = tenant_cfg["board"]

    if integration_id:
        integration = verify_exact_integration(integrations, platform, integration_id)
    else:
        integration = legacy_select(integrations, platform, account_hint or job.get("account_hint"))
    return platform, integration, overrides


def upload_media(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(path)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as fh:
        response = requests.post(
            f"{API_BASE}/upload",
            headers=headers(),
            files={"file": (path.name, fh, mime)},
            timeout=300,
        )
    if not response.ok:
        raise RuntimeError(f"Postiz upload failed: {response.status_code} {response.text[:1000]}")
    payload = response.json()
    if isinstance(payload, list):
        payload = payload[0]
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload = payload["data"]
    if not isinstance(payload, dict) or not payload.get("path"):
        raise RuntimeError(f"Unexpected upload response: {payload}")
    return payload


def default_settings(platform: str, job: dict[str, Any], integration: dict[str, Any]) -> dict[str, Any]:
    title = str(job.get("title") or job.get("caption") or job.get("client_name") or "Social post")[:100]
    if platform == "facebook":
        return {"__type": "facebook"}
    if platform == "instagram":
        provider = integration_kind(integration)
        return {"__type": provider, "post_type": "post", "is_trial_reel": False, "collaborators": []}
    if platform in {"linkedin", "linkedin-page"}:
        return {"__type": platform, "post_as_images_carousel": False}
    if platform == "tiktok":
        return {
            "__type": "tiktok",
            "title": title[:90],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "duet": False,
            "stitch": False,
            "comment": True,
            "autoAddMusic": "no",
            "brand_content_toggle": False,
            "brand_organic_toggle": False,
            "video_made_with_ai": bool(job.get("video_made_with_ai", False)),
            "content_posting_method": "DIRECT_POST",
        }
    if platform == "youtube":
        return {
            "__type": "youtube",
            "title": title,
            "type": "public",
            "selfDeclaredMadeForKids": "no",
            "thumbnail": None,
            "tags": [{"value": x, "label": x} for x in job.get("youtube_tags", [])[:15]],
        }
    if platform == "pinterest":
        return {"__type": "pinterest", "title": title, "link": job.get("link", "")}
    return {"__type": platform}


def scheduled_type(job: dict[str, Any]) -> tuple[str, str]:
    raw = str(job.get("scheduled_at") or "").strip()
    if not raw:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return "now", now
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("scheduled_at must include timezone offset or Z")
    return "schedule", dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def publish_platform(job: dict[str, Any], platform_spec: Any, integrations: list[dict[str, Any]], media: dict[str, Any] | None) -> dict[str, Any]:
    platform, integration, overrides = resolve_integration(job, platform_spec, integrations)
    post_type, publish_date = scheduled_type(job)
    settings = default_settings(platform, job, integration)
    settings.update(overrides)
    if platform == "pinterest" and not settings.get("board"):
        raise RuntimeError("Pinterest requires a board ID in the tenant configuration")

    media_array = []
    if media:
        media_array = [{"id": media.get("id"), "path": media["path"]}]

    payload = {
        "type": post_type,
        "date": publish_date,
        "shortLink": False,
        "tags": [],
        "posts": [{
            "integration": {"id": integration["id"]},
            "value": [{"content": str(job.get("caption") or ""), "image": media_array}],
            "settings": settings,
        }],
    }
    result = api("POST", "/posts", json=payload).json()
    return {
        "platform": platform,
        "integration_id": integration["id"],
        "integration_name": integration_name(integration),
        "result": result,
    }


def main() -> int:
    if not API_KEY:
        print("POSTIZ_API_KEY is not configured; publisher safely disabled.")
        return 0

    queue = load_queue()
    ready = [j for j in queue.get("jobs", []) if j.get("enabled", True) and j.get("status") == "ready"]
    if not ready:
        print("No ready jobs.")
        return 0

    integrations = get_integrations()
    failures = 0
    for job in ready:
        job.setdefault("published_platforms", [])
        job.setdefault("postiz_results", [])
        try:
            client_id = str(job.get("client_id") or "")
            if not client_id and not ALLOW_LEGACY_HINTS:
                raise RuntimeError("Job has no client_id; legacy jobs are disabled")
            media = upload_media(job["media"]) if job.get("media") else None
            requested = job.get("platforms") or []
            if not requested:
                raise RuntimeError("Job has no configured platforms")

            for spec in requested:
                platform = spec if isinstance(spec, str) else str(spec.get("platform") or "")
                if platform in job["published_platforms"]:
                    continue
                result = publish_platform(job, spec, integrations, media)
                job["postiz_results"].append(result)
                job["published_platforms"].append(platform)
                save_queue(queue)
                print(f"Queued {job.get('id')} -> {platform} ({result['integration_name']})")

            job["status"] = "scheduled"
            job["submitted_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            job.pop("error", None)
        except Exception as exc:
            failures += 1
            job["status"] = "error"
            job["error"] = str(exc)
            print(f"ERROR {job.get('id')}: {exc}", file=sys.stderr)
        finally:
            save_queue(queue)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
