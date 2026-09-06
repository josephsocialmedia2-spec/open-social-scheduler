from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from publisher.chatgpt_query_runner.core import (  # noqa: E402
    advance_after_completed,
    atomic_write_json,
    build_prompt,
    create_run,
    deterministic_image_name,
    finalize_run,
    get_or_create_run,
    load_state,
    run_counts,
    save_state,
    transition,
)
from publisher.chatgpt_query_runner.ui_driver import ChromeChatGPTDriver, GPT_URL  # noqa: E402

QUERY_FILE = ROOT / "publisher" / "github_graphics" / "queries.json"
STATE_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "state.json"
LAST_RUN_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "last_run.json"
OUTPUT_ROOT = ROOT / "publisher" / "final_assets" / "chatgpt_generated"
AUTOMATION_ROOT = ROOT / "publisher" / "f1_graphics_automation"
LOG_ROOT = AUTOMATION_ROOT / "logs"
ROME = ZoneInfo("Europe/Rome")
INBOX_HOST = "127.0.0.1"
INBOX_PORT = int(os.getenv("F1_INBOX_PORT", "8877"))
DEFAULT_BATCH_SIZE = int(os.getenv("F1_QUERY_BATCH_SIZE", "4"))
MAX_ATTEMPTS = max(1, int(os.getenv("F1_MAX_ATTEMPTS", "3")))

LOG_ROOT.mkdir(parents=True, exist_ok=True)
RUN_LOG = LOG_ROOT / f"worker-{datetime.now(ROME):%Y%m%d-%H%M%S}.log"


def log(message: str) -> None:
    line = f"[{datetime.now(ROME):%H:%M:%S}] {message}"
    print(line, flush=True)
    with RUN_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def load_queries() -> list[dict]:
    payload = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    rows = list(payload.get("queries") or [])
    if not rows:
        raise RuntimeError("Nessuna query disponibile in publisher/github_graphics/queries.json")
    return rows


