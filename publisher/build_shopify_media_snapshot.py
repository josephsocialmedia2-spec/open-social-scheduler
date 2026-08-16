#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from shopify_public_media import extract

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "publisher" / "clients" / "real-media-pro.json"
OUT = ROOT / "publisher" / "shopify_media_snapshot.json"


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    urls = cfg.get("campaign", {}).get("shopify_public_sources", [])
    pages = []
    for url in urls:
        try:
            media = extract(str(url))
            pages.append({
                "page_url": media.page_url,
                "title": media.title,
                "images": media.images[:40],
                "videos": media.videos[:20],
                "status": "ok",
            })
        except Exception as exc:
            pages.append({"page_url": str(url), "title": str(url), "images": [], "videos": [], "status": "error", "error": str(exc)})
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "client_id": "real-media-pro",
        "pages": pages,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Snapshot: {sum(len(p['images']) for p in pages)} images, {sum(len(p['videos']) for p in pages)} videos from {len(pages)} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
