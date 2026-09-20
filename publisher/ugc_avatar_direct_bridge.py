#!/usr/bin/env python3
"""Consume UGC Avatar Studio Modal outbox through the existing direct API publisher."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import requests

import direct_api_publish as core
import direct_api_entry as compat

DEFAULT_URL = "https://joseph-socialmedia2--ugc-avatar-studio-web.modal.run"
TIMEOUT = 120


def get_json(url: str) -> dict[str, Any]:
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def download(url: str, path: Path) -> None:
    with requests.get(url, timeout=300, stream=True) as r:
        r.raise_for_status()
        with path.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
    if path.stat().st_size <= 1024:
        raise RuntimeError(f"Downloaded video is invalid: {path.stat().st_size} bytes")


def ack(base: str, modal_job_id: str, status: str) -> None:
    r = requests.post(
        f"{base}/api/jobs/{modal_job_id}/ack",
        data={"status": status},
        timeout=60,
    )
    r.raise_for_status()


def configured_platforms(job: dict[str, Any], client: dict[str, Any]) -> tuple[list[str], dict[str, list[str]]]:
    requested = []
    for raw in job.get("platforms", []):
        p = str(raw.get("platform") if isinstance(raw, dict) else raw or "").strip()
        if p and p not in requested:
            requested.append(p)
    ready: list[str] = []
    blocked: dict[str, list[str]] = {}
    for platform in requested:
        missing = core.required_secrets(platform, client)
        if missing:
            blocked[platform] = missing
        else:
            ready.append(platform)
    return ready, blocked


def process(base: str, dry_run: bool, max_jobs: int, modal_job_id: str | None = None) -> dict[str, Any]:
    compat.core.PUBLISHERS["tiktok"] = compat.tiktok_publish_fixed
    if modal_job_id:
        detail = get_json(f"{base}/api/jobs/{modal_job_id}")
        row = dict(detail.get("publisher_job") or {})
        if not row:
            raise RuntimeError(f"Modal job {modal_job_id} has no publisher_job")
        row["modal_job_id"] = modal_job_id
        row["video_url"] = f"/api/jobs/{modal_job_id}/video"
        rows = [row]
    else:
        payload = get_json(f"{base}/api/outbox?limit={max_jobs}")
        rows = payload.get("jobs") or []
    report: list[dict[str, Any]] = []

    for row in rows[:max_jobs]:
        modal_job_id = str(row.get("modal_job_id") or "").strip()
        client_id = str(row.get("client_id") or "f1-immobiliare").strip()
        if not modal_job_id:
            report.append({"status": "error", "error": "missing modal_job_id"})
            continue
        client = core.client_config(client_id)
        ready, blocked = configured_platforms(row, client)
        item: dict[str, Any] = {
            "job_id": row.get("id"),
            "modal_job_id": modal_job_id,
            "client_id": client_id,
            "ready_platforms": ready,
            "blocked_platforms": blocked,
            "dry_run": dry_run,
        }
        if not ready:
            item["status"] = "blocked_no_configured_platforms"
            report.append(item)
            continue

        with tempfile.TemporaryDirectory(prefix="ugc-direct-") as td:
            video = Path(td) / f"{modal_job_id}.mp4"
            video_url = str(row.get("video_url") or "")
            if video_url.startswith("/"):
                video_url = base + video_url
            download(video_url, video)

            job = dict(row)
            job["media"] = str(video)
            job["platforms"] = ready
            job["status"] = "ready"
            results, ok = core.publish_job(job, set(ready), dry_run)
            item["results"] = results
            item["publisher_ok"] = ok
            published = [x for x in results if x.get("status") == "published"]
            if dry_run:
                item["status"] = "dry_run_ok" if ok else "dry_run_failed"
            elif published:
                item["status"] = "published" if ok else "partially_published"
                ack(base, modal_job_id, item["status"])
            else:
                item["status"] = "publish_failed"
            report.append(item)

    return {
        "source": base,
        "dry_run": dry_run,
        "jobs_found": len(rows),
        "processed": len(report),
        "report": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("UGC_AVATAR_MODAL_URL", DEFAULT_URL))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-jobs", type=int, default=10)
    parser.add_argument("--modal-job-id", help="Validate/publish one exact Modal job, including TEST_ONLY jobs")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    if args.modal_job_id and not args.dry_run:
        raise SystemExit("--modal-job-id is restricted to --dry-run for safe certification")
    result = process(base, args.dry_run, max(1, min(args.max_jobs, 50)), args.modal_job_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    failures = [
        x for x in result["report"]
        if x.get("status") in {"blocked_no_configured_platforms", "dry_run_failed", "publish_failed"}
    ]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
