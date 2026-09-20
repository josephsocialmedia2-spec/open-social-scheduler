from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSET_ROOT = ROOT / "publisher" / "final_assets" / "manual_inbox"
GENERATED_ROOT = ROOT / "publisher" / "final_assets" / "chatgpt_generated"
QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
QUERY_FILE = ROOT / "publisher" / "github_graphics" / "queries.json"
LAST_RUN_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "last_run.json"
COMMUNICATIONS_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "communications.local.json"
WORKER_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "worker.py"
GPT_URL = "https://chatgpt.com/g/g-6a9c210485488191b072eb694c2f114c-generatore-grafica-f1"
ROME = ZoneInfo("Europe/Rome")

app = Flask(__name__)


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=check)


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
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def existing_hashes(queue: dict) -> set[str]:
    hashes: set[str] = set()
    for job in queue.get("jobs", []):
        for asset in job.get("assets") or []:
            if isinstance(asset, dict) and asset.get("sha256"):
                hashes.add(str(asset["sha256"]).lower())
    return hashes


def auto_caption(query: str, family: str) -> str:
    q = query.strip()
    if family == "recruiting":
        return (
            f"{q}. F1 Immobiliare amplia la propria presenza sul territorio e cerca persone serie, motivate e con voglia di crescere nel settore immobiliare. "
            "Invia il tuo curriculum via WhatsApp al 371 370 8294.\n\n"
            "#F1Immobiliare #RicercaPersonale #LavoraConNoi #ValleDiSusa"
        )
    return (
        f"{q}. F1 Immobiliare lavora sul territorio con una comunicazione mirata e una promozione pensata per intercettare il pubblico corretto. "
        "Per informazioni o per richiedere una valutazione gratuita: +39 371 370 8294 – www.f1immobiliare.com.\n\n"
        "#F1Immobiliare #ValleDiSusa #Immobiliare #Casa"
    )


def query_map() -> dict[str, dict]:
    if not QUERY_FILE.exists():
        return {}
    payload = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    return {str(row.get("id")): row for row in payload.get("queries") or []}


def _safe_generated_path(value: str) -> Path:
    raw = Path(value)
    path = raw if raw.is_absolute() else ROOT / raw
    resolved = path.resolve()
    generated = GENERATED_ROOT.resolve()
    try:
        resolved.relative_to(generated)
    except ValueError as exc:
        raise ValueError("Percorso grafica generata non autorizzato") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"Grafica generata non trovata: {resolved}")
    return resolved


