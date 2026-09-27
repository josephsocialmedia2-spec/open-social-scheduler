from __future__ import annotations

from pathlib import Path
from typing import Any

from ..locks import browser_profile_lock
from .base import BrowserPublishError, PublishResult
from .platforms import PUBLISHERS


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
    with browser_profile_lock(profile_path):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise BrowserPublishError(
                "Playwright is not installed on this runner",
                "PLAYWRIGHT_MISSING",
            ) from exc

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_path),
                headless=True,
                viewport={"width": 1440, "height": 1100},
                locale="it-IT",
                timezone_id="Europe/Rome",
                args=["--disable-dev-shm-usage"],
            )
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
