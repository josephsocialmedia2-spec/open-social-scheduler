#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import webbrowser
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python 3.8 on the existing F1 Windows runner
    ZoneInfo = None

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://nqnmlsmeiynxbdojeyjt.supabase.co").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
ARCHIVE_ROOT = Path(os.getenv("F1_WHATSAPP_ARCHIVE_ROOT", r"C:\F1Social\WhatsAppArchive"))
INBOX_ROOT = Path(os.getenv("F1_WHATSAPP_RECOVERY_INBOX", r"C:\F1Social\WhatsAppRecoveryInbox"))
REQUEST_TIMEOUT = 120
MEDIA_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif",
    ".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv",
    ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".wma",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv"}
AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac", ".wma"}
DOCUMENT_SUFFIXES = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"}

IOS_RE = re.compile(
    r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\]\s*(?:(?P<sender>[^:]+):\s*)?(?P<body>.*)$"
)
ANDROID_RE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\s*-\s*(?:(?P<sender>[^:]+):\s*)?(?P<body>.*)$"
)
ISO_NAME_RE = re.compile(r"(?P<year>20\d{2})[-_]?(?P<month>0[1-9]|1[0-2])[-_]?(?P<day>0[1-9]|[12]\d|3[01])")
COMPACT_NAME_RE = re.compile(r"(?P<year>20\d{2})(?P<month>0[1-9]|1[0-2])(?P<day>0[1-9]|[12]\d|3[01])")


class RecoveryError(RuntimeError):
    pass


@dataclass
class Message:
    when: datetime
    sender: str
    body: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require_env() -> None:
    if not SERVICE_KEY:
        raise RecoveryError("SUPABASE_SERVICE_ROLE_KEY non presente nell'ambiente locale")


def headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    out = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        out.update(extra)
    return out


def get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers(),
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise RecoveryError(f"GET {table}: {r.status_code} {r.text[:700]}")
    data = r.json()
    return data if isinstance(data, list) else []


def patch(table: str, row_id: str, payload: dict[str, Any]) -> None:
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{row_id}"},
        json={**payload, "updated_at": now_iso()},
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise RecoveryError(f"PATCH {table}: {r.status_code} {r.text[:700]}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_slug(value: str) -> str:
    raw = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug or "cliente"


def safe_name(value: str) -> str:
    name = Path(value).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or f"file-{uuid.uuid4().hex[:8]}"


def timezone_for(tz_name: str):
    """Return the requested IANA timezone when available.

    The existing Windows runner can use Python 3.8, which has no stdlib
    zoneinfo. In that case use the PC local timezone. This is correct for the
    operator's Italy-local WhatsApp exports and keeps the worker executable
    without adding a native dependency.
    """
    if ZoneInfo is not None:
        try:
            return timezone_for(tz_name)
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo or timezone.utc


def parse_job_date(value: str | None, tz_name: str) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone_for(tz_name))
    return dt.astimezone(timezone_for(tz_name))


def parse_chat_datetime(date_value: str, time_value: str, tz_name: str) -> datetime:
    clean_time = (
        time_value.replace("\u202f", " ")
        .replace("\u00a0", " ")
        .strip()
        .upper()
    )
    candidates = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %I:%M:%S %p",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%y %I:%M:%S %p",
        "%d/%m/%y %I:%M %p",
    ]
    raw = f"{date_value} {clean_time}"
    for fmt in candidates:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone_for(tz_name))
        except ValueError:
            continue
    raise RecoveryError(f"Formato data WhatsApp non riconosciuto: {raw}")


def parse_chat_file(path: Path, tz_name: str) -> list[Message]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    messages: list[Message] = []
    current: Message | None = None
    for line in raw.splitlines():
        match = IOS_RE.match(line) or ANDROID_RE.match(line)
        if match:
            try:
                when = parse_chat_datetime(match.group("date"), match.group("time"), tz_name)
            except RecoveryError:
                current = None
                continue
            current = Message(
                when=when,
                sender=(match.group("sender") or "").strip(),
                body=(match.group("body") or "").strip(),
            )
            messages.append(current)
        elif current is not None:
            current.body += "\n" + line
    return messages


def category_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "FOTO"
    if suffix in VIDEO_SUFFIXES:
        return "VIDEO"
    if suffix in AUDIO_SUFFIXES:
        return "AUDIO"
    if suffix in DOCUMENT_SUFFIXES:
        return "DOCUMENTI"
    return "ALTRI"


def media_date_from_filename(name: str, tz_name: str) -> datetime | None:
    stem = Path(name).stem
    match = ISO_NAME_RE.search(stem) or COMPACT_NAME_RE.search(stem)
    if not match:
        return None
    try:
        return datetime(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            12,
            0,
            tzinfo=timezone_for(tz_name),
        )
    except ValueError:
        return None


