#!/usr/bin/env python3
"""Publish/schedule queued social posts through Postiz.

The queue is intentionally file-based so ChatGPT or any other process with
repository write access can add a job. GitHub Actions then sends it to Postiz,
which handles the official social-provider APIs.
"""

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
QUEUE_PATH = Path(os.getenv("F1_SOCIAL_QUEUE", ROOT / "publisher" / "queue.json"))
API_BASE = os.getenv("POSTIZ_API_URL", "https://api.postiz.com/public/v1").rstrip("/")
API_KEY = os.getenv("POSTIZ_API_KEY", "").strip()

ALIASES = {
    "facebook": {"facebook", "facebook-page"},
    "instagram": {"instagram", "instagram-standalone"},
    "linkedin": {"linkedin", "linkedin-page"},
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


def load_queue() -> dict[str, Any]:
    if not QUEUE_PATH.exists():
        print(f"No queue at {QUEUE_PATH}; nothing to do.")
        return {"version": 1, "jobs": []}
    with QUEUE_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data.get("jobs"), list):
        raise ValueError("queue.json must contain a jobs array")
    return data


def save_queue(data: dict[str, Any]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(QUEUE_PATH)


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
        value = item.get(key)
        if value:
            return str(value).lower()
    return ""


def integration_name(item: dict[str, Any]) -> str:
    for key in ("name", "displayName", "username", "identifier"):
        value = item.get(key)
        if value:
            return str(value)
    return str(item.get("id", ""))


def select_integration(integrations: list[dict[str, Any]], platform: str, account_hint: str | None = None) -> dict[str, Any]:
    platform = platform.lower()
    allowed = ALIASES.get(platform, {platform})
    candidates = [i for i in integrations if integration_kind(i) in allowed]
    if account_hint:
        hint = account_hint.lower()
        hinted = [i for i in candidates if hint in integration_name(i).lower()]
        if hinted:
            candidates = hinted
    if not candidates:
        connected = ", ".join(sorted({integration_kind(i) for i in integrations}))
        raise RuntimeError(f"No Postiz integration found for '{platform}'. Connected: {connected or 'none'}")
    if len(candidates) > 1 and not account_hint:
        names = ", ".join(integration_name(i) for i in candidates)
        raise RuntimeError(f"Multiple '{platform}' integrations found ({names}). Add account_hint to the queue job.")
    return candidates[0]


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


def default_settings(platform: str, job: dict[str, Any]) -> dict[str, Any]:
    title = str(job.get("title") or job.get("caption") or "F1 Immobiliare")[:100]
    if platform == "facebook":
        return {"__type": "facebook"}
    if platform == "instagram":
        return {"__type": "instagram", "post_type": "post", "is_trial_reel": False, "collaborators": []}
    if platform in {"linkedin", "linkedin-page"}:
        return {"__type": "linkedin-page" if platform == "linkedin-page" else "linkedin", "post_as_images_carousel": False}
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
            "tags": [{"value": x, "label": x} for x in job.get("youtube_tags", [])[:15]],
        }
    if platform == "pinterest":
        board = job.get("pinterest_board")
        if not board:
            raise RuntimeError("Pinterest requires pinterest_board in the queue job")
        return {"__type": "pinterest", "board": board, "title": title, "link": job.get("link", "")}
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
    if isinstance(platform_spec, str):
        platform = platform_spec.lower()
        overrides: dict[str, Any] = {}
        account_hint = job.get("account_hint")
    else:
        platform = str(platform_spec["platform"]).lower()
        overrides = dict(platform_spec.get("settings") or {})
        account_hint = platform_spec.get("account_hint") or job.get("account_hint")

    integration = select_integration(integrations, platform, account_hint)
    post_type, date = scheduled_type(job)
    settings = default_settings(platform, job)
    settings.update(overrides)

    media_array = []
    if media:
        media_array = [{"id": media.get("id"), "path": media["path"]}]

    payload = {
        "type": post_type,
        "date": date,
        "shortLink": False,
        "tags": [],
        "posts": [{
            "integration": {"id": integration["id"]},
            "value": [{"content": str(job.get("caption") or ""), "image": media_array}],
            "settings": settings,
        }],
    }
    result = api("POST", "/posts", json=payload).json()
    return {"platform": platform, "integration_id": integration["id"], "result": result}


def main() -> int:
    if not API_KEY:
        print("POSTIZ_API_KEY is not configured.", file=sys.stderr)
        return 2

    queue = load_queue()
    jobs = queue.get("jobs", [])
    ready = [j for j in jobs if j.get("enabled", True) and j.get("status", "ready") == "ready"]
    if not ready:
        print("No ready jobs.")
        return 0

    integrations = get_integrations()
    failures = 0

    for job in ready:
        job.setdefault("published_platforms", [])
        job.setdefault("postiz_results", [])
        try:
            media = upload_media(job["media"]) if job.get("media") else None
            requested = job.get("platforms") or []
            if not requested:
                raise RuntimeError("Job has no platforms")

            for spec in requested:
                platform = spec if isinstance(spec, str) else spec.get("platform")
                if platform in job["published_platforms"]:
                    continue
                result = publish_platform(job, spec, integrations, media)
                job["postiz_results"].append(result)
                job["published_platforms"].append(platform)
                save_queue(queue)  # checkpoint after every provider
                print(f"Queued {job.get('id')} -> {platform}")

            job["status"] = "scheduled"
            job["submitted_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            job.pop("error", None)
        except Exception as exc:  # keep job retriable, while preventing duplicates via published_platforms
            failures += 1
            job["error"] = str(exc)
            print(f"ERROR {job.get('id')}: {exc}", file=sys.stderr)
        finally:
            save_queue(queue)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
