#!/usr/bin/env python3
"""F1 Social Intelligence local Windows folder agent.

The operator controls one deterministic folder tree:
  C:\F1Social\Clients\<client-slug>\INBOX

Clients do not choose paths. New stable files are uploaded automatically to the
correct Content Hub tenant and then the server-side Intelligence worker takes
over. Optional screen recording is allowed only when explicit operator consent
exists in f1_operator_preferences. Recording is visible (REC overlay), targets
only the F1 Content Hub browser window, and is uploaded to the private
f1-rmp-demo bucket.

Secrets must be supplied through local environment variables and are never
written to the repository.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://nqnmlsmeiynxbdojeyjt.supabase.co").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
ROOT = Path(os.getenv("F1_LOCAL_ROOT", r"C:\F1Social\Clients"))
POLL_SECONDS = max(2, int(os.getenv("F1_LOCAL_POLL_SECONDS", "5")))
STABLE_SECONDS = max(5, int(os.getenv("F1_FILE_STABLE_SECONDS", "10")))
MAX_ATTEMPTS = 3
BUCKET = "f1-content-media"
DEMO_BUCKET = "f1-rmp-demo"
REQUEST_TIMEOUT = 300
ALLOWED_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif",
    ".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv",
    ".mp3", ".wav", ".m4a", ".aac",
    ".pdf", ".doc", ".docx",
}


class AgentError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require_env() -> None:
    if not SERVICE_KEY:
        raise AgentError(
            "SUPABASE_SERVICE_ROLE_KEY non presente nell'ambiente locale. "
            "Il segreto deve restare sul PC dell'operatore e non va inserito nel repository."
        )


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
        timeout=60,
    )
    if not r.ok:
        raise AgentError(f"GET {table}: {r.status_code} {r.text[:500]}")
    data = r.json()
    return data if isinstance(data, list) else []


def post(table: str, payload: dict[str, Any], return_rows: bool = False) -> list[dict[str, Any]]:
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=representation" if return_rows else "return=minimal"}),
        json=payload,
        timeout=60,
    )
    if not r.ok:
        raise AgentError(f"POST {table}: {r.status_code} {r.text[:500]}")
    if return_rows and r.text.strip():
        data = r.json()
        return data if isinstance(data, list) else []
    return []


def safe_name(value: str) -> str:
    name = Path(value).name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return clean or f"file-{uuid.uuid4().hex[:8]}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_file(bucket: str, object_path: str, file_path: Path, content_type: str) -> None:
    encoded = "/".join(quote(part, safe="") for part in object_path.lstrip("/").split("/"))
    with file_path.open("rb") as fh:
        r = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{bucket}/{encoded}",
            headers={
                "apikey": SERVICE_KEY,
                "Authorization": f"Bearer {SERVICE_KEY}",
                "Content-Type": content_type,
                "x-upsert": "false",
            },
            data=fh,
            timeout=REQUEST_TIMEOUT,
        )
    if not r.ok:
        raise AgentError(f"Storage upload {bucket}: {r.status_code} {r.text[:600]}")


def content_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".heic", ".heif"}:
        return "image/heic" if suffix == ".heic" else "image/heif"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def content_kind(mime: str, suffix: str) -> str:
    if mime.startswith("image/"):
        return "FOTO"
    if mime.startswith("video/"):
        return "VIDEO"
    if mime.startswith("audio/"):
        return "AUDIO"
    if suffix.lower() in {".pdf", ".doc", ".docx"}:
        return "DOCUMENTO"
    return "CONTENUTO"


def client_dirs(client: dict[str, Any]) -> dict[str, Path]:
    base = ROOT / str(client["slug"])
    dirs = {
        "base": base,
        "inbox": base / "INBOX",
        "processing": base / "PROCESSING",
        "done": base / "DONE",
        "error": base / "ERROR",
        "demo": base / "DEMO",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    readme = base / "LEGGIMI.txt"
    if not readme.exists():
        readme.write_text(
            "F1 SOCIAL INTELLIGENCE\n\n"
            "Inserisci foto e video esclusivamente nella cartella INBOX.\n"
            "Il percorso è assegnato automaticamente dal software.\n"
            "Non rinominare o spostare le altre cartelle.\n",
            encoding="utf-8",
        )
    return dirs


def already_ingested(owner_id: str, digest: str) -> bool:
    rows = get(
        "f1_intelligence_jobs",
        {
            "select": "id,status",
            "owner_id": f"eq.{owner_id}",
            "unique_key": f"eq.local-file:{digest}",
            "limit": "1",
        },
    )
    return bool(rows and str(rows[0].get("status") or "") in {"COMPLETED", "RUNNING", "QUEUED"})


def ingest_one(client: dict[str, Any], source: Path) -> str:
    owner_id = str(client["owner_id"])
    client_id = str(client["id"])
    digest = sha256_file(source)
    if already_ingested(owner_id, digest):
        return "DUPLICATE"

    title = re.sub(r"[_-]+", " ", source.stem).strip() or "Contenuto"
    mime = content_type_for(source)
    item_rows = post(
        "f1_content_items",
        {
            "owner_id": owner_id,
            "client_id": client_id,
            "title": title,
            "description": "",
            "source_text": "",
            "content_type": content_kind(mime, source.suffix),
            "source": "LOCAL_FOLDER_AGENT",
            "status": "IN ARRIVO",
            "priority": "NORMALE",
            "campaign": "AUTO_INGEST",
            "tags": [],
            "notes": f"Import automatico cartella cliente · SHA256 {digest}",
            "distribution_plan": {
                "local_ingest": {
                    "sha256": digest,
                    "source_file": source.name,
                    "ingested_at": now_iso(),
                    "pipeline": "F1_INTELLIGENCE_V1",
                }
            },
        },
        return_rows=True,
    )
    if not item_rows:
        raise AgentError("Contenuto non creato")
    item = item_rows[0]
    content_id = str(item["id"])

    filename = safe_name(source.name)
    storage_path = f"{owner_id}/{client_id}/{content_id}/local-{uuid.uuid4().hex[:12]}-{filename}"
    try:
        upload_file(BUCKET, storage_path, source, mime)
        media_rows = post(
            "f1_content_media",
            {
                "owner_id": owner_id,
                "content_id": content_id,
                "client_id": client_id,
                "file_name": filename,
                "mime_type": mime,
                "storage_path": storage_path,
                "file_size": source.stat().st_size,
                "source": "LOCAL_FOLDER_AGENT",
            },
            return_rows=True,
        )
        if not media_rows:
            raise AgentError("Media non registrato")

        job_rows = post(
            "f1_intelligence_jobs",
            {
                "owner_id": owner_id,
                "client_id": client_id,
                "content_id": content_id,
                "job_type": "LOCAL_INGEST",
                "status": "COMPLETED",
                "stage": "CARICATO",
                "unique_key": f"local-file:{digest}",
                "payload": {"source_name": source.name, "sha256": digest},
                "result": {"media_id": media_rows[0].get("id"), "storage_path": storage_path},
                "completed_at": now_iso(),
            },
            return_rows=False,
        )
        post(
            "f1_intelligence_events",
            {
                "owner_id": owner_id,
                "client_id": client_id,
                "content_id": content_id,
                "stage": "CARICATO",
                "status": "COMPLETED",
                "message": "File rilevato nella cartella cliente e caricato automaticamente nel cloud",
                "progress": 15,
                "details": {"sha256": digest, "source": "LOCAL_FOLDER_AGENT"},
            },
        )
    except Exception:
        # The Intelligence worker will never see a half-valid media row.
        raise
    return content_id


def find_f1_window_title() -> str:
    if os.name != "nt":
        return ""
    cmd = [
        "powershell.exe", "-NoProfile", "-Command",
        "(Get-Process | Where-Object {$_.MainWindowTitle -like '*F1 Content Hub*' -or $_.MainWindowTitle -like '*F1 Social Intelligence*'} | Select-Object -First 1 -ExpandProperty MainWindowTitle)"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return r.stdout.strip()


class VisibleRecorder:
    def __init__(self, output: Path):
        self.output = output
        self.proc: subprocess.Popen | None = None
        self.stop_overlay = threading.Event()
        self.overlay_thread: threading.Thread | None = None

    def _overlay(self) -> None:
        try:
            import tkinter as tk
            root = tk.Tk()
            root.title("F1 Social Intelligence · REC")
            root.attributes("-topmost", True)
            root.overrideredirect(True)
            root.geometry("270x44+20+20")
            label = tk.Label(
                root,
                text="● REC  F1 SOCIAL INTELLIGENCE",
                bg="#07111f",
                fg="#39f28a",
                font=("Segoe UI", 11, "bold"),
                padx=12,
                pady=9,
            )
            label.pack(fill="both", expand=True)
            def tick():
                if self.stop_overlay.is_set():
                    root.destroy()
                    return
                root.after(250, tick)
            root.after(250, tick)
            root.mainloop()
        except Exception:
            return

    def start(self) -> bool:
        if os.name != "nt" or not shutil.which("ffmpeg"):
            return False
        title = find_f1_window_title()
        if not title:
            print("REC: finestra F1 Social non trovata; registrazione non avviata.")
            return False
        self.output.parent.mkdir(parents=True, exist_ok=True)
        args = [
            "ffmpeg", "-y", "-f", "gdigrab", "-framerate", "15",
            "-i", f"title={title}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-pix_fmt", "yuv420p", "-an", str(self.output),
        ]
        self.proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.overlay_thread = threading.Thread(target=self._overlay, daemon=True)
        self.overlay_thread.start()
        time.sleep(1.0)
        return self.proc.poll() is None

    def stop(self) -> None:
        self.stop_overlay.set()
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.communicate("q\n", timeout=10)
            except Exception:
                self.proc.kill()


def operator_preferences(owner_id: str) -> dict[str, Any]:
    rows = get(
        "f1_operator_preferences",
        {"select": "*", "owner_id": f"eq.{owner_id}", "limit": "1"},
    )
    return rows[0] if rows else {}


def upload_demo(owner_id: str, client: dict[str, Any], recording: Path) -> None:
    if not recording.exists() or recording.stat().st_size < 10_000:
        return
    date = datetime.now().strftime("%Y-%m-%d")
    object_path = f"{owner_id}/{client['slug']}/{date}/{recording.name}"
    upload_file(DEMO_BUCKET, object_path, recording, "video/mp4")
    meta = recording.with_suffix(".json")
    meta.write_text(
        json.dumps(
            {
                "client_id": client["id"],
                "client_name": client["name"],
                "recording_scope": "F1_SOCIAL_WINDOW",
                "consent": True,
                "created_at": now_iso(),
                "object_path": object_path,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    upload_file(DEMO_BUCKET, object_path[:-4] + ".json", meta, "application/json")


def main() -> int:
    require_env()
    ROOT.mkdir(parents=True, exist_ok=True)
    seen: dict[str, tuple[int, float, float]] = {}
    failures: dict[str, int] = {}

    print(f"F1 Social Intelligence local agent · root={ROOT}")
    while True:
        clients = get(
            "f1_content_clients",
            {"select": "*", "status": "eq.ATTIVO", "order": "name.asc"},
        )
        for client in clients:
            dirs = client_dirs(client)
            owner_id = str(client["owner_id"])
            prefs = operator_preferences(owner_id)
            for source in sorted(dirs["inbox"].iterdir()):
                if not source.is_file() or source.suffix.lower() not in ALLOWED_SUFFIXES:
                    continue
                key = str(source.resolve())
                stat = source.stat()
                prior = seen.get(key)
                if not prior or prior[0] != stat.st_size or prior[1] != stat.st_mtime:
                    seen[key] = (stat.st_size, stat.st_mtime, time.time())
                    continue
                if time.time() - prior[2] < STABLE_SECONDS:
                    continue

                processing = dirs["processing"] / source.name
                try:
                    shutil.move(str(source), str(processing))
                    rec: VisibleRecorder | None = None
                    recording = dirs["demo"] / f"{datetime.now():%Y%m%d-%H%M%S}-{safe_name(source.stem)}.mp4"
                    if (
                        prefs.get("screen_recording_enabled")
                        and prefs.get("screen_recording_consented_at")
                        and prefs.get("demo_upload_enabled")
                    ):
                        rec = VisibleRecorder(recording)
                        rec.start()
                    try:
                        result = ingest_one(client, processing)
                    finally:
                        if rec:
                            rec.stop()
                    target = dirs["done"] / processing.name
                    shutil.move(str(processing), str(target))
                    if rec and recording.exists():
                        upload_demo(owner_id, client, recording)
                    print(f"{client['name']}: {source.name} -> {result}")
                    failures.pop(key, None)
                    seen.pop(key, None)
                except Exception as exc:
                    failures[key] = failures.get(key, 0) + 1
                    print(f"ERROR {client.get('name')} {source.name}: {exc}", file=sys.stderr)
                    if processing.exists():
                        if failures[key] >= MAX_ATTEMPTS:
                            shutil.move(str(processing), str(dirs["error"] / processing.name))
                            seen.pop(key, None)
                        else:
                            shutil.move(str(processing), str(dirs["inbox"] / processing.name))
                    time.sleep(2)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
