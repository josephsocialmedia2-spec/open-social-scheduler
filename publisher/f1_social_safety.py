#!/usr/bin/env python3
"""Fail-closed safety checks for isolated F1 Social publishing."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class SecurityError(RuntimeError):
    pass


def _platform(value: str) -> str:
    p = str(value or "").strip().lower()
    return "linkedin" if p == "linkedin-page" else p


def _exclusive(client: dict[str, Any]) -> bool:
    return bool((client.get("safety") or {}).get("exclusive_account_whitelist"))


def _auth_record(client: dict[str, Any], platform: str) -> dict[str, Any] | None:
    return (client.get("authorized_accounts") or {}).get(_platform(platform))


def _norm_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        u = urlparse(raw)
        host = (u.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = (u.path or "").rstrip("/").lower()
        return host + path
    except Exception:
        return raw.rstrip("/").lower()


def _handle_from_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        p = [x for x in urlparse(raw).path.split("/") if x]
        if not p:
            return ""
        if p[0].lower() == "channel" and len(p) > 1:
            return p[1]
        return p[0].lstrip("@").lower()
    except Exception:
        return ""


def required_scope(platform: str) -> str:
    return {
        "facebook": "pages_manage_posts",
        "instagram": "instagram_content_publish",
        "tiktok": "video.publish",
        "youtube": "https://www.googleapis.com/auth/youtube.upload",
        "linkedin": "w_member_social",
    }.get(_platform(platform), "")


def assert_platform_authorized(client: dict[str, Any], platform: str) -> None:
    if not _exclusive(client):
        return
    record = _auth_record(client, platform)
    if not record or not bool(record.get("authorized")):
        raise SecurityError(f"ACCOUNT_NON_AUTORIZZATO:{_platform(platform)}")


def assert_broker_account(client: dict[str, Any], platform: str, payload: dict[str, Any]) -> None:
    if not _exclusive(client):
        return
    p = _platform(platform)
    assert_platform_authorized(client, p)
    record = _auth_record(client, p) or {}

    if payload.get("account_shared") is not False:
        raise SecurityError(f"ACCOUNT_CONDIVISO:{p}")

    scopes = {str(x) for x in (payload.get("scopes") or [])}
    scope = required_scope(p)
    if scope and scope not in scopes:
        raise SecurityError(f"AUTH_REQUIRED_SCOPE:{p}:{scope}")

    expected_url = str(record.get("url") or "")
    expected_handle = str(record.get("handle") or "").lstrip("@").lower()
    expected_channel = str(record.get("channel_id") or "")

    actual_url = str(payload.get("profile_url") or "")
    actual_handle = str(payload.get("creator_username") or payload.get("username") or "").lstrip("@").lower()
    actual_id = str(payload.get("account_id") or "")

    matched = False
    if expected_url and actual_url and _norm_url(expected_url) == _norm_url(actual_url):
        matched = True
    if expected_handle and actual_handle and expected_handle == actual_handle:
        matched = True
    if expected_channel and actual_id and expected_channel == actual_id:
        matched = True
    if expected_url and p == "youtube" and actual_id and _handle_from_url(expected_url) == actual_id:
        matched = True

    if not matched:
        raise SecurityError(f"BLOCKED_ACCOUNT_OWNERSHIP_MISMATCH:{p}")


def assert_job_safety(
    client: dict[str, Any],
    job: dict[str, Any],
    paths: list[Path],
    platforms: list[str],
) -> None:
    if not _exclusive(client):
        return
    if str(client.get("id") or "") != "f1-social" or str(job.get("client_id") or "") != "f1-social":
        raise SecurityError("BLOCKED_TENANT_OWNERSHIP_MISMATCH")
    if bool((client.get("safety") or {}).get("allow_client_accounts")):
        raise SecurityError("INVALID_F1_SOCIAL_SAFETY_CONFIG")

    provider = str(job.get("provider") or "").strip().lower()
    broker_platforms = {"facebook", "instagram", "tiktok", "youtube", "linkedin", "linkedin-page"}
    if any(_platform(p) in {_platform(x) for x in broker_platforms} for p in platforms) and provider != "oauth_broker":
        raise SecurityError("F1_SOCIAL_REQUIRES_OAUTH_BROKER")

    for platform in platforms:
        assert_platform_authorized(client, platform)

    if not paths:
        raise SecurityError("MEDIA_MISSING")
    expected_hash = str(job.get("expected_media_sha256") or "").strip().lower()
    if expected_hash:
        actual = hashlib.sha256(paths[0].read_bytes()).hexdigest().lower()
        if actual != expected_hash:
            raise SecurityError("MEDIA_DIVERSO_DALL_ORIGINALE")
