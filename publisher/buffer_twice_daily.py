#!/usr/bin/env python3
"""Autonomous F1 publisher through Buffer Free.

Creates exactly two daily content slots and schedules each slot to the connected
Facebook, Instagram and LinkedIn channels through Buffer's GraphQL API.

Authentication model:
- BUFFER_API_KEY: one Buffer personal API key.
- CLOUDINARY_URL: one Cloudinary environment URL for stable public media hosting.

The social account OAuth tokens never enter this repository. Buffer owns those
connections after the one-time account linking step.

This module deliberately uses queue statuses outside the legacy direct publisher
(`ready` / `partially_published`) so the old direct-API workflow cannot pick up
Buffer jobs by accident.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time as time_module
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

import meta_twice_daily as content

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"
CLIENT_PATH = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
BANK_PATH = ROOT / "publisher" / "content_bank" / "f1-immobiliare.json"
ROME = ZoneInfo("Europe/Rome")
TARGET_SERVICES = ("facebook", "instagram", "linkedin")
BUFFER_API = "https://api.buffer.com"
HTTP_TIMEOUT = 120
SLOTS = {
    "morning": time(10, 30),
    "evening": time(18, 30),
}


class BufferAutomationError(RuntimeError):
    pass


def gql_quote(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def buffer_request(api_key: str, query: str) -> dict[str, Any]:
    response = requests.post(
        BUFFER_API,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={"query": query},
        timeout=HTTP_TIMEOUT,
    )
    if not response.ok:
        raise BufferAutomationError(
            f"Buffer HTTP {response.status_code}: {response.text[:1200]}"
        )
    payload = response.json()
    if payload.get("errors"):
        raise BufferAutomationError(
            "Buffer GraphQL error: " + json.dumps(payload["errors"], ensure_ascii=False)[:1800]
        )
    return payload.get("data") or {}


def discover_buffer_channels(api_key: str) -> tuple[str, dict[str, dict[str, str]]]:
    account = buffer_request(
        api_key,
        """
        query F1Organizations {
          account {
            organizations {
              id
              name
            }
          }
        }
        """,
    )
    organizations = list((account.get("account") or {}).get("organizations") or [])
    if not organizations:
        raise BufferAutomationError("Buffer account has no organization")

    diagnostics: list[str] = []
    for org in organizations:
        org_id = str(org.get("id") or "")
        if not org_id:
            continue
        data = buffer_request(
            api_key,
            f"""
            query F1Channels {{
              channels(input: {{
                organizationId: {gql_quote(org_id)},
                filter: {{ isLocked: false }}
              }}) {{
                id
                name
                displayName
                service
              }}
            }}
            """,
        )
        channels = list(data.get("channels") or [])
        by_service: dict[str, list[dict[str, str]]] = {}
        for raw in channels:
            service = str(raw.get("service") or "").lower()
            if service not in TARGET_SERVICES:
                continue
            by_service.setdefault(service, []).append(
                {
                    "id": str(raw.get("id") or ""),
                    "name": str(raw.get("displayName") or raw.get("name") or service),
                    "service": service,
                }
            )

        if all(len(by_service.get(service, [])) == 1 for service in TARGET_SERVICES):
            return org_id, {service: by_service[service][0] for service in TARGET_SERVICES}

        diagnostics.append(
            f"{org.get('name') or org_id}: "
            + ", ".join(f"{s}={len(by_service.get(s, []))}" for s in TARGET_SERVICES)
        )

    raise BufferAutomationError(
        "Connect exactly one unlocked Facebook, Instagram and LinkedIn channel "
        "inside the same Buffer organization. Found: " + " | ".join(diagnostics)
    )


def parse_cloudinary_url(raw: str) -> tuple[str, str, str]:
    value = raw.strip()
    parsed = urlparse(value)
    if parsed.scheme != "cloudinary" or not parsed.username or not parsed.password or not parsed.hostname:
        raise BufferAutomationError(
            "CLOUDINARY_URL must look like cloudinary://API_KEY:API_SECRET@CLOUD_NAME"
        )
    return parsed.hostname, parsed.username, parsed.password


def cloudinary_signature(params: dict[str, str], api_secret: str) -> str:
    canonical = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return hashlib.sha1((canonical + api_secret).encode("utf-8")).hexdigest()


def cloudinary_upload(path: Path, public_id: str, cloudinary_url: str) -> dict[str, str]:
    cloud_name, api_key, api_secret = parse_cloudinary_url(cloudinary_url)
    timestamp = str(int(time_module.time()))
    signed = {
        "overwrite": "true",
        "public_id": public_id,
        "timestamp": timestamp,
    }
    signature = cloudinary_signature(signed, api_secret)
    endpoint = f"https://api.cloudinary.com/v1_1/{cloud_name}/auto/upload"
    with path.open("rb") as fh:
        response = requests.post(
            endpoint,
            data={
                **signed,
                "api_key": api_key,
                "signature": signature,
            },
            files={"file": (path.name, fh)},
            timeout=300,
        )
    if not response.ok:
        raise BufferAutomationError(
            f"Cloudinary HTTP {response.status_code}: {response.text[:1200]}"
        )
    payload = response.json()
    secure_url = str(payload.get("secure_url") or "")
    if not secure_url.startswith("https://"):
        raise BufferAutomationError("Cloudinary upload did not return a secure_url")
    return {
        "url": secure_url,
        "public_id": str(payload.get("public_id") or public_id),
        "resource_type": str(payload.get("resource_type") or ""),
        "bytes": str(payload.get("bytes") or ""),
    }


def media_is_live(url: str) -> bool:
    try:
        response = requests.head(url, allow_redirects=False, timeout=20)
        return response.ok and not response.is_redirect
    except requests.RequestException:
        return False


def make_buffer_job(
    client: dict[str, Any], bank: dict[str, Any], day: date, slot: str
) -> dict[str, Any]:
    job = content.build_job(client, bank, day, slot)
    job["id"] = f"f1-immobiliare-buffer-{day.isoformat()}-{slot}"
    job["platforms"] = [
        {"platform": service, "integration_id": "buffer"} for service in TARGET_SERVICES
    ]
    job["status"] = "buffer_pending"
    job["created_by"] = "buffer-twice-daily"
    job["buffer_posts"] = []
    job["buffer_scheduled_platforms"] = []
    job["approval_required"] = False
    job["manual_approval_required"] = False
    job["autonomous_publish"] = True
    return job


def find_job(queue: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    for job in queue.get("jobs", []):
        if str(job.get("id")) == job_id:
            return job
    return None


def target_date(raw: str | None, now: datetime) -> date:
    return date.fromisoformat(raw) if raw else now.date()


def pick_slot(now: datetime, requested: str) -> str | None:
    if requested in SLOTS:
        return requested
    if requested != "auto":
        raise ValueError(f"Unsupported slot: {requested}")

    current = now.timetz().replace(tzinfo=None)
    # GitHub runs at 08:00 and 16:00 UTC. This is 09:00/17:00 in CET and
    # 10:00/18:00 in CEST, so each run is safely before its Rome target.
    # Generous windows also turn delayed Actions runs into a same-day catch-up.
    if time(16, 30) <= current <= time(21, 30):
        return "evening"
    if time(8, 30) <= current <= time(13, 30):
        return "morning"
    return None


def due_datetime(day: date, slot: str) -> datetime:
    hhmm = SLOTS[slot]
    return datetime(day.year, day.month, day.day, hhmm.hour, hhmm.minute, tzinfo=ROME)


def schedule_mode(now: datetime, due: datetime) -> tuple[str, str | None]:
    if now < due:
        utc_due = due.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return "customScheduled", utc_due
    return "shareNow", None


def absolute_media_paths(job: dict[str, Any]) -> list[Path]:
    raw = job.get("media")
    values = raw if isinstance(raw, list) else [raw]
    paths = [ROOT / str(value) for value in values if str(value or "").strip()]
    if not paths:
        raise BufferAutomationError("Generated job has no media paths")
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise BufferAutomationError("Generated media missing: " + ", ".join(missing))
    return paths


def ensure_cloudinary_assets(job: dict[str, Any], cloudinary_url: str) -> list[dict[str, str]]:
    existing = list(job.get("cloudinary_assets") or [])
    if existing and all(media_is_live(str(row.get("url") or "")) for row in existing):
        return existing

    paths = absolute_media_paths(job)
    assets: list[dict[str, str]] = []
    for index, path in enumerate(paths, 1):
        public_id = (
            f"f1-buffer/{job['id']}/"
            + (f"slide-{index:02d}" if len(paths) > 1 else "video")
        )
        assets.append(cloudinary_upload(path, public_id, cloudinary_url))
    job["cloudinary_assets"] = assets
    return assets


def gql_assets(service: str, job: dict[str, Any], hosted: list[dict[str, str]]) -> str:
    urls = [str(row["url"]) for row in hosted]
    if str(job.get("format")) == "reel":
        extra = " metadata: { thumbnailOffset: 2000 }" if service == "instagram" else ""
        return "[{ video: { url: " + gql_quote(urls[0]) + extra + " } }]"
    return "[" + ", ".join(
        "{ image: { url: " + gql_quote(url) + " } }" for url in urls[:10]
    ) + "]"


def gql_metadata(service: str, job: dict[str, Any]) -> str:
    is_reel = str(job.get("format")) == "reel"
    if service == "facebook":
        return "{ facebook: { type: " + ("reel" if is_reel else "post") + " } }"
    if service == "instagram":
        post_type = "reel" if is_reel else "carousel"
        return (
            "{ instagram: { type: "
            + post_type
            + ", shouldShareToFeed: true"
            + (", isAiGenerated: true" if is_reel and job.get("video_made_with_ai") else "")
            + " } }"
        )
    return ""


def create_buffer_post(
    api_key: str,
    channel_id: str,
    service: str,
    job: dict[str, Any],
    hosted: list[dict[str, str]],
    now: datetime,
) -> dict[str, Any]:
    due = datetime.fromisoformat(str(job["scheduled_at"]))
    mode, due_at = schedule_mode(now, due)
    fields = [
        f"text: {gql_quote(str(job.get('caption') or ''))}",
        f"channelId: {gql_quote(channel_id)}",
        "schedulingType: automatic",
        f"mode: {mode}",
        f"assets: {gql_assets(service, job, hosted)}",
        "aiAssisted: true",
        f"source: {gql_quote('f1-github-buffer')}",
    ]
    if due_at:
        fields.append(f"dueAt: {gql_quote(due_at)}")
    metadata = gql_metadata(service, job)
    if metadata:
        fields.append(f"metadata: {metadata}")

    query = """
    mutation F1CreatePost {
      createPost(input: {
        %s
      }) {
        ... on PostActionSuccess {
          post {
            id
            status
            dueAt
            channelId
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """ % "\n        ".join(fields)

    data = buffer_request(api_key, query)
    result = data.get("createPost") or {}
    if result.get("message"):
        raise BufferAutomationError(f"Buffer {service}: {result['message']}")
    post = result.get("post")
    if not isinstance(post, dict) or not post.get("id"):
        raise BufferAutomationError(
            f"Buffer {service}: createPost returned no post id: {json.dumps(result, ensure_ascii=False)}"
        )
    return {
        "service": service,
        "channel_id": channel_id,
        "post_id": str(post["id"]),
        "buffer_status": str(post.get("status") or ""),
        "due_at": post.get("dueAt"),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def prune_history(queue: dict[str, Any], keep: int = 120) -> None:
    jobs = list(queue.get("jobs", []))
    owned = [j for j in jobs if str(j.get("created_by")) == "buffer-twice-daily"]
    if len(owned) <= keep:
        return
    owned = sorted(owned, key=lambda j: str(j.get("scheduled_at") or ""), reverse=True)
    keep_ids = {str(j.get("id")) for j in owned[:keep]}
    queue["jobs"] = [
        job
        for job in jobs
        if str(job.get("created_by")) != "buffer-twice-daily"
        or str(job.get("id")) in keep_ids
    ]


def persist_queue(queue: dict[str, Any]) -> None:
    queue["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prune_history(queue)
    content.save_json(QUEUE_PATH, queue)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["auto", "morning", "evening"], default="auto")
    parser.add_argument("--date", help="Europe/Rome date YYYY-MM-DD; default today")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate credentials/channels and render, but do not create Buffer posts",
    )
    args = parser.parse_args()

    now = datetime.now(ROME)
    slot = pick_slot(now, args.slot)
    if slot is None:
        print(f"NOOP: no F1 Buffer slot is due at {now.isoformat(timespec='minutes')}")
        return 0

    day = target_date(args.date, now)
    if args.slot == "auto" and day != now.date():
        print("NOOP: automatic scheduler only handles today's Rome date")
        return 0

    client = content.load_json(CLIENT_PATH)
    bank = content.load_json(BANK_PATH)
    queue = content.load_json(QUEUE_PATH, {"version": 6, "jobs": []})
    queue.setdefault("jobs", [])

    template = make_buffer_job(client, bank, day, slot)
    existing = find_job(queue, template["id"])
    if existing:
        scheduled = set(str(x) for x in existing.get("buffer_scheduled_platforms", []))
        if set(TARGET_SERVICES).issubset(scheduled):
            print(f"NOOP: {template['id']} already scheduled in Buffer for all 3 channels")
            return 0
        preserved = {
            "buffer_posts": list(existing.get("buffer_posts", [])),
            "buffer_scheduled_platforms": list(existing.get("buffer_scheduled_platforms", [])),
            "cloudinary_assets": list(existing.get("cloudinary_assets", [])),
        }
        existing.clear()
        existing.update(template)
        existing.update(preserved)
        job = existing
    else:
        queue["jobs"].append(template)
        job = template

    api_key = os.getenv("BUFFER_API_KEY", "").strip()
    cloudinary_url = os.getenv("CLOUDINARY_URL", "").strip()
    missing = [
        name
        for name, value in (
            ("BUFFER_API_KEY", api_key),
            ("CLOUDINARY_URL", cloudinary_url),
        )
        if not value
    ]
    if missing:
        job["status"] = "awaiting_buffer_credentials"
        job["blocked_reason"] = "missing GitHub Actions Secrets: " + ", ".join(missing)
        persist_queue(queue)
        print(json.dumps({"job_id": job["id"], "status": job["status"], "missing": missing}, indent=2))
        return 2

    try:
        organization_id, channels = discover_buffer_channels(api_key)
    except Exception as exc:
        job["status"] = "awaiting_buffer_channels"
        job["blocked_reason"] = str(exc)
        persist_queue(queue)
        print(json.dumps({"job_id": job["id"], "status": job["status"], "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    job["buffer_organization_id"] = organization_id
    job["buffer_channels"] = channels

    try:
        content.render_job(job, client)
        hosted = ensure_cloudinary_assets(job, cloudinary_url)
        persist_queue(queue)

        if args.dry_run:
            job["status"] = "buffer_dry_run_ok"
            job.pop("blocked_reason", None)
            persist_queue(queue)
            print(
                json.dumps(
                    {
                        "job_id": job["id"],
                        "status": job["status"],
                        "channels": channels,
                        "media": [row["url"] for row in hosted],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        scheduled = set(str(x) for x in job.get("buffer_scheduled_platforms", []))
        results: list[dict[str, Any]] = []
        for service in TARGET_SERVICES:
            if service in scheduled:
                continue
            channel = channels[service]
            try:
                result = create_buffer_post(
                    api_key,
                    str(channel["id"]),
                    service,
                    job,
                    hosted,
                    datetime.now(ROME),
                )
                job.setdefault("buffer_posts", []).append(result)
                job.setdefault("buffer_scheduled_platforms", []).append(service)
                scheduled.add(service)
                results.append({**result, "status": "scheduled"})
                # Persist after every successful channel so retries only target the remainder.
                persist_queue(queue)
            except Exception as exc:
                results.append({"service": service, "status": "error", "error": str(exc)})

        if set(TARGET_SERVICES).issubset(scheduled):
            job["status"] = "scheduled_in_buffer"
            job.pop("blocked_reason", None)
            exit_code = 0
        elif scheduled:
            job["status"] = "buffer_partially_scheduled"
            job["blocked_reason"] = "Buffer retry required for remaining channels"
            exit_code = 1
        else:
            job["status"] = "buffer_retry_required"
            job["blocked_reason"] = "Buffer did not schedule any target channel"
            exit_code = 1

        persist_queue(queue)
        print(
            json.dumps(
                {
                    "job_id": job["id"],
                    "slot": slot,
                    "status": job["status"],
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return exit_code
    except Exception as exc:
        job["status"] = "buffer_render_or_media_failed"
        job["blocked_reason"] = str(exc)
        persist_queue(queue)
        print(
            json.dumps(
                {"job_id": job["id"], "status": job["status"], "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    finally:
        content.cleanup_media(job)


if __name__ == "__main__":
    raise SystemExit(main())