def candidate_export_zips(client: dict[str, Any], inbox: Path) -> list[Path]:
    candidates: list[Path] = []
    if inbox.exists():
        candidates.extend(p for p in inbox.rglob("*.zip") if p.is_file())
    name = str(client.get("name") or "").lower()
    tokens = [t for t in re.findall(r"[a-z0-9]+", name) if len(t) >= 3]
    for root in (Path.home() / "Downloads", Path.home() / "Desktop"):
        if not root.exists():
            continue
        for p in root.glob("*.zip"):
            lower = p.name.lower()
            if "whatsapp" in lower or any(t in lower for t in tokens):
                candidates.append(p)
    unique: dict[str, Path] = {}
    for p in candidates:
        try:
            unique[str(p.resolve()).lower()] = p
        except Exception:
            unique[str(p).lower()] = p
    return sorted(unique.values(), key=lambda p: p.stat().st_mtime, reverse=True)


def choose_chat_text(root: Path) -> Path | None:
    txts = [p for p in root.rglob("*.txt") if p.is_file()]
    if not txts:
        return None
    txts.sort(key=lambda p: (0 if "chat" in p.name.lower() else 1, len(str(p))))
    return txts[0]


def referenced_media(messages: list[Message], media_paths: list[Path]) -> dict[str, Message]:
    names = [p.name.casefold() for p in media_paths]
    out: dict[str, Message] = {}
    for message in messages:
        body = message.body.casefold()
        for name in names:
            if name not in out and name in body:
                out[name] = message
    return out


