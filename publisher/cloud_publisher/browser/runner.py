from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..locks import browser_profile_lock
from .base import BrowserPublishError, PublishResult
from .platforms import PUBLISHERS


def _bool_env(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def publish_with_profile(
    *,
    profile_path: Path,
    platform: str,
    expected_url: str,
    expected_id: str | None,
    expected_name: str | None,
    caption: str,
    files: list[Path],
    dry_run: bool,
    metadata: dict[str, Any],
) -> PublishResult:
    if platform not in PUBLISHERS:
        raise BrowserPublishError(
            f"Unsupported browser platform: {platform}",
            "UNSUPPORTED_PLATFORM",
        )

    profile_path.mkdir(parents=True, exist_ok=True)
    channel = (os.getenv("F1_BROWSER_CHANNEL") or "").strip() or (
        "chrome" if os.name == "nt" else ""
    )
    headless = _bool_env("F1_BROWSER_HEADLESS", True)

    with browser_profile_lock(profile_path):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise BrowserPublishError(
                "Playwright is not installed on this runner",
                "PLAYWRIGHT_MISSING",
            ) from exc

        with sync_playwright() as p:
            launch_kwargs: dict[str, Any] = {
                "user_data_dir": str(profile_path),
                "headless": headless,
                "viewport": {"width": 1440, "height": 1100},
                "locale": "it-IT",
                "timezone_id": "Europe/Rome",
            }
            if channel:
                launch_kwargs["channel"] = channel

            try:
                context = p.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as exc:
                raise BrowserPublishError(
                    f"Unable to open dedicated Chrome profile: {exc}",
                    "BROWSER_PROFILE_OPEN_FAILED",
                ) from exc

            try:
                page = context.pages[0] if context.pages else context.new_page()
                kwargs = dict(
                    page=page,
                    expected_url=expected_url,
                    expected_id=expected_id,
                    expected_name=expected_name,
                    caption=caption,
                    files=files,
                    dry_run=dry_run,
                )
                if platform == "youtube":
                    kwargs["title"] = str(
                        metadata.get("content_title")
                        or "F1 Social"
                    )
                return PUBLISHERS[platform](**kwargs)
            finally:
                context.close()
