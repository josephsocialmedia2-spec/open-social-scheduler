#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from publisher import direct_api_publish as direct

ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
STATE_PATH = ROOT / "publisher" / "news" / "f1_news_cloud_state.json"
CLIENT_ID = "f1-immobiliare"
MAX_PUBLISH_ATTEMPTS = 3


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def save_queue(queue: dict[str, Any]) -> None:
    queue["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_json(QUEUE_PATH, queue)


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_json(STATE_PATH, state)


def find_job(queue: dict[str, Any], job_id: str) -> dict[str, Any]:
    job = next((x for x in queue.get("jobs", []) if str(x.get("id") or "") == job_id), None)
    if job is None:
        raise RuntimeError(f"JOB_NOT_FOUND:{job_id}")
    if str(job.get("publisher_backend") or "") != "direct_api_cloud_news":
        raise RuntimeError(f"WRONG_BACKEND:{job.get('publisher_backend')}")
    return job


def graph_get(object_id: str, token: str, fields: str) -> dict[str, Any]:
    response = requests.get(
        f"{direct.meta_graph_base()}/{object_id}",
        params={"fields": fields, "access_token": token},
        timeout=90,
    )
    if not response.ok:
        raise direct.PublishError(
            f"VERIFY GET {object_id} -> {response.status_code}: {response.text[:1200]}"
        )
    return response.json()


def verify_facebook(result: dict[str, Any], client: dict[str, Any]) -> dict[str, Any]:
    token = direct.secret(client, "FACEBOOK_PAGE_ACCESS_TOKEN")
    candidates = [str(result.get("post_id") or "").strip(), str(result.get("photo_id") or "").strip()]
    last_error = ""
    for object_id in [x for x in candidates if x]:
        try:
            data = graph_get(object_id, token, "id,permalink_url,created_time")
            return {
                "verified": True,
                "remote_post_id": str(data.get("id") or object_id),
                "remote_post_url": str(data.get("permalink_url") or ""),
                "published_at": str(data.get("created_time") or ""),
                "verification_payload": data,
            }
        except Exception as exc:
            last_error = str(exc)
            try:
                data = graph_get(object_id, token, "id,link,created_time")
                return {
                    "verified": True,
                    "remote_post_id": str(data.get("id") or object_id),
                    "remote_post_url": str(data.get("link") or ""),
                    "published_at": str(data.get("created_time") or ""),
                    "verification_payload": data,
                }
            except Exception as exc2:
                last_error = str(exc2)
    raise direct.PublishError(f"Facebook remote verification failed: {last_error or 'missing remote id'}")


def verify_instagram(result: dict[str, Any], client: dict[str, Any]) -> dict[str, Any]:
    token = direct.secret(client, "INSTAGRAM_ACCESS_TOKEN")
    media_id = str(result.get("media_id") or "").strip()
    if not media_id:
        raise direct.PublishError("Instagram media_id missing after media_publish")
    data = graph_get(media_id, token, "id,permalink,timestamp,media_type")
    return {
        "verified": True,
        "remote_post_id": str(data.get("id") or media_id),
        "remote_post_url": str(data.get("permalink") or ""),
        "published_at": str(data.get("timestamp") or ""),
        "verification_payload": data,
    }


def sync_state(job: dict[str, Any], status: str) -> None:
    state = load_json(STATE_PATH, {"version": 1, "jobs": {}, "slots": {}})
    record = state.setdefault("jobs", {}).get(str(job["id"]))
    if record is None:
        return
    record["status"] = status
    record["publish_attempts"] = int(job.get("publish_attempts") or 0)
    record["platform_states"] = job.get("platform_states") or {}
    record["remote_post_id"] = job.get("remote_post_id")
    record["remote_post_ids"] = job.get("remote_post_ids") or []
    record["remote_post_url"] = job.get("remote_post_url")
    record["remote_post_urls"] = job.get("remote_post_urls") or []
    record["published_at"] = job.get("published_at")
    record["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    slot_key = str(record.get("slot_key") or job.get("slot_key") or "")
    if slot_key:
        state.setdefault("slots", {})[slot_key] = {
            "job_id": job["id"],
            "status": status,
            "updated_at": record["updated_at"],
        }
    save_state(state)


def publish(job_id: str) -> int:
    queue = load_json(QUEUE_PATH, {})
    job = find_job(queue, job_id)

    if str(job.get("status") or "") == "PUBLISHED_VERIFIED":
        print(json.dumps({"status": "PUBLISHED_VERIFIED", "job_id": job_id}, ensure_ascii=False))
        sync_state(job, "PUBLISHED_VERIFIED")
        return 0

    client = direct.client_config(CLIENT_ID)
    asset_entry = (job.get("assets") or [None])[0]
    asset_path = str(asset_entry.get("path") if isinstance(asset_entry, dict) else asset_entry or "").strip()
    path = ROOT / asset_path
    if not path.exists():
        raise RuntimeError(f"ASSET_MISSING:{asset_path}")

    base_job = {
        "id": job_id,
        "client_id": CLIENT_ID,
        "title": job.get("title") or job_id,
        "caption": job.get("caption") or "",
        "format": "photo",
        "media": asset_path,
        "platforms": ["facebook", "instagram"],
        "scheduled_at": job.get("scheduled_at"),
        "status": "ready",
    }

    platform_states = dict(job.get("platform_states") or {})
    pending = [
        platform
        for platform in ("facebook", "instagram")
        if str((platform_states.get(platform) or {}).get("status") or "") != "PUBLISHED_VERIFIED"
    ]

    missing: dict[str, list[str]] = {}
    for platform in pending:
        names = direct.required_secrets(platform, client)
        if names:
            missing[platform] = names
    if missing:
        job["status"] = "FAILED_RETRYABLE"
        job["publisher_error"] = "Missing GitHub Secrets: " + ", ".join(
            f"{p}={','.join(v)}" for p, v in missing.items()
        )
        save_queue(queue)
        sync_state(job, "FAILED_RETRYABLE")
        print(json.dumps({"status": "FAILED_RETRYABLE", "job_id": job_id, "missing": missing}, ensure_ascii=False))
        return 2

    attempts = int(job.get("publish_attempts") or 0)
    if attempts >= MAX_PUBLISH_ATTEMPTS:
        job["status"] = "FAILED_FINAL"
        save_queue(queue)
        sync_state(job, "FAILED_FINAL")
        print(json.dumps({"status": "FAILED_FINAL", "job_id": job_id, "attempts": attempts}, ensure_ascii=False))
        return 3

    job["publish_attempts"] = attempts + 1
    job["status"] = "PUBLISHING"
    job["last_publish_attempt_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_queue(queue)
    sync_state(job, "PUBLISHING")

    cache = direct.PublicMediaCache()
    try:
        for platform in pending:
            try:
                if platform == "facebook":
                    result = direct.facebook_publish(base_job, client, [path], cache)
                    verified = verify_facebook(result, client)
                elif platform == "instagram":
                    result = direct.instagram_publish(base_job, client, [path], cache)
                    verified = verify_instagram(result, client)
                else:
                    continue
                platform_states[platform] = {
                    "status": "PUBLISHED_VERIFIED",
                    "provider": "meta-direct-api",
                    "provider_result": result,
                    **verified,
                }
                job["platform_states"] = platform_states
                save_queue(queue)
            except Exception as exc:
                platform_states[platform] = {
                    "status": "FAILED_RETRYABLE",
                    "provider": "meta-direct-api",
                    "error": f"{type(exc).__name__}: {exc}"[:1600],
                    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                job["platform_states"] = platform_states
                save_queue(queue)
    finally:
        cache.cleanup()

    verified_rows = [
        row for row in platform_states.values()
        if str(row.get("status") or "") == "PUBLISHED_VERIFIED"
    ]
    remote_ids = [str(row.get("remote_post_id") or "") for row in verified_rows if row.get("remote_post_id")]
    remote_urls = [str(row.get("remote_post_url") or "") for row in verified_rows if row.get("remote_post_url")]

    job["remote_post_id"] = remote_ids[0] if remote_ids else ""
    job["remote_post_ids"] = remote_ids
    job["remote_post_url"] = remote_urls[0] if remote_urls else ""
    job["remote_post_urls"] = remote_urls

    all_verified = all(
        str((platform_states.get(platform) or {}).get("status") or "") == "PUBLISHED_VERIFIED"
        for platform in ("facebook", "instagram")
    )
    if all_verified:
        job["status"] = "PUBLISHED_VERIFIED"
        timestamps = [
            str((platform_states.get(p) or {}).get("published_at") or "")
            for p in ("facebook", "instagram")
        ]
        job["published_at"] = max([x for x in timestamps if x] or [datetime.now(timezone.utc).isoformat(timespec="seconds")])
        job["last_step"] = "PUBLISHED_VERIFIED"
        save_queue(queue)
        sync_state(job, "PUBLISHED_VERIFIED")
        print(json.dumps({
            "status": "PUBLISHED_VERIFIED",
            "job_id": job_id,
            "remote_post_ids": remote_ids,
            "remote_post_urls": remote_urls,
            "platform_states": platform_states,
        }, ensure_ascii=False, indent=2))
        return 0

    job["status"] = "FAILED_FINAL" if int(job.get("publish_attempts") or 0) >= MAX_PUBLISH_ATTEMPTS else "FAILED_RETRYABLE"
    job["last_step"] = job["status"]
    save_queue(queue)
    sync_state(job, job["status"])
    print(json.dumps({
        "status": job["status"],
        "job_id": job_id,
        "attempt": job["publish_attempts"],
        "platform_states": platform_states,
    }, ensure_ascii=False, indent=2))
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    return publish(args.job_id)


if __name__ == "__main__":
    raise SystemExit(main())
