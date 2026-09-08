#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import buffer_twice_daily as base

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "publisher" / "territory_channels.json"


def _norm(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[^a-z0-9à-ÿ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise base.BufferAutomationError("Missing publisher/territory_channels.json")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def discover_all_channels(api_key: str) -> tuple[str, list[dict[str, str]]]:
    account = base.buffer_request(api_key, """
    query F1Organizations {
      account { organizations { id name } }
    }
    """)
    organizations = list((account.get("account") or {}).get("organizations") or [])
    if not organizations:
        raise base.BufferAutomationError("Buffer account has no organization")

    all_channels: list[dict[str, str]] = []
    selected_org = ""
    for org in organizations:
        org_id = str(org.get("id") or "")
        if not org_id:
            continue
        data = base.buffer_request(api_key, f"""
        query F1Channels {{
          channels(input: {{ organizationId: {base.gql_quote(org_id)}, filter: {{ isLocked: false }} }}) {{
            id name displayName service
          }}
        }}
        """)
        channels = list(data.get("channels") or [])
        if channels and not selected_org:
            selected_org = org_id
        for raw in channels:
            service = str(raw.get("service") or "").lower()
            if service not in base.TARGET_SERVICES:
                continue
            all_channels.append({
                "id": str(raw.get("id") or ""),
                "name": str(raw.get("displayName") or raw.get("name") or service),
                "service": service,
                "organization_id": org_id,
            })
    if not all_channels:
        raise base.BufferAutomationError("No unlocked Buffer social channels found")
    return selected_org, all_channels


def _match_channel(channels: list[dict[str, str]], service: str, aliases: list[str]) -> dict[str, str] | None:
    candidates = [c for c in channels if c.get("service") == service]
    normalized_aliases = [_norm(a) for a in aliases if _norm(a)]
    if normalized_aliases:
        matches = [c for c in candidates if any(a in _norm(c.get("name", "")) for a in normalized_aliases)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise base.BufferAutomationError(
                f"Ambiguous Buffer mapping for {service}: " + ", ".join(c["name"] for c in matches)
            )

    # Operational fallback: when Buffer exposes exactly one unlocked channel for a
    # requested service, use it even if the display name does not contain the
    # municipality. This prevents territory-label mismatches from blocking the lot.
    if len(candidates) == 1:
        return candidates[0]
    return None


def resolve_job_channels(api_key: str, job: dict[str, Any]) -> tuple[str, dict[str, dict[str, str]]]:
    cfg = load_config()
    organization_id, channels = discover_all_channels(api_key)
    scope = str(job.get("scope") or cfg.get("default_scope") or "territory")
    requested_platforms = [str(x).lower() for x in (job.get("platforms") or ["facebook", "instagram"])]

    if scope == str(cfg.get("corporate_scope") or "network"):
        resolved: dict[str, dict[str, str]] = {}
        for service in requested_platforms:
            candidates = [c for c in channels if c.get("service") == service]
            if len(candidates) == 1:
                resolved[service] = candidates[0]
            else:
                raise base.BufferAutomationError(
                    f"Network scope currently requires exactly one {service} channel; found {len(candidates)}"
                )
        return organization_id, resolved

    territory = str(job.get("territory") or "").strip()
    if not territory:
        raise base.BufferAutomationError(f"{job.get('id')}: territory missing for territory-scoped job")
    territory_key = _norm(territory).replace(" ", "-")
    territory_cfg = (cfg.get("territories") or {}).get(territory_key)
    if not territory_cfg or territory_cfg.get("enabled") is not True:
        raise base.BufferAutomationError(f"Territory not enabled: {territory}")

    channel_match = territory_cfg.get("channel_match") or {}
    resolved = {}
    unresolved: list[str] = []
    for service in requested_platforms:
        aliases = list(channel_match.get(service) or [])
        channel = _match_channel(channels, service, aliases)
        if channel:
            resolved[service] = channel
        else:
            unresolved.append(service)

    if unresolved:
        visible = ", ".join(f"{c['service']}={c['name']}" for c in channels)
        if not resolved:
            raise base.BufferAutomationError(
                f"No Buffer channels matched territory {territory}. Available: {visible}"
            )
        raise base.BufferAutomationError(
            f"Partial Buffer mapping for {territory}; unresolved {', '.join(unresolved)}. Available: {visible}"
        )
    return organization_id, resolved
