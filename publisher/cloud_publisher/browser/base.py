from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse


class BrowserPublishError(RuntimeError):
    def __init__(
        self,
        message: str,
        code: str = "BROWSER_ERROR",
        *,
        auth_required: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.auth_required = auth_required


@dataclass
class PublishResult:
    external_post_id: str | None = None
    external_post_url: str | None = None
    actual_account: str | None = None
    verified: bool = False


def expected_handle(platform: str, profile_url: str | None) -> str:
    if not profile_url:
        return ""
    try:
        u = urlparse(profile_url)
        parts = [p for p in u.path.split("/") if p]
        if platform == "facebook" and u.path.lower().endswith("profile.php"):
            return (parse_qs(u.query).get("id") or [""])[0]
        if platform == "youtube" and parts and parts[0].lower() == "channel" and len(parts) > 1:
            return parts[1].lower()
        return (parts[0] if parts else "").lstrip("@").lower()
    except Exception:
        return ""


def assert_no_auth_wall(page: Any, platform: str) -> None:
    url = page.url.lower()
    text = ""
    try:
        text = page.locator("body").inner_text(timeout=3000).lower()[:10000]
    except Exception:
        pass
    markers = {
        "facebook": ["login", "checkpoint", "two-factor", "security check", "accedi"],
        "instagram": ["accounts/login", "challenge", "accedi", "log in"],
        "tiktok": ["/login", "verification", "log in", "accedi"],
        "linkedin-page": ["/login", "/checkpoint", "sign in", "accedi"],
        "youtube": ["accounts.google.com", "signin", "verify it's you", "accedi"],
    }.get(platform, [])
    if any(m in url or m in text for m in markers):
        raise BrowserPublishError(
            "Browser session requires authentication or security verification",
            "AUTH_REQUIRED",
            auth_required=True,
        )


def verify_expected_account(
    page: Any,
    *,
    platform: str,
    expected_url: str | None,
    expected_id: str | None,
    expected_name: str | None,
) -> str:
    assert_no_auth_wall(page, platform)
    current = page.url
    try:
        title = page.title().lower()
    except Exception:
        title = ""
    try:
        body = page.locator("body").inner_text(timeout=5000).lower()[:20000]
    except Exception:
        body = ""
    hay = f"{current.lower()}\n{title}\n{body}"
    handle = expected_handle(platform, expected_url)
    id_ok = bool(expected_id and str(expected_id).lower() in hay)
    handle_ok = bool(handle and handle in hay)
    name_ok = bool(expected_name and str(expected_name).strip().lower() in hay)
    strong_expected = bool(expected_id or handle)
    strong_ok = id_ok or handle_ok
    if expected_url and ((strong_expected and not strong_ok) or (not strong_expected and not name_ok)):
        raise BrowserPublishError(
            "Opened social account does not match the client account guard",
            "ACCOUNT_WRONG",
        )
    return expected_name or expected_id or handle or current


def first_visible(
    page: Any,
    selectors: list[tuple[str, str]],
    timeout_ms: int = 5000,
):
    for kind, value in selectors:
        try:
            if kind == "role_button":
                loc = page.get_by_role("button", name=re.compile(value, re.I)).first
            elif kind == "role_link":
                loc = page.get_by_role("link", name=re.compile(value, re.I)).first
            elif kind == "text":
                loc = page.get_by_text(re.compile(value, re.I)).first
            else:
                loc = page.locator(value).first
            loc.wait_for(state="visible", timeout=timeout_ms)
            return loc
        except Exception:
            continue
    return None
