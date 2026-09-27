from __future__ import annotations

import argparse

from .config import Settings
from .database import Database
from .runtime import run_due


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-only", action="store_true")
    parser.add_argument("--browser-only", action="store_true")
    args = parser.parse_args()

    settings = Settings.from_env()
    db = Database(settings.supabase_url, settings.service_role_key)

    stats = db.sync_from_calendar()
    reactivated = db.reactivate_auth_ready()
    print(f"QUEUE_SYNC={stats} AUTH_REACTIVATED={reactivated}")

    if args.sync_only:
        return 0

    results = run_due(db, settings)
    print("CLOUD_BROWSER_RESULT=" + str(results))
    return 1 if results.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
