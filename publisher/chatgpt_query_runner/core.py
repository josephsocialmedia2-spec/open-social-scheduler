from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_VERSION = 2
MAX_RUN_HISTORY = 30

STAGES = (
    "QUERY_CARICATA",
    "PROMPT_COSTRUITO",
    "COMPOSER_TROVATO",
    "TESTO_INSERITO",
    "TESTO_VERIFICATO",
    "PROMPT_INVIATO",
    "INVIO_VERIFICATO",
    "GENERAZIONE_IN_CORSO",
    "GENERAZIONE_TERMINATA",
    "IMMAGINE_RILEVATA",
    "IMMAGINE_SALVATA",
    "COMPLETED",
)
TERMINAL_RUN_STATUSES = {"GRAFICHE_PRONTE", "ANNULLATO"}


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now().astimezone()).isoformat(timespec="seconds")


def normalize_query(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if not value:
        raise ValueError("Query vuota")
    return value


def build_prompt(query: str) -> str:
    return (
        "Genera un'immagine ultrarealistica, usa i modelli che abbiamo caricato per "
        f"cerchiamo {normalize_query(query)}."
    )


def safe_slug(value: str, max_len: int = 72) -> str:
    value = normalize_query(value).lower()
    value = re.sub(r"[^a-z0-9àèéìòù]+", "-", value, flags=re.IGNORECASE).strip("-")
    return (value[:max_len] or "grafica").strip("-") or "grafica"


def deterministic_image_name(run_date: str, sequence: int, query: str, ext: str = ".png") -> str:
    ext = ext.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".png"
    return f"{run_date}_{sequence:03d}_{safe_slug(query)}{ext}"


def blank_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "next_index": 0,
        "active_run": None,
        "runs": [],
        "legacy_unverified": [],
    }


