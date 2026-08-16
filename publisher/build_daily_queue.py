#!/usr/bin/env python3
"""Build/reconcile a multi-client publishing queue with explicit approval gates.

The engine may prepare and render content before approval, but a job cannot become
ready for publishing until its approval key has been explicitly approved.
Future unpublished jobs are replaced when the editorial plan changes, preventing
duplicate blasts after a content-bank or schedule update.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "publisher" / "clients"
BANK_DIR = ROOT / "publisher" / "content_bank"
QUEUE_PATH = ROOT / "publisher" / "queue.json"
DEFAULT_CATEGORIES = ["attract", "nurture", "hyperlocal", "convert"]
_APPROVAL_CACHE: dict[str, dict[str, Any]] = {}


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


def format_platforms(client: dict[str, Any], content_format: str | None = None) -> list[str]:
    publishing = client.get("publishing", {})
    by_format = publishing.get("platforms_by_format", {})
    if content_format and isinstance(by_format.get(content_format), list):
        return list(by_format[content_format])
    return list(publishing.get("platforms", []))


def integration_specs(client: dict[str, Any], content_format: str | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    configured: list[dict[str, Any]] = []
    missing_required: list[str] = []
    integrations = client.get("integrations", {})
    for platform in format_platforms(client, content_format):
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


def approval_key_for_date(client: dict[str, Any], target: date) -> str:
    approval = client.get("approval", {})
    if not approval.get("required", False):
        return ""
    mode = str(approval.get("mode") or "iso_week")
    if mode == "iso_week":
        iso = target.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return target.isoformat()


def approval_state(client: dict[str, Any], key: str) -> bool:
    approval = client.get("approval", {})
    if not approval.get("required", False):
        return True
    rel = str(approval.get("file") or "").strip()
    if not rel:
        return False
    if rel not in _APPROVAL_CACHE:
        path = ROOT / rel
        _APPROVAL_CACHE[rel] = load_json(path) if path.exists() else {"approved": [], "revoked": []}
    data = _APPROVAL_CACHE[rel]
    approved = {str(x) for x in data.get("approved", [])}
    revoked = {str(x) for x in data.get("revoked", [])}
    return bool(key and key in approved and key not in revoked)


def media_exists(media_value: Any) -> bool:
    values = media_value if isinstance(media_value, list) else [media_value]
    values = [str(v).strip() for v in values if str(v or "").strip()]
    if not values:
        return False
    return all((ROOT / value).exists() for value in values)


def desired_status(client: dict[str, Any], job: dict[str, Any]) -> tuple[str, str | None]:
    approval_key = str(job.get("approval_key") or "")
    if client.get("approval", {}).get("required", False) and not approval_state(client, approval_key):
        return "awaiting_approval", f"approval required for {approval_key}"
    if client.get("publishing", {}).get("require_media", True) and not media_exists(job.get("media")):
        return "awaiting_media", "rendered media is missing"
    specs, missing_required = integration_specs(client, str(job.get("format") or "reel"))
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
    publishing = client.get("publishing", {})
    slots = publishing.get("slots", [])
    categories = publishing.get("categories", DEFAULT_CATEGORIES)
    if not isinstance(categories, list) or not categories:
        categories = DEFAULT_CATEGORIES
    formats = publishing.get("formats", {})
    territories = client.get("campaign", {}).get("territories", []) or [""]
    ordinal = target.toordinal()
    territory = territories[ordinal % len(territories)]
    approval_key = approval_key_for_date(client, target)

    jobs: list[dict[str, Any]] = []
    for idx, category in enumerate(categories):
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
            "phone": str(client.get("campaign", {}).get("phone") or ""),
        }
        item = replace_tokens(item, tokens)
        hh, mm = [int(x) for x in slots[idx].split(":", 1)]
        scheduled = datetime(target.year, target.month, target.day, hh, mm, tzinfo=tz)
        slug = str(item.get("slug") or f"slot-{idx + 1}")
        content_format = str(formats.get(category) or item.get("format") or "reel").lower()
        slides = list(item.get("slides") or [])
        if content_format == "carousel":
            media: Any = [f"publisher/media/generated/{client_id}/{target.isoformat()}/{idx + 1:02d}-{slug}/slide-{n:02d}.jpg" for n in range(1, len(slides) + 1)]
        else:
            media = f"publisher/media/generated/{client_id}/{target.isoformat()}/{idx + 1:02d}-{slug}.mp4"

        specs, _ = integration_specs(client, content_format)
        voiceover = str(item.get("voiceover") or item.get("caption") or item.get("title") or "")
        job = {
            "id": f"{client_id}-{target.isoformat()}-{idx + 1:02d}-{slug}",
            "client_id": client_id,
            "client_name": client.get("name", client_id),
            "category": category,
            "editorial_role": category,
            "format": content_format,
            "title": item.get("title", ""),
            "caption": item.get("caption", ""),
            "voiceover": voiceover,
            "slides": slides,
            "media": media,
            "scheduled_at": scheduled.isoformat(),
            "approval_key": approval_key,
            "platforms": specs,
            "enabled": True,
            "status": "draft",
            "published_platforms": [],
            "postiz_results": [],
            "video_made_with_ai": content_format == "reel",
            "created_by": "open-social-scheduler",
        }
        status, reason = desired_status(client, job)
        job["status"] = status
        if reason:
            job["blocked_reason"] = reason
        jobs.append(job)
    return jobs


def reconcile(queue: dict[str, Any], client_map: dict[str, dict[str, Any]]) -> None:
    _APPROVAL_CACHE.clear()
    for job in queue.get("jobs", []):
        if job.get("status") in {"scheduled", "published", "disabled"}:
            continue
        client = client_map.get(str(job.get("client_id") or ""))
        if not client:
            if job.get("client_id"):
                job["status"] = "blocked"
                job["blocked_reason"] = "unknown client_id"
            continue
        specs, _ = integration_specs(client, str(job.get("format") or "reel"))
        job["platforms"] = specs
        status, reason = desired_status(client, job)
        job["status"] = status
        if reason:
            job["blocked_reason"] = reason
        else:
            job.pop("blocked_reason", None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Local calendar date YYYY-MM-DD; explicit dates build one day only")
    args = parser.parse_args()

    queue = load_json(QUEUE_PATH) if QUEUE_PATH.exists() else {"version": 3, "jobs": []}
    queue["version"] = max(int(queue.get("version", 1)), 3)
    queue.setdefault("jobs", [])

    all_clients = clients()
    client_map = {c["id"]: c for c in all_clients}
    explicit_date = bool(args.date or os.getenv("SOCIAL_DATE", "").strip())
    offset_days = int(os.getenv("SOCIAL_START_OFFSET_DAYS", "0") or 0)

    targets_by_client: dict[str, list[date]] = {}
    for client in all_clients:
        if not client.get("active", False):
            continue
        tz = ZoneInfo(client.get("timezone", "UTC"))
        start = parse_target_date(args.date, tz) + timedelta(days=offset_days)
        horizon = 1 if explicit_date else max(1, int(client.get("planning", {}).get("horizon_days", 1)))
        targets_by_client[client["id"]] = [start + timedelta(days=i) for i in range(horizon)]

    target_keys = {client_id: {d.isoformat() for d in days} for client_id, days in targets_by_client.items()}
    preserved: list[dict[str, Any]] = []
    replaced = 0
    for job in queue["jobs"]:
        client_id = str(job.get("client_id") or "")
        job_date = str(job.get("scheduled_at") or "")[:10]
        is_target = job_date in target_keys.get(client_id, set())
        is_final = job.get("status") in {"published", "scheduled"}
        if is_target and not is_final:
            replaced += 1
            continue
        preserved.append(job)
    queue["jobs"] = preserved

    existing = {str(j.get("id")) for j in queue["jobs"]}
    added = 0
    for client in all_clients:
        if not client.get("active", False):
            continue
        for target in targets_by_client.get(client["id"], []):
            for job in build_for_client(client, target):
                if job["id"] not in existing:
                    queue["jobs"].append(job)
                    existing.add(job["id"])
                    added += 1

    reconcile(queue, client_map)
    queue["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_json(QUEUE_PATH, queue)
    print(f"Queue reconciled: {replaced} stale future job(s) replaced, {added} new job(s), {len(queue['jobs'])} total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
