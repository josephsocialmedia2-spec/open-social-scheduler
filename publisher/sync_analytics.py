#!/usr/bin/env python3
"""Snapshot Postiz platform analytics for every configured client integration."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "publisher" / "clients"
OUT_DIR = ROOT / "publisher" / "analytics"
API_BASE = os.getenv("POSTIZ_API_URL", "https://api.postiz.com/public/v1").rstrip("/")
API_KEY = os.getenv("POSTIZ_API_KEY", "").strip()
DAYS = int(os.getenv("ANALYTICS_DAYS", "30"))


def fetch_analytics(integration_id: str) -> Any:
    response = requests.get(
        f"{API_BASE}/analytics/{integration_id}",
        headers={"Authorization": API_KEY},
        params={"date": str(DAYS)},
        timeout=90,
    )
    if not response.ok:
        return {"error": f"{response.status_code}: {response.text[:500]}"}
    return response.json()


def main() -> int:
    if not API_KEY:
        print("POSTIZ_API_KEY missing; analytics sync skipped safely.")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for path in sorted(CLIENT_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if not cfg.get("active", False):
            continue
        snapshot: dict[str, Any] = {
            "client_id": cfg["id"],
            "client_name": cfg.get("name", cfg["id"]),
            "generated_at": now,
            "lookback_days": DAYS,
            "platforms": {},
        }
        for platform, integ in cfg.get("integrations", {}).items():
            integration_id = str(integ.get("id") or "").strip()
            if not integration_id:
                continue
            snapshot["platforms"][platform] = {
                "integration_id": integration_id,
                "metrics": fetch_analytics(integration_id),
            }
        out = OUT_DIR / f"{cfg['id']}.json"
        out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Analytics -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
