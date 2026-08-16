#!/usr/bin/env python3
"""Build/reconcile a daily multi-client publishing queue.

The script is deterministic: no external AI call is required to keep the schedule
alive. Each client can provide a rotating content bank. Rendering and publishing
are separate stages, so missing media or OAuth connections never cause accidental
text-only publication.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "publisher" / "clients"
BANK_DIR = ROOT / "publisher" / "content_bank"
QUEUE_PATH = ROOT / "publisher" / "queue.json"
CATEGORIES = ["attract", "nurture", "hyperlocal", "convert"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def clients() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(CLIENT_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = load_json(path)
        data["_path"] = str(path.relative_to(ROOT))
        out.append(data)
    return out


def replace_tokens(value: Any, tokens: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, replacement in tokens.items():
            value = value.replace("{" + key + "}", replacement)
        return value
    if isinstance(value, list):
        return [replace_tokens(item, tokens) for item in value]
    if isinstance(value, dict):
        return {key: replace_tokens(item, tokens) for key, item in value.items()}
    return value


def parse_target_date(raw: str | None, tz: ZoneInfo) -> date:
    if raw:
        return date.fromisoformat(raw)
    env_date = os.getenv("SOCIAL_DATE", "").strip()
    if env_date:
        return date.fromisoformat(env_date)
    return datetime.now(tz).date()


def integration_specs(client: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    configured: list[dict[str, Any]] = []
    missing_required: list[str] = []
    integrations = client.get("integrations", {})
    for platform in client.get("publishing", {}).get("platforms", []):
        cfg = integrations.get(platform, {})
        integration_id = str(cfg.get("id") or "").strip()
        if integration_id:
            spec: dict[str, Any] = {"platform": platform, "integration_id": integration_id}
            if platform == "pinterest" and cfg.get("board"):
                spec["settings"] = {"board": cfg["board"]}
            configured.append(spec)
        elif cfg.get("required", False):
            missing_required.append(platform)
    return configured, missing_required


def desired_status(client: dict[str, Any], job: dict[str, Any]) -> tuple[str, str | None]:
    media = str(job.get("media") or "").strip()
    if client.get("publishing", {}).get("require_media", True):
        if not media or not (ROOT / media).exists():
            return "awaiting_media", "rendered media is missing"

    specs, missing_required = integration_specs(client)
    if missing_required:
        return "awaiting_integrations", "missing required integration IDs: " + ", ".join(missing_required)
    if not specs:
        return "awaiting_integrations", "no configured social integration IDs"
    return "ready", None


def build_for_client(client: dict[str, Any], target: date) -> list[dict[str, Any]]:
    client_id = client["id"]
    bank_path = BANK_DIR / f"{client_id}.json"
    if not bank_path.exists():
        return []
    bank = load_json(bank_path)
    tz = ZoneInfo(client.get("timezone", "UTC"))
    slots = client.get("publishing", {}).get("slots", [])
    territories = client.get("campaign", {}).get("territories", []) or [""]
    ordinal = target.toordinal()
    territory = territories[ordinal % len(territories)]
    specs, _ = integration_specs(client)

    jobs: list[dict[str, Any]] = []
    for idx, category in enumerate(CATEGORIES):
        if idx >= len(slots):
            break
        items = bank.get(category, [])
        if not items:
            continue
        item = items[(ordinal + idx) % len(items)]
        tokens = {
            "territory": territory,
            "cta": client.get("campaign", {}).get("cta", ""),
            "client": client.get("name", client_id),
        }
        item = replace_tokens(item, tokens)
        hh, mm = [int(x) for x in slots[idx].split(":", 1)]
        scheduled = datetime(target.year, target.month, target.day, hh, mm, tzinfo=tz)
        slug = str(item.get("slug") or f"slot-{idx + 1}")
        media = f"publisher/media/generated/{client_id}/{target.isoformat()}/{idx + 1:02d}-{slug}.mp4"
        job = {
            "id": f"{client_id}-{target.isoformat()}-{idx + 1:02d}-{slug}",
            "client_id": client_id,
            "client_name": client.get("name", client_id),
            "category": category,
            "title": item.get("title", ""),
            "caption": item.get("caption", ""),
            "slides": item.get("slides", []),
            "media": media,
            "scheduled_at": scheduled.isoformat(),
            "platforms": specs,
            "enabled": True,
            "status": "draft",
            "published_platforms": [],
            "postiz_results": [],
            "created_by": "open-social-scheduler",
        }
        status, reason = desired_status(client, job)
        job["status"] = status
        if reason:
            job["blocked_reason"] = reason
        jobs.append(job)
    return jobs


def reconcile(queue: dict[str, Any], client_map: dict[str, dict[str, Any]]) -> None:
    for job in queue.get("jobs", []):
        if job.get("status") in {"scheduled", "published", "disabled"}:
            continue
        client = client_map.get(str(job.get("client_id") or ""))
        if not client:
            if job.get("client_id"):
                job["status"] = "blocked"
                job["blocked_reason"] = "unknown client_id"
            continue
        specs, _ = integration_specs(client)
        job["platforms"] = specs
        status, reason = desired_status(client, job)
        job["status"] = status
        if reason:
            job["blocked_reason"] = reason
        else:
            job.pop("blocked_reason", None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Local calendar date YYYY-MM-DD; defaults to today per client timezone")
    args = parser.parse_args()

    queue = load_json(QUEUE_PATH) if QUEUE_PATH.exists() else {"version": 2, "jobs": []}
    queue["version"] = max(int(queue.get("version", 1)), 2)
    queue.setdefault("jobs", [])

    all_clients = clients()
    client_map = {c["id"]: c for c in all_clients}
    existing = {str(j.get("id")) for j in queue["jobs"]}
    added = 0

    for client in all_clients:
        if not client.get("active", False):
            continue
        tz = ZoneInfo(client.get("timezone", "UTC"))
        target = parse_target_date(args.date, tz)
        for job in build_for_client(client, target):
            if job["id"] not in existing:
                queue["jobs"].append(job)
                existing.add(job["id"])
                added += 1

    reconcile(queue, client_map)
    queue["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_json(QUEUE_PATH, queue)
    print(f"Queue reconciled: {added} new job(s), {len(queue['jobs'])} total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
