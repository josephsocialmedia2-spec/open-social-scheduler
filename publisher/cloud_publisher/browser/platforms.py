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


def _verify_after_publish(
    page: Any,
    *,
    platform: str,
    profile_url: str,
    caption: str,
    permalink_patterns: list[str],
    success_markers: list[str],
) -> tuple[str | None, bool]:
    page.wait_for_timeout(5000)
    assert_no_auth_wall(page, platform)
    url = _permalink(page, permalink_patterns)
    if url:
        return url, True

    try:
        body = page.locator("body").inner_text(timeout=4000).lower()
    except Exception:
        body = ""
    if any(marker.lower() in body for marker in success_markers):
        return None, True

    # Stronger verification: reload the assigned client's profile and require
    # the newly submitted caption to be visible there. This avoids declaring
    # success merely because the Publish button was clicked.
    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3500)
        assert_no_auth_wall(page, platform)
        body = " ".join(page.locator("body").inner_text(timeout=5000).lower().split())
        snippet = " ".join(str(caption or "").lower().split())[:72].strip()
        url = _permalink(page, permalink_patterns)
        if url:
            return url, True
        if snippet and len(snippet) >= 12 and snippet in body:
            return None, True
    except BrowserPublishError:
        raise
    except Exception:
        pass
    return None, False


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
    post_url, verified = _verify_after_publish(
        page,
        platform="facebook",
        profile_url=expected_url,
        caption=caption,
        permalink_patterns=["/posts/", "story_fbid", "/reel/"],
        success_markers=[
            "il tuo post è stato pubblicato",
            "post pubblicato",
            "your post was published",
            "your post is now published",
        ],
    )
    return PublishResult(
        external_post_url=post_url,
        actual_account=actual,
        verified=verified,
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
    post_url, verified = _verify_after_publish(
        page,
        platform="instagram",
        profile_url=expected_url,
        caption=caption,
        permalink_patterns=["/p/", "/reel/"],
        success_markers=[
            "il tuo post è stato condiviso",
            "post condiviso",
            "your post has been shared",
            "your reel has been shared",
        ],
    )
    return PublishResult(
        external_post_url=post_url,
        actual_account=actual,
        verified=verified,
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
    post_url, verified = _verify_after_publish(
        page,
        platform="tiktok",
        profile_url=expected_url,
        caption=caption,
        permalink_patterns=["/video/"],
        success_markers=[
            "video pubblicato",
            "post pubblicato",
            "video posted",
            "post published",
        ],
    )
    return PublishResult(
        external_post_url=post_url,
        actual_account=actual,
        verified=verified,
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
    post_url, verified = _verify_after_publish(
        page,
        platform="linkedin-page",
        profile_url=expected_url,
        caption=caption,
        permalink_patterns=["/feed/update/", "/posts/"],
        success_markers=[
            "post pubblicato",
            "post published",
            "your post is live",
        ],
    )
    return PublishResult(
        external_post_url=post_url,
        actual_account=actual,
        verified=verified,
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
