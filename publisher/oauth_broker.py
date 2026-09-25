#!/usr/bin/env python3
"""Internal client for the F1 Social OAuth broker.

The broker is deliberately opt-in. Existing Buffer/direct GitHub-Secret
connections keep working until F1_OAUTH_BROKER_ENABLED=true is configured.
"""
from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_BROKER_URL = (
    "https://nqnmlsmeiynxbdojeyjt.supabase.co/functions/v1/f1-social-oauth"
)


class BrokerError(RuntimeError):
    def __init__(self, message: str, *, auth_required: bool = False) -> None:
        super().__init__(message)
        self.auth_required = auth_required


def enabled() -> bool:
    flag = os.getenv("F1_OAUTH_BROKER_ENABLED", "").strip().lower()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    return flag in {"1", "true", "yes", "on"} and bool(service_key)


def broker_url() -> str:
    return os.getenv("F1_OAUTH_BROKER_URL", DEFAULT_BROKER_URL).rstrip("/")


def token(client: dict[str, Any], platform: str, timeout: int = 30) -> dict[str, Any]:
    if not enabled():
        raise BrokerError("OAuth broker disabled")

    client_ref = str(
        client.get("id")
        or client.get("slug")
        or client.get("client_id")
        or ""
    ).strip()
    if not client_ref:
        raise BrokerError("Client configuration has no id/slug")

    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    response = requests.get(
        f"{broker_url()}/token",
        params={"client": client_ref, "platform": platform},
        headers={
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
            "Accept": "application/json",
        },
        timeout=timeout,
    )

    try:
        payload = response.json()
    except Exception as exc:
        raise BrokerError(
            f"OAuth broker returned invalid JSON ({response.status_code})"
        ) from exc

    if response.status_code == 409 and payload.get("error") == "AUTH_REQUIRED":
        raise BrokerError("OAuth authorization required", auth_required=True)
    if not response.ok:
        raise BrokerError(
            f"OAuth broker {response.status_code}: "
            f"{str(payload.get('detail') or payload.get('error') or payload)[:700]}"
        )

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise BrokerError("OAuth broker response has no access token")
    return payload
