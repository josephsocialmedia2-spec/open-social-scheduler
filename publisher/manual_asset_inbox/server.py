from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSET_ROOT = ROOT / "publisher" / "final_assets" / "manual_inbox"
QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
QUERY_FILE = ROOT / "publisher" / "github_graphics" / "queries.json"
LAST_RUN_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "last_run.json"
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


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/ready")
def ready():
    return send_from_directory(HERE, "morning_notice.html")


@app.get("/api/health")
def api_health():
    return jsonify({"ok": True, "service": "f1-manual-asset-inbox"})


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


@app.post("/api/ingest")
def ingest():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "error": "Nessun file ricevuto"}), 400

    meta_raw = request.form.get("metadata", "[]")
    try:
        metadata = json.loads(meta_raw)
    except Exception:
        return jsonify({"ok": False, "error": "Metadata non validi"}), 400
    if len(metadata) != len(files):
        return jsonify({"ok": False, "error": "Numero file e metadata non coincide"}), 400

    status = run_git("status", "--porcelain")
    if status.stdout.strip():
        return jsonify({"ok": False, "error": "Repository locale con modifiche non salvate. Attendi la chiusura del ciclo notturno o esegui il salvataggio Git."}), 409
    run_git("pull", "--rebase", "origin", "main")

    queue = load_queue()
    hashes = existing_hashes(queue)
    qmap = query_map()
    today = datetime.now(ROME).strftime("%Y%m%d")
    dest_dir = ASSET_ROOT / today
    dest_dir.mkdir(parents=True, exist_ok=True)
    created = []

    for pos, (upload, meta) in enumerate(zip(files, metadata), start=1):
        data = upload.read()
        if len(data) < 10_000:
            return jsonify({"ok": False, "error": f"{upload.filename}: file troppo piccolo"}), 400
        digest = sha256_bytes(data)
        if digest.lower() in hashes:
            return jsonify({"ok": False, "error": f"{upload.filename}: immagine già presente in coda"}), 409

        query_id = str(meta.get("query_id") or "").strip()
        row = qmap.get(query_id, {})
        query = str(meta.get("query") or row.get("query") or upload.filename or "Grafica F1").strip()
        family = str(meta.get("family") or row.get("family") or "property").strip()
        caption = str(meta.get("caption") or "").strip() or auto_caption(query, family)
        scheduled_at = str(meta.get("scheduled_at") or "").strip() or next_slot()

        ext = Path(upload.filename or "asset.png").suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
            ext = ".png"
        stem = safe_slug(query)
        filename = f"{today}-{pos:02d}-{stem}{ext}"
        out = dest_dir / filename
        out.write_bytes(data)
        rel = out.relative_to(ROOT).as_posix()

        job_id = f"manual-{today}-{pos:02d}-{digest[:8]}"
        job = {
            "id": job_id,
            "title": query,
            "format": "photo",
            "assets": [{"path": rel, "sha256": digest}],
            "caption": caption,
            "cta": "",
            "hashtags": [],
            "scheduled_at": scheduled_at,
            "status": "READY",
            "source": "manual-f1-custom-gpt",
            "generator_url": GPT_URL,
            "query_id": query_id,
            "query": query,
            "family": family,
        }
        queue.setdefault("jobs", []).append(job)
        hashes.add(digest.lower())
        created.append(job)

    queue["updated_at"] = datetime.now(ROME).isoformat(timespec="seconds")
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    run_git("add", "publisher/final_assets/manual_inbox", "publisher/final_content_queue.json")
    run_git("config", "user.name", "F1 Manual Inbox")
    run_git("config", "user.email", "actions@users.noreply.github.com")
    run_git("commit", "-m", f"Ingest {len(created)} ChatGPT final assets")
    push = run_git("push", "origin", "main", check=False)
    if push.returncode != 0:
        return jsonify({
            "ok": False,
            "error": "File salvati e commit creato, ma push GitHub fallito",
            "details": push.stderr.strip(),
            "created": created,
        }), 500

    return jsonify({"ok": True, "created": created, "message": "Grafiche inviate a GitHub e messe in coda READY"})


if __name__ == "__main__":
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    app.run(host="127.0.0.1", port=int(os.getenv("F1_INBOX_PORT", "8765")), debug=False)
