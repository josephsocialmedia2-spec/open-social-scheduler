#!/usr/bin/env python3
"""Publish approval-gated social jobs through official platform APIs.

The queue remains the source of truth. This publisher never bypasses approval:
it only considers jobs whose queue status is ``ready`` or ``partially_published``.
GitHub Actions secrets are namespaced per client through ``secret_prefix``.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import oauth_broker

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"
CLIENT_DIR = ROOT / "publisher" / "clients"
HTTP_TIMEOUT = 90
CACHE_RELEASE_TAG = "social-media-cache"


class PublishError(RuntimeError):
    pass


class PublishPending(PublishError):
    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


class PlatformReviewRequired(PublishError):
    def __init__(self, message: str, reason: str = "TIKTOK_REVIEW_REQUIRED") -> None:
        super().__init__(message)
        self.reason = reason


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def request(method: str, url: str, *, allow_404: bool = False, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", HTTP_TIMEOUT)
    response = requests.request(method, url, **kwargs)
    if allow_404 and response.status_code == 404:
        return response
    if not response.ok:
        raise PublishError(f"{method} {url} -> {response.status_code}: {response.text[:1600]}")
    return response


def client_config(client_id: str) -> dict[str, Any]:
    path = CLIENT_DIR / f"{client_id}.json"
    if not path.exists():
        raise PublishError(f"Unknown client: {client_id}")
    return load_json(path)


def secret(client: dict[str, Any], suffix: str, required: bool = True) -> str:
    prefix = str(client.get("publishing", {}).get("secret_prefix") or "").strip().upper()
    name = f"{prefix}_{suffix}" if prefix else suffix
    value = os.getenv(name, "").strip()
    if required and not value:
        raise PublishError(f"missing GitHub Secret: {name}")
    return value


def media_paths(job: dict[str, Any]) -> list[Path]:
    raw = job.get("media")
    values = raw if isinstance(raw, list) else [raw]
    paths = [ROOT / str(value) for value in values if str(value or "").strip()]
    if not paths:
        raise PublishError(f"{job.get('id')}: media is empty")
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise PublishError(f"{job.get('id')}: missing media: {', '.join(missing)}")
    return paths


def job_platforms(job: dict[str, Any]) -> list[str]:
    platforms: list[str] = []
    for item in job.get("platforms", []):
        platform = item.get("platform") if isinstance(item, dict) else item
        platform = str(platform or "").strip()
        if platform and platform not in platforms:
            platforms.append(platform)
    return platforms


def iso_due(job: dict[str, Any], now: datetime) -> bool:
    raw = str(job.get("scheduled_at") or "").strip()
    if not raw:
        return False
    try:
        scheduled = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    return scheduled.astimezone(timezone.utc) <= now.astimezone(timezone.utc)


def remaining_platforms(job: dict[str, Any], only: set[str] | None = None) -> list[str]:
    published = {str(x) for x in job.get("published_platforms", [])}
    out = [p for p in job_platforms(job) if p not in published]
    if only is not None:
        out = [p for p in out if p in only]
    return out


def required_secrets(platform: str, client: dict[str, Any], job: dict[str, Any] | None = None) -> list[str]:
    provider = str((job or {}).get("provider") or "").strip().lower()
    broker_requested = provider == "oauth_broker" and platform in {"facebook", "instagram", "tiktok", "linkedin", "linkedin-page", "youtube"}
    broker_active = broker_requested or (oauth_broker.enabled() and platform in {"tiktok", "linkedin", "linkedin-page", "youtube"})
    if broker_active:
        return []
    by_platform = {
        "facebook": ["FACEBOOK_PAGE_ACCESS_TOKEN"],
        "instagram": ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"],
        "tiktok": ["TIKTOK_ACCESS_TOKEN"],
        "linkedin": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN"],
        "linkedin-page": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN"],
        "youtube": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
        "pinterest": ["PINTEREST_ACCESS_TOKEN", "PINTEREST_BOARD_ID"],
    }
    missing: list[str] = []
    prefix = str(client.get("publishing", {}).get("secret_prefix") or "").strip().upper()
    for suffix in by_platform.get(platform, []):
        name = f"{prefix}_{suffix}" if prefix else suffix
        if not os.getenv(name, "").strip():
            missing.append(name)
    return missing


class PublicMediaCache:
    """Temporary public GitHub Release assets used only where an API pulls URLs."""

    def __init__(self) -> None:
        self.token = os.getenv("GITHUB_TOKEN", "").strip()
        self.repo = os.getenv("GITHUB_REPOSITORY", "").strip()
        self.release: dict[str, Any] | None = None
        self.uploaded_asset_ids: list[int] = []

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.repo)

    def headers(self, content_type: str | None = None) -> dict[str, str]:
        out = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if content_type:
            out["Content-Type"] = content_type
        return out

    def ensure_release(self) -> dict[str, Any]:
        if self.release:
            return self.release
        if not self.enabled:
            raise PublishError("GITHUB_TOKEN/GITHUB_REPOSITORY are required for Instagram public media URLs")
        api = f"https://api.github.com/repos/{self.repo}/releases/tags/{CACHE_RELEASE_TAG}"
        response = request("GET", api, headers=self.headers(), allow_404=True)
        if response.status_code == 404:
            created = request(
                "POST",
                f"https://api.github.com/repos/{self.repo}/releases",
                headers=self.headers("application/json"),
                json={
                    "tag_name": CACHE_RELEASE_TAG,
                    "name": "Temporary social media cache",
                    "body": "Ephemeral media used by approved official-API publishing jobs.",
                    "draft": False,
                    "prerelease": True,
                },
            )
            self.release = created.json()
        else:
            self.release = response.json()
        return self.release

    def upload(self, path: Path, job_id: str, index: int) -> str:
        release = self.ensure_release()
        ext = path.suffix.lower() or ".bin"
        safe_job = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in job_id)
        name = f"{safe_job}-{index:02d}{ext}"
        for asset in release.get("assets", []):
            if asset.get("name") == name:
                request(
                    "DELETE",
                    f"https://api.github.com/repos/{self.repo}/releases/assets/{asset['id']}",
                    headers=self.headers(),
                )
        upload_url = str(release["upload_url"]).split("{")[0]
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        response = request(
            "POST",
            upload_url,
            headers=self.headers(ctype),
            params={"name": name},
            data=path.read_bytes(),
            timeout=300,
        )
        asset = response.json()
        self.uploaded_asset_ids.append(int(asset["id"]))
        url = str(asset["browser_download_url"])
        for _ in range(12):
            check = requests.head(url, allow_redirects=True, timeout=20)
            if check.ok:
                return url
            time.sleep(5)
        raise PublishError(f"temporary media is not publicly fetchable: {url}")

    def cleanup(self) -> None:
        if not self.enabled:
            return
        for asset_id in self.uploaded_asset_ids:
            try:
                request(
                    "DELETE",
                    f"https://api.github.com/repos/{self.repo}/releases/assets/{asset_id}",
                    headers=self.headers(),
                )
            except Exception as exc:
                print(f"WARN cleanup GitHub asset {asset_id}: {exc}")
        self.uploaded_asset_ids.clear()


def meta_graph_base() -> str:
    return f"https://graph.facebook.com/{os.getenv('META_GRAPH_VERSION', 'v23.0').strip()}"


def facebook_publish(job: dict[str, Any], client: dict[str, Any], paths: list[Path], _cache: PublicMediaCache) -> dict[str, Any]:
    broker_requested = str(job.get("provider") or "").strip().lower() == "oauth_broker"
    if broker_requested:
        broker = oauth_broker.token(client, "facebook", force=True)
        token = str(broker["access_token"])
    else:
        token = secret(client, "FACEBOOK_PAGE_ACCESS_TOKEN")
    if str(job.get("format") or "reel") == "reel":
        start = request("POST", f"{meta_graph_base()}/me/video_reels", params={"access_token": token, "upload_phase": "start"}).json()
        video_id = str(start["video_id"])
        upload_url = str(start["upload_url"])
        data = paths[0].read_bytes()
        request("POST", upload_url, headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data)), "Content-Type": "application/octet-stream"}, data=data, timeout=300)
        finish = request("POST", f"{meta_graph_base()}/me/video_reels", params={"access_token": token, "video_id": video_id, "upload_phase": "finish", "video_state": "PUBLISHED", "description": str(job.get("caption") or "")[:5000], "title": str(job.get("title") or "")[:255]}).json()
        return {"video_id": video_id, "finish": finish}
    with paths[0].open("rb") as fh:
        media_type = mimetypes.guess_type(paths[0].name)[0] or "image/jpeg"
        response = request("POST", f"{meta_graph_base()}/me/photos", params={"access_token": token, "message": str(job.get("caption") or "")[:5000]}, files={"source": (paths[0].name, fh, media_type)}, timeout=180).json()
    return {"photo_id": response.get("id"), "post_id": response.get("post_id"), "mode": "first_slide"}


def ig_wait_container(container_id: str, token: str, timeout_seconds: int = 300) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = request("GET", f"{meta_graph_base()}/{container_id}", params={"fields": "status_code,status", "access_token": token}).json()
        code = status.get("status_code")
        if code == "FINISHED" or "status_code" not in status:
            return
        if code in {"ERROR", "EXPIRED"}:
            raise PublishError(f"Instagram container failed: {status}")
        time.sleep(6)
    raise PublishError(f"Instagram container {container_id} did not finish")


def instagram_publish(job: dict[str, Any], client: dict[str, Any], paths: list[Path], cache: PublicMediaCache) -> dict[str, Any]:
    broker_requested = str(job.get("provider") or "").strip().lower() == "oauth_broker"
    if broker_requested:
        broker = oauth_broker.token(client, "instagram", force=True)
        token = str(broker["access_token"])
        ig_user_id = str(broker.get("instagram_user_id") or broker.get("account_id") or "").strip()
        if not ig_user_id:
            raise oauth_broker.BrokerError("Instagram account selection required", auth_required=True)
    else:
        token = secret(client, "INSTAGRAM_ACCESS_TOKEN")
        ig_user_id = secret(client, "INSTAGRAM_USER_ID")
    urls = [cache.upload(path, str(job["id"]), idx) for idx, path in enumerate(paths, 1)]
    if str(job.get("format") or "reel") == "reel":
        created = request("POST", f"{meta_graph_base()}/{ig_user_id}/media", params={"media_type": "REELS", "video_url": urls[0], "caption": str(job.get("caption") or "")[:2200], "share_to_feed": "true", "access_token": token}).json()
        container_id = str(created["id"])
        ig_wait_container(container_id, token)
        published = request("POST", f"{meta_graph_base()}/{ig_user_id}/media_publish", params={"creation_id": container_id, "access_token": token}).json()
        return {"container_id": container_id, "media_id": published.get("id")}
    if len(urls) == 1:
        created = request(
            "POST",
            f"{meta_graph_base()}/{ig_user_id}/media",
            params={
                "image_url": urls[0],
                "caption": str(job.get("caption") or "")[:2200],
                "access_token": token,
            },
        ).json()
        container_id = str(created["id"])
        ig_wait_container(container_id, token)
        published = request(
            "POST",
            f"{meta_graph_base()}/{ig_user_id}/media_publish",
            params={"creation_id": container_id, "access_token": token},
        ).json()
        return {"container_id": container_id, "media_id": published.get("id"), "mode": "single_image"}
    children: list[str] = []
    for url in urls[:10]:
        child = request("POST", f"{meta_graph_base()}/{ig_user_id}/media", params={"image_url": url, "is_carousel_item": "true", "access_token": token}).json()
        children.append(str(child["id"]))
    parent = request("POST", f"{meta_graph_base()}/{ig_user_id}/media", params={"caption": str(job.get("caption") or "")[:2200], "media_type": "CAROUSEL", "children": ",".join(children), "access_token": token}).json()
    container_id = str(parent["id"])
    ig_wait_container(container_id, token)
    published = request("POST", f"{meta_graph_base()}/{ig_user_id}/media_publish", params={"creation_id": container_id, "access_token": token}).json()
    return {"container_id": container_id, "media_id": published.get("id"), "children": children}


def tiktok_error_code(payload: dict[str, Any]) -> str:
    return str((payload.get("error") or {}).get("code") or "").strip()


def tiktok_raise_api_error(context: str, payload: dict[str, Any]) -> None:
    code = tiktok_error_code(payload)
    if not code or code == "ok":
        return
    detail = str((payload.get("error") or {}).get("message") or code)
    if code in {"access_token_invalid", "scope_not_authorized"}:
        raise oauth_broker.BrokerError(f"TikTok {context}: {code} - {detail}", auth_required=True)
    if code in {"privacy_level_option_mismatch"}:
        raise PlatformReviewRequired(f"TikTok {context}: {code} - {detail}")
    raise PublishError(f"TikTok {context}: {code} - {detail}")


def tiktok_creator_info(token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    payload = request(
        "POST",
        "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
        headers=headers,
        json={},
    ).json()
    tiktok_raise_api_error("creator_info", payload)
    data = payload.get("data") or {}
    if not data.get("privacy_level_options"):
        raise PlatformReviewRequired("TikTok creator_info did not return privacy options")
    return data


def tiktok_utf16_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def tiktok_video_duration(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.SubprocessError, ValueError) as exc:
        raise PublishError("TikTok video duration validation requires ffprobe") from exc


def tiktok_settings_for_job(job: dict[str, Any]) -> dict[str, Any]:
    raw = job.get("tiktok_settings")
    return raw if isinstance(raw, dict) else {}


def tiktok_validate_settings(
    settings: dict[str, Any],
    creator: dict[str, Any],
    duration_seconds: float,
) -> None:
    if not settings.get("consent_confirmed"):
        raise PlatformReviewRequired("TikTok explicit publishing consent is missing")

    mode = str(settings.get("mode") or "DIRECT_POST").upper()
    if mode not in {"DIRECT_POST", "DRAFT_UPLOAD"}:
        raise PlatformReviewRequired("TikTok publishing mode must be selected again")

    max_duration = float(creator.get("max_video_post_duration_sec") or 0)
    if max_duration > 0 and duration_seconds > max_duration + 0.05:
        raise PlatformReviewRequired(
            "This video exceeds the maximum duration allowed by the connected TikTok account"
        )

    caption = str(settings.get("caption") or "")
    if tiktok_utf16_units(caption) > 2200:
        raise PlatformReviewRequired("TikTok caption exceeds the 2200 UTF-16 unit limit")

    if mode == "DRAFT_UPLOAD":
        return

    privacy = str(settings.get("privacy_level") or "")
    options = [str(x) for x in creator.get("privacy_level_options") or []]
    if not privacy or privacy not in options:
        raise PlatformReviewRequired("TikTok privacy choice is missing or no longer available")

    if bool(settings.get("allow_comment")) and bool(creator.get("comment_disabled")):
        raise PlatformReviewRequired("TikTok comments are no longer available for this creator")
    if bool(settings.get("allow_duet")) and bool(creator.get("duet_disabled")):
        raise PlatformReviewRequired("TikTok Duet is no longer available for this creator")
    if bool(settings.get("allow_stitch")) and bool(creator.get("stitch_disabled")):
        raise PlatformReviewRequired("TikTok Stitch is no longer available for this creator")

    commercial = bool(settings.get("commercial_content"))
    your_brand = bool(settings.get("your_brand"))
    branded = bool(settings.get("branded_content"))
    if commercial and not (your_brand or branded):
        raise PlatformReviewRequired("TikTok commercial content disclosure is incomplete")
    if not commercial and (your_brand or branded):
        raise PlatformReviewRequired("TikTok commercial content settings are inconsistent")
    if branded and privacy == "SELF_ONLY":
        raise PlatformReviewRequired("TikTok branded content cannot use private visibility")


def tiktok_chunk_plan(size: int) -> tuple[int, int]:
    if size <= 0:
        raise PublishError("TikTok video is empty")
    max_chunk = 64 * 1024 * 1024
    if size <= max_chunk:
        return size, 1
    total_chunks = math.ceil(size / max_chunk)
    chunk_size = math.ceil(size / total_chunks)
    if chunk_size > max_chunk:
        raise PublishError("TikTok chunk plan exceeds 64 MiB")
    return chunk_size, total_chunks


def tiktok_upload_file(upload_url: str, path: Path, chunk_size: int, total_chunks: int) -> None:
    size = path.stat().st_size
    with path.open("rb") as fh:
        start = 0
        for chunk_index in range(total_chunks):
            read_size = size - start if chunk_index == total_chunks - 1 else min(chunk_size, size - start)
            body = fh.read(read_size)
            if not body:
                raise PublishError(f"TikTok upload ended early at chunk {chunk_index + 1}/{total_chunks}")
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
                raise PublishError(f"TikTok binary upload -> {response.status_code}: {response.text[:1000]}")
            start = end + 1
    if start != size:
        raise PublishError(f"TikTok upload byte mismatch: sent {start} of {size}")


def tiktok_fetch_status(token: str, publish_id: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    payload = request(
        "POST",
        "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
        headers=headers,
        json={"publish_id": publish_id},
    ).json()
    tiktok_raise_api_error("publish_status", payload)
    return payload.get("data") or {}


def tiktok_publish(job: dict[str, Any], client: dict[str, Any], paths: list[Path], _cache: PublicMediaCache) -> dict[str, Any]:
    if str(job.get("format") or "reel") != "reel":
        raise PlatformReviewRequired("TikTok Direct Post currently requires a video/reel job")

    broker_requested = str(job.get("provider") or "").strip().lower() == "oauth_broker"
    if oauth_broker.enabled() or broker_requested:
        token_payload = oauth_broker.token(client, "tiktok", force=broker_requested)
        token = str(token_payload["access_token"])
    else:
        token = secret(client, "TIKTOK_ACCESS_TOKEN")

    settings = tiktok_settings_for_job(job)
    mode = str(settings.get("mode") or "DIRECT_POST").upper()
    existing_publish_id = str(job.get("tiktok_publish_id") or "").strip()
    if existing_publish_id:
        status = tiktok_fetch_status(token, existing_publish_id)
        state = str(status.get("status") or "")
        job["tiktok_last_status"] = status
        if state == "FAILED":
            raise PublishError(f"TikTok publish failed: {status.get('fail_reason') or 'unknown'}")
        if state == "PUBLISH_COMPLETE" or (mode == "DRAFT_UPLOAD" and state == "SEND_TO_USER_INBOX"):
            public_ids = status.get("publicaly_available_post_id") or []
            return {
                "publish_id": existing_publish_id,
                "status": state,
                "post_ids": public_ids,
                "mode": mode,
            }
        raise PublishPending(
            f"TikTok publish is still processing: {state or 'UNKNOWN'}",
            {"publish_id": existing_publish_id, "status": state or "PROCESSING"},
        )

    path = paths[0]
    duration = tiktok_video_duration(path)
    creator = tiktok_creator_info(token)
    tiktok_validate_settings(settings, creator, duration)

    size = path.stat().st_size
    chunk_size, total_chunks = tiktok_chunk_plan(size)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}

    if mode == "DRAFT_UPLOAD":
        init_url = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
        init_body = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            }
        }
    else:
        privacy = str(settings["privacy_level"])
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        init_body = {
            "post_info": {
                "title": str(settings.get("caption") or job.get("caption") or ""),
                "privacy_level": privacy,
                "disable_duet": not bool(settings.get("allow_duet")),
                "disable_comment": not bool(settings.get("allow_comment")),
                "disable_stitch": not bool(settings.get("allow_stitch")),
                "video_cover_timestamp_ms": 1000,
                "brand_organic_toggle": bool(settings.get("commercial_content") and settings.get("your_brand")),
                "brand_content_toggle": bool(settings.get("commercial_content") and settings.get("branded_content")),
                "is_aigc": bool(job.get("video_made_with_ai", False)),
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }

    init = request("POST", init_url, headers=headers, json=init_body).json()
    tiktok_raise_api_error("init", init)
    data = init.get("data") or {}
    publish_id = str(data.get("publish_id") or "")
    upload_url = str(data.get("upload_url") or "")
    if not publish_id or not upload_url:
        raise PublishError("TikTok init response did not return publish_id/upload_url")

    job["tiktok_publish_id"] = publish_id
    job["tiktok_publish_mode"] = mode
    job["tiktok_last_status"] = {"status": "PROCESSING_UPLOAD"}

    tiktok_upload_file(upload_url, path, chunk_size, total_chunks)
    status = tiktok_fetch_status(token, publish_id)
    state = str(status.get("status") or "")
    job["tiktok_last_status"] = status

    if state == "FAILED":
        raise PublishError(f"TikTok publish failed: {status.get('fail_reason') or 'unknown'}")
    if state == "PUBLISH_COMPLETE" or (mode == "DRAFT_UPLOAD" and state == "SEND_TO_USER_INBOX"):
        return {
            "publish_id": publish_id,
            "status": state,
            "post_ids": status.get("publicaly_available_post_id") or [],
            "privacy_level": settings.get("privacy_level"),
            "mode": mode,
        }
    raise PublishPending(
        f"TikTok publish is processing: {state or 'UNKNOWN'}",
        {"publish_id": publish_id, "status": state or "PROCESSING"},
    )

def linkedin_publish(job: dict[str, Any], client: dict[str, Any], _paths: list[Path], _cache: PublicMediaCache) -> dict[str, Any]:
    broker_requested = str(job.get("provider") or "").strip().lower() == "oauth_broker"
    if oauth_broker.enabled() or broker_requested:
        broker = oauth_broker.token(client, "linkedin", force=broker_requested)
        token = str(broker["access_token"])
        author = str(broker.get("author_urn") or "").strip()
        if not author:
            raise oauth_broker.BrokerError("LinkedIn account selection required", auth_required=True)
    else:
        token = secret(client, "LINKEDIN_ACCESS_TOKEN")
        author = secret(client, "LINKEDIN_AUTHOR_URN")
    version = os.getenv("LINKEDIN_VERSION", "202601").strip()
    response = request("POST", "https://api.linkedin.com/rest/posts", headers={"Authorization": f"Bearer {token}", "X-Restli-Protocol-Version": "2.0.0", "Linkedin-Version": version, "Content-Type": "application/json"}, json={"author": author, "commentary": str(job.get("caption") or "")[:3000], "visibility": "PUBLIC", "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []}, "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False})
    return {"post_id": response.headers.get("x-restli-id", ""), "mode": "text"}


def youtube_publish(job: dict[str, Any], client: dict[str, Any], paths: list[Path], _cache: PublicMediaCache) -> dict[str, Any]:
    if str(job.get("format") or "reel") != "reel":
        raise PublishError("YouTube publisher accepts video/reel jobs only")
    broker_requested = str(job.get("provider") or "").strip().lower() == "oauth_broker"
    if oauth_broker.enabled() or broker_requested:
        access_token = str(oauth_broker.token(client, "youtube", force=broker_requested)["access_token"])
    else:
        client_id = secret(client, "YOUTUBE_CLIENT_ID")
        client_secret = secret(client, "YOUTUBE_CLIENT_SECRET")
        refresh_token = secret(client, "YOUTUBE_REFRESH_TOKEN")
        oauth = request("POST", "https://oauth2.googleapis.com/token", data={"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}).json()
        access_token = str(oauth["access_token"])
    path = paths[0]
    metadata = {"snippet": {"title": str(job.get("title") or job.get("client_name") or "Video")[:100], "description": str(job.get("caption") or "")[:5000], "categoryId": os.getenv("YOUTUBE_CATEGORY_ID", "22").strip()}, "status": {"privacyStatus": os.getenv("YOUTUBE_PRIVACY_STATUS", "private").strip()}}
    init = request("POST", "https://www.googleapis.com/upload/youtube/v3/videos", params={"uploadType": "resumable", "part": "snippet,status"}, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": str(path.stat().st_size), "X-Upload-Content-Type": "video/mp4"}, data=json.dumps(metadata).encode("utf-8"))
    upload_url = init.headers.get("Location")
    if not upload_url:
        raise PublishError("YouTube did not return a resumable upload URL")
    result = request("PUT", upload_url, headers={"Content-Type": "video/mp4", "Content-Length": str(path.stat().st_size)}, data=path.read_bytes(), timeout=600).json()
    return {"video_id": result.get("id"), "privacy": metadata["status"]["privacyStatus"]}


def pinterest_publish(job: dict[str, Any], client: dict[str, Any], paths: list[Path], _cache: PublicMediaCache) -> dict[str, Any]:
    token = secret(client, "PINTEREST_ACCESS_TOKEN")
    board_id = secret(client, "PINTEREST_BOARD_ID")
    path = paths[0]
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise PublishError("Pinterest is configured only for carousel/image jobs")
    content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    payload: dict[str, Any] = {"board_id": board_id, "title": str(job.get("title") or job.get("client_name") or "")[:100], "description": str(job.get("caption") or "")[:800], "media_source": {"source_type": "image_base64", "is_standard": True, "content_type": content_type, "data": base64.b64encode(path.read_bytes()).decode("ascii")}}
    prefix = str(client.get("publishing", {}).get("secret_prefix") or "").strip().upper()
    link = os.getenv(f"{prefix}_PINTEREST_LINK", os.getenv("PINTEREST_LINK", "")).strip()
    if link:
        payload["link"] = link
    result = request("POST", "https://api.pinterest.com/v5/pins", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=payload).json()
    return {"pin_id": result.get("id")}


PUBLISHERS = {"facebook": facebook_publish, "instagram": instagram_publish, "tiktok": tiktok_publish, "linkedin": linkedin_publish, "linkedin-page": linkedin_publish, "youtube": youtube_publish, "pinterest": pinterest_publish}


def pick_jobs(queue: dict[str, Any], job_id: str | None) -> list[dict[str, Any]]:
    def direct_eligible(job: dict[str, Any]) -> bool:
        return str(job.get("provider") or "direct").strip().lower() != "buffer"

    if job_id:
        return [
            job for job in queue.get("jobs", [])
            if job.get("id") == job_id and direct_eligible(job)
        ]
    now = datetime.now(timezone.utc)
    return [
        job for job in queue.get("jobs", [])
        if direct_eligible(job)
        and job.get("enabled", True)
        and job.get("status") in {"ready", "partially_published"}
        and iso_due(job, now)
    ]


def publish_job(job: dict[str, Any], only: set[str] | None, dry_run: bool) -> tuple[list[dict[str, Any]], bool]:
    client = client_config(str(job["client_id"]))
    paths = media_paths(job)
    platforms = remaining_platforms(job, only)
    results: list[dict[str, Any]] = []
    if not platforms:
        return results, True
    blocked = {platform: required_secrets(platform, client, job) for platform in platforms}
    blocked = {platform: names for platform, names in blocked.items() if names}
    if blocked:
        for platform, names in blocked.items():
            results.append({"platform": platform, "status": "blocked", "missing": names})
        return results, False
    if dry_run:
        for platform in platforms:
            results.append({"platform": platform, "status": "ready"})
        return results, True
    cache = PublicMediaCache()
    success = True
    auth_required_platforms: set[str] = set()
    review_required_platforms: set[str] = set()
    processing_platforms: set[str] = set()
    try:
        for platform in platforms:
            publisher = PUBLISHERS.get(platform)
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
            except PublishPending as exc:
                processing_platforms.add(platform)
                results.append({"platform": platform, "status": "processing", "result": exc.payload, "error": str(exc)})
            except PlatformReviewRequired as exc:
                review_required_platforms.add(platform)
                results.append({"platform": platform, "status": "review_required", "reason": exc.reason, "error": str(exc)})
                success = False
            except oauth_broker.BrokerError as exc:
                if exc.auth_required:
                    auth_required_platforms.add(platform)
                    results.append({"platform": platform, "status": "auth_required", "error": str(exc)})
                else:
                    results.append({"platform": platform, "status": "error", "error": str(exc)})
                success = False
            except Exception as exc:
                results.append({"platform": platform, "status": "error", "error": str(exc)})
                success = False
    finally:
        cache.cleanup()
    expected = set(job_platforms(job))
    done = set(str(x) for x in job.get("published_platforms", []))
    if expected and expected.issubset(done):
        job["status"] = "published"
        job.pop("blocked_reason", None)
        job.pop("auth_required_platforms", None)
        job.pop("review_required_platforms", None)
        job.pop("processing_platforms", None)
    elif review_required_platforms:
        job["review_required_platforms"] = sorted(review_required_platforms)
        job["status"] = "partially_published" if done else "blocked"
        job["blocked_reason"] = "TIKTOK_REVIEW_REQUIRED"
    elif auth_required_platforms:
        job["auth_required_platforms"] = sorted(auth_required_platforms)
        job["status"] = "partially_published" if done else "blocked"
        job["blocked_reason"] = "AUTH_REQUIRED"
    elif processing_platforms:
        job["processing_platforms"] = sorted(processing_platforms)
        job["status"] = "partially_published"
        job["blocked_reason"] = "IN_PUBBLICAZIONE"
    elif done:
        job["status"] = "partially_published"
    return results, success


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", help="Publish/check one exact approved queue job; default publishes due jobs")
    parser.add_argument("--platforms", default="all", help="all or comma-separated platform names")
    parser.add_argument("--dry-run", action="store_true", help="Check media and secrets only; do not publish")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any selected job is blocked/failed")
    args = parser.parse_args()
    queue = load_json(QUEUE_PATH)
    jobs = pick_jobs(queue, args.job_id)
    only = None if args.platforms == "all" else {x.strip() for x in args.platforms.split(",") if x.strip()}
    report: list[dict[str, Any]] = []
    all_ok = True
    for job in jobs:
        if args.job_id and job.get("status") not in {"ready", "partially_published"}:
            report.append({"job_id": job.get("id"), "status": "blocked_by_queue", "queue_status": job.get("status"), "reason": job.get("blocked_reason")})
            all_ok = False
            continue
        results, ok = publish_job(job, only, args.dry_run)
        job.setdefault("direct_api_results", []).append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dry_run": args.dry_run, "results": results})
        report.append({"job_id": job.get("id"), "results": results})
        all_ok = all_ok and ok
    if not jobs:
        print("No approved due jobs.")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.dry_run:
        queue["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_json(QUEUE_PATH, queue)
    return 1 if args.strict and not all_ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