def ensure_archive_dirs(base: Path) -> dict[str, Path]:
    dirs = {
        "base": base,
        "FOTO": base / "FOTO",
        "VIDEO": base / "VIDEO",
        "AUDIO": base / "AUDIO",
        "DOCUMENTI": base / "DOCUMENTI",
        "ALTRI": base / "ALTRI",
        "TESTI": base / "TESTI",
        "METADATA": base / "METADATA",
        "DUPLICATI": base / "DUPLICATI",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def existing_hashes(base: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in base.rglob("*"):
        if not p.is_file() or p.name.startswith("manifest"):
            continue
        if p.parent.name in {"METADATA", "TESTI", "DUPLICATI"}:
            continue
        try:
            out[sha256_file(p)] = str(p)
        except Exception:
            pass
    return out


def unique_target(folder: Path, name: str) -> Path:
    target = folder / safe_name(name)
    if not target.exists():
        return target
    stem, suffix, index = target.stem, target.suffix, 2
    while target.exists():
        target = folder / f"{stem}_{index}{suffix}"
        index += 1
    return target


def write_manifests(base: Path, metadata: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[Path, Path]:
    json_path = base / "manifest.json"
    csv_path = base / "manifest.csv"
    json_path.write_text(
        json.dumps({**metadata, "files": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fields = [
        "file_name", "original_name", "type", "mime_type", "message_datetime",
        "sender", "message_id", "caption", "sha256", "local_path", "source", "status",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})
    return json_path, csv_path


def windows_notify(title: str, message: str) -> None:
    if os.name != "nt":
        return
    escaped_title = title.replace("'", "''")
    escaped_message = message.replace("'", "''")
    script = (
        "Add-Type -AssemblyName PresentationFramework; "
        f"[System.Windows.MessageBox]::Show('{escaped_message}','{escaped_title}') | Out-Null"
    )
    try:
        subprocess.Popen(["powershell.exe", "-NoProfile", "-Command", script])
    except Exception:
        pass


def open_chat(number: str) -> None:
    digits = re.sub(r"\D+", "", number)
    if not digits:
        return
    try:
        webbrowser.open(f"https://web.whatsapp.com/send?phone={quote(digits)}", new=1)
    except Exception:
        pass


def claim_job(job: dict[str, Any]) -> None:
    patch(
        "f1_whatsapp_recovery_jobs",
        str(job["id"]),
        {
            "status": "RUNNING",
            "started_at": job.get("started_at") or now_iso(),
            "last_error": None,
            "checkpoint": {
                **(job.get("checkpoint") or {}),
                "phase": "LOCAL_WORKER_STARTED",
                "worker_started_at": now_iso(),
            },
        },
    )


def process_export(job: dict[str, Any], client: dict[str, Any], export_zip: Path) -> dict[str, Any]:
    tz_name = str(job.get("timezone") or client.get("timezone") or "Europe/Rome")
    date_from = parse_job_date(job.get("date_from"), tz_name)
    date_to = parse_job_date(job.get("date_to"), tz_name) or datetime.now(timezone_for(tz_name))
    if not date_from:
        raise RecoveryError("date_from mancante")

    slug = safe_slug(str(client.get("slug") or client.get("name") or "cliente"))
    base = ARCHIVE_ROOT / slug / f"{date_from.date().isoformat()}_oggi"
    dirs = ensure_archive_dirs(base)

    patch(
        "f1_whatsapp_recovery_jobs",
        str(job["id"]),
        {
            "status": "RUNNING",
            "local_archive_path": str(base),
            "checkpoint": {
                **(job.get("checkpoint") or {}),
                "phase": "EXTRACTING_EXPORT",
                "export_zip": str(export_zip),
            },
        },
    )

    with tempfile.TemporaryDirectory(prefix="f1-wa-recovery-") as td:
        temp_root = Path(td)
        with zipfile.ZipFile(export_zip, "r") as zf:
            root_resolved = temp_root.resolve()
            for info in zf.infolist():
                target = (temp_root / info.filename).resolve()
                try:
                    target.relative_to(root_resolved)
                except ValueError as exc:
                    raise RecoveryError("ZIP WhatsApp contiene un percorso non sicuro") from exc
            zf.extractall(temp_root)

        chat_path = choose_chat_text(temp_root)
        if chat_path is None:
            raise RecoveryError("Esportazione WhatsApp senza file chat TXT")
        messages = parse_chat_file(chat_path, tz_name)
        filtered_messages = [m for m in messages if date_from <= m.when <= date_to]
        media_paths = [
            p for p in temp_root.rglob("*")
            if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES and p != chat_path
        ]
        refs = referenced_media(filtered_messages, media_paths)
        hashes = existing_hashes(base)
        rows: list[dict[str, Any]] = []
        duplicate_lines: list[str] = []
        saved = photos = videos = audio = documents = duplicates = unmatched = errors = 0

        (dirs["TESTI"] / "chat_filtrata.txt").write_text(
            "\n\n".join(f"[{m.when.isoformat()}] {m.sender}: {m.body}" for m in filtered_messages),
            encoding="utf-8",
        )

        for source in sorted(media_paths, key=lambda p: p.name.casefold()):
            message = refs.get(source.name.casefold())
            inferred_date = media_date_from_filename(source.name, tz_name)
            when = message.when if message else inferred_date
            if when is None or not (date_from <= when <= date_to):
                unmatched += 1
                continue
            try:
                digest = sha256_file(source)
                kind = category_for(source)
                mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
                if digest in hashes:
                    duplicates += 1
                    duplicate_lines.append(f"{source.name}\t{digest}\t{hashes[digest]}")
                    rows.append({
                        "file_name": source.name, "original_name": source.name, "type": kind,
                        "mime_type": mime, "message_datetime": when.isoformat(),
                        "sender": message.sender if message else "", "message_id": "",
                        "caption": message.body if message else "", "sha256": digest,
                        "local_path": hashes[digest], "source": "WHATSAPP_EXPORT",
                        "status": "DUPLICATO_GIA_PRESENTE",
                    })
                    continue

                target = unique_target(dirs.get(kind, dirs["ALTRI"]), source.name)
                shutil.copy2(source, target)
                hashes[digest] = str(target)
                saved += 1
                if kind == "FOTO": photos += 1
                elif kind == "VIDEO": videos += 1
                elif kind == "AUDIO": audio += 1
                elif kind == "DOCUMENTI": documents += 1
                rows.append({
                    "file_name": target.name, "original_name": source.name, "type": kind,
                    "mime_type": mime, "message_datetime": when.isoformat(),
                    "sender": message.sender if message else "", "message_id": "",
                    "caption": message.body if message else "", "sha256": digest,
                    "local_path": str(target), "source": "WHATSAPP_EXPORT", "status": "SALVATO",
                })
            except Exception as exc:
                errors += 1
                rows.append({
                    "file_name": source.name, "original_name": source.name,
                    "type": category_for(source),
                    "mime_type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
                    "message_datetime": when.isoformat() if when else "",
                    "sender": message.sender if message else "", "message_id": "",
                    "caption": message.body if message else "", "sha256": "", "local_path": "",
                    "source": "WHATSAPP_EXPORT", "status": f"ERRORE: {exc}",
                })

        if duplicate_lines:
            (dirs["DUPLICATI"] / "duplicati.txt").write_text("\n".join(duplicate_lines), encoding="utf-8")

        stats = {
            "messages_scanned": len(filtered_messages), "photos": photos, "videos": videos,
            "audio": audio, "documents": documents, "duplicates": duplicates, "saved": saved,
            "unmatched_media": unmatched, "errors": errors,
        }
        manifest_json, manifest_csv = write_manifests(
            base,
            {
                "client_id": client.get("id"), "client_name": client.get("name"),
                "client_slug": slug, "whatsapp_number": job.get("whatsapp_number"),
                "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
                "started_at": job.get("started_at") or now_iso(), "completed_at": now_iso(),
                **stats, "export_zip": str(export_zip),
            },
            rows,
        )
        status = "COMPLETED" if errors == 0 else "COMPLETED_WITH_ERRORS"
        patch(
            "f1_whatsapp_recovery_jobs",
            str(job["id"]),
            {
                "status": status, "local_archive_path": str(base),
                "manifest_json_path": str(manifest_json), "manifest_csv_path": str(manifest_csv),
                "stats": stats,
                "checkpoint": {
                    "phase": status, "resume_supported": True,
                    "export_zip": str(export_zip), "completed_at": now_iso(),
                },
                "completed_at": now_iso(),
                "last_error": None if errors == 0 else f"{errors} file con errore",
            },
        )
        windows_notify(
            "RECUPERO WHATSAPP COMPLETATO",
            (
                f"Cliente: {client.get('name')}\n"
                f"Periodo: {date_from.date()} → {date_to.date()}\n"
                f"File salvati: {saved}\n"
                f"Foto: {photos} · Video: {videos} · Audio: {audio} · Documenti: {documents}\n"
                f"Duplicati esclusi: {duplicates}\n\n"
                "Apri il Content Hub e scegli SELEZIONA I FILE DA PREPARARE."
            ),
        )
        return stats


def process_job(job: dict[str, Any], open_whatsapp: bool) -> dict[str, Any]:
    clients = get(
        "f1_content_clients",
        {
            "select": "*", "id": f"eq.{job['client_id']}",
            "owner_id": f"eq.{job['owner_id']}", "limit": "1",
        },
    )
    if not clients:
        raise RecoveryError("Cliente non trovato")
    client = clients[0]
    slug = safe_slug(str(client.get("slug") or client.get("name") or "cliente"))
    inbox = INBOX_ROOT / slug
    inbox.mkdir(parents=True, exist_ok=True)

    original_status = str(job.get("status") or "")
    claim_job(job)
    if open_whatsapp and original_status in {"QUEUED", "WAITING_LOCAL_SESSION"}:
        open_chat(str(job.get("whatsapp_number") or client.get("whatsapp") or ""))

    zips = candidate_export_zips(client, inbox)
    if not zips:
        (inbox / "LEGGIMI_RECUPERO.txt").write_text(
            "F1 WhatsApp Recovery\n\n"
            "Questa cartella riceve l'esportazione ZIP della chat WhatsApp del cliente.\n"
            "Il worker la rileva automaticamente, filtra il periodo richiesto, evita i doppioni e genera manifest JSON/CSV.\n",
            encoding="utf-8",
        )
        patch(
            "f1_whatsapp_recovery_jobs",
            str(job["id"]),
            {
                "status": "WAITING_LOCAL_EXPORT",
                "local_archive_path": str(ARCHIVE_ROOT / slug),
                "checkpoint": {
                    **(job.get("checkpoint") or {}),
                    "phase": "WAITING_LOCAL_EXPORT", "local_inbox": str(inbox),
                    "chat_opened": bool(open_whatsapp), "checked_at": now_iso(),
                },
                "last_error": "Nessuna esportazione WhatsApp ZIP trovata nella cartella locale, in Download o sul Desktop.",
            },
        )
        return {"status": "WAITING_LOCAL_EXPORT", "client": client.get("name"), "inbox": str(inbox)}

    stats = process_export(job, client, zips[0])
    return {"status": "COMPLETED", "client": client.get("name"), "stats": stats}


def pending_jobs(limit: int) -> list[dict[str, Any]]:
    return get(
        "f1_whatsapp_recovery_jobs",
        {
            "select": "*",
            "status": "in.(QUEUED,WAITING_LOCAL_SESSION,WAITING_LOCAL_EXPORT,RUNNING)",
            "order": "created_at.asc", "limit": str(max(1, limit)),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="F1 local WhatsApp retro recovery coordinator")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--open-chat", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()

    require_env()
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    INBOX_ROOT.mkdir(parents=True, exist_ok=True)

    while True:
        jobs = pending_jobs(args.limit)
        if not jobs:
            print("Nessun recupero WhatsApp pendente.")
        for job in jobs:
            try:
                result = process_job(job, args.open_chat)
                print(json.dumps({"job_id": job.get("id"), **result}, ensure_ascii=False))
            except Exception as exc:
                print(f"ERROR recovery {job.get('id')}: {exc}", file=sys.stderr)
                try:
                    patch(
                        "f1_whatsapp_recovery_jobs",
                        str(job["id"]),
                        {
                            "status": "ERROR", "last_error": str(exc)[:1200],
                            "checkpoint": {
                                **(job.get("checkpoint") or {}),
                                "phase": "ERROR", "error_at": now_iso(),
                            },
                        },
                    )
                except Exception:
                    pass
        if args.once:
            break
        time.sleep(max(15, args.poll_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
