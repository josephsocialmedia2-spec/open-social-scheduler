#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
CONTROL_PATH = ROOT / "publisher" / "chatgpt_query_runner" / "f1_daily_creative_control.json"
FINAL_QUEUE = ROOT / "publisher" / "final_content_queue.json"
STATUS_PATH = ROOT / "publisher" / "chatgpt_query_runner" / "f1_daily_creative_live_status.json"
REPO = os.getenv("GITHUB_REPOSITORY", "josephsocialmedia2-spec/open-social-scheduler").strip()
TOKEN = os.getenv("GITHUB_TOKEN", "").strip()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def find_final(payload: dict[str, Any], communication_id: str) -> dict[str, Any] | None:
    for row in payload.get("jobs") or []:
        if str(row.get("communication_id") or "") == communication_id:
            return row
    return None


def latest_run() -> dict[str, Any]:
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/f1-daily-creative-pc-immediate.yml/runs?per_page=5"
    headers = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        runs = r.json().get("workflow_runs") or []
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


def core(payload: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(payload, ensure_ascii=False))
    clone.pop("last_changed_at", None)
    return clone


def main() -> int:
    control = load_json(CONTROL_PATH, {})
    communication_id = str(control.get("expected_communication_id") or "")
    final_payload = load_json(FINAL_QUEUE, {"jobs": []})
    final = find_final(final_payload, communication_id) if communication_id else None

    hosted = [
        str(x).strip()
        for x in ((final or {}).get("hosted_asset_urls") or [])
        if str(x).strip()
    ]
    repo_links: list[str] = []
    for raw in (final or {}).get("assets") or []:
        path_value = str(raw.get("path") if isinstance(raw, dict) else raw or "").strip()
        if path_value and (ROOT / path_value).is_file():
            repo_links.append(f"https://github.com/{REPO}/blob/main/{path_value}")

    graphic_url = str((final or {}).get("graphic_url") or "").strip()
    if not graphic_url and hosted:
        graphic_url = hosted[0]
    if not graphic_url and repo_links:
        graphic_url = repo_links[0]

    status = {
        "communication_id": communication_id,
        "query_id": control.get("target_query_id") or "",
        "search_intent": "QUANTO VALE CASA MIA",
        "variant": "A",
        "control_status": control.get("status") or "",
        "final_status": (final or {}).get("status") or "NOT_CREATED",
        "last_step": (final or {}).get("last_step") or "",
        "graphic_ready": bool(graphic_url),
        "graphic_url": graphic_url,
        "hosted_asset_urls": hosted,
        "repository_asset_links": repo_links,
        "remote_post_ids": (final or {}).get("remote_post_ids") or [],
        "remote_post_urls": (final or {}).get("remote_post_urls") or (final or {}).get("published_urls") or [],
        "sha256": ((final or {}).get("assets") or [{}])[0].get("sha256") if (final or {}).get("assets") else "",
        "pc_workflow": latest_run(),
    }

    existing = load_json(STATUS_PATH, {})
    if core(existing) == core(status):
        print(json.dumps({"status": "NO_CHANGE", **status}, ensure_ascii=False))
        return 0

    status["last_changed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "UPDATED", **status}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
