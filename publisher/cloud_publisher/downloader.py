from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


class DownloadError(RuntimeError):
    pass


def safe_name(value: str, fallback: str) -> str:
    name = Path(str(value or fallback)).name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return clean or fallback


def download_media(
    job_id: str,
    media: list[dict[str, Any]],
    *,
    root: Path,
    supabase_url: str,
    service_key: str,
    bucket: str,
) -> list[Path]:
    target = root / ".tmp" / job_id
    target.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for index, item in enumerate(media, 1):
        name = safe_name(
            str(item.get("file_name") or f"media-{index}.bin"),
            f"media-{index}.bin",
        )
        dest = target / name
        direct = str(item.get("url") or item.get("public_url") or "").strip()
        storage_path = str(item.get("storage_path") or "").lstrip("/")
        headers: dict[str, str] = {}
        if direct:
            url = direct
        elif storage_path:
            encoded = "/".join(quote(part, safe="") for part in storage_path.split("/"))
            url = f"{supabase_url}/storage/v1/object/{bucket}/{encoded}"
            headers = {
                "Authorization": f"Bearer {service_key}",
                "apikey": service_key,
            }
        else:
            raise DownloadError(f"media {index} has no URL or storage_path")
        r = requests.get(url, headers=headers, timeout=120)
        if not r.ok:
            raise DownloadError(f"download failed {r.status_code} for {name}")
        dest.write_bytes(r.content)
        if dest.stat().st_size <= 0:
            raise DownloadError(f"empty media file: {name}")
        expected_size = item.get("file_size")
        if expected_size and int(expected_size) != dest.stat().st_size:
            raise DownloadError(f"size mismatch for {name}")
        item["sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
        item["mime_type"] = (
            item.get("mime_type")
            or mimetypes.guess_type(name)[0]
            or "application/octet-stream"
        )
        out.append(dest)
    return out
