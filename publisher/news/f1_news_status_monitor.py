#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
BROWSER_QUEUE = ROOT / "publisher" / "news" / "f1_news_browser_queue.json"
FINAL_QUEUE = ROOT / "publisher" / "final_content_queue.json"
STATUS_PATH = ROOT / "publisher" / "news" / "f1_news_live_status.json"
TARGET = os.getenv("F1_NEWS_TARGET", "COMM-NEWS-20260921-EVENING-E6871421").strip()
REPO = os.getenv("GITHUB_REPOSITORY", "josephsocialmedia2-spec/open-social-scheduler").strip()
TOKEN = os.getenv("GITHUB_TOKEN", "").strip()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def find_job(payload: dict[str, Any], target: str) -> dict[str, Any] | None:
    for row in payload.get("jobs") or payload.get("items") or []:
        if str(row.get("communication_id") or "") == target or str(row.get("id") or "") == target:
            return row
    return None


def asset_links(job: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    if not job:
        return [], []
    urls = [str(x).strip() for x in (job.get("hosted_asset_urls") or []) if str(x).strip()]
    repo_links: list[str] = []
    for raw in job.get("assets") or []:
        path_value = str(raw.get("path") if isinstance(raw, dict) else raw or "").strip()
        if not path_value:
            continue
        file_path = ROOT / path_value
        if file_path.is_file():
            repo_links.append(f"https://github.com/{REPO}/blob/main/{path_value}")
    return urls, repo_links


def latest_pc_run() -> dict[str, Any]:
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/f1-news-pc-immediate.yml/runs?per_page=5"
    headers = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        runs = response.json().get("workflow_runs") or []
        if not runs:
            return {}
        row = runs[0]
        return {
            "id": row.get("id"),
            "status": row.get("status"),
            "conclusion": row.get("conclusion"),
            "html_url": row.get("html_url"),
            "updated_at": row.get("updated_at"),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def normalize_core(status: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(status, ensure_ascii=False))
    clone.pop("last_changed_at", None)
    return clone


def main() -> int:
    browser_payload = load_json(BROWSER_QUEUE, {"items": []})
    final_payload = load_json(FINAL_QUEUE, {"jobs": []})
    browser = find_job(browser_payload, TARGET)
    final = find_job(final_payload, TARGET)

    hosted_urls, repo_asset_links = asset_links(final)
    graphic_url = ""
    if hosted_urls:
        graphic_url = hosted_urls[0]
    elif repo_asset_links:
        graphic_url = repo_asset_links[0]

    remote_urls = []
    if final:
        remote_urls = [str(x).strip() for x in (final.get("remote_post_urls") or final.get("published_urls") or []) if str(x).strip()]

    state = {
        "communication_id": TARGET,
        "headline": (final or browser or {}).get("headline") or "",
        "browser_status": (browser or {}).get("status") or "NOT_FOUND",
        "final_status": (final or {}).get("status") or "NOT_CREATED",
        "last_step": (final or {}).get("last_step") or "",
        "force_immediate": bool((browser or {}).get("force_immediate")),
        "slot_key": (browser or {}).get("slot_key") or (final or {}).get("slot_key") or "",
        "graphic_ready": bool(graphic_url),
        "graphic_url": graphic_url,
        "hosted_asset_urls": hosted_urls,
        "repository_asset_links": repo_asset_links,
        "remote_post_urls": remote_urls,
        "remote_post_ids": (final or {}).get("remote_post_ids") or [],
        "pc_workflow": latest_pc_run(),
    }

    existing = load_json(STATUS_PATH, {})
    if normalize_core(existing) == normalize_core(state):
        print(json.dumps({"status": "NO_CHANGE", **state}, ensure_ascii=False))
        return 0

    state["last_changed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    STATUS_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "UPDATED", **state}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
