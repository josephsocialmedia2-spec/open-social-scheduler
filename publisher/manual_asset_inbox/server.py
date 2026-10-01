from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, send_from_directory
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSET_ROOT = ROOT / "publisher" / "final_assets" / "manual_inbox"
QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
ROME = ZoneInfo("Europe/Rome")

ALLOWED_IMAGE_FORMATS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
}
ALLOWED_PLATFORMS = {"facebook", "instagram", "linkedin"}

app = Flask(__name__)


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=check)


def now_iso() -> str:
    return datetime.now(ROME).isoformat(timespec="seconds")


def safe_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9àèéìòù]+", "-", value, flags=re.IGNORECASE)
    value = value.strip("-")
    return value[:72] or "grafica"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def next_slot() -> str:
    now = datetime.now(ROME)
    morning = now.replace(hour=10, minute=30, second=0, microsecond=0)
    evening = now.replace(hour=18, minute=30, second=0, microsecond=0)
    if now < morning:
        target = morning
    elif now < evening:
        target = evening
    else:
        target = (now + timedelta(days=1)).replace(hour=10, minute=30, second=0, microsecond=0)
    return target.isoformat()


def load_queue() -> dict:
    if not QUEUE_PATH.exists():
        raise RuntimeError("publisher/final_content_queue.json mancante")
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    queue.setdefault("jobs", [])
    return queue


def existing_hashes(queue: dict) -> set[str]:
    hashes: set[str] = set()
    for job in queue.get("jobs", []):
        for asset in job.get("assets") or []:
            if isinstance(asset, dict) and asset.get("sha256"):
                hashes.add(str(asset["sha256"]).lower())
    return hashes


def existing_ids(queue: dict) -> set[str]:
    return {str(job.get("id") or "") for job in queue.get("jobs", []) if job.get("id")}


def normalize_platforms(value) -> list[str]:
    raw = value if isinstance(value, list) else []
    out: list[str] = []
    for item in raw:
        platform = str(item or "").strip().lower()
        if platform in ALLOWED_PLATFORMS and platform not in out:
            out.append(platform)
    return out or ["facebook", "instagram"]


def validate_image_bytes(data: bytes, original_name: str) -> dict:
    if not data:
        raise ValueError(f"{original_name}: file vuoto")
    try:
        with Image.open(BytesIO(data)) as image:
            detected = str(image.format or "").upper()
            image.verify()
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f"{original_name}: immagine non leggibile o corrotta") from exc

    if detected not in ALLOWED_IMAGE_FORMATS:
        raise ValueError(
            f"{original_name}: formato {detected or 'sconosciuto'} non supportato; usa PNG, JPG/JPEG o WEBP"
        )
    if int(width) <= 0 or int(height) <= 0:
        raise ValueError(f"{original_name}: dimensioni immagine non valide")

    return {
        "format": detected,
        "extension": ALLOWED_IMAGE_FORMATS[detected],
        "width": int(width),
        "height": int(height),
        "bytes": len(data),
    }


def ensure_repo_ready() -> None:
    status = run_git("status", "--porcelain")
    if status.stdout.strip():
        raise RuntimeError(
            "Repository locale con modifiche non salvate. Salva o annulla le modifiche prima di caricare una grafica."
        )
    pull = run_git("pull", "--rebase", "origin", "main", check=False)
    if pull.returncode != 0:
        raise RuntimeError(f"Git pull fallito: {pull.stderr.strip() or pull.stdout.strip()}")


def commit_and_push(paths: list[str], message: str) -> None:
    run_git("add", *paths)
    run_git("config", "user.name", "F1 Manual Publisher")
    run_git("config", "user.email", "actions@users.noreply.github.com")
    commit = run_git("commit", "-m", message, check=False)
    if commit.returncode != 0:
        raise RuntimeError(f"Commit Git fallito: {commit.stderr.strip() or commit.stdout.strip()}")

    last_push_error = ""
    for attempt in range(1, 4):
        push = run_git("push", "origin", "main", check=False)
        if push.returncode == 0:
            return
        last_push_error = push.stderr.strip() or push.stdout.strip()
        if attempt >= 3:
            break
        pull = run_git("pull", "--rebase", "origin", "main", check=False)
        if pull.returncode != 0:
            run_git("rebase", "--abort", check=False)
            raise RuntimeError(
                "Push GitHub concorrente e rebase automatico non riuscito: "
                + (pull.stderr.strip() or pull.stdout.strip())
            )
    raise RuntimeError(f"Push GitHub fallito dopo 3 tentativi: {last_push_error}")