def migrate_state(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return blank_state()
    if payload.get("version") == STATE_VERSION:
        state = deepcopy(payload)
        state.setdefault("next_index", 0)
        state.setdefault("active_run", None)
        state.setdefault("runs", [])
        state.setdefault("legacy_unverified", [])
        return state
    state = blank_state()
    old_completed = payload.get("completed") or []
    if isinstance(old_completed, list):
        state["legacy_unverified"] = deepcopy(old_completed)[-100:]
    return state


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return blank_state()
    try:
        return migrate_state(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return blank_state()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def save_state(path: Path, state: dict[str, Any]) -> None:
    atomic_write_json(path, state)


def _new_job(row: dict[str, Any], query_index: int, sequence: int) -> dict[str, Any]:
    query = normalize_query(row.get("query") or "")
    stamp = now_iso()
    return {
        "sequence": sequence,
        "query_index": query_index,
        "query_id": str(row.get("id") or f"QUERY-{query_index + 1:03d}"),
        "query": query,
        "prompt": build_prompt(query),
        "status": "QUERY_CARICATA",
        "retry_count": 0,
        "submitted_at": None,
        "generation_started_at": None,
        "generation_completed_at": None,
        "image_path": None,
        "image_sha256": None,
        "capture_mode": None,
        "error": None,
        "updated_at": stamp,
        "history": [{"status": "QUERY_CARICATA", "at": stamp}],
    }


def _archive_active_before_fresh_run(state: dict[str, Any], now: datetime | None = None) -> None:
    active = state.get("active_run")
    if not isinstance(active, dict) or not active.get("run_id"):
        return
    snapshot = deepcopy(active)
    if snapshot.get("status") != "GRAFICHE_PRONTE":
        snapshot["status"] = "ANNULLATO"
        snapshot["completed_at"] = now_iso(now)
        snapshot["error"] = (
            "Batch sostituito da un nuovo avvio esplicito (--fresh-run); "
            "stato precedente preservato nello storico."
        )
    history = state.setdefault("runs", [])
    if history and history[-1].get("run_id") == snapshot.get("run_id"):
        history[-1] = snapshot
    else:
        history.append(snapshot)
    if len(history) > MAX_RUN_HISTORY:
        del history[:-MAX_RUN_HISTORY]


def create_run(
    state: dict[str, Any],
    queries: list[dict[str, Any]],
    batch_size: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not queries:
        raise ValueError("Nessuna query disponibile")
    _archive_active_before_fresh_run(state, now=now)
    batch_size = max(1, int(batch_size))
    start = int(state.get("next_index", 0)) % len(queries)
    stamp = (now or datetime.now().astimezone()).strftime("%Y%m%dT%H%M%S")
    run = {
        "run_id": f"{stamp}-{uuid.uuid4().hex[:8]}",
        "status": "RUNNING",
        "batch_size": batch_size,
        "start_index": start,
        "started_at": now_iso(now),
        "completed_at": None,
        "jobs": [
            _new_job(queries[(start + offset) % len(queries)], (start + offset) % len(queries), offset + 1)
            for offset in range(batch_size)
        ],
        "error": None,
    }
    state["active_run"] = run
    return run


def get_or_create_run(
    state: dict[str, Any],
    queries: list[dict[str, Any]],
    batch_size: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    active = state.get("active_run")
    if isinstance(active, dict):
        incomplete = any(job.get("status") != "COMPLETED" for job in active.get("jobs") or [])
        if incomplete and active.get("status") not in TERMINAL_RUN_STATUSES:
            active["status"] = "RUNNING"
            active["completed_at"] = None
            return active
    return create_run(state, queries, batch_size, now=now)


def transition(job: dict[str, Any], status: str, *, at: str | None = None, **fields: Any) -> None:
    if status not in STAGES and status not in {"ERRORE", "RETRY"}:
        raise ValueError(f"Stato non valido: {status}")
    stamp = at or now_iso()
    job["status"] = status
    job["updated_at"] = stamp
    for key, value in fields.items():
        job[key] = value
    job.setdefault("history", []).append(
        {
            "status": status,
            "at": stamp,
            **{k: v for k, v in fields.items() if k in {"error", "retry_count"}},
        }
    )


def advance_after_completed(state: dict[str, Any], job: dict[str, Any], total_queries: int) -> None:
    if job.get("status") != "COMPLETED":
        raise ValueError("next_index può avanzare solo dopo COMPLETED")
    if not str(job.get("image_path") or "").strip():
        raise ValueError("COMPLETED richiede image_path")
    if total_queries <= 0:
        raise ValueError("total_queries non valido")
    state["next_index"] = (int(job["query_index"]) + 1) % total_queries


def run_counts(run: dict[str, Any]) -> dict[str, int]:
    jobs = list(run.get("jobs") or [])
    return {
        "query_previste": len(jobs),
        "query_inviate": sum(1 for j in jobs if j.get("submitted_at")),
        "query_riuscite": sum(1 for j in jobs if j.get("status") == "COMPLETED"),
        "immagini_generate": sum(1 for j in jobs if j.get("generation_completed_at")),
        "immagini_salvate": sum(1 for j in jobs if j.get("image_path")),
    }


def finalize_run(state: dict[str, Any], *, now: datetime | None = None) -> str:
    run = state.get("active_run")
    if not isinstance(run, dict):
        raise ValueError("active_run mancante")
    counts = run_counts(run)
    expected = counts["query_previste"]
    if expected and counts["query_riuscite"] == expected and counts["immagini_salvate"] == expected:
        status = "GRAFICHE_PRONTE"
    elif counts["query_riuscite"] or counts["immagini_salvate"]:
        status = "PARZIALE"
    else:
        status = "ERRORE"
    run["status"] = status
    run["completed_at"] = now_iso(now)
    run["counts"] = counts
    history = state.setdefault("runs", [])
    snapshot = deepcopy(run)
    if history and history[-1].get("run_id") == run.get("run_id"):
        history[-1] = snapshot
    else:
        history.append(snapshot)
    if len(history) > MAX_RUN_HISTORY:
        del history[:-MAX_RUN_HISTORY]
    return status