def latest_generated_jobs() -> list[dict]:
    if not LAST_RUN_FILE.exists():
        return []
    try:
        payload = json.loads(LAST_RUN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    result = []
    for job in payload.get("jobs") or []:
        image_path = str(job.get("image_path") or "").strip()
        if not image_path:
            continue
        try:
            path = _safe_generated_path(image_path)
        except Exception:
            continue
        rel_generated = path.relative_to(GENERATED_ROOT.resolve()).as_posix()
        result.append(
            {
                "query_id": str(job.get("query_id") or ""),
                "query": str(job.get("query") or ""),
                "prompt": str(job.get("prompt") or ""),
                "status": str(job.get("status") or ""),
                "retry_count": int(job.get("retry_count") or 0),
                "capture_mode": str(job.get("capture_mode") or ""),
                "image_path": image_path,
                "image_url": f"/generated/{rel_generated}",
                "generation_completed_at": job.get("generation_completed_at"),
                "image_sha256": job.get("image_sha256"),
            }
        )
    return result


def ensure_repo_ready() -> None:
    status = run_git("status", "--porcelain")
    if status.stdout.strip():
        raise RuntimeError("Repository locale con modifiche non salvate. Chiudi eventuali modifiche manuali prima dell'approvazione.")
    pull = run_git("pull", "--rebase", "origin", "main", check=False)
    if pull.returncode != 0:
        raise RuntimeError(f"Git pull fallito: {pull.stderr.strip() or pull.stdout.strip()}")


def _prepare_records(items: list[dict], queue: dict) -> list[dict]:
    hashes = existing_hashes(queue)
    qmap = query_map()
    prepared = []
    seen_hashes: set[str] = set()
    seen_queries: set[str] = set()

    for pos, item in enumerate(items, start=1):
        data = item["data"]
        original_name = str(item.get("filename") or "asset.png")
        meta = item.get("meta") or {}
        if len(data) < 10_000:
            raise ValueError(f"{original_name}: file troppo piccolo")
        digest = sha256_bytes(data)
        if digest.lower() in hashes or digest.lower() in seen_hashes:
            raise ValueError(f"{original_name}: immagine già presente in coda o duplicata nel batch")

        query_id = str(meta.get("query_id") or "").strip()
        if query_id and query_id in seen_queries:
            raise ValueError(f"Query {query_id} associata a più immagini nello stesso batch")
        row = qmap.get(query_id, {})
        query = str(meta.get("query") or row.get("query") or original_name or "Grafica F1").strip()
        family = str(meta.get("family") or row.get("family") or "property").strip()
        caption = str(meta.get("caption") or "").strip() or auto_caption(query, family)
        scheduled_at = str(meta.get("scheduled_at") or "").strip() or next_slot()
        territory = str(meta.get("territory") or row.get("commune") or "").strip()
        scope = str(meta.get("scope") or ("territory" if territory else "network")).strip()
        platforms = [str(x).lower() for x in (meta.get("platforms") or ["facebook", "instagram"])]
        client = str(meta.get("client") or "F1 Immobiliare").strip()
        communication_id = str(meta.get("communication_id") or "").strip()

        ext = Path(original_name).suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
            ext = ".png"
        prepared.append(
            {
                "pos": pos,
                "data": data,
                "digest": digest,
                "ext": ext,
                "query_id": query_id,
                "query": query,
                "family": family,
                "caption": caption,
                "scheduled_at": scheduled_at,
                "source": str(meta.get("source") or "manual-f1-custom-gpt"),
                "generator_path": str(meta.get("generator_path") or ""),
                "territory": territory,
                "scope": scope,
                "platforms": platforms,
                "client": client,
                "communication_id": communication_id,
            }
        )
        seen_hashes.add(digest.lower())
        if query_id:
            seen_queries.add(query_id)
    return prepared


def commit_prepared(prepared: list[dict], queue: dict) -> list[dict]:
    today = datetime.now(ROME).strftime("%Y%m%d")
    dest_dir = ASSET_ROOT / today
    dest_dir.mkdir(parents=True, exist_ok=True)
    created = []

    # Tutti i file sono stati validati prima di qualsiasi scrittura.
    for row in prepared:
        stem = safe_slug(row["query"])
        filename = f"{today}-{row['pos']:02d}-{stem}-{row['digest'][:8]}{row['ext']}"
        out = dest_dir / filename
        out.write_bytes(row["data"])
        rel = out.relative_to(ROOT).as_posix()
        job_id = f"manual-{today}-{row['pos']:02d}-{row['digest'][:8]}"
        job = {
            "id": job_id,
            "title": row["query"],
            "format": "photo",
            "assets": [{"path": rel, "sha256": row["digest"]}],
            "caption": row["caption"],
            "cta": "",
            "hashtags": [],
            "scheduled_at": row["scheduled_at"],
            "status": "READY",
            "source": row["source"],
            "generator_url": GPT_URL,
            "generator_path": row["generator_path"],
            "query_id": row["query_id"],
            "query": row["query"],
            "family": row["family"],
            "client": row["client"],
            "communication_id": row["communication_id"],
            "platforms": row["platforms"],
            "scope": row["scope"],
            "territory": row["territory"],
            "approval_required": False,
            "manual_approval_required": False,
            "autonomous_publish": True,
        }
        queue.setdefault("jobs", []).append(job)
        created.append(job)

    queue["updated_at"] = datetime.now(ROME).isoformat(timespec="seconds")
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_git("add", "publisher/final_assets/manual_inbox", "publisher/final_content_queue.json")
    run_git("config", "user.name", "F1 Manual Inbox")
    run_git("config", "user.email", "actions@users.noreply.github.com")
    commit = run_git("commit", "-m", f"Ingest {len(created)} ChatGPT final assets", check=False)
    if commit.returncode != 0:
        raise RuntimeError(f"Commit Git fallito: {commit.stderr.strip() or commit.stdout.strip()}")
    last_push_error = ""
    for attempt in range(1, 4):
        push = run_git("push", "origin", "main", check=False)
        if push.returncode == 0:
            return created
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
    raise RuntimeError(f"File salvati e commit creato, ma push GitHub fallito dopo 3 tentativi: {last_push_error}")


def _load_communications() -> dict:
    if not COMMUNICATIONS_FILE.exists():
        return {"version": 1, "items": []}
    try:
        payload = json.loads(COMMUNICATIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = {"version": 1, "items": []}
    payload.setdefault("version", 1)
    payload.setdefault("items", [])
    return payload


def _save_communications(payload: dict) -> None:
    COMMUNICATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = COMMUNICATIONS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(COMMUNICATIONS_FILE)


def _communication_hash(
    communication: str,
    client: str,
    territory: str,
    platforms: list[str],
) -> str:
    payload = "\n".join([
        re.sub(r"\\s+", " ", communication).strip().casefold(),
        client.strip().casefold(),
        territory.strip().casefold(),
        ",".join(sorted(set(platforms))),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _recent_duplicate(payload: dict, digest: str, now: datetime, window_minutes: int = 15) -> dict | None:
    cutoff = now - timedelta(minutes=max(1, window_minutes))
    for item in reversed(payload.get("items") or []):
        if str(item.get("communication_hash") or "") != digest:
            continue
        try:
            created = datetime.fromisoformat(str(item.get("created_at") or ""))
            if created.tzinfo is None:
                created = created.replace(tzinfo=ROME)
        except Exception:
            continue
        if created.astimezone(ROME) < cutoff:
            continue
        if str(item.get("status") or "").upper() not in {"FAILED", "CANCELLED"}:
            return item
    return None


def _communication_prompt(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return (
        "Genera una grafica social professionale e ultrarealistica usando i modelli che abbiamo già caricato. "
        "Rappresenta fedelmente questo comunicato per la clientela, senza inventare prezzi, date, indirizzi, "
        "promozioni, disponibilità, contatti o caratteristiche non presenti nel testo. "
        f"Comunicato: {clean}"
    )


def _launch_communication_worker(communication_id: str) -> None:
    env = os.environ.copy()
    env["F1_INBOX_PORT"] = str(int(os.getenv("F1_INBOX_PORT", "8877")))
    kwargs: dict = {
        "cwd": ROOT,
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [sys.executable, str(WORKER_FILE), "--communication-id", communication_id, "--batch-size", "1", "--fresh-run"],
        **kwargs,
    )


@app.get("/api/communications")
def api_communications():
    # Pull publication-state commits made by GitHub Actions only when the local
    # working tree is clean. A dirty tree is never modified by this status endpoint.
    try:
        status = run_git("status", "--porcelain", check=False)
        if status.returncode == 0 and not status.stdout.strip():
            run_git("pull", "--ff-only", "origin", "main", check=False)
    except Exception:
        pass

    payload = _load_communications()
    final_by_communication: dict[str, dict] = {}
    try:
        queue = load_queue()
        for job in queue.get("jobs") or []:
            communication_id = str(job.get("communication_id") or "")
            if communication_id:
                final_by_communication[communication_id] = job
    except Exception:
        final_by_communication = {}

    items = []
    for item in payload.get("items") or []:
        merged = dict(item)
        final = final_by_communication.get(str(item.get("id") or ""))
        if final:
            merged["publication_status"] = final.get("status")
            merged["published_at"] = final.get("published_at")
            merged["published_urls"] = final.get("published_urls") or []
            merged["buffer_posts"] = final.get("buffer_posts") or []
            merged["publication_error"] = final.get("error")
            if final.get("status") == "PUBLISHED":
                merged["status"] = "PUBLISHED"
            elif final.get("status") == "SCHEDULED":
                merged["status"] = "SCHEDULED"
            elif final.get("status") == "ERROR":
                merged["status"] = "ERROR"
        items.append(merged)
    return jsonify({"items": items})


@app.post("/api/communications")
def create_communication():
    body = request.get_json(silent=True) or {}
    communication = re.sub(r"\s+", " ", str(body.get("communication") or "")).strip()
    if not communication:
        return jsonify({"ok": False, "error": "Inserisci il comunicato"}), 400
    now = datetime.now(ROME)
    territory = str(body.get("territory") or "").strip()
    platforms = [str(x).lower() for x in (body.get("platforms") or ["facebook", "instagram"])]
    platforms = [x for x in platforms if x in {"facebook", "instagram", "linkedin"}]
    if not platforms:
        platforms = ["facebook", "instagram"]
    client = str(body.get("client") or "F1 Immobiliare").strip() or "F1 Immobiliare"
    digest = _communication_hash(communication, client, territory, platforms)
    payload = _load_communications()
    duplicate = _recent_duplicate(payload, digest, now)
    if duplicate:
        return jsonify({
            "ok": True,
            "id": duplicate.get("id"),
            "status": duplicate.get("status"),
            "duplicate": True,
            "message": "Comunicato identico già acquisito recentemente: riuso il job esistente.",
        })
    communication_id = f"COMM-{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"
    item = {
        "id": communication_id,
        "client": client,
        "communication": communication,
        "communication_hash": digest,
        "query": communication,
        "prompt": _communication_prompt(communication),
        "caption": communication,
        "territory": territory,
        "scope": "territory" if territory else "network",
        "platforms": platforms,
        "scheduled_at": str(body.get("scheduled_at") or now.isoformat(timespec="seconds")),
        "source": "client-communication",
        "status": "NEW",
        "attempt_count": 0,
        "created_at": now.isoformat(timespec="seconds"),
        "updated_at": now.isoformat(timespec="seconds"),
        "last_error": None,
    }
    payload.setdefault("items", []).append(item)
    item["status"] = "PROCESSING"
    item["updated_at"] = datetime.now(ROME).isoformat(timespec="seconds")
    _save_communications(payload)
    try:
        _launch_communication_worker(communication_id)
    except Exception as exc:
        item["status"] = "ERROR"
        item["last_error"] = str(exc)
        item["updated_at"] = datetime.now(ROME).isoformat(timespec="seconds")
        _save_communications(payload)
        return jsonify({"ok": False, "id": communication_id, "error": str(exc)}), 500
    return jsonify({"ok": True, "id": communication_id, "status": item["status"]})


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/ready")
def ready():
    return send_from_directory(HERE, "morning_notice.html")


@app.get("/api/health")
def api_health():
    return jsonify({"ok": True, "service": "f1-manual-asset-inbox", "port": int(os.getenv("F1_INBOX_PORT", "8877"))})


@app.get("/api/run-status")
def api_run_status():
    if not LAST_RUN_FILE.exists():
        return jsonify({"status": "NESSUNA_ESECUZIONE", "gpt_url": GPT_URL})
    try:
        return jsonify(json.loads(LAST_RUN_FILE.read_text(encoding="utf-8")))
    except Exception as exc:
        return jsonify({"status": "ERRORE_STATUS", "error": str(exc), "gpt_url": GPT_URL})


@app.get("/api/queries")
def api_queries():
    if not QUERY_FILE.exists():
        return jsonify({"queries": []})
    return jsonify(json.loads(QUERY_FILE.read_text(encoding="utf-8")))


@app.get("/api/generated")
def api_generated():
    return jsonify({"generated": latest_generated_jobs()})


@app.get("/generated/<path:relative_path>")
def generated_file(relative_path: str):
    try:
        target = _safe_generated_path(str(GENERATED_ROOT / relative_path))
    except Exception:
        return "Not found", 404
    return send_from_directory(target.parent, target.name)


@app.post("/api/ingest-generated")
def ingest_generated():
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify({"ok": False, "error": "Nessuna grafica generata selezionata"}), 400
    try:
        ensure_repo_ready()
        raw_items = []
        for item in items:
            path = _safe_generated_path(str(item.get("image_path") or ""))
            meta = {
                "query_id": item.get("query_id"),
                "query": item.get("query"),
                "family": item.get("family"),
                "caption": item.get("caption"),
                "scheduled_at": item.get("scheduled_at"),
                "territory": item.get("territory"),
                "scope": item.get("scope"),
                "platforms": item.get("platforms"),
                "client": item.get("client"),
                "communication_id": item.get("communication_id"),
                "source": "verified-f1-custom-gpt",
                "generator_path": path.relative_to(ROOT).as_posix(),
            }
            raw_items.append({"data": path.read_bytes(), "filename": path.name, "meta": meta})
        queue = load_queue()
        prepared = _prepare_records(raw_items, queue)
        created = commit_prepared(prepared, queue)
        return jsonify({"ok": True, "created": created, "message": "Grafiche verificate inviate a GitHub e messe in coda READY"})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
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
        raw_items = []
        for upload, meta in zip(files, metadata):
            raw_items.append(
                {
                    "data": upload.read(),
                    "filename": upload.filename or "asset.png",
                    "meta": meta,
                }
            )
        queue = load_queue()
        prepared = _prepare_records(raw_items, queue)
        created = commit_prepared(prepared, queue)
        return jsonify({"ok": True, "created": created, "message": "Grafiche inviate a GitHub e messe in coda READY"})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    app.run(host="127.0.0.1", port=int(os.getenv("F1_INBOX_PORT", "8877")), debug=False)
