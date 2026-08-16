#!/usr/bin/env python3
"""Discover Postiz integration IDs and optionally bind them to client configs.

Binding is deliberately conservative: a platform is written only when exactly one
connected Postiz integration matches the client's exact `postiz_customer_name`.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / "publisher" / "clients"
API_BASE = os.getenv("POSTIZ_API_URL", "https://api.postiz.com/public/v1").rstrip("/")
API_KEY = os.getenv("POSTIZ_API_KEY", "").strip()

ALIASES = {
    "facebook": {"facebook"},
    "instagram": {"instagram", "instagram-standalone"},
    "linkedin-page": {"linkedin-page"},
    "tiktok": {"tiktok"},
    "youtube": {"youtube"},
    "pinterest": {"pinterest"},
}


def api_integrations() -> list[dict[str, Any]]:
    if not API_KEY:
        raise RuntimeError("POSTIZ_API_KEY is required")
    res = requests.get(f"{API_BASE}/integrations", headers={"Authorization": API_KEY}, timeout=60)
    res.raise_for_status()
    payload = res.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected response: {payload}")
    return payload


def load_clients() -> list[tuple[Path, dict[str, Any]]]:
    out = []
    for path in sorted(CLIENT_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        out.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return out


def customer_name(item: dict[str, Any]) -> str:
    customer = item.get("customer") or {}
    return str(customer.get("name") or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Persist unambiguous integration IDs to client configs")
    args = parser.parse_args()

    integrations = api_integrations()
    changed = 0
    for path, cfg in load_clients():
        expected_customer = str(cfg.get("postiz_customer_name") or cfg.get("name") or "").strip()
        print(f"\n[{cfg.get('id')}] expected Postiz customer: {expected_customer!r}")
        dirty = False
        for platform, platform_cfg in cfg.get("integrations", {}).items():
            if str(platform_cfg.get("id") or "").strip():
                print(f"  {platform}: already bound -> {platform_cfg['id']}")
                continue
            allowed = ALIASES.get(platform, {platform})
            candidates = [
                item for item in integrations
                if str(item.get("identifier") or "").lower() in allowed
                and customer_name(item).casefold() == expected_customer.casefold()
                and item.get("disabled") is not True
            ]
            if len(candidates) == 1:
                item = candidates[0]
                print(f"  {platform}: MATCH {item.get('name')} / {item.get('profile')} -> {item.get('id')}")
                if args.write:
                    platform_cfg["id"] = str(item["id"])
                    dirty = True
            elif len(candidates) == 0:
                print(f"  {platform}: no exact customer match")
            else:
                ids = ", ".join(str(item.get("id")) for item in candidates)
                print(f"  {platform}: AMBIGUOUS ({ids}); refusing auto-bind")

        if args.write and dirty:
            path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    print(f"\nUpdated {changed} client file(s)." if args.write else "\nDiscovery only; no files changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
