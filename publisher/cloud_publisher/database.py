from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from .queue import normalize_platform


PUBLISHED_STATES = {"PUBBLICATO", "PUBLISHED", "COMPLETED", "SUCCESS"}
ACTIVE_CALENDAR_STATES = {
    "PROGRAMMATO", "APPROVATO", "IN PUBBLICAZIONE", "ERRORE_PUBBLICAZIONE",
    "CANALE_DA_COLLEGARE", "CREDENZIALI_MANCANTI", "AUTH_REQUIRED", "DA_RIAUTORIZZARE",
}


class Database:
    def __init__(self, url: str, service_key: str, timeout: int = 45) -> None:
        self.url = url.rstrip("/")
        self.key = service_key
        self.timeout = timeout

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def get(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        r = requests.get(
            f"{self.url}/rest/v1/{table}",
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
        )
        if not r.ok:
            raise RuntimeError(f"GET {table}: {r.status_code} {r.text[:800]}")
        data = r.json()
        return data if isinstance(data, list) else [data]

    def patch(self, table: str, match: dict[str, str], payload: dict[str, Any]) -> None:
        params = {k: f"eq.{v}" for k, v in match.items()}
        r = requests.patch(
            f"{self.url}/rest/v1/{table}",
            headers=self._headers({"Prefer": "return=minimal"}),
            params=params,
            json=payload,
            timeout=self.timeout,
        )
        if not r.ok:
            raise RuntimeError(f"PATCH {table}: {r.status_code} {r.text[:800]}")

    def post(
        self,
        table: str,
        payload: dict[str, Any] | list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        params = {"on_conflict": on_conflict} if on_conflict else None
        prefer = "resolution=merge-duplicates,return=minimal" if on_conflict else "return=minimal"
        r = requests.post(
            f"{self.url}/rest/v1/{table}",
            headers=self._headers({"Prefer": prefer}),
            params=params,
            json=payload,
            timeout=self.timeout,
        )
        if not r.ok:
            raise RuntimeError(f"POST {table}: {r.status_code} {r.text[:800]}")

    def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        r = requests.post(
            f"{self.url}/rest/v1/rpc/{name}",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        if not r.ok:
            raise RuntimeError(f"RPC {name}: {r.status_code} {r.text[:800]}")
        return r.json() if r.text.strip() else None

    def sync_from_calendar(self) -> dict[str, int]:
        rows = self.get(
            "f1_content_calendar",
            {
                "select": (
                    "id,owner_id,content_id,client_id,platform,publication_at,status,external_post_id,"
                    "external_url,error,platform_metadata,"
                    "f1_content_items(id,title,description,source_text,status,content_type,"
                    "f1_content_media(id,file_name,mime_type,storage_path,file_size,archive_url,storage_state,hot_deleted_at)),"
                    "f1_content_clients(id,name,slug,timezone)"
                ),
                "order": "publication_at.asc",
                "limit": "1000",
            },
        )
        stats = {"upserted": 0, "published": 0, "skipped": 0}
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            item = row.get("f1_content_items") or {}
            client = row.get("f1_content_clients") or {}
            if not item or not client:
                stats["skipped"] += 1
                continue
            platform = normalize_platform(row.get("platform", ""))
            if platform not in {"facebook", "instagram", "tiktok", "youtube", "linkedin-page"}:
                stats["skipped"] += 1
                continue
            calendar_status = str(row.get("status") or "").upper()
            if calendar_status in PUBLISHED_STATES:
                self.patch(
                    "f1_publication_queue",
                    {"calendar_id": str(row["id"])},
                    {
                        "status": "PUBLISHED",
                        "published_at": now,
                        "external_post_id": row.get("external_post_id"),
                        "external_post_url": row.get("external_url"),
                        "error_code": None,
                        "error_message": None,
                        "locked_at": None,
                        "locked_by": None,
                        "lock_expires_at": None,
                        "updated_at": now,
                    },
                )
                stats["published"] += 1
                continue
            if calendar_status not in ACTIVE_CALENDAR_STATES:
                stats["skipped"] += 1
                continue
            metadata = row.get("platform_metadata") or {}
            caption = str(
                metadata.get("caption")
                or item.get("description")
                or item.get("source_text")
                or ""
            ).strip()
            media = item.get("f1_content_media") or []
            if isinstance(media, dict):
                media = [media]
            queue_status = (
                "AUTH_REQUIRED"
                if calendar_status in {"AUTH_REQUIRED", "DA_RIAUTORIZZARE", "CREDENZIALI_MANCANTI"}
                else "SCHEDULED"
            )
            payload = {
                "owner_id": row["owner_id"],
                "client_id": row["client_id"],
                "calendar_id": row["id"],
                "content_id": row["content_id"],
                "platform": platform,
                "scheduled_at": row["publication_at"],
                "timezone": str(client.get("timezone") or "Europe/Rome"),
                "content_type": str(item.get("content_type") or "post"),
                "caption": caption,
                "media_payload": media,
                "status": queue_status,
                "approval_status": "APPROVED",
                "error_code": str(row.get("error") or "")[:120] or None,
                "error_message": str(row.get("error") or "")[:1000] or None,
                "metadata": {
                    "client_name": client.get("name"),
                    "client_slug": client.get("slug"),
                    "content_title": item.get("title"),
                    "calendar_status": calendar_status,
                    "platform_metadata": metadata,
                },
                "updated_at": now,
            }
            self.post(
                "f1_publication_queue",
                payload,
                on_conflict="owner_id,client_id,content_id,platform,scheduled_at",
            )
            stats["upserted"] += 1
        return stats

    def reactivate_auth_ready(self) -> int:
        rows = self.get(
            "f1_publication_queue",
            {"select": "id,client_id,platform,status", "status": "eq.AUTH_REQUIRED", "limit": "500"},
        )
        changed = 0
        for row in rows:
            sessions = self.get(
                "f1_client_browser_social_sessions",
                {
                    "select": "id,status",
                    "client_id": f"eq.{row['client_id']}",
                    "platform": f"eq.{row['platform']}",
                    "limit": "1",
                },
            )
            if sessions and sessions[0].get("status") == "CONNECTED":
                self.patch(
                    "f1_publication_queue",
                    {"id": str(row["id"])},
                    {
                        "status": "SCHEDULED",
                        "error_code": None,
                        "error_message": None,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                changed += 1
        return changed

    def claim_due(self, worker_id: str, limit: int) -> list[dict[str, Any]]:
        data = self.rpc(
            "f1_claim_due_publications",
            {"p_worker": worker_id, "p_limit": limit},
        ) or []
        return data if isinstance(data, list) else []

    def client(self, client_id: str) -> dict[str, Any] | None:
        rows = self.get(
            "f1_content_clients",
            {"select": "*", "id": f"eq.{client_id}", "limit": "1"},
        )
        return rows[0] if rows else None

    def channel(self, client_id: str, platform: str) -> dict[str, Any] | None:
        rows = self.get(
            "f1_client_social_channels",
            {
                "select": "*",
                "client_id": f"eq.{client_id}",
                "platform": f"eq.{platform}",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def browser_profile(self, client_id: str) -> dict[str, Any] | None:
        rows = self.get(
            "f1_client_browser_profiles",
            {"select": "*", "client_id": f"eq.{client_id}", "limit": "1"},
        )
        return rows[0] if rows else None

    def browser_session(self, client_id: str, platform: str) -> dict[str, Any] | None:
        rows = self.get(
            "f1_client_browser_social_sessions",
            {
                "select": "*",
                "client_id": f"eq.{client_id}",
                "platform": f"eq.{platform}",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def update_job(self, job_id: str, payload: dict[str, Any]) -> None:
        self.patch(
            "f1_publication_queue",
            {"id": job_id},
            {**payload, "updated_at": datetime.now(timezone.utc).isoformat()},
        )

    def update_calendar(self, calendar_id: str | None, payload: dict[str, Any]) -> None:
        if calendar_id:
            self.patch(
                "f1_content_calendar",
                {"id": calendar_id},
                {**payload, "updated_at": datetime.now(timezone.utc).isoformat()},
            )

    def update_browser_session(self, session_id: str | None, payload: dict[str, Any]) -> None:
        if session_id:
            self.patch(
                "f1_client_browser_social_sessions",
                {"id": session_id},
                {**payload, "updated_at": datetime.now(timezone.utc).isoformat()},
            )

    def update_browser_profile(self, profile_id: str | None, payload: dict[str, Any]) -> None:
        if profile_id:
            self.patch(
                "f1_client_browser_profiles",
                {"id": profile_id},
                {**payload, "updated_at": datetime.now(timezone.utc).isoformat()},
            )

    def audit(self, payload: dict[str, Any]) -> None:
        safe = dict(payload)
        for forbidden in (
            "password", "cookie", "cookies", "token", "access_token",
            "refresh_token", "secret",
        ):
            safe.pop(forbidden, None)
        self.post("f1_publication_audit", safe)
