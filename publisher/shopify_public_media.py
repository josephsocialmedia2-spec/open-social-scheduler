#!/usr/bin/env python3
"""Extract reusable public media from Shopify storefront pages.

This module only reads assets already exposed by a public storefront. It does not
access Shopify Admin, private files or customer data. It is intended for brands
that own or are authorised to reuse the storefront media in their social content.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass, asdict
from urllib.parse import urljoin

import requests

UA = "RealMediaPro-ContentEngine/1.0"
IMAGE_RE = re.compile(r"https?://[^\"'<>\s]+(?:cdn\.shopify\.com|shopifycdn\.net)[^\"'<>\s]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\"'<>\s]*)?", re.I)
VIDEO_RE = re.compile(r"https?://[^\"'<>\s]+(?:cdn\.shopify\.com|shopifycdn\.net)[^\"'<>\s]+?\.(?:mp4|webm|mov)(?:\?[^\"'<>\s]*)?", re.I)
META_RE = re.compile(r'<meta[^>]+(?:property|name)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']+)["\']', re.I)
SOURCE_RE = re.compile(r'<(?:source|video|img)[^>]+(?:src|poster)=["\']([^"\']+)["\']', re.I)


@dataclass
class StorefrontMedia:
    page_url: str
    title: str
    images: list[str]
    videos: list[str]


def uniq(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = html.unescape(raw).replace("\\u0026", "&")
        if value.startswith("//"):
            value = "https:" + value
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def extract(url: str) -> StorefrontMedia:
    response = requests.get(url, headers={"User-Agent": UA}, timeout=45)
    response.raise_for_status()
    body = response.text
    title_match = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    title = re.sub(r"\s+", " ", html.unescape(title_match.group(1))).strip() if title_match else url
    images = list(IMAGE_RE.findall(body))
    videos = list(VIDEO_RE.findall(body))
    for key, value in META_RE.findall(body):
        key = key.lower()
        value = urljoin(url, html.unescape(value))
        if key in {"og:image", "twitter:image", "twitter:image:src"}:
            images.append(value)
        elif key in {"og:video", "og:video:url", "og:video:secure_url"}:
            videos.append(value)
    for value in SOURCE_RE.findall(body):
        value = urljoin(url, html.unescape(value))
        low = value.lower().split("?", 1)[0]
        if low.endswith((".jpg", ".jpeg", ".png", ".webp")):
            images.append(value)
        elif low.endswith((".mp4", ".webm", ".mov")):
            videos.append(value)
    return StorefrontMedia(page_url=url, title=title, images=uniq(images), videos=uniq(videos))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="+")
    parser.add_argument("--output")
    args = parser.parse_args()
    rows = [asdict(extract(url)) for url in args.url]
    payload = json.dumps({"pages": rows}, ensure_ascii=False, indent=2)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
