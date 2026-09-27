from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def default_browser_root() -> Path:
    configured = (os.getenv("F1_BROWSER_ROOT") or "").strip()
    if configured:
        return Path(configured)
    if os.name == "nt":
        return Path(r"C:\F1Social\BrowserProfiles")
    return Path("/srv/f1social/browser-profiles")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    service_role_key: str
    browser_root: Path
    storage_bucket: str
    dry_run: bool
    worker_id: str
    claim_limit: int

    @classmethod
    def from_env(cls) -> "Settings":
        url = (
            os.getenv("SUPABASE_URL")
            or "https://nqnmlsmeiynxbdojeyjt.supabase.co"
        ).rstrip("/")
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required")
        root = default_browser_root()
        dry = (os.getenv("DRY_RUN") or "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        worker = (
            os.getenv("GITHUB_RUN_ID")
            or os.getenv("F1_WORKER_ID")
            or "f1-social-local-pc"
        ).strip()
        limit = int(os.getenv("F1_CLAIM_LIMIT") or "10")
        return cls(
            url,
            key,
            root,
            os.getenv("F1_CONTENT_BUCKET") or "f1-content-media",
            dry,
            worker,
            max(1, min(limit, 50)),
        )
