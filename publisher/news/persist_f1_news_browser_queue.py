#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

QUEUE_REPO_PATH = "publisher/news/f1_news_browser_queue.json"
API_VERSION = "2022-11-28"
MAX_ATTEMPTS = 5


class PersistError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def item_map(queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in queue.get("items") or []:
        item_id = str(item.get("id") or "")
        if item_id:
            result[item_id] = item
    return result


def changed_item_ids(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    old = item_map(before)
    new = item_map(after)
    return {
        item_id
        for item_id in set(old) | set(new)
        if old.get(item_id) != new.get(item_id)
    }


def github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "F1-News-Browser-Control/1.0",
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
        raise PersistError("GitHub browser queue response missing content/sha")
    return json.loads(base64.b64decode(encoded).decode("utf-8")), sha


def merge_queue(
    remote: dict[str, Any],
    after: dict[str, Any],
    changed_ids: set[str],
) -> dict[str, Any]:
    merged = json.loads(json.dumps(remote, ensure_ascii=False))
    remote_items = list(merged.get("items") or [])
    positions = {
        str(item.get("id") or ""): idx
        for idx, item in enumerate(remote_items)
        if str(item.get("id") or "")
    }
    desired = item_map(after)

    for item_id in sorted(changed_ids):
        item = desired.get(item_id)
        if item is None:
            continue
        if item_id in positions:
            remote_items[positions[item_id]] = item
        else:
            positions[item_id] = len(remote_items)
            remote_items.append(item)

    merged["items"] = remote_items

    # Rejections are diagnostics only; merge by source_hash+error to avoid loss.
    remote_rejected = list(merged.get("rejected") or [])
    seen = {
        (
            str(x.get("source_hash") or ""),
            str(x.get("error") or ""),
        )
        for x in remote_rejected
    }
    for row in after.get("rejected") or []:
        key = (str(row.get("source_hash") or ""), str(row.get("error") or ""))
        if key not in seen:
            remote_rejected.append(row)
            seen.add(key)
    merged["rejected"] = remote_rejected[-100:]
    merged["version"] = after.get("version", remote.get("version", 1))
    merged["updated_at"] = after.get("updated_at") or remote.get("updated_at")
    return merged


def put_remote(api_url: str, token: str, sha: str, queue: dict[str, Any]) -> requests.Response:
    raw = (json.dumps(queue, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return requests.put(
        api_url,
        headers=github_headers(token),
        json={
            "message": "Persist F1 News browser queue",
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
    changed_ids = changed_item_ids(before, after)
    rejected_changed = before.get("rejected") != after.get("rejected")
    updated_changed = before.get("updated_at") != after.get("updated_at")
    if not changed_ids and not rejected_changed and not updated_changed:
        print("NOOP: no durable F1 News browser queue changes")
        return 0

    token = os.getenv("GITHUB_TOKEN", "").strip()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not token or "/" not in repository:
        raise PersistError("GITHUB_TOKEN/GITHUB_REPOSITORY unavailable")

    api_url = f"https://api.github.com/repos/{repository}/contents/{QUEUE_REPO_PATH}"
    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        remote, sha = fetch_remote(api_url, token)
        merged = merge_queue(remote, after, changed_ids)
        if merged == remote:
            print("NOOP: remote browser queue already contains desired state")
            return 0
        response = put_remote(api_url, token, sha, merged)
        if response.ok:
            result = response.json()
            commit_sha = str((result.get("commit") or {}).get("sha") or "")
            print(json.dumps({
                "status": "PERSISTED",
                "attempt": attempt,
                "changed_items": sorted(changed_ids),
                "commit_sha": commit_sha,
            }, ensure_ascii=False))
            return 0
        last_error = f"GitHub PUT {response.status_code}: {response.text[:1000]}"
        if response.status_code not in {409, 422}:
            break
        time.sleep(min(attempt * 2, 8))

    raise PersistError(
        f"Unable to persist F1 News browser queue after {MAX_ATTEMPTS} attempts: {last_error}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
