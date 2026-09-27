from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .browser.base import BrowserPublishError
from .browser.runner import publish_with_profile
from .database import Database
from .downloader import DownloadError, download_media
from .queue import PublicationJob


def api_ready(channel: dict | None) -> bool:
    return bool(
        channel
        and channel.get("enabled")
        and channel.get("verified")
        and not channel.get("reauthorization_required")
        and str(channel.get("provider") or "") in {"direct", "oauth_broker", "buffer"}
    )


def expected_url(client: dict, session: dict | None, channel: dict | None, platform: str) -> str:
    if session and session.get("expected_profile_url"):
        return str(session["expected_profile_url"])
    if channel and channel.get("profile_url"):
        return str(channel["profile_url"])
    col = {
        "facebook": "facebook",
        "instagram": "instagram",
        "tiktok": "tiktok",
        "youtube": "youtube",
        "linkedin-page": "linkedin",
    }[platform]
    return str(client.get(col) or "")


def auth_required(
    db: Database,
    job: PublicationJob,
    profile: dict | None,
    session: dict | None,
    code: str,
    message: str,
) -> None:
    db.update_job(
        job.id,
        {
            "status": "AUTH_REQUIRED",
            "publishing_method": "BROWSER",
            "error_code": code,
            "error_message": message[:1000],
            "locked_at": None,
            "locked_by": None,
            "lock_expires_at": None,
        },
    )
    db.update_calendar(
        job.calendar_id,
        {"status": "AUTH_REQUIRED", "error": f"{code}: {message[:500]}"},
    )
    db.update_browser_session(
        session.get("id") if session else None,
        {"status": "AUTH_REQUIRED", "error_code": code, "error_message": message[:1000]},
    )
    db.update_browser_profile(
        profile.get("id") if profile else None,
        {"status": "AUTH_REQUIRED"},
    )


