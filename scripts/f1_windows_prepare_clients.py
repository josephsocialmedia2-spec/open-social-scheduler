#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import requests

from publisher.cloud_publisher.browser.base import (
    BrowserPublishError,
    assert_manageable_target,
    verify_expected_account,
)


SUPABASE_URL = (
    os.getenv("SUPABASE_URL")
    or "https://nqnmlsmeiynxbdojeyjt.supabase.co"
).rstrip("/")
SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
BROWSER_ROOT = Path(
    os.getenv("F1_BROWSER_ROOT")
    or (
        r"C:\F1Social\BrowserProfiles"
        if os.name == "nt"
        else "/srv/f1social/browser-profiles"
    )
)


def headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    out = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        out.update(extra)
    return out


def get(table: str, params: dict[str, str]) -> list[dict]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers(),
        params=params,
        timeout=45,
    )
    r.raise_for_status()
    return r.json()


def patch(table: str, row_id: str, payload: dict) -> None:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{row_id}"},
        json=payload,
        timeout=45,
    )
    r.raise_for_status()


def api_connected(channel: dict | None) -> bool:
    return bool(
        channel
        and channel.get("enabled")
        and channel.get("verified")
        and str(channel.get("connection_status") or "").upper() == "COLLEGATO"
        and not channel.get("reauthorization_required")
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare dedicated local Chrome profiles for F1 Social clients"
    )
    parser.add_argument(
        "--client",
        default="",
        help="Optional client slug or UUID; empty means all active clients",
    )
    parser.add_argument(
        "--platform",
        default="",
        choices=["", "facebook", "instagram", "tiktok", "youtube", "linkedin-page"],
        help="Optional single social platform",
    )
    parser.add_argument(
        "--auto-wait",
        action="store_true",
        help="Poll opened social tabs until the correct accounts are available",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Seconds to wait per client in --auto-wait mode",
    )
    args = parser.parse_args()

    if not SERVICE_KEY:
        raise SystemExit(
            "SUPABASE_SERVICE_ROLE_KEY is required locally. "
            "Do not place it in GitHub files or chat messages."
        )

    from playwright.sync_api import sync_playwright

    clients = get(
        "f1_content_clients",
        {
            "select": "id,name,slug,status",
            "status": "eq.ATTIVO",
            "order": "name.asc",
        },
    )
    if args.client:
        clients = [
            item for item in clients
            if str(item.get("slug") or "") == args.client
            or str(item.get("id") or "") == args.client
        ]
        if not clients:
            raise SystemExit("Requested client not found or not active")
    channels = get(
        "f1_client_social_channels",
        {"select": "*", "limit": "1000"},
    )
    profiles = get(
        "f1_client_browser_profiles",
        {"select": "*", "limit": "1000"},
    )
    sessions = get(
        "f1_client_browser_social_sessions",
        {"select": "*", "limit": "1000"},
    )

    channel_map = {
        (str(x["client_id"]), str(x["platform"])): x
        for x in channels
    }
    profile_map = {
        str(x["client_id"]): x
        for x in profiles
    }
    session_map = {
        (str(x["client_id"]), str(x["platform"])): x
        for x in sessions
    }

    with sync_playwright() as p:
        for client in clients:
            client_id = str(client["id"])
            profile = profile_map.get(client_id)
            if not profile:
                print(
                    f"SKIP {client['name']}: browser profile row missing"
                )
                continue

            needed: list[dict] = []
            for platform in (
                "facebook",
                "instagram",
                "tiktok",
                "youtube",
                "linkedin-page",
            ):
                if args.platform and platform != args.platform:
                    continue
                channel = channel_map.get((client_id, platform))
                session = session_map.get((client_id, platform))
                if not session:
                    continue
                if api_connected(channel):
                    continue
                expected = str(
                    session.get("expected_profile_url") or ""
                ).strip()
                if not expected:
                    continue
                needed.append(session)

            if not needed:
                print(
                    f"OK   {client['name']}: "
                    "no browser fallback setup needed"
                )
                continue

            profile_path = (
                BROWSER_ROOT
                / client_id
                / "chrome-profile"
            )
            profile_path.mkdir(
                parents=True,
                exist_ok=True,
            )

            print("\n" + "=" * 72)
            print(f"CLIENTE: {client['name']}")
            print(f"PROFILO CHROME: {profile_path}")
            print("SOCIAL NON CONFIGURATI DA VERIFICARE:")
            for session in needed:
                print(
                    f" - {session['platform']}: "
                    f"{session['expected_profile_url']}"
                )

            launch_kwargs = {
                "user_data_dir": str(profile_path),
                "headless": False,
                "locale": "it-IT",
                "timezone_id": "Europe/Rome",
                "viewport": {
                    "width": 1440,
                    "height": 1000,
                },
            }
            if os.name == "nt":
                launch_kwargs["channel"] = "chrome"

            context = p.chromium.launch_persistent_context(
                **launch_kwargs
            )

            pages: list[tuple[dict, object]] = []
            try:
                for i, session in enumerate(needed):
                    page = (
                        context.pages[0]
                        if i == 0 and context.pages
                        else context.new_page()
                    )
                    page.goto(
                        str(session["expected_profile_url"]),
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                    pages.append((session, page))

                if not args.auto_wait:
                    input(
                        "\nCompleta eventuali login/2FA nelle schede "
                        "aperte. Quando tutti gli account del cliente "
                        "sono corretti, premi INVIO..."
                    )

                connected = 0
                pending = list(pages)
                last_errors: dict[str, BrowserPublishError] = {}
                deadline = time.time() + max(60, args.timeout)

                while pending:
                    next_pending: list[tuple[dict, object]] = []
                    for session, page in pending:
                        platform = str(session["platform"])
                        try:
                            actual = verify_expected_account(
                                page,
                                platform=platform,
                                expected_url=str(
                                    session["expected_profile_url"]
                                ),
                                expected_id=session.get(
                                    "expected_account_id"
                                ),
                                expected_name=(
                                    session.get(
                                        "expected_account_name"
                                    )
                                    or client["name"]
                                ),
                            )
                            assert_manageable_target(page, platform)
                            now = datetime.now(
                                timezone.utc
                            ).isoformat()
                            patch(
                                "f1_client_browser_social_sessions",
                                str(session["id"]),
                                {
                                    "status": "CONNECTED",
                                    "last_verified_at": now,
                                    "last_used_at": now,
                                    "error_code": None,
                                    "error_message": None,
                                    "metadata": {
                                        **(
                                            session.get("metadata")
                                            or {}
                                        ),
                                        "verified_account": actual,
                                        "execution_mode":
                                            "local_windows_pc",
                                    },
                                    "updated_at": now,
                                },
                            )
                            connected += 1
                            print(
                                f"OK   {client['name']} / "
                                f"{platform}"
                            )
                        except BrowserPublishError as exc:
                            last_errors[platform] = exc
                            next_pending.append((session, page))

                    pending = next_pending
                    if not pending:
                        break
                    if not args.auto_wait:
                        break
                    if time.time() >= deadline:
                        break
                    print(
                        f"ATTESA {client['name']}: "
                        f"{len(pending)} social richiedono login/verifica. "
                        "Completa le finestre Chrome aperte."
                    )
                    time.sleep(5)

                for session, _page in pending:
                    platform = str(session["platform"])
                    exc = last_errors.get(platform)
                    status = (
                        "ACCOUNT_WRONG"
                        if exc and exc.code == "ACCOUNT_WRONG"
                        else "AUTH_REQUIRED"
                    )
                    patch(
                        "f1_client_browser_social_sessions",
                        str(session["id"]),
                        {
                            "status": status,
                            "error_code": (
                                exc.code
                                if exc
                                else "AUTH_REQUIRED"
                            ),
                            "error_message": (
                                str(exc)[:1000]
                                if exc
                                else "Login or verification required"
                            ),
                            "updated_at": datetime.now(
                                timezone.utc
                            ).isoformat(),
                        },
                    )
                    print(
                        f"STOP {client['name']} / "
                        f"{platform}: {status}"
                    )

                now = datetime.now(
                    timezone.utc
                ).isoformat()
                patch(
                    "f1_client_browser_profiles",
                    str(profile["id"]),
                    {
                        "browser_host": "local-windows",
                        "profile_path":
                            f"{client_id}/chrome-profile",
                        "status":
                            "READY"
                            if connected
                            else "AUTH_REQUIRED",
                        "last_started_at": now,
                        "last_verified_at":
                            now
                            if connected
                            else None,
                        "metadata": {
                            **(
                                profile.get("metadata")
                                or {}
                            ),
                            "execution_mode":
                                "local_windows_pc",
                            "resolved_profile_path":
                                str(profile_path),
                            "connected_browser_socials":
                                connected,
                        },
                        "updated_at": now,
                    },
                )
            finally:
                context.close()

    print(
        "\nConfigurazione dei profili Chrome locali completata."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
