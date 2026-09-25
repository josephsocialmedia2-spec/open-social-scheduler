#!/usr/bin/env python3
"""Publish Content Hub queue jobs through the correct Buffer account.

This module is intentionally separate from the legacy F1 twice-daily Buffer
scheduler. It only handles queue jobs whose provider is "buffer" and resolves
credentials + channel IDs from the selected client's checked-in configuration.

Secrets remain in GitHub Actions. Client JSON files contain only secret variable
names and non-sensitive Buffer channel IDs.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from buffer_twice_daily import (
    ROME,
    buffer_request,
    create_buffer_post,
    ensure_cloudinary_assets,
    get_buffer_post,
    gql_quote,
)

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"
CLIENTS_DIR = ROOT / "publisher" / "clients"
PAST_DUE_GRACE = timedelta(minutes=60)


class BufferQueueError(RuntimeError):
    pass


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise BufferQueueError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_queue(queue: dict[str, Any]) -> None:
    queue["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    QUEUE_PATH.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_client(client_id: str) -> dict[str, Any]:
    path = CLIENTS_DIR / f"{client_id}.json"
    client = load_json(path)
    if str(client.get("id") or "") != client_id:
        raise BufferQueueError(f"Client config mismatch for {client_id}")
    return client


def buffer_config(client: dict[str, Any]) -> tuple[str, dict[str, str]]:
    publishing = client.get("publishing") or {}
    secret_env = str(publishing.get("buffer_secret_env") or "").strip()
    raw_channels = publishing.get("buffer_channels") or {}
    channels = {
        str(service).strip().lower(): str(channel_id).strip()
        for service, channel_id in raw_channels.items()
        if str(service).strip() and str(channel_id).strip()
    }
    if str(publishing.get("backend") or "").strip().lower() != "buffer":
        raise BufferQueueError(f"{client.get('id')}: publishing.backend is not buffer")
    if not secret_env:
        raise BufferQueueError(f"{client.get('id')}: buffer_secret_env is missing")
    if not channels:
        raise BufferQueueError(f"{client.get('id')}: buffer_channels is empty")
    return secret_env, channels


def buffer_secret_env(client: dict[str, Any]) -> str:
    publishing = client.get("publishing") or {}
    secret_env = str(publishing.get("buffer_secret_env") or "").strip()
    if not secret_env:
        raise BufferQueueError(f"{client.get('id')}: buffer_secret_env is missing")
    return secret_env


def secret_for_client(client: dict[str, Any]) -> str:
    secret_env = buffer_secret_env(client)
    value = os.getenv(secret_env, "").strip()
    if not value:
        raise BufferQueueError(f"Missing GitHub Actions secret: {secret_env}")
    return value


def discover_buffer_channels(api_key: str) -> dict[str, dict[str, str]]:
    account = buffer_request(
        api_key,
        """
        query ContentHubOrganizations {
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
        raise BufferQueueError("Buffer account has no organization")

    discovered: dict[str, dict[str, str]] = {}
    for org in organizations:
        org_id = str(org.get("id") or "").strip()
        if not org_id:
            continue
        data = buffer_request(
            api_key,
            f"""
            query ContentHubChannels {{
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
        for raw in list(data.get("channels") or []):
            channel_id = str(raw.get("id") or "").strip()
            if not channel_id:
                continue
            discovered[channel_id] = {
                "id": channel_id,
                "name": str(raw.get("displayName") or raw.get("name") or ""),
                "service": str(raw.get("service") or "").strip().lower(),
                "organization_id": org_id,
                "organization_name": str(org.get("name") or ""),
            }
    return discovered


def discover_client(client_id: str) -> dict[str, Any]:
    client = load_client(client_id)
    secret_env = buffer_secret_env(client)
    api_key = secret_for_client(client)
    discovered = discover_buffer_channels(api_key)

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in discovered.values():
        service = str(row.get("service") or "")
        grouped.setdefault(service, []).append({
            "id": str(row.get("id") or ""),
            "name": str(row.get("name") or ""),
            "organization_name": str(row.get("organization_name") or ""),
        })

    return {
        "client_id": client_id,
        "secret_env": secret_env,
        "publishing_backend": str((client.get("publishing") or {}).get("backend") or ""),
        "channels": grouped,
        "channel_count": len(discovered),
    }


def verify_client(client_id: str) -> dict[str, Any]:
    client = load_client(client_id)
    secret_env, expected = buffer_config(client)
    api_key = secret_for_client(client)
    discovered = discover_buffer_channels(api_key)

    result: dict[str, Any] = {
        "client_id": client_id,
        "secret_env": secret_env,
        "channels": {},
        "ok": True,
    }
    for service, channel_id in expected.items():
        row = discovered.get(channel_id)
        ok = bool(row and row.get("service") == service)
        result["channels"][service] = {
            "channel_id": channel_id,
            "found": bool(row),
            "service_matches": ok,
            "name": row.get("name") if row else None,
        }
        if not ok:
            result["ok"] = False

    if not result["ok"]:
        raise BufferQueueError(
            "Configured Buffer channel IDs do not match the connected account: "
            + json.dumps(result, ensure_ascii=False)
        )
    return result


def job_platforms(job: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in job.get("platforms") or []:
        platform = item.get("platform") if isinstance(item, dict) else item
        platform = str(platform or "").strip().lower()
        if platform == "linkedin-page":
            platform = "linkedin"
        if platform and platform not in out:
            out.append(platform)
    return out


def parse_due(job: dict[str, Any]) -> datetime:
    raw = str(job.get("scheduled_at") or "").strip()
    if not raw:
        raise BufferQueueError(f"{job.get('id')}: scheduled_at is missing")
    due = datetime.fromisoformat(raw)
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return due


def provider_channel_id(job: dict[str, Any], client: dict[str, Any], service: str) -> str:
    _, configured = buffer_config(client)
    channel_id = configured.get(service, "")
    queue_channel_id = str(job.get("provider_channel_id") or "").strip()
    if queue_channel_id and channel_id and queue_channel_id != channel_id:
        raise BufferQueueError(
            f"{job.get('id')}: queue channel {queue_channel_id} does not match "
            f"client config {channel_id}"
        )
    if not channel_id:
        raise BufferQueueError(f"{client.get('id')}: no Buffer channel for {service}")
    return channel_id


def reconcile_existing(job: dict[str, Any], api_key: str) -> bool:
    posts = list(job.get("buffer_posts") or [])
    if not posts:
        return False

    refreshed: list[dict[str, Any]] = []
    all_sent = True
    for post in posts:
        post_id = str(post.get("post_id") or "").strip()
        if not post_id:
            all_sent = False
            refreshed.append(post)
            continue
        state = get_buffer_post(api_key, post_id)
        merged = {**post, **state}
        refreshed.append(merged)
        if not state.get("sent_at") and not state.get("external_link"):
            all_sent = False

    job["buffer_posts"] = refreshed
    if all_sent and refreshed:
        job["status"] = "published"
        job["enabled"] = False
        last = refreshed[-1]
        job["external_post_id"] = last.get("post_id")
        job["external_url"] = last.get("external_link")
        job.pop("blocked_reason", None)
    else:
        job["status"] = "buffer_scheduled"
        job["enabled"] = True
    return True


def process_job(
    job: dict[str, Any],
    *,
    dry_run: bool,
    channel_cache: dict[str, dict[str, dict[str, str]]],
) -> dict[str, Any]:
    client_id = str(job.get("client_id") or "").strip()
    client = load_client(client_id)
    api_key = secret_for_client(client)

    if reconcile_existing(job, api_key):
        return {
            "job_id": job.get("id"),
            "client_id": client_id,
            "status": job.get("status"),
            "reconciled": True,
        }

    platforms = job_platforms(job)
    if len(platforms) != 1:
        raise BufferQueueError(
            f"{job.get('id')}: Content Hub Buffer jobs must target exactly one platform"
        )
    service = platforms[0]
    channel_id = provider_channel_id(job, client, service)

    discovered = channel_cache.get(client_id)
    if discovered is None:
        discovered = discover_buffer_channels(api_key)
        channel_cache[client_id] = discovered
    row = discovered.get(channel_id)
    if not row:
        raise BufferQueueError(
            f"{job.get('id')}: Buffer channel {channel_id} is not connected to {client_id}"
        )
    if str(row.get("service") or "") != service:
        raise BufferQueueError(
            f"{job.get('id')}: Buffer channel {channel_id} is {row.get('service')}, not {service}"
        )

    due = parse_due(job)
    now = datetime.now(timezone.utc)
    if due < now - PAST_DUE_GRACE:
        job["status"] = "buffer_review_required"
        job["blocked_reason"] = "Scheduled time is more than 60 minutes in the past; manual review required"
        return {
            "job_id": job.get("id"),
            "client_id": client_id,
            "status": job["status"],
            "scheduled_at": job.get("scheduled_at"),
        }

    media = [str(x) for x in (job.get("media") or []) if str(x or "").strip()]
    if not media:
        raise BufferQueueError(f"{job.get('id')}: no media")
    for relative in media:
        path = ROOT / relative
        if not path.exists() or path.stat().st_size == 0:
            raise BufferQueueError(f"{job.get('id')}: missing media {relative}")

    if dry_run:
        return {
            "job_id": job.get("id"),
            "client_id": client_id,
            "service": service,
            "channel_id": channel_id,
            "channel_name": row.get("name"),
            "status": "buffer_dry_run_ok",
        }

    cloudinary_url = os.getenv("CLOUDINARY_URL", "").strip()
    if not cloudinary_url:
        raise BufferQueueError("Missing GitHub Actions secret: CLOUDINARY_URL")

    hosted = ensure_cloudinary_assets(job, cloudinary_url)
    result = create_buffer_post(
        api_key,
        channel_id,
        service,
        job,
        hosted,
        datetime.now(ROME),
    )
    job.setdefault("buffer_posts", []).append(result)
    job["buffer_scheduled_platforms"] = [service]
    job["status"] = "buffer_scheduled"
    job["enabled"] = True
    job.pop("blocked_reason", None)
    return {
        "job_id": job.get("id"),
        "client_id": client_id,
        "service": service,
        "channel_id": channel_id,
        "channel_name": row.get("name"),
        "status": job["status"],
        "buffer_post_id": result.get("post_id"),
        "due_at": result.get("due_at"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id")
    parser.add_argument("--client-id")
    parser.add_argument("--verify-client")
    parser.add_argument("--discover-client")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if args.discover_client:
        try:
            print(json.dumps(discover_client(args.discover_client), ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(json.dumps({"status": "BUFFER_DISCOVERY_FAILED", "error": str(exc)}, ensure_ascii=False, indent=2))
            return 2

    if args.verify_client:
        try:
            print(json.dumps(verify_client(args.verify_client), ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(json.dumps({"status": "BUFFER_VERIFY_FAILED", "error": str(exc)}, ensure_ascii=False, indent=2))
            return 2

    queue = load_json(QUEUE_PATH, {"version": 6, "jobs": []})
    jobs = []
    for job in queue.get("jobs") or []:
        if str(job.get("provider") or "").strip().lower() != "buffer":
            continue
        if args.job_id and str(job.get("id")) != args.job_id:
            continue
        if args.client_id and str(job.get("client_id")) != args.client_id:
            continue
        if str(job.get("status") or "") not in {
            "ready", "buffer_scheduled", "buffer_review_required"
        }:
            continue
        if not job.get("enabled", True) and str(job.get("status")) != "buffer_scheduled":
            continue
        jobs.append(job)

    report: dict[str, Any] = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dry_run": args.dry_run,
        "selected": len(jobs),
        "results": [],
        "errors": [],
    }
    channel_cache: dict[str, dict[str, dict[str, str]]] = {}
    changed = False

    for job in jobs:
        before = json.dumps(job, sort_keys=True, ensure_ascii=False)
        try:
            report["results"].append(
                process_job(job, dry_run=args.dry_run, channel_cache=channel_cache)
            )
        except Exception as exc:
            report["errors"].append({
                "job_id": job.get("id"),
                "client_id": job.get("client_id"),
                "error": str(exc),
            })
            if not args.dry_run:
                job["status"] = "buffer_retry_required"
                job["blocked_reason"] = str(exc)
        after = json.dumps(job, sort_keys=True, ensure_ascii=False)
        if before != after:
            changed = True
            if not args.dry_run:
                save_queue(queue)

    if changed and not args.dry_run:
        save_queue(queue)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and report["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
