#!/usr/bin/env python3
"""Atomically persist changed F1 final-queue jobs to GitHub main.

The publisher can create external Buffer posts before another process pushes a
new communication to main. A normal git push can then lose the race. This
script merges only the locally changed queue jobs into the latest remote JSON
and updates the file with GitHub's contents API using the current blob SHA.

A SHA conflict is retried against the newest remote version, preserving new
jobs that arrived concurrently.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

QUEUE_REPO_PATH = "publisher/final_content_queue.json"
API_VERSION = "2022-11-28"
MAX_ATTEMPTS = 5


class PersistError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def job_map(queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for job in queue.get("jobs") or []:
        job_id = str(job.get("id") or "")
        if job_id:
            result[job_id] = job
    return result


def changed_job_ids(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    old = job_map(before)
    new = job_map(after)
    return {
        job_id
        for job_id in set(old) | set(new)
        if old.get(job_id) != new.get(job_id)
    }


def changed_top_level_keys(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    keys = (set(before) | set(after)) - {"jobs"}
    return {key for key in keys if before.get(key) != after.get(key)}


def merge_queue(
    remote: dict[str, Any],
    after: dict[str, Any],
    changed_ids: set[str],
    changed_keys: set[str],
) -> dict[str, Any]:
    merged = json.loads(json.dumps(remote, ensure_ascii=False))
    remote_jobs = list(merged.get("jobs") or [])
    positions = {
        str(job.get("id") or ""): index
        for index, job in enumerate(remote_jobs)
        if str(job.get("id") or "")
    }
    desired = job_map(after)

    for job_id in sorted(changed_ids):
        job = desired.get(job_id)
        if job is None:
            # Queue deletions are intentionally not propagated by the autonomous
            # publisher. This avoids deleting a concurrently-created job.
            continue
        if job_id in positions:
            remote_jobs[positions[job_id]] = job
        else:
            positions[job_id] = len(remote_jobs)
            remote_jobs.append(job)

    merged["jobs"] = remote_jobs
    for key in changed_keys:
        if key == "jobs":
            continue
        if key in after:
            merged[key] = after[key]
    return merged


def github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "F1-Autonomous-Publisher/1.0",
    }


def fetch_remote(api_url: str, token: str) -> tuple[dict[str, Any], str]:
    response = requests.get(
        api_url,
        headers=github_headers(token),
        params={"ref": "main"},
        timeout=60,
    )
    if not response.ok:
        raise PersistError(f"GitHub GET {response.status_code}: {response.text[:1000]}")
    payload = response.json()
    encoded = str(payload.get("content") or "").replace("\n", "")
    sha = str(payload.get("sha") or "")
    if not encoded or not sha:
        raise PersistError("GitHub queue response missing content/sha")
    queue = json.loads(base64.b64decode(encoded).decode("utf-8"))
    return queue, sha


def put_remote(api_url: str, token: str, sha: str, queue: dict[str, Any]) -> requests.Response:
    raw = (json.dumps(queue, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return requests.put(
        api_url,
        headers=github_headers(token),
        json={
            "message": "Persist F1 publication state",
            "content": base64.b64encode(raw).decode("ascii"),
            "sha": sha,
            "branch": "main",
        },
        timeout=90,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", default=QUEUE_REPO_PATH)
    args = parser.parse_args()

    before = load_json(Path(args.before))
    after = load_json(Path(args.after))
    changed_ids = changed_job_ids(before, after)
    changed_keys = changed_top_level_keys(before, after)
    if not changed_ids and not changed_keys:
        print("NOOP: no durable final queue changes")
        return 0

    token = os.getenv("GITHUB_TOKEN", "").strip()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not token or "/" not in repository:
        raise PersistError("GITHUB_TOKEN/GITHUB_REPOSITORY unavailable")

    api_url = f"https://api.github.com/repos/{repository}/contents/{QUEUE_REPO_PATH}"
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        remote, sha = fetch_remote(api_url, token)
        merged = merge_queue(remote, after, changed_ids, changed_keys)

        if merged == remote:
            print("NOOP: remote queue already contains the desired publication state")
            return 0

        response = put_remote(api_url, token, sha, merged)
        if response.ok:
            result = response.json()
            commit_sha = str((result.get("commit") or {}).get("sha") or "")
            print(
                json.dumps(
                    {
                        "status": "PERSISTED",
                        "attempt": attempt,
                        "changed_jobs": sorted(changed_ids),
                        "commit_sha": commit_sha,
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        last_error = f"GitHub PUT {response.status_code}: {response.text[:1000]}"
        if response.status_code not in {409, 422}:
            break
        time.sleep(min(attempt * 2, 8))

    raise PersistError(f"Unable to persist final queue after {MAX_ATTEMPTS} attempts: {last_error}")


if __name__ == "__main__":
    raise SystemExit(main())
