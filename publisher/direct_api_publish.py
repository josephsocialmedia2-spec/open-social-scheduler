#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import requests

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"
CLIENT_DIR = ROOT / "publisher" / "clients"
TIMEOUT = 60


class PublishError(RuntimeError):
    pass


def env(name: str, required: bool = True, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if required and not value:
        raise PublishError(f"missing secret/config: {name}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def req(method: str, url: str, **kwargs: Any) -> requests.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    response = requests.request(method, url, **kwargs)
    if not response.ok:
        body = response.text[:1500]
        raise PublishError(f"{method} {url} -> {response.status_code}: {body}")
    return response


def client_config(client_id: str) -> dict[str, Any]:
    path = CLIENT_DIR / f"{client_id}.json"
    if not path.exists():
        raise PublishError(f"unknown client: {client_id}")
    return load_json(path)


def facebook_reel(job: dict[str, Any], media: Path) -> dict[str, Any]:
    token = env("FACEBOOK_PAGE_ACCESS_TOKEN")
    version = env("META_GRAPH_VERSION", required=False, default="v23.0")
    start = req(
        "POST",
        f"https://graph.facebook.com/{version}/me/video_reels",
        params={"access_token": token, "upload_phase": "start"},
    ).json()
    video_id = str(start["video_id"])
    upload_url = str(start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{version}/{video_id}")
    data = media.read_bytes()
    req(
        "POST",
        upload_url,
        headers={
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(len(data)),
            "Content-Type": "application/octet-stream",
        },
        data=data,
    )
    finish = req(
        "POST",
        f"https://graph.facebook.com/{version}/me/video_reels",
        params={
            "access_token": token,
            "video_id": video_id,
            "upload_phase": "finish",
            "video_state": "PUBLISHED",
            "description": job.get("caption", "")[:5000],
            "title": job.get("title", "")[:255],
        },
    ).json()
    return {"video_id": video_id, "response": finish}


def instagram_reel(job: dict[str, Any], _media: Path) -> dict[str, Any]:
    token = env("INSTAGRAM_ACCESS_TOKEN")
    ig_user_id = env("INSTAGRAM_USER_ID")
    media_url = env("APPROVED_MEDIA_PUBLIC_URL")
    version = env("META_GRAPH_VERSION", required=False, default="v23.0")
    base = f"https://graph.facebook.com/{version}"
    created = req(
        "POST",
        f"{base}/{ig_user_id}/media",
        params={
            "media_type": "REELS",
            "video_url": media_url,
            "caption": job.get("caption", "")[:2200],
            "share_to_feed": "true",
            "access_token": token,
        },
    ).json()
    container_id = str(created["id"])
    deadline = time.time() + 300
    while time.time() < deadline:
        status = req(
            "GET",
            f"{base}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
        ).json()
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in {"ERROR", "EXPIRED"}:
            raise PublishError(f"Instagram container failed: {status}")
        time.sleep(8)
    else:
        raise PublishError("Instagram container did not finish within 5 minutes")
    published = req(
        "POST",
        f"{base}/{ig_user_id}/media_publish",
        params={"creation_id": container_id, "access_token": token},
    ).json()
    return {"container_id": container_id, "media_id": published.get("id")}


def tiktok_video(job: dict[str, Any], media: Path) -> dict[str, Any]:
    token = env("TIKTOK_ACCESS_TOKEN")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    creator = req(
        "POST",
        "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
        headers=headers,
        json={},
    ).json()
    error = creator.get("error", {})
    if error.get("code") not in {None, "ok"}:
        raise PublishError(f"TikTok creator_info failed: {creator}")
    options = creator.get("data", {}).get("privacy_level_options") or ["SELF_ONLY"]
    preferred = os.getenv("TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE")
    privacy = preferred if preferred in options else options[0]
    size = media.stat().st_size
    chunk = size if size < 5 * 1024 * 1024 else min(size, 64 * 1024 * 1024)
    total = max(1, size // chunk)
    payload = {
        "post_info": {
            "title": job.get("caption", "")[:2200],
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
            "brand_organic_toggle": True,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": chunk,
            "total_chunk_count": total,
        },
    }
    init = req(
        "POST",
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json=payload,
    ).json()
    if init.get("error", {}).get("code") != "ok":
        raise PublishError(f"TikTok init failed: {init}")
    upload_url = init["data"]["upload_url"]
    publish_id = init["data"]["publish_id"]
    with media.open("rb") as fh:
        start = 0
        while start < size:
            body = fh.read(chunk)
            end = start + len(body) - 1
            response = req(
                "PUT",
                upload_url,
                headers={
                    "Content-Type": mimetypes.guess_type(media.name)[0] or "video/mp4",
                    "Content-Length": str(len(body)),
                    "Content-Range": f"bytes {start}-{end}/{size}",
                },
                data=body,
            )
            start = end + 1
            if response.status_code not in {201, 206}:
                raise PublishError(f"TikTok upload returned {response.status_code}")
    return {"publish_id": publish_id, "privacy_level": privacy}


def linkedin_text(job: dict[str, Any], _media: Path) -> dict[str, Any]:
    token = env("LINKEDIN_ACCESS_TOKEN")
    author = env("LINKEDIN_AUTHOR_URN")
    version = env("LINKEDIN_VERSION", required=False, default="202601")
    payload = {
        "author": author,
        "commentary": job.get("caption", "")[:3000],
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    response = req(
        "POST",
        "https://api.linkedin.com/rest/posts",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Linkedin-Version": version,
            "Content-Type": "application/json",
        },
        json=payload,
    )
    return {"post_id": response.headers.get("x-restli-id", "")}


def youtube_video(job: dict[str, Any], media: Path) -> dict[str, Any]:
    client_id = env("YOUTUBE_CLIENT_ID")
    client_secret = env("YOUTUBE_CLIENT_SECRET")
    refresh_token = env("YOUTUBE_REFRESH_TOKEN")
    token = req(
        "POST",
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    ).json()["access_token"]
    metadata = {
        "snippet": {
            "title": (job.get("title") or "F1 Immobiliare")[:100],
            "description": job.get("caption", "")[:5000],
            "categoryId": os.getenv("YOUTUBE_CATEGORY_ID", "22"),
        },
        "status": {"privacyStatus": os.getenv("YOUTUBE_PRIVACY_STATUS", "public")},
    }
    init = req(
        "POST",
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(media.stat().st_size),
            "X-Upload-Content-Type": "video/mp4",
        },
        data=json.dumps(metadata).encode("utf-8"),
    )
    upload_url = init.headers.get("Location")
    if not upload_url:
        raise PublishError("YouTube did not return resumable upload URL")
    result = req(
        "PUT",
        upload_url,
        headers={"Content-Type": "video/mp4", "Content-Length": str(media.stat().st_size)},
        data=media.read_bytes(),
        timeout=300,
    ).json()
    return {"video_id": result.get("id")}


def make_pin_image(media: Path) -> Path:
    target = Path(os.getenv("PIN_IMAGE_PATH", str(media.with_suffix(".pin.jpg"))))
    if target.exists():
        return target
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "1", "-i", str(media), "-frames:v", "1", "-q:v", "2", str(target)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return target


def pinterest_pin(job: dict[str, Any], media: Path) -> dict[str, Any]:
    token = env("PINTEREST_ACCESS_TOKEN")
    board_id = env("PINTEREST_BOARD_ID")
    image = make_pin_image(media)
    encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    payload = {
        "board_id": board_id,
        "title": (job.get("title") or "F1 Immobiliare")[:100],
        "description": job.get("caption", "")[:800],
        "media_source": {
            "source_type": "image_base64",
            "is_standard": True,
            "content_type": "image/jpeg",
            "data": encoded,
        },
    }
    link = os.getenv("PINTEREST_LINK", "").strip()
    if link:
        payload["link"] = link
    result = req(
        "POST",
        "https://api.pinterest.com/v5/pins",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
    ).json()
    return {"pin_id": result.get("id")}


PUBLISHERS: dict[str, Callable[[dict[str, Any], Path], dict[str, Any]]] = {
    "facebook": facebook_reel,
    "instagram": instagram_reel,
    "tiktok": tiktok_video,
    "linkedin": linkedin_text,
    "youtube": youtube_video,
    "pinterest": pinterest_pin,
}

REQUIRED_ENV = {
    "facebook": ["FACEBOOK_PAGE_ACCESS_TOKEN"],
    "instagram": ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID", "APPROVED_MEDIA_PUBLIC_URL"],
    "tiktok": ["TIKTOK_ACCESS_TOKEN"],
    "linkedin": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN"],
    "youtube": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
    "pinterest": ["PINTEREST_ACCESS_TOKEN", "PINTEREST_BOARD_ID"],
}


def missing_for(platform: str) -> list[str]:
    return [name for name in REQUIRED_ENV.get(platform, []) if not os.getenv(name, "").strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--platforms", default="all", help="comma separated or all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    queue = load_json(QUEUE_PATH)
    jobs = queue.get("jobs", [])
    job = next((item for item in jobs if item.get("id") == args.job_id), None)
    if not job:
        raise PublishError(f"job not found: {args.job_id}")
    if job.get("status") in {"published", "disabled"}:
        raise PublishError(f"job cannot be published from status {job.get('status')}")
    media = ROOT / str(job.get("media") or "")
    if not media.exists():
        raise PublishError(f"media missing: {media}")
    client = client_config(str(job["client_id"]))
    configured = client.get("publishing", {}).get("platforms", [])
    selected = configured if args.platforms == "all" else [x.strip() for x in args.platforms.split(",") if x.strip()]
    selected = [p for p in selected if p in PUBLISHERS]
    if not selected:
        raise PublishError("no supported platforms selected")

    results: list[dict[str, Any]] = []
    failures = 0
    for platform in selected:
        missing = missing_for(platform)
        if missing:
            results.append({"platform": platform, "status": "blocked", "missing": missing})
            failures += 1
            continue
        if args.dry_run:
            results.append({"platform": platform, "status": "ready"})
            continue
        try:
            payload = PUBLISHERS[platform](job, media)
            results.append({"platform": platform, "status": "published", "result": payload})
        except Exception as exc:
            results.append({"platform": platform, "status": "error", "error": str(exc)})
            failures += 1

    job.setdefault("direct_api_results", []).extend(results)
    if not args.dry_run:
        published = {r["platform"] for r in results if r.get("status") == "published"}
        job["published_platforms"] = sorted(set(job.get("published_platforms", [])) | published)
        if published and failures == 0:
            job["status"] = "published"
        elif published:
            job["status"] = "partially_published"
        else:
            job["status"] = "awaiting_credentials"
    save_json(QUEUE_PATH, queue)
    print(json.dumps({"job_id": args.job_id, "dry_run": args.dry_run, "results": results}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
