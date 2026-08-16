#!/usr/bin/env python3
"""Runtime compatibility layer for direct social publishing.

Keeps platform-specific hotfixes small and testable without weakening the queue
approval logic in direct_api_publish.py.
"""
from __future__ import annotations

import mimetypes
import os
from typing import Any

import requests

import direct_api_publish as core


def tiktok_publish_fixed(job: dict[str, Any], client: dict[str, Any], paths, _cache) -> dict[str, Any]:
    if str(job.get("format") or "reel") != "reel":
        raise core.PublishError("TikTok direct publisher currently accepts reel/video jobs only")

    token = core.secret(client, "TIKTOK_ACCESS_TOKEN")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    creator = core.request(
        "POST",
        "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
        headers=headers,
        json={},
    ).json()
    if creator.get("error", {}).get("code") != "ok":
        raise core.PublishError(f"TikTok creator info error: {creator}")

    options = creator.get("data", {}).get("privacy_level_options") or ["SELF_ONLY"]
    preferred = os.getenv("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY").strip()
    privacy = preferred if preferred in options else options[0]

    path = paths[0]
    size = path.stat().st_size
    min_chunk = 5 * 1024 * 1024
    max_chunk = 64 * 1024 * 1024

    if size <= max_chunk:
        chunk_size = size
        total_chunks = 1
    else:
        chunk_size = max_chunk
        total_chunks = size // chunk_size
        remainder = size - total_chunks * chunk_size
        if 0 < remainder < min_chunk:
            total_chunks -= 1
        total_chunks = max(1, total_chunks)

    init = core.request(
        "POST",
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {
                "title": str(job.get("caption") or "")[:2200],
                "privacy_level": privacy,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
                "brand_organic_toggle": True,
                "is_aigc": bool(job.get("video_made_with_ai", False)),
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        },
    ).json()
    if init.get("error", {}).get("code") != "ok":
        raise core.PublishError(f"TikTok init error: {init}")

    upload_url = str(init["data"]["upload_url"])
    publish_id = str(init["data"]["publish_id"])

    with path.open("rb") as fh:
        start = 0
        for chunk_index in range(total_chunks):
            is_last = chunk_index == total_chunks - 1
            read_size = size - start if is_last else chunk_size
            body = fh.read(read_size)
            if not body:
                raise core.PublishError(
                    f"TikTok upload ended early at chunk {chunk_index + 1}/{total_chunks}"
                )
            end = start + len(body) - 1
            response = requests.put(
                upload_url,
                headers={
                    "Content-Type": mimetypes.guess_type(path.name)[0] or "video/mp4",
                    "Content-Length": str(len(body)),
                    "Content-Range": f"bytes {start}-{end}/{size}",
                },
                data=body,
                timeout=300,
            )
            if response.status_code not in {200, 201, 206}:
                raise core.PublishError(
                    f"TikTok binary upload -> {response.status_code}: {response.text[:1000]}"
                )
            start = end + 1

        if start != size:
            raise core.PublishError(f"TikTok upload byte mismatch: sent {start} of {size}")

    return {"publish_id": publish_id, "privacy_level": privacy}


def main() -> int:
    os.environ.setdefault("LINKEDIN_VERSION", "202604")
    os.environ.setdefault("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY")
    core.PUBLISHERS["tiktok"] = tiktok_publish_fixed
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
