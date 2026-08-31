#!/usr/bin/env python3
"""Read-only connectivity pilot for F1 Immobiliare and Real Media Pro.

This script NEVER publishes, creates media containers, changes queues, or writes
social state. It only validates local safety gates, checks whether the required
Meta secrets are present, and (when present) performs read-only Graph API calls.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "publisher" / "clients"
APPROVAL_DIR = ROOT / "publisher" / "approvals"
REPORT_PATH = ROOT / "publisher" / "pilot_social_report.json"
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0").strip() or "v23.0"

CLIENTS = (
    ("f1-immobiliare", "F1"),
    ("real-media-pro", "RMP"),
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def graph_get(path: str, token: str, fields: str) -> dict[str, Any]:
    params = urllib.parse.urlencode({"fields": fields, "access_token": token})
    url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{path}?{params}"
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "F1-RMP-Social-Pilot/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {"ok": True, "status": response.status, "data": json.loads(response.read().decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1600]
        try:
            detail = json.loads(body)
        except Exception:
            detail = {"message": body}
        return {"ok": False, "status": exc.code, "error": detail}
    except Exception as exc:
        return {"ok": False, "status": None, "error": {"message": str(exc)}}


def secret_state(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def validate_client(client_id: str, expected_prefix: str) -> dict[str, Any]:
    client_path = CLIENT_DIR / f"{client_id}.json"
    approval_path = APPROVAL_DIR / f"{client_id}.json"
    client = load_json(client_path)
    approval = load_json(approval_path)

    prefix = str(client.get("publishing", {}).get("secret_prefix") or "").strip().upper()
    manual_publish_only = bool(client.get("planning", {}).get("manual_publish_only", False))
    approval_required = bool(client.get("approval", {}).get("required", False))
    approved_weeks = list(approval.get("approved") or [])

    facebook_secret = f"{expected_prefix}_FACEBOOK_PAGE_ACCESS_TOKEN"
    instagram_token_secret = f"{expected_prefix}_INSTAGRAM_ACCESS_TOKEN"
    instagram_id_secret = f"{expected_prefix}_INSTAGRAM_USER_ID"

    secrets = {
        facebook_secret: secret_state(facebook_secret),
        instagram_token_secret: secret_state(instagram_token_secret),
        instagram_id_secret: secret_state(instagram_id_secret),
    }

    facebook: dict[str, Any] = {"configured": secrets[facebook_secret], "read_only_check": None}
    if secrets[facebook_secret]:
        result = graph_get("me", os.environ[facebook_secret].strip(), "id,name")
        if result.get("ok"):
            data = result.get("data") or {}
            facebook["read_only_check"] = {"ok": True, "id": data.get("id"), "name": data.get("name")}
        else:
            facebook["read_only_check"] = {"ok": False, "status": result.get("status"), "error": result.get("error")}

    instagram: dict[str, Any] = {
        "configured": secrets[instagram_token_secret] and secrets[instagram_id_secret],
        "read_only_check": None,
    }
    if instagram["configured"]:
        ig_id = os.environ[instagram_id_secret].strip()
        result = graph_get(ig_id, os.environ[instagram_token_secret].strip(), "id,username")
        if result.get("ok"):
            data = result.get("data") or {}
            instagram["read_only_check"] = {"ok": True, "id": data.get("id"), "username": data.get("username")}
        else:
            instagram["read_only_check"] = {"ok": False, "status": result.get("status"), "error": result.get("error")}

    safety = {
        "approval_required": approval_required,
        "approved_weeks": approved_weeks,
        "no_week_currently_approved": len(approved_weeks) == 0,
        "manual_publish_only": manual_publish_only,
        "secret_prefix_matches": prefix == expected_prefix,
    }

    return {
        "client_id": client_id,
        "name": client.get("name"),
        "active": bool(client.get("active", False)),
        "safety": safety,
        "secret_presence": secrets,
        "facebook": facebook,
        "instagram": instagram,
        "pilot_ready": bool(
            client.get("active", False)
            and approval_required
            and len(approved_weeks) == 0
            and manual_publish_only
            and prefix == expected_prefix
            and facebook.get("configured")
            and instagram.get("configured")
            and (facebook.get("read_only_check") or {}).get("ok")
            and (instagram.get("read_only_check") or {}).get("ok")
        ),
    }


def main() -> int:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "READ_ONLY_NO_PUBLICATION",
        "meta_graph_version": META_GRAPH_VERSION,
        "clients": [validate_client(client_id, prefix) for client_id, prefix in CLIENTS],
    }
    report["all_ready"] = all(item["pilot_ready"] for item in report["clients"])
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Console output contains no token values.
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\nPILOT RESULT:", "READY" if report["all_ready"] else "SETUP REQUIRED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