def _health_ok() -> bool:
    try:
        with urllib.request.urlopen(f"http://{INBOX_HOST}:{INBOX_PORT}/api/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return bool(payload.get("ok")) and payload.get("service") == "f1-manual-asset-inbox"
    except Exception:
        return False


def _port_open() -> bool:
    try:
        with socket.create_connection((INBOX_HOST, INBOX_PORT), timeout=1):
            return True
    except OSError:
        return False


def start_inbox_server() -> None:
    if _health_ok():
        return
    if _port_open():
        raise RuntimeError(f"Porta {INBOX_PORT} occupata da un servizio che non è F1 Raccolta Grafiche.")
    server = ROOT / "publisher" / "manual_asset_inbox" / "server.py"
    if not server.exists():
        raise RuntimeError(f"Server Raccolta F1 non trovato: {server}")
    env = os.environ.copy()
    env.pop("RUNNER_TRACKING_ID", None)
    env["F1_INBOX_PORT"] = str(INBOX_PORT)
    kwargs: dict = {
        "cwd": ROOT,
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([sys.executable, str(server)], **kwargs)
    for _ in range(40):
        if _health_ok():
            return
        time.sleep(0.5)
    raise RuntimeError(f"F1 Raccolta Grafiche non disponibile su http://{INBOX_HOST}:{INBOX_PORT}/")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def epoch_iso(value: float) -> str:
    return datetime.fromtimestamp(value, ROME).isoformat(timespec="seconds")


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return str(path)


def last_run_payload(state: dict, run: dict, status: str | None = None, error: str | None = None) -> dict:
    counts = run_counts(run)
    return {
        "status": status or run.get("status") or "RUNNING",
        "updated_at": datetime.now(ROME).isoformat(timespec="seconds"),
        "gpt_url": GPT_URL,
        "inbox_url": f"http://{INBOX_HOST}:{INBOX_PORT}/",
        "run_id": run.get("run_id"),
        "batch_size": run.get("batch_size"),
        "next_index": state.get("next_index", 0),
        "counts": counts,
        "processed_count": counts["query_riuscite"],
        "jobs": run.get("jobs") or [],
        "completed_at": run.get("completed_at"),
        "error": error or run.get("error"),
        "log_path": relative_path(RUN_LOG),
        "browser_mode": "normal-chrome-accessibility-ui",
    }


def persist(state: dict, run: dict, *, status: str | None = None, error: str | None = None) -> None:
    save_state(STATE_FILE, state)
    atomic_write_json(LAST_RUN_FILE, last_run_payload(state, run, status=status, error=error))


def mark(state: dict, run: dict, job: dict, status: str, **fields) -> None:
    transition(job, status, **fields)
    persist(state, run)
    log(f"Query {job['sequence']}/{run['batch_size']} [{job['query_id']}] -> {status}")


def job_image_exists(job: dict) -> bool:
    value = str(job.get("image_path") or "").strip()
    if not value:
        return False
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    try:
        return path.is_file() and path.stat().st_size > 10_000
    except OSError:
        return False


def _output_stem(run: dict, job: dict) -> Path:
    run_date = str(run.get("started_at") or datetime.now(ROME).isoformat())[:10].replace("-", "")
    filename = deterministic_image_name(run_date, int(job["sequence"]), str(job["query"]), ".png")
    return OUTPUT_ROOT / run_date / Path(filename).stem


def process_job(driver: ChromeChatGPTDriver, state: dict, run: dict, job: dict, total_queries: int) -> bool:
    if job.get("status") == "COMPLETED" and job_image_exists(job):
        log(f"Query {job['sequence']}/{run['batch_size']} già COMPLETED con immagine valida: skip")
        return True
    if job.get("status") == "COMPLETED" and not job_image_exists(job):
        mark(state, run, job, "ERRORE", error="Stato COMPLETED trovato ma image_path manca o non è valido.")

    prompt = build_prompt(str(job.get("query") or ""))
    job["prompt"] = prompt
    persist(state, run)

    initial_retry = int(job.get("retry_count") or 0)
    for attempt in range(initial_retry + 1, MAX_ATTEMPTS + 1):
        stage = "QUERY_CARICATA"
        try:
            if attempt > 1 or job.get("status") in {"ERRORE", "RETRY"}:
                mark(state, run, job, "RETRY", retry_count=attempt - 1, error=None)
                driver.open_gpt()

            log(f"Query {job['sequence']}/{run['batch_size']} caricata: {job['query']}")
            mark(state, run, job, "QUERY_CARICATA", retry_count=attempt - 1, error=None)
            stage = "PROMPT_COSTRUITO"
            mark(state, run, job, "PROMPT_COSTRUITO", prompt=prompt)
            log(f"Prompt: {prompt}")

            baseline = driver.snapshot()

            stage = "COMPOSER_TROVATO"
            driver.wait_composer(timeout=40)
            mark(state, run, job, "COMPOSER_TROVATO")

            stage = "TESTO_INSERITO"
            focus_method = driver.set_and_verify_prompt(prompt)
            mark(state, run, job, "TESTO_INSERITO", focus_method=focus_method)
            stage = "TESTO_VERIFICATO"
            mark(state, run, job, "TESTO_VERIFICATO", focus_method=focus_method)

            stage = "PROMPT_INVIATO"
            submitted_at = datetime.now(ROME).isoformat(timespec="seconds")
            driver.send_and_verify(prompt)
            mark(state, run, job, "PROMPT_INVIATO", submitted_at=submitted_at)
            stage = "INVIO_VERIFICATO"
            mark(state, run, job, "INVIO_VERIFICATO", submitted_at=submitted_at)

            stage = "GENERAZIONE_IN_CORSO"
            result = driver.wait_generation(baseline)
            mark(
                state,
                run,
                job,
                "GENERAZIONE_IN_CORSO",
                generation_started_at=epoch_iso(result.started_at),
            )
            stage = "GENERAZIONE_TERMINATA"
            mark(
                state,
                run,
                job,
                "GENERAZIONE_TERMINATA",
                generation_completed_at=epoch_iso(result.completed_at),
            )
            stage = "IMMAGINE_RILEVATA"
            mark(state, run, job, "IMMAGINE_RILEVATA")

            stage = "IMMAGINE_SALVATA"
            saved_path, capture_mode = driver.save_image(result, _output_stem(run, job))
            digest = sha256_file(saved_path)
            mark(
                state,
                run,
                job,
                "IMMAGINE_SALVATA",
                image_path=relative_path(saved_path),
                image_sha256=digest,
                capture_mode=capture_mode,
            )

            stage = "COMPLETED"
            mark(state, run, job, "COMPLETED", error=None)
            advance_after_completed(state, job, total_queries)
            persist(state, run)
            log(f"Query {job['sequence']} COMPLETED: {relative_path(saved_path)}")
            return True

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            diagnostics = {}
            try:
                diagnostics = driver.save_diagnostics(
                    stage=stage,
                    query=str(job.get("query") or ""),
                    retry_count=attempt,
                    error=error,
                )
            except Exception as diag_exc:
                diagnostics = {"diagnostic_error": str(diag_exc)}
            mark(
                state,
                run,
                job,
                "ERRORE",
                retry_count=attempt,
                error=error,
                diagnostics=diagnostics,
            )
            log(f"ERRORE query {job['sequence']} tentativo {attempt}/{MAX_ATTEMPTS}: {error}")
            if attempt >= MAX_ATTEMPTS:
                return False
            time.sleep(min(5 * attempt, 15))
    return False


def run(batch_size: int, *, fresh_run: bool = False) -> int:
    start_inbox_server()
    queries = load_queries()
    state = load_state(STATE_FILE)
    if fresh_run:
        run = create_run(state, queries, batch_size)
    else:
        run = get_or_create_run(state, queries, batch_size)
    run["status"] = "RUNNING"
    run["completed_at"] = None
    persist(state, run, status="RUNNING")

    log(f"RUN START {run['run_id']} - batch {run['batch_size']}")
    driver = ChromeChatGPTDriver(log=log, diagnostic_root=LOG_ROOT)
    try:
        driver.open_gpt()
    except Exception as exc:
        run["error"] = f"{type(exc).__name__}: {exc}"
        final_status = finalize_run(state)
        persist(state, run, status=final_status, error=run["error"])
        try:
            driver.save_diagnostics(stage="APERTURA_GPT", query="", retry_count=0, error=run["error"])
        except Exception:
            pass
        raise

    success = 0
    for job in run.get("jobs") or []:
        if process_job(driver, state, run, job, len(queries)):
            success += 1

    final_status = finalize_run(state)
    persist(state, run, status=final_status)
    counts = run_counts(run)
    log(
        "RUN END "
        f"status={final_status} previste={counts['query_previste']} "
        f"riuscite={counts['query_riuscite']} immagini_salvate={counts['immagini_salvate']}"
    )

    # Raccolta e chat restano separate: apre la schermata mattutina in una nuova scheda.
    try:
        driver.open_new_tab(f"http://{INBOX_HOST}:{INBOX_PORT}/ready")
    except Exception as exc:
        log(f"Impossibile aprire automaticamente la schermata mattutina: {exc}")

    return 0 if final_status == "GRAFICHE_PRONTE" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--fresh-run", action="store_true", help="Avvia un nuovo batch senza riprendere quello precedente")
    args = parser.parse_args()

    if args.scheduled:
        now = datetime.now(ROME)
        if now.hour != 23:
            print(f"NOOP: ora locale {now:%H:%M}; esecuzione automatica ammessa alle 23:xx Europe/Rome")
            return 0

    try:
        return run(max(1, args.batch_size), fresh_run=args.fresh_run)
    except Exception as exc:
        log(f"FATAL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
