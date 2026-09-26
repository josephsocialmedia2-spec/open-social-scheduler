#!/usr/bin/env python3
"""Snapshot Postiz analytics and persist tenant-scoped raw metrics for F1 Social.

The provider payload is stored as-is. No cross-platform metric is invented or
normalized unless a future explicit mapping is added.
"""
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

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
REQUEST_TIMEOUT = 90


def fetch_analytics(integration_id: str) -> Any:
    response = requests.get(
        f"{API_BASE}/analytics/{integration_id}",
        headers={"Authorization": API_KEY},
        params={"date": str(DAYS)},
        timeout=REQUEST_TIMEOUT,
    )
    if not response.ok:
        return {"error": f"{response.status_code}: {response.text[:500]}"}
    return response.json()


def supabase_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def load_supabase_clients() -> dict[str, dict[str, Any]]:
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        return {}
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/f1_content_clients",
        headers=supabase_headers(),
        params={"select": "id,owner_id,slug,name"},
        timeout=45,
    )
    if not response.ok:
        raise RuntimeError(
            f"Supabase client lookup failed {response.status_code}: {response.text[:500]}"
        )
    return {
        str(row.get("slug") or ""): row
        for row in response.json()
        if row.get("slug") and row.get("id") and row.get("owner_id")
    }


def persist_snapshot(
    client_row: dict[str, Any],
    *,
    platform: str,
    integration_id: str,
    metrics: Any,
    captured_at: str,
) -> None:
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        return
    error = metrics.get("error") if isinstance(metrics, dict) else None
    payload = {
        "owner_id": client_row["owner_id"],
        "client_id": client_row["id"],
        "platform": platform,
        "provider": "postiz",
        "integration_id": integration_id,
        "lookback_days": DAYS,
        "metrics": metrics if isinstance(metrics, (dict, list)) else {"value": metrics},
        "error": error,
        "snapshot_date": captured_at[:10],
        "captured_at": captured_at,
    }
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/f1_social_analytics_snapshots",
        headers=supabase_headers(
            {
                "Prefer": "resolution=merge-duplicates,return=minimal",
            }
        ),
        params={
            "on_conflict": "client_id,platform,provider,lookback_days,snapshot_date",
        },
        json=payload,
        timeout=45,
    )
    if not response.ok:
        raise RuntimeError(
            f"Supabase analytics upsert failed {response.status_code}: {response.text[:500]}"
        )


def main() -> int:
    if not API_KEY:
        print("POSTIZ_API_KEY missing; analytics sync skipped safely.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        supabase_clients = load_supabase_clients()
    except Exception as exc:
        # Provider snapshots are still written to disk. A persistence failure must
        # not erase the analytics source or expose credentials.
        print(f"WARN Supabase analytics persistence unavailable: {type(exc).__name__}: {exc}")
        supabase_clients = {}

    persisted = 0
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
        client_row = supabase_clients.get(str(cfg.get("id") or ""))

        for platform, integ in cfg.get("integrations", {}).items():
            integration_id = str(integ.get("id") or "").strip()
            if not integration_id:
                continue
            metrics = fetch_analytics(integration_id)
            snapshot["platforms"][platform] = {
                "integration_id": integration_id,
                "metrics": metrics,
            }
            if client_row:
                try:
                    persist_snapshot(
                        client_row,
                        platform=str(platform),
                        integration_id=integration_id,
                        metrics=metrics,
                        captured_at=now,
                    )
                    persisted += 1
                except Exception as exc:
                    print(
                        "WARN analytics snapshot not persisted "
                        f"{cfg['id']}:{platform}: {type(exc).__name__}: {exc}"
                    )

        out = OUT_DIR / f"{cfg['id']}.json"
        out.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Analytics -> {out.relative_to(ROOT)}")

    if supabase_clients:
        print(f"Supabase analytics snapshots persisted: {persisted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
