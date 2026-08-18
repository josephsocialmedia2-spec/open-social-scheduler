#!/usr/bin/env python3
"""Build/reconcile the multi-client daily content queue with a rolling 48-item cap."""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "publisher" / "clients"
BANK_DIR = ROOT / "publisher" / "content_bank"
QUEUE_PATH = ROOT / "publisher" / "queue.json"
DEFAULT_CATEGORIES = ["attract", "nurture", "convert"]
_APPROVAL_CACHE: dict[str, dict[str, Any]] = {}
MAX_QUEUE_ITEMS = 48


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
    return bool(values) and all((ROOT / value).exists() for value in values)


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


def hashtags_for(client: dict[str, Any], ordinal: int, slot_index: int) -> list[str]:
    sets = client.get("campaign", {}).get("hashtag_sets", [])
    sets = [row for row in sets if isinstance(row, list) and row]
    if not sets:
        return []
    return [str(tag).strip() for tag in sets[(ordinal + slot_index) % len(sets)] if str(tag).strip()]


def caption_with_hashtags(caption: str, hashtags: list[str]) -> str:
    base = str(caption or "").strip()
    if not hashtags:
        return base
    existing = {part for part in base.split() if part.startswith("#")}
    extra = [tag for tag in hashtags if tag not in existing]
    return base if not extra else base + "\n\n" + " ".join(extra)


def build_for_client(client: dict[str, Any], target: date) -> list[dict[str, Any]]:
    client_id = client["id"]
    bank_path = BANK_DIR / f"{client_id}.json"
    if not bank_path.exists():
        return []
    bank = load_json(bank_path)
    tz = ZoneInfo(client.get("timezone", "UTC"))
    publishing = client.get("publishing", {})
    slots = list(publishing.get("slots", []))
    categories = list(publishing.get("categories", DEFAULT_CATEGORIES))
    formats = publishing.get("formats", {})
    format_sequence = list(publishing.get("format_sequence", []))

    # Deluxe daily production: 10 publishable candidates per brand,
    # split 5 Reels + 5 carousels. Config remains backward-compatible.
    if client_id == "f1-immobiliare":
        slots = ["08:00", "09:15", "10:30", "11:45", "13:00", "14:15", "15:30", "16:45", "18:00", "19:15"]
        categories = ["data", "error", "proof", "data", "error", "proof", "data", "error", "proof", "data"]
        format_sequence = ["reel", "carousel", "reel", "carousel", "reel", "carousel", "reel", "carousel", "reel", "carousel"]
    elif client_id == "real-media-pro":
        slots = ["08:10", "09:25", "10:40", "11:55", "13:10", "14:25", "15:40", "16:55", "18:10", "19:25"]
        categories = ["attract", "nurture", "convert", "attract", "nurture", "convert", "attract", "nurture", "convert", "attract"]
        format_sequence = ["reel", "carousel", "reel", "carousel", "reel", "carousel", "reel", "carousel", "reel", "carousel"]
    campaign = client.get("campaign", {})
    territories = campaign.get("territories", []) or [""]
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
        item = dict(items[(ordinal + idx) % len(items)])
        tokens = {
            "territory": territory,
            "cta": str(campaign.get("cta") or ""),
            "client": str(client.get("name") or client_id),
            "phone": str(campaign.get("phone") or ""),
        }
        item = replace_tokens(item, tokens)
        hh, mm = [int(x) for x in slots[idx].split(":", 1)]
        scheduled = datetime(target.year, target.month, target.day, hh, mm, tzinfo=tz)
        slug = str(item.get("slug") or f"slot-{idx + 1}")
        content_format = (
            str(format_sequence[idx]).lower()
            if idx < len(format_sequence)
            else str(item.get("format") or formats.get(category) or "reel").lower()
        )
        slides = list(item.get("slides") or [])
        if content_format == "carousel":
            slide_count = max(10, len(slides))
            media: Any = [
                f"publisher/media/generated/{client_id}/{target.isoformat()}/{idx + 1:02d}-{slug}/slide-{n:02d}.jpg"
                for n in range(1, slide_count + 1)
            ]
        else:
            media = f"publisher/media/generated/{client_id}/{target.isoformat()}/{idx + 1:02d}-{slug}.mp4"

        specs, _ = integration_specs(client, content_format)
        raw_caption = str(item.get("caption") or "")
        voiceover = str(item.get("voiceover") or raw_caption or item.get("title") or "")
        item_hashtags = [str(x).strip() for x in item.get("hashtags", []) if str(x).strip()]
        hashtags = item_hashtags or hashtags_for(client, ordinal, idx)
        job = {
            "id": f"{client_id}-{target.isoformat()}-{idx + 1:02d}-{slug}",
            "client_id": client_id,
            "client_name": client.get("name", client_id),
            "category": category,
            "editorial_role": category,
            "campaign": str(campaign.get("name") or "Daily content"),
            "format": content_format,
            "title": item.get("title", ""),
            "caption": caption_with_hashtags(raw_caption, hashtags),
            "hashtags": hashtags,
            "voiceover": voiceover,
            "slides": slides,
            "visuals": list(item.get("visuals") or []),
            "cta": item.get("cta", campaign.get("cta", "")),
            "media": media,
            "scheduled_at": scheduled.isoformat(),
            "territory": territory,
            "property_focus": campaign.get("property_focus", {}),
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


def cap_queue(queue: dict[str, Any], limit: int = MAX_QUEUE_ITEMS) -> int:
    jobs = list(queue.get("jobs", []))
    if len(jobs) <= limit:
        return 0
    jobs.sort(key=lambda j: (str(j.get("scheduled_at") or ""), str(j.get("id") or "")), reverse=True)
    removed = len(jobs) - limit
    queue["jobs"] = jobs[:limit]
    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Local calendar date YYYY-MM-DD; explicit dates build one day only")
    args = parser.parse_args()

    queue = load_json(QUEUE_PATH) if QUEUE_PATH.exists() else {"version": 5, "jobs": []}
    queue["version"] = max(int(queue.get("version", 1)), 5)
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
        if is_final:
            preserved.append(job)
            continue
        if is_target:
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
    removed = cap_queue(queue)
    queue["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_json(QUEUE_PATH, queue)
    print(
        f"Queue reconciled: {replaced} current draft job(s) replaced, "
        f"{added} new candidate(s), {removed} oldest item(s) removed, "
        f"{len(queue['jobs'])} total."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
