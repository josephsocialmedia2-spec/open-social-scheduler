from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import (
    BrowserPublishError,
    PublishResult,
    assert_no_auth_wall,
    first_visible,
    verify_expected_account,
)


def _set_files(page: Any, files: list[Path]) -> None:
    if not files:
        return
    inputs = page.locator('input[type="file"]')
    if inputs.count() == 0:
        raise BrowserPublishError(
            "No file upload control found",
            "UPLOAD_CONTROL_NOT_FOUND",
        )
    inputs.first.set_input_files([str(p) for p in files])


def _fill_caption(page: Any, caption: str) -> None:
    if not caption:
        return
    candidates = [
        page.get_by_role("textbox").last,
        page.locator("textarea").last,
        page.locator('[contenteditable="true"]').last,
    ]
    for loc in candidates:
        try:
            loc.wait_for(state="visible", timeout=4000)
            loc.click()
            try:
                loc.fill(caption)
            except Exception:
                loc.press("Control+A")
                loc.type(caption, delay=1)
            return
        except Exception:
            continue
    raise BrowserPublishError(
        "Caption editor not found",
        "CAPTION_EDITOR_NOT_FOUND",
    )


def _permalink(page: Any, patterns: list[str]) -> str | None:
    for pat in patterns:
        try:
            links = page.locator(f'a[href*="{pat}"]')
            if links.count():
                href = links.first.get_attribute("href")
                if href:
                    if href.startswith("http"):
                        return href
                    origin = "/".join(page.url.split("/")[:3])
                    return origin + href
        except Exception:
            pass
    return None