def _prepare_records(items: list[dict], queue: dict) -> list[dict]:
    hashes = existing_hashes(queue)
    ids = existing_ids(queue)
    prepared: list[dict] = []
    seen_hashes: set[str] = set()
    seen_ids: set[str] = set()
    stamp = datetime.now(ROME)

    for pos, item in enumerate(items, start=1):
        data = item["data"]
        original_name = str(item.get("filename") or "asset.png")
        meta = item.get("meta") or {}

        image_info = validate_image_bytes(data, original_name)
        digest = sha256_bytes(data)
        if digest.lower() in hashes or digest.lower() in seen_hashes:
            raise ValueError(f"{original_name}: grafica già presente in coda o duplicata nel batch")

        requested_id = str(meta.get("content_id") or "").strip()
        content_id = requested_id or f"F1-{stamp:%Y%m%d}-{stamp:%H%M%S}-{pos:02d}-{digest[:8]}"
        if content_id in ids or content_id in seen_ids:
            raise ValueError(f"{content_id}: content ID già esistente")

        title = str(meta.get("title") or Path(original_name).stem or "Grafica F1").strip()
        caption = str(meta.get("caption") or "")
        territory = str(meta.get("territory") or "").strip()
        scope = str(meta.get("scope") or ("territory" if territory else "network")).strip()
        if scope not in {"territory", "network"}:
            scope = "territory" if territory else "network"
        platforms = normalize_platforms(meta.get("platforms"))
        scheduled_at = str(meta.get("scheduled_at") or "").strip() or next_slot()
        approved = bool(meta.get("approved"))

        if approved and caption.strip():
            status = "READY"
            publication_status = "READY_TO_PUBLISH"
        elif not caption.strip():
            status = "HOLD"
            publication_status = "CAPTION_MISSING"
        else:
            status = "HOLD"
            publication_status = "DA_APPROVARE"

        prepared.append(
            {
                "pos": pos,
                "data": data,
                "digest": digest,
                "content_id": content_id,
                "title": title,
                "caption": caption,
                "scheduled_at": scheduled_at,
                "territory": territory,
                "scope": scope,
                "platforms": platforms,
                "approved": approved,
                "status": status,
                "publication_status": publication_status,
                "original_name": original_name,
                "image_info": image_info,
            }
        )
        seen_hashes.add(digest.lower())
        seen_ids.add(content_id)

    return prepared


def build_queue_job(row: dict, rel: str, created_at: str) -> dict:
    approved_at = created_at if row["approved"] and row["caption"].strip() else None
    state_history = [{"state": "CARICATO", "at": created_at}]
    if row["publication_status"] == "READY_TO_PUBLISH":
        state_history.extend(
            [
                {"state": "APPROVATO", "at": created_at},
                {"state": "PROGRAMMATO", "at": created_at},
                {"state": "READY_TO_PUBLISH", "at": created_at},
            ]
        )
    else:
        state_history.append({"state": row["publication_status"], "at": created_at})
    return {
        "id": row["content_id"],
        "client_id": "f1-immobiliare",
        "client": "F1 Immobiliare",
        "title": row["title"],
        "format": "photo",
        "assets": [
            {
                "path": rel,
                "sha256": row["digest"],
                "original_filename": row["original_name"],
                "size_bytes": row["image_info"]["bytes"],
                "width": row["image_info"]["width"],
                "height": row["image_info"]["height"],
                "format": row["image_info"]["format"],
            }
        ],
        "caption": row["caption"],
        "cta": "",
        "hashtags": [],
        "scheduled_at": row["scheduled_at"],
        "status": row["status"],
        "publication_status": row["publication_status"],
        "workflow_state": row["publication_status"],
        "state_history": state_history,
        "last_step": row["publication_status"],
        "attempt_count": 0,
        "publish_attempts": 0,
        "last_error": None,
        "updated_at": created_at,
        "uploaded_at": created_at,
        "source": "manual-upload",
        "created_by": "manual-asset-inbox",
        "graphics_source": "manual_only",
        "ai_image_generation": False,
        "automatic_brand_layer": False,
        "automatic_rendering": False,
        "pixel_in_pixel_out": True,
        "input_sha256": row["digest"],
        "platforms": row["platforms"],
        "scope": row["scope"],
        "territory": row["territory"],
        "approval_required": True,
        "manual_approval_required": True,
        "approved_at": approved_at,
        "approved_by": "manual-operator" if approved_at else None,
        "autonomous_publish": bool(row["status"] == "READY"),
    }


def commit_prepared(prepared: list[dict], queue: dict) -> list[dict]:
    today = datetime.now(ROME).strftime("%Y%m%d")
    created_at = now_iso()
    dest_dir = ASSET_ROOT / today
    dest_dir.mkdir(parents=True, exist_ok=True)
    created: list[dict] = []

    for row in prepared:
        stem = safe_slug(row["title"])
        filename = f"{row['content_id']}-{stem}{row['image_info']['extension']}"
        out = dest_dir / filename
        out.write_bytes(row["data"])

        written_digest = sha256_bytes(out.read_bytes())
        if written_digest.lower() != row["digest"].lower():
            out.unlink(missing_ok=True)
            raise RuntimeError(f"{row['original_name']}: SHA256 cambiato durante il salvataggio")

        rel = out.relative_to(ROOT).as_posix()
        job = build_queue_job(row, rel, created_at)
        queue.setdefault("jobs", []).append(job)
        created.append(job)

    queue["updated_at"] = created_at
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    commit_and_push(
        ["publisher/final_assets/manual_inbox", "publisher/final_content_queue.json"],
        f"Ingest {len(created)} manual F1 asset(s)",
    )
    return created