def process_one(db: Database, settings, row: dict) -> str:
    job = PublicationJob.from_row(row)
    client = db.client(job.client_id)
    if not client:
        db.update_job(
            job.id,
            {
                "status": "ERROR",
                "error_code": "CLIENT_NOT_FOUND",
                "error_message": "Client missing",
                "locked_at": None,
                "locked_by": None,
                "lock_expires_at": None,
            },
        )
        return "error"

    channel = db.channel(job.client_id, job.platform)
    if api_ready(channel):
        db.update_job(
            job.id,
            {
                "status": "SCHEDULED",
                "publishing_method": "API",
                "locked_at": None,
                "locked_by": None,
                "lock_expires_at": None,
            },
        )
        return "api"

    profile = db.browser_profile(job.client_id)
    session = db.browser_session(job.client_id, job.platform)
    if (
        not profile
        or profile.get("status") != "READY"
        or not session
        or session.get("status") != "CONNECTED"
    ):
        auth_required(
            db,
            job,
            profile,
            session,
            "AUTH_REQUIRED",
            "Cloud browser profile or social session is not READY/CONNECTED",
        )
        return "auth"

    exp_url = expected_url(client, session, channel, job.platform)
    if not exp_url:
        auth_required(
            db,
            job,
            profile,
            session,
            "EXPECTED_ACCOUNT_MISSING",
            "Expected social profile URL is missing",
        )
        return "auth"

    profile_path = Path(
        str(
            profile.get("profile_path")
            or settings.browser_root / job.client_id / "chrome-profile"
        )
    )
    try:
        profile_path.resolve().relative_to(settings.browser_root.resolve())
    except ValueError:
        db.update_job(
            job.id,
            {
                "status": "ACCOUNT_WRONG",
                "error_code": "PROFILE_PATH_OUTSIDE_ROOT",
                "error_message": "Browser profile path is outside F1_BROWSER_ROOT",
                "locked_at": None,
                "locked_by": None,
                "lock_expires_at": None,
            },
        )
        return "error"

    db.update_job(job.id, {"status": "PUBLISHING", "publishing_method": "BROWSER"})
    started = datetime.now(timezone.utc).isoformat()
    files: list[Path] = []

    try:
        files = download_media(
            job.id,
            job.media_payload,
            root=settings.browser_root,
            supabase_url=settings.supabase_url,
            service_key=settings.service_role_key,
            bucket=settings.storage_bucket,
        )
        result = publish_with_profile(
            profile_path=profile_path,
            platform=job.platform,
            expected_url=exp_url,
            expected_id=str(
                session.get("expected_account_id")
                or (channel or {}).get("external_channel_id")
                or ""
            ) or None,
            expected_name=str(
                session.get("expected_account_name")
                or (channel or {}).get("account_name")
                or client.get("name")
                or ""
            ) or None,
            caption=job.caption,
            files=files,
            dry_run=settings.dry_run,
            metadata=job.metadata,
        )

        now = datetime.now(timezone.utc).isoformat()
        if settings.dry_run:
            db.update_job(
                job.id,
                {
                    "status": "SCHEDULED",
                    "publishing_method": "BROWSER",
                    "error_code": None,
                    "error_message": None,
                    "locked_at": None,
                    "locked_by": None,
                    "lock_expires_at": None,
                    "metadata": {**job.metadata, "last_dry_run_at": now},
                },
            )
            final_status = "DRY_RUN_OK"
            result_key = "dry"
        else:
            db.update_job(
                job.id,
                {
                    "status": "PUBLISHED",
                    "published_at": now,
                    "external_post_id": result.external_post_id,
                    "external_post_url": result.external_post_url,
                    "error_code": None,
                    "error_message": None,
                    "locked_at": None,
                    "locked_by": None,
                    "lock_expires_at": None,
                },
            )
            db.update_calendar(
                job.calendar_id,
                {
                    "status": "PUBBLICATO",
                    "provider": "browser-cloud",
                    "external_post_id": result.external_post_id,
                    "external_url": result.external_post_url,
                    "error": None,
                    "last_checked_at": now,
                },
            )
            db.update_browser_session(
                session.get("id"),
                {
                    "status": "CONNECTED",
                    "last_used_at": now,
                    "last_verified_at": now,
                    "error_code": None,
                    "error_message": None,
                },
            )
            db.update_browser_profile(
                profile.get("id"),
                {"status": "READY", "last_started_at": now, "last_verified_at": now},
            )
            final_status = "PUBLISHED"
            result_key = "published"

        db.audit(
            {
                "publication_id": job.id,
                "owner_id": job.owner_id,
                "client_id": job.client_id,
                "platform": job.platform,
                "method": "BROWSER",
                "expected_account": exp_url,
                "actual_account": result.actual_account,
                "started_at": started,
                "completed_at": now,
                "media_count": len(files),
                "github_run_id": os.getenv("GITHUB_RUN_ID"),
                "github_sha": os.getenv("GITHUB_SHA"),
                "browser_profile_id": profile.get("id"),
                "external_post_id": result.external_post_id,
                "external_post_url": result.external_post_url,
                "status": final_status,
                "details": {"dry_run": settings.dry_run},
            }
        )
        return result_key

    except BrowserPublishError as exc:
        if exc.code == "ACCOUNT_WRONG":
            db.update_job(
                job.id,
                {
                    "status": "ACCOUNT_WRONG",
                    "error_code": exc.code,
                    "error_message": str(exc)[:1000],
                    "locked_at": None,
                    "locked_by": None,
                    "lock_expires_at": None,
                },
            )
            db.update_browser_session(
                session.get("id"),
                {
                    "status": "ACCOUNT_WRONG",
                    "error_code": exc.code,
                    "error_message": str(exc)[:1000],
                },
            )
            result_key = "error"
        elif exc.auth_required or exc.code == "AUTH_REQUIRED":
            auth_required(db, job, profile, session, exc.code, str(exc))
            result_key = "auth"
        else:
            db.update_job(
                job.id,
                {
                    "status": "ERROR",
                    "error_code": exc.code,
                    "error_message": str(exc)[:1000],
                    "locked_at": None,
                    "locked_by": None,
                    "lock_expires_at": None,
                },
            )
            result_key = "error"

        db.audit(
            {
                "publication_id": job.id,
                "owner_id": job.owner_id,
                "client_id": job.client_id,
                "platform": job.platform,
                "method": "BROWSER",
                "expected_account": exp_url,
                "started_at": started,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "media_count": len(files),
                "github_run_id": os.getenv("GITHUB_RUN_ID"),
                "github_sha": os.getenv("GITHUB_SHA"),
                "browser_profile_id": profile.get("id"),
                "status": "ERROR",
                "error_code": exc.code,
                "error_message": str(exc)[:1000],
            }
        )
        return result_key

    except DownloadError as exc:
        db.update_job(
            job.id,
            {
                "status": "ERROR",
                "error_code": "NETWORK_ERROR",
                "error_message": str(exc)[:1000],
                "locked_at": None,
                "locked_by": None,
                "lock_expires_at": None,
            },
        )
        return "error"

    except Exception as exc:
        code = "UPLOAD_TIMEOUT" if "timeout" in str(exc).lower() else "TEMPORARY_PLATFORM_ERROR"
        db.update_job(
            job.id,
            {
                "status": "ERROR",
                "error_code": code,
                "error_message": str(exc)[:1000],
                "locked_at": None,
                "locked_by": None,
                "lock_expires_at": None,
            },
        )
        return "error"

    finally:
        shutil.rmtree(settings.browser_root / ".tmp" / job.id, ignore_errors=True)


def run_due(db: Database, settings) -> dict[str, int]:
    rows = db.claim_due(settings.worker_id, settings.claim_limit)
    results = {"api": 0, "published": 0, "dry": 0, "auth": 0, "error": 0}
    for row in rows:
        key = process_one(db, settings, row)
        results[key] = results.get(key, 0) + 1
    return results
