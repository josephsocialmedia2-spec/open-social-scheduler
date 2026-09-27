#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import requests


def headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def get(
    url: str,
    key: str,
    table: str,
    params: dict[str, str],
):
    r = requests.get(
        f"{url}/rest/v1/{table}",
        headers=headers(key),
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def patch(
    url: str,
    key: str,
    table: str,
    row_id: str,
    payload: dict,
):
    r = requests.patch(
        f"{url}/rest/v1/{table}",
        headers={
            **headers(key),
            "Prefer": "return=minimal",
        },
        params={"id": f"eq.{row_id}"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-time interactive login for one F1 Social client browser profile"
    )
    parser.add_argument(
        "client",
        help="client slug or UUID",
    )
    parser.add_argument(
        "platform",
        choices=[
            "facebook",
            "instagram",
            "tiktok",
            "youtube",
            "linkedin-page",
        ],
    )
    args = parser.parse_args()

    url = (
        os.getenv("SUPABASE_URL")
        or "https://nqnmlsmeiynxbdojeyjt.supabase.co"
    ).rstrip("/")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    ).strip()
    if not key:
        raise SystemExit(
            "SUPABASE_SERVICE_ROLE_KEY is required on the VPS"
        )

    is_uuid = (
        len(args.client) > 30
        and "-" in args.client
    )
    client_filter = {
        "id" if is_uuid else "slug": f"eq.{args.client}",
        "select": "id,owner_id,name,slug",
        "limit": "1",
    }
    clients = get(
        url,
        key,
        "f1_content_clients",
        client_filter,
    )
    if not clients:
        raise SystemExit("Client not found")

    client = clients[0]
    profiles = get(
        url,
        key,
        "f1_client_browser_profiles",
        {
            "client_id": f"eq.{client['id']}",
            "select": "*",
            "limit": "1",
        },
    )
    sessions = get(
        url,
        key,
        "f1_client_browser_social_sessions",
        {
            "client_id": f"eq.{client['id']}",
            "platform": f"eq.{args.platform}",
            "select": "*",
            "limit": "1",
        },
    )
    if not profiles or not sessions:
        raise SystemExit(
            "Browser profile/session rows are missing"
        )

    profile = profiles[0]
    session = sessions[0]
    expected = session.get("expected_profile_url")
    if not expected:
        raise SystemExit(
            "Expected profile URL is missing in F1 Social"
        )

    from playwright.sync_api import sync_playwright

    profile_path = Path(profile["profile_path"])
    profile_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(profile_path),
            headless=False,
            locale="it-IT",
            timezone_id="Europe/Rome",
        )
        page = (
            context.pages[0]
            if context.pages
            else context.new_page()
        )
        page.goto(
            expected,
            wait_until="domcontentloaded",
            timeout=60000,
        )
        print(
            f"\nCLIENTE: {client['name']}"
            f"\nSOCIAL: {args.platform}"
            f"\nATTESO: {expected}"
        )
        print(
            "Completa manualmente login/2FA nel browser remoto. "
            "Non inserire password in terminale o repository."
        )
        input(
            "Quando l'account corretto è aperto, premi INVIO "
            "qui per registrare la sessione come CONNECTED..."
        )

        now = datetime.now(
            timezone.utc
        ).isoformat()
        patch(
            url,
            key,
            "f1_client_browser_profiles",
            profile["id"],
            {
                "status": "READY",
                "last_started_at": now,
                "last_verified_at": now,
                "updated_at": now,
            },
        )
        patch(
            url,
            key,
            "f1_client_browser_social_sessions",
            session["id"],
            {
                "status": "CONNECTED",
                "last_verified_at": now,
                "last_used_at": now,
                "error_code": None,
                "error_message": None,
                "updated_at": now,
            },
        )
        context.close()

    print(
        "Sessione cloud registrata come CONNECTED."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