def _refresh_from_origin_if_clean() -> None:
    try:
        status = run_git("status", "--porcelain", check=False)
        if status.returncode == 0 and not status.stdout.strip():
            run_git("pull", "--ff-only", "origin", "main", check=False)
    except Exception:
        pass


def _manual_jobs(queue: dict) -> list[dict]:
    return [
        job
        for job in queue.get("jobs") or []
        if str(job.get("graphics_source") or "") == "manual_only"
        or str(job.get("source") or "") == "manual-upload"
    ]


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/ready")
def ready():
    return send_from_directory(HERE, "morning_notice.html")


@app.get("/api/health")
def api_health():
    return jsonify(
        {
            "ok": True,
            "service": "f1-manual-asset-inbox",
            "mode": "manual-publish-only",
            "ai_image_generation": False,
            "port": int(os.getenv("F1_INBOX_PORT", "8877")),
        }
    )


@app.get("/api/queue-status")
def api_queue_status():
    _refresh_from_origin_if_clean()
    queue = load_queue()
    jobs = _manual_jobs(queue)
    counts: dict[str, int] = {}
    for job in jobs:
        status = str(job.get("status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    recent = []
    for job in sorted(jobs, key=lambda row: str(row.get("updated_at") or ""), reverse=True)[:20]:
        recent.append(
            {
                "id": job.get("id"),
                "title": job.get("title"),
                "status": job.get("status"),
                "publication_status": job.get("publication_status"),
                "scheduled_at": job.get("scheduled_at"),
                "caption": job.get("caption") or "",
                "platforms": job.get("platforms") or [],
                "archived": bool(job.get("archived") or str(job.get("status") or "") == "ARCHIVED"),
                "published_urls": job.get("published_urls") or job.get("remote_post_urls") or [],
                "last_error": job.get("last_error") or job.get("error"),
                "sha256": ((job.get("assets") or [{}])[0] or {}).get("sha256"),
            }
        )
    return jsonify({"mode": "manual-publish-only", "counts": counts, "recent": recent})


@app.post("/api/archive")
def archive():
    payload = request.get_json(silent=True) or {}
    content_id = str(payload.get("content_id") or "").strip()
    if not content_id:
        return jsonify({"ok": False, "error": "content_id mancante"}), 400

    try:
        ensure_repo_ready()
        queue = load_queue()
        job = next(
            (
                row
                for row in _manual_jobs(queue)
                if str(row.get("id") or "") == content_id
            ),
            None,
        )
        if not job:
            return jsonify({"ok": False, "error": "Contenuto manuale non trovato"}), 404

        stamp = now_iso()
        job["archived"] = True
        job["archived_at"] = stamp
        job["workflow_state"] = "ARCHIVED"
        job["publication_status"] = "ARCHIVED"
        job["last_step"] = "ARCHIVED"
        job["updated_at"] = stamp
        job["autonomous_publish"] = False
        if str(job.get("status") or "") not in {"PUBLISHED", "PUBLISHED_VERIFIED"}:
            job["status"] = "ARCHIVED"
        history = list(job.get("state_history") or [])
        history.append({"state": "ARCHIVED", "at": stamp})
        job["state_history"] = history[-50:]
        queue["updated_at"] = stamp
        QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        commit_and_push(
            ["publisher/final_content_queue.json"],
            f"Archive manual F1 content {content_id}",
        )
        return jsonify({"ok": True, "id": content_id, "status": job.get("status"), "publication_status": "ARCHIVED"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/ingest")
def ingest():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "error": "Nessun file ricevuto"}), 400

    try:
        metadata = json.loads(request.form.get("metadata", "[]"))
    except Exception:
        return jsonify({"ok": False, "error": "Metadata non validi"}), 400
    if len(metadata) != len(files):
        return jsonify({"ok": False, "error": "Numero file e metadata non coincide"}), 400

    try:
        ensure_repo_ready()
        raw_items = [
            {
                "data": upload.read(),
                "filename": upload.filename or "asset.png",
                "meta": meta,
            }
            for upload, meta in zip(files, metadata)
        ]
        queue = load_queue()
        prepared = _prepare_records(raw_items, queue)
        created = commit_prepared(prepared, queue)
        return jsonify(
            {
                "ok": True,
                "created": created,
                "message": "Grafiche manuali salvate senza modifiche e inserite nella coda di pubblicazione",
            }
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("F1_INBOX_PORT", "8877")),
        debug=False,
    )
