from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CANONICAL_PLATFORMS = {"facebook", "instagram", "tiktok", "youtube", "linkedin-page"}


def normalize_platform(value: str) -> str:
    p = str(value or "").strip().lower().replace("_", "-")
    if p == "linkedin":
        return "linkedin-page"
    return p


@dataclass
class PublicationJob:
    id: str
    owner_id: str
    client_id: str
    content_id: str
    calendar_id: str | None
    platform: str
    scheduled_at: str
    content_type: str
    caption: str
    media_payload: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    attempt_count: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "PublicationJob":
        platform = normalize_platform(row.get("platform", ""))
        if platform not in CANONICAL_PLATFORMS:
            raise ValueError(f"Unsupported platform: {platform}")
        media = row.get("media_payload") or []
        if isinstance(media, dict):
            media = [media]
        if not isinstance(media, list):
            raise ValueError("media_payload must be a list")
        return cls(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            client_id=str(row["client_id"]),
            content_id=str(row["content_id"]),
            calendar_id=str(row["calendar_id"]) if row.get("calendar_id") else None,
            platform=platform,
            scheduled_at=str(row["scheduled_at"]),
            content_type=str(row.get("content_type") or "post"),
            caption=str(row.get("caption") or ""),
            media_payload=[x for x in media if isinstance(x, dict)],
            metadata=row.get("metadata") or {},
            attempt_count=int(row.get("attempt_count") or 0),
        )