def publish_facebook(
    page: Any,
    *,
    expected_url: str,
    expected_id: str | None,
    expected_name: str | None,
    caption: str,
    files: list[Path],
    dry_run: bool,
) -> PublishResult:
    page.goto(expected_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    actual = verify_expected_account(
        page,
        platform="facebook",
        expected_url=expected_url,
        expected_id=expected_id,
        expected_name=expected_name,
    )
    trigger = first_visible(
        page,
        [
            ("role_button", r"Crea.*post|Create.*post|A cosa stai pensando|What's on your mind"),
            ("text", r"Crea.*post|A cosa stai pensando"),
        ],
        7000,
    )
    if not trigger:
        raise BrowserPublishError(
            "Facebook post composer not found",
            "COMPOSER_NOT_FOUND",
        )
    trigger.click()
    page.wait_for_timeout(1500)
    if files:
        _set_files(page, files)
        page.wait_for_timeout(2500)
    _fill_caption(page, caption)
    if dry_run:
        return PublishResult(actual_account=actual)
    button = first_visible(
        page,
        [("role_button", r"^Pubblica$|^Post$")],
        8000,
    )
    if not button:
        raise BrowserPublishError(
            "Facebook publish button not found",
            "PUBLISH_BUTTON_NOT_FOUND",
        )
    button.click()
    page.wait_for_timeout(5000)
    assert_no_auth_wall(page, "facebook")
    return PublishResult(
        external_post_url=_permalink(
            page,
            ["/posts/", "story_fbid", "/reel/"],
        ),
        actual_account=actual,
    )


def publish_instagram(
    page: Any,
    *,
    expected_url: str,
    expected_id: str | None,
    expected_name: str | None,
    caption: str,
    files: list[Path],
    dry_run: bool,
) -> PublishResult:
    page.goto(expected_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    actual = verify_expected_account(
        page,
        platform="instagram",
        expected_url=expected_url,
        expected_id=expected_id,
        expected_name=expected_name,
    )
    create = first_visible(
        page,
        [
            ("role_link", r"Crea|Create"),
            ("role_button", r"Crea|Create"),
        ],
        7000,
    )
    if not create:
        raise BrowserPublishError(
            "Instagram create control not found",
            "COMPOSER_NOT_FOUND",
        )
    create.click()
    page.wait_for_timeout(1200)
    _set_files(page, files)
    for _ in range(2):
        nxt = first_visible(
            page,
            [("role_button", r"Avanti|Next")],
            3000,
        )
        if nxt:
            nxt.click()
            page.wait_for_timeout(800)
    _fill_caption(page, caption)
    if dry_run:
        return PublishResult(actual_account=actual)
    share = first_visible(
        page,
        [("role_button", r"Condividi|Share")],
        6000,
    )
    if not share:
        raise BrowserPublishError(
            "Instagram share button not found",
            "PUBLISH_BUTTON_NOT_FOUND",
        )
    share.click()
    page.wait_for_timeout(5000)
    assert_no_auth_wall(page, "instagram")
    return PublishResult(
        external_post_url=_permalink(page, ["/p/", "/reel/"]),
        actual_account=actual,
    )


def publish_tiktok(
    page: Any,
    *,
    expected_url: str,
    expected_id: str | None,
    expected_name: str | None,
    caption: str,
    files: list[Path],
    dry_run: bool,
) -> PublishResult:
    page.goto(expected_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1800)
    actual = verify_expected_account(
        page,
        platform="tiktok",
        expected_url=expected_url,
        expected_id=expected_id,
        expected_name=expected_name,
    )
    page.goto(
        "https://www.tiktok.com/tiktokstudio/upload",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_timeout(1800)
    assert_no_auth_wall(page, "tiktok")
    if len(files) != 1:
        raise BrowserPublishError(
            "TikTok browser fallback requires exactly one media file",
            "INVALID_MEDIA_COUNT",
        )
    _set_files(page, files)
    page.wait_for_timeout(2500)
    _fill_caption(page, caption)
    if dry_run:
        return PublishResult(actual_account=actual)
    post = first_visible(
        page,
        [("role_button", r"^Pubblica$|^Post$")],
        8000,
    )
    if not post:
        raise BrowserPublishError(
            "TikTok publish button not found",
            "PUBLISH_BUTTON_NOT_FOUND",
        )
    post.click()
    page.wait_for_timeout(5000)
    assert_no_auth_wall(page, "tiktok")
    return PublishResult(
        external_post_url=_permalink(page, ["/video/"]),
        actual_account=actual,
    )


def publish_linkedin(
    page: Any,
    *,
    expected_url: str,
    expected_id: str | None,
    expected_name: str | None,
    caption: str,
    files: list[Path],
    dry_run: bool,
) -> PublishResult:
    page.goto(expected_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1800)
    actual = verify_expected_account(
        page,
        platform="linkedin-page",
        expected_url=expected_url,
        expected_id=expected_id,
        expected_name=expected_name,
    )
    start = first_visible(
        page,
        [("role_button", r"Avvia un post|Start a post")],
        7000,
    )
    if not start:
        page.goto(
            "https://www.linkedin.com/feed/",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        start = first_visible(
            page,
            [("role_button", r"Avvia un post|Start a post")],
            7000,
        )
    if not start:
        raise BrowserPublishError(
            "LinkedIn post composer not found",
            "COMPOSER_NOT_FOUND",
        )
    start.click()
    page.wait_for_timeout(1000)
    _fill_caption(page, caption)
    if files:
        media_btn = first_visible(
            page,
            [("role_button", r"Media|Foto|Photo|Video")],
            3000,
        )
        if media_btn:
            media_btn.click()
            page.wait_for_timeout(500)
        _set_files(page, files)
    if dry_run:
        return PublishResult(actual_account=actual)
    post = first_visible(
        page,
        [("role_button", r"^Pubblica$|^Post$")],
        7000,
    )
    if not post:
        raise BrowserPublishError(
            "LinkedIn publish button not found",
            "PUBLISH_BUTTON_NOT_FOUND",
        )
    post.click()
    page.wait_for_timeout(4500)
    assert_no_auth_wall(page, "linkedin-page")
    return PublishResult(
        external_post_url=_permalink(
            page,
            ["/feed/update/", "/posts/"],
        ),
        actual_account=actual,
    )


def publish_youtube(
    page: Any,
    *,
    expected_url: str,
    expected_id: str | None,
    expected_name: str | None,
    caption: str,
    files: list[Path],
    dry_run: bool,
    title: str = "F1 Social",
) -> PublishResult:
    if len(files) != 1:
        raise BrowserPublishError(
            "YouTube browser fallback requires exactly one video file",
            "INVALID_MEDIA_COUNT",
        )
    page.goto(
        "https://studio.youtube.com/",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_timeout(2200)
    assert_no_auth_wall(page, "youtube")
    actual = verify_expected_account(
        page,
        platform="youtube",
        expected_url=None,
        expected_id=expected_id,
        expected_name=expected_name,
    )
    create = first_visible(
        page,
        [("role_button", r"Crea|Create")],
        6000,
    )
    if create:
        create.click()
        page.wait_for_timeout(600)
        upload = first_visible(
            page,
            [("text", r"Carica video|Upload videos")],
            4000,
        )
        if upload:
            upload.click()
            page.wait_for_timeout(700)
    _set_files(page, files)
    page.wait_for_timeout(2200)
    textboxes = page.get_by_role("textbox")
    if textboxes.count() > 0:
        try:
            textboxes.nth(0).fill(title[:100])
        except Exception:
            pass
    if textboxes.count() > 1:
        try:
            textboxes.nth(1).fill(caption[:5000])
        except Exception:
            pass
    if dry_run:
        return PublishResult(actual_account=actual)
    raise BrowserPublishError(
        "YouTube upload reached metadata stage; audience/visibility require configured browser metadata",
        "AUTH_REQUIRED",
        auth_required=True,
    )


PUBLISHERS = {
    "facebook": publish_facebook,
    "instagram": publish_instagram,
    "tiktok": publish_tiktok,
    "linkedin-page": publish_linkedin,
    "youtube": publish_youtube,
}
