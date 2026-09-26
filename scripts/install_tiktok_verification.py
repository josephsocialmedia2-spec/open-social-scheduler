#!/usr/bin/env python3
"""Install the exact TikTok URL-property signature file on main + gh-pages.

The script never invents a TikTok filename or signature. Both values must come
from the TikTok Developer Portal.
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import time
from urllib.parse import quote

import requests

API = "https://api.github.com"
PUBLIC_PREFIX = "https://josephsocialmedia2-spec.github.io/open-social-scheduler/"


def validate_filename(value: str) -> str:
    value = str(value or "").strip()
    if not value or value in {".", ".."}:
        raise SystemExit("filename is required")
    if "/" in value or "\\" in value or ".." in value:
        raise SystemExit("filename must be a single root-level file without traversal")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,180}", value):
        raise SystemExit("filename contains unsupported characters")
    return value


def gh_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_existing(repo: str, filename: str, branch: str, token: str) -> dict | None:
    url = f"{API}/repos/{repo}/contents/{quote(filename)}"
    r = requests.get(url, headers=gh_headers(token), params={"ref": branch}, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def put_file(repo: str, filename: str, content: str, branch: str, token: str) -> str:
    existing = get_existing(repo, filename, branch, token)
    payload = {
        "message": f"Install TikTok URL verification file on {branch}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if existing and existing.get("sha"):
        payload["sha"] = existing["sha"]
    url = f"{API}/repos/{repo}/contents/{quote(filename)}"
    r = requests.put(url, headers=gh_headers(token), json=payload, timeout=30)
    r.raise_for_status()
    return str((r.json().get("commit") or {}).get("sha") or "")


def wait_public(url: str, expected: str, timeout: int) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            r = requests.get(url, headers={"Cache-Control": "no-cache"}, timeout=20)
            last = f"HTTP {r.status_code}"
            if r.ok and r.text.strip() == expected.strip():
                return
        except requests.RequestException as exc:
            last = str(exc)
        time.sleep(5)
    raise SystemExit(f"GitHub Pages verification timed out: {last}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename", required=True, help="Exact filename supplied by TikTok")
    parser.add_argument("--content", required=True, help="Exact signature text supplied by TikTok")
    parser.add_argument("--repo", default="josephsocialmedia2-spec/open-social-scheduler")
    parser.add_argument("--token", default=os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"))
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    filename = validate_filename(args.filename)
    signature = str(args.content).strip()
    if not signature.startswith("tiktok-developers-site-verification="):
        raise SystemExit("content does not look like a TikTok site-verification signature")
    if not args.token:
        raise SystemExit("GH_TOKEN or GITHUB_TOKEN is required")

    main_sha = put_file(args.repo, filename, signature + "\n", "main", args.token)
    pages_sha = put_file(args.repo, filename, signature + "\n", "gh-pages", args.token)
    public_url = PUBLIC_PREFIX + quote(filename)
    wait_public(public_url, signature, args.timeout)

    print(f"main_commit={main_sha}")
    print(f"gh_pages_commit={pages_sha}")
    print(f"verified_url={public_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
