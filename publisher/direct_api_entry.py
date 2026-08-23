#!/usr/bin/env python3
"""Runtime compatibility layer for automatic direct social publishing.

Adds photo-safe publishing behavior without weakening queue isolation:
- Instagram publishes one static image as a normal feed post.
- LinkedIn uploads the image asset and publishes an image post.
- Missing optional platform secrets no longer block platforms that are ready.
- TikTok video publishing keeps the resilient chunked uploader.
"""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any

import requests

import direct_api_publish as core


def instagram_publish_fixed(
    job: dict[str, Any],
    client: dict[str, Any],
    paths: list[Path],
    cache: core.PublicMediaCache,
) -> dict[str, Any]:
    """Publish a single photo correctly; delegate reels/carousels to core."""
    content_format = str(job.get("format") or "photo").lower()
    if content_format == "reel" or len(paths) > 1:
        return core.instagram_publish(job, client, paths, cache)

    token = core.secret(client, "INSTAGRAM_ACCESS_TOKEN")
    ig_user_id = core.secret(client, "INSTAGRAM_USER_ID")
    url = cache.upload(paths[0], str(job["id"]), 1)
    created = core.request(
        "POST",
        f"{core.meta_graph_base()}/{ig_user_id}/media",
        params={
            "image_url": url,
            "caption": str(job.get("caption") or "")[:2200],
            "access_token": token,
        },
    ).json()
    container_id = str(created["id"])
    core.ig_wait_container(container_id, token)
    published = core.request(
        "POST",
        f"{core.meta_graph_base()}/{ig_user_id}/media_publish",
        params={"creation_id": container_id, "access_token": token},
    ).json()
    return {
        "container_id": container_id,
        "media_id": published.get("id"),
        "mode": "single-photo",
    }


def linkedin_publish_fixed(
    job: dict[str, Any],
    client: dict[str, Any],
    paths: list[Path],
    _cache: core.PublicMediaCache,
) -> dict[str, Any]:
    """Publish static posts with the LinkedIn Images API + Posts API."""
    token = core.secret(client, "LINKEDIN_ACCESS_TOKEN")
    author = core.secret(client, "LINKEDIN_AUTHOR_URN")
    version = os.getenv("LINKEDIN_VERSION", "202606").strip()
    base_headers = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": version,
        "Content-Type": "application/json",
    }

    content: dict[str, Any] | None = None
    if paths and paths[0].suffix.lower() in {".jpg", ".jpeg", ".png"}:
        initialized = core.request(
            "POST",
            "https://api.linkedin.com/rest/images?action=initializeUpload",
            headers=base_headers,
            json={"initializeUploadRequest": {"owner": author}},
        ).json()
        value = initialized.get("value") or {}
        upload_url = str(value.get("uploadUrl") or "")
        image_urn = str(value.get("image") or "")
        if not upload_url or not image_urn:
            raise core.PublishError(f"LinkedIn image init response incomplete: {initialized}")

        mime = mimetypes.guess_type(paths[0].name)[0] or "image/jpeg"
        uploaded = requests.put(
            upload_url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": mime},
            data=paths[0].read_bytes(),
            timeout=300,
        )
        if uploaded.status_code not in {200, 201, 202}:
            raise core.PublishError(
                f"LinkedIn image upload -> {uploaded.status_code}: {uploaded.text[:1000]}"
            )
        content = {
            "media": {
                "id": image_urn,
                "altText": str(job.get("title") or job.get("client_name") or "")[:120],
            }
        }

    payload: dict[str, Any] = {
        "author": author,
        "commentary": str(job.get("caption") or "")[:3000],
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if content:
        payload["content"] = content

    response = core.request(
        "POST",
        "https://api.linkedin.com/rest/posts",
        headers=base_headers,
        json=payload,
    )
    return {
        "post_id": response.headers.get("x-restli-id", ""),
        "mode": "image" if content else "text",
    }


def tiktok_publish_fixed(
    job: dict[str, Any],
    client: dict[str, Any],
    paths: list[Path],
    _cache: core.PublicMediaCache,
) -> dict[str, Any]:
    """Keep the proven chunked video uploader for future video jobs."""
    if str(job.get("format") or "photo") != "reel":
        raise core.PublishError(
            "TikTok photo publishing requires a verified public media URL; photo jobs are excluded until configured"
        )

    token = core.secret(client, "TIKTOK_ACCESS_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
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


def publish_job_resilient(
    job: dict[str, Any], only: set[str] | None, dry_run: bool
) -> tuple[list[dict[str, Any]], bool]:
    """Publish every platform that is configured, even when optional ones lack secrets."""
    client = core.client_config(str(job["client_id"]))
    paths = core.media_paths(job)
    platforms = core.remaining_platforms(job, only)
    results: list[dict[str, Any]] = []
    if not platforms:
        return results, True

    runnable: list[str] = []
    for platform in platforms:
        missing = core.required_secrets(platform, client)
        if missing:
            results.append({"platform": platform, "status": "blocked", "missing": missing})
        else:
            runnable.append(platform)

    if dry_run:
        for platform in runnable:
            results.append({"platform": platform, "status": "ready"})
        return results, True

    cache = core.PublicMediaCache()
    success = True
    try:
        for platform in runnable:
            publisher = core.PUBLISHERS.get(platform)
            if not publisher:
                results.append({"platform": platform, "status": "unsupported"})
                success = False
                continue
            try:
                payload = publisher(job, client, paths, cache)
                results.append({"platform": platform, "status": "published", "result": payload})
                published = set(str(x) for x in job.get("published_platforms", []))
                published.add(platform)
                job["published_platforms"] = sorted(published)
            except Exception as exc:
                results.append({"platform": platform, "status": "error", "error": str(exc)})
                success = False
    finally:
        cache.cleanup()

    expected = set(core.job_platforms(job))
    done = set(str(x) for x in job.get("published_platforms", []))
    if expected and expected.issubset(done):
        job["status"] = "published"
        job.pop("blocked_reason", None)
    elif done:
        job["status"] = "partially_published"
    return results, success


def main() -> int:
    os.environ.setdefault("LINKEDIN_VERSION", "202606")
    os.environ.setdefault("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY")
    core.PUBLISHERS["instagram"] = instagram_publish_fixed
    core.PUBLISHERS["linkedin"] = linkedin_publish_fixed
    core.PUBLISHERS["linkedin-page"] = linkedin_publish_fixed
    core.PUBLISHERS["tiktok"] = tiktok_publish_fixed
    core.publish_job = publish_job_resilient
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
