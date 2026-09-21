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
from datetime import datetime, timedelta
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
from publisher.chatgpt_query_runner.f1_brand_layer import apply_f1_brand_layer  # noqa: E402

QUERY_FILE = Path(os.getenv("F1_QUERY_FILE", str(ROOT / "publisher" / "github_graphics" / "queries.json")))
COMMUNICATIONS_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "communications.local.json"
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
MAX_COMMUNICATION_ATTEMPTS = max(1, int(os.getenv("F1_COMM_MAX_ATTEMPTS", "5")))
MAX_PUBLISH_VERIFY_SECONDS = max(60, int(os.getenv("F1_PUBLISH_VERIFY_SECONDS", "1800")))
FINAL_QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
DAILY_QUERY_FILE = "f1_browser_creative_queries.json"
NEWS_QUERY_FILE = "f1_news_current.local.json"

LOG_ROOT.mkdir(parents=True, exist_ok=True)
RUN_LOG = LOG_ROOT / f"worker-{datetime.now(ROME):%Y%m%d-%H%M%S}.log"


def log(message: str) -> None:
    line = f"[{datetime.now(ROME):%H:%M:%S}] {message}"
    print(line, flush=True)
    with RUN_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


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
    atomic_write_json(COMMUNICATIONS_FILE, payload)


def set_communication_status(communication_id: str | None, status: str, error: str | None = None) -> None:
    if not communication_id:
        return
    payload = _load_communications()
    for item in payload.get("items") or []:
        if str(item.get("id") or "") != communication_id:
            continue
        item["status"] = status
        item["updated_at"] = datetime.now(ROME).isoformat(timespec="seconds")
        item["last_error"] = error
        if status == "PROCESSING":
            item["attempt_count"] = int(item.get("attempt_count") or 0) + 1
        _save_communications(payload)
        return


def pending_communication_ids(limit: int) -> list[str]:
    payload = _load_communications()
    now = datetime.now(ROME)
    result: list[str] = []
    for item in payload.get("items") or []:
        communication_id = str(item.get("id") or "")
        if not communication_id:
            continue
        attempts = int(item.get("attempt_count") or 0)
        if attempts >= MAX_COMMUNICATION_ATTEMPTS:
            continue
        status = str(item.get("status") or "NEW").upper()
        eligible = status in {"NEW", "ERROR"}
        if status == "PROCESSING":
            try:
                updated = datetime.fromisoformat(str(item.get("updated_at") or ""))
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=ROME)
                eligible = now - updated.astimezone(ROME) >= timedelta(minutes=20)
            except Exception:
                eligible = True
        if eligible:
            result.append(communication_id)
        if len(result) >= max(1, int(limit)):
            break
    return result


def load_queries(communication_id: str | None = None) -> list[dict]:
    if communication_id:
        payload = _load_communications()
        for item in payload.get("items") or []:
            if str(item.get("id") or "") == communication_id:
                return [{
                    "id": communication_id,
                    "query": str(item.get("query") or item.get("communication") or "").strip(),
                    "communication": str(item.get("communication") or "").strip(),
                    "prompt": str(item.get("prompt") or "").strip(),
                    "caption": str(item.get("caption") or item.get("communication") or "").strip(),
                    "client": str(item.get("client") or "F1 Immobiliare").strip(),
                    "territory": str(item.get("territory") or "").strip(),
                    "scope": str(item.get("scope") or ("territory" if item.get("territory") else "network")).strip(),
                    "platforms": list(item.get("platforms") or ["facebook", "instagram"]),
                    "scheduled_at": str(item.get("scheduled_at") or datetime.now(ROME).isoformat(timespec="seconds")),
                    "source": "client-communication",
                }]
        raise RuntimeError(f"Comunicato non trovato: {communication_id}")

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


def is_daily_f1_mode() -> bool:
    return QUERY_FILE.name.casefold() == DAILY_QUERY_FILE.casefold()


def is_news_f1_mode() -> bool:
    return QUERY_FILE.name.casefold() == NEWS_QUERY_FILE.casefold()


def _resolve_job_path(value: str | None) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _valid_image_path(value: str | None) -> Path | None:
    path = _resolve_job_path(value)
    if path is None:
        return None
    try:
        return path if path.is_file() and path.stat().st_size > 10_000 else None
    except OSError:
        return None


def _daily_communication_id(job: dict) -> str:
    today = datetime.now(ROME).strftime("%Y%m%d")
    query_id = str(job.get("query_id") or "F1-DAILY").replace(" ", "-")
    return f"COMM-F1-{today}-{query_id}"


def _brand_path_for(source: Path) -> Path:
    return source.with_name(source.stem + "-brand.png")


def apply_brand_to_job(state: dict, run: dict, job: dict, source: Path) -> Path:
    destination = _brand_path_for(source)
    result = apply_f1_brand_layer(
        source,
        destination,
        headline=str(job.get("headline") or "QUANTO VALE CASA MIA?"),
        cta=str(job.get("cta") or "RICHIEDI UNA VALUTAZIONE"),
        territory=str(job.get("territory") or "VALLE DI SUSA"),
    )
    branded = ROOT / result["path"]
    job["source_image_path"] = relative_path(source)
    job["brand_path"] = result["path"]
    job["image_path"] = result["path"]
    job["image_sha256"] = result["sha256"]
    job["brand_qa"] = result["brand_qa"]
    job["visual_qa"] = result["visual_qa"]
    mark(state, run, job, "FILE_VALIDATED", image_path=result["path"], image_sha256=result["sha256"])
    mark(state, run, job, "QA_PENDING")
    mark(state, run, job, "QA_PASS", visual_qa=result["visual_qa"])
    mark(state, run, job, "BRAND_PASS", brand_qa=result["brand_qa"])
    return branded


def _origin_queue() -> dict:
    fetch = subprocess.run(
        ["git", "-C", str(ROOT), "fetch", "origin", "main"],
        capture_output=True,
        text=True,
        check=False,
    )
    if fetch.returncode != 0:
        raise RuntimeError(fetch.stderr.strip() or fetch.stdout.strip() or "git fetch origin main fallito")
    show = subprocess.run(
        ["git", "-C", str(ROOT), "show", "origin/main:publisher/final_content_queue.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if show.returncode != 0:
        raise RuntimeError(show.stderr.strip() or "Impossibile leggere la coda remota")
    return json.loads(show.stdout)


def wait_for_publication_verification(communication_id: str, timeout: int = MAX_PUBLISH_VERIFY_SECONDS) -> dict:
    deadline = time.time() + timeout
    last_status = ""
    while time.time() < deadline:
        try:
            queue = _origin_queue()
            for item in queue.get("jobs") or []:
                if str(item.get("communication_id") or "") != communication_id:
                    continue
                status = str(item.get("status") or "")
                if status != last_status:
                    log(f"PUBBLICAZIONE {communication_id}: {status}")
                    last_status = status
                if status == "PUBLISHED_VERIFIED":
                    return item
                if status == "ERROR":
                    raise RuntimeError(str(item.get("error") or "Publisher remoto in errore"))
        except RuntimeError:
            raise
        except Exception as exc:
            log(f"Verifica pubblicazione transitoria: {type(exc).__name__}: {exc}")
        time.sleep(15)
    raise RuntimeError(
        f"Timeout verifica remota dopo {timeout}s; ultimo stato={last_status or 'non disponibile'}"
    )


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
    post_generation = {
        "COMPLETED", "READY_TO_PUBLISH", "PUBLISHING", "PUBLISHED",
        "VERIFYING_PUBLICATION", "PUBLISHED_VERIFIED"
    }
    existing = _valid_image_path(job.get("image_path"))
    if job.get("status") in post_generation and existing is not None:
        log(
            f"Query {job['sequence']}/{run['batch_size']} già oltre la generazione "
            f"({job.get('status')}): riuso {relative_path(existing)}"
        )
        return True

    # Recovery: immagine già scaricata ma brand layer non completato.
    source_existing = _valid_image_path(job.get("source_image_path")) or (
        existing if existing is not None and not str(job.get("brand_path") or "").strip() else None
    )
    if source_existing is not None and job.get("status") in {
        "IMMAGINE_SALVATA", "DOWNLOADED", "FILE_VALIDATED", "QA_PENDING", "QA_PASS", "BRAND_PASS"
    }:
        branded = _valid_image_path(job.get("brand_path"))
        if branded is None:
            branded = apply_brand_to_job(state, run, job, source_existing)
        mark(state, run, job, "COMPLETED", error=None, image_path=relative_path(branded))
        advance_after_completed(state, job, total_queries)
        persist(state, run)
        return True

    prompt = str(job.get("prompt") or "").strip() or build_prompt(str(job.get("query") or ""))
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
            mark(state, run, job, "PROMPT_SUBMITTED", submitted_at=submitted_at)
            stage = "INVIO_VERIFICATO"
            mark(state, run, job, "INVIO_VERIFICATO", submitted_at=submitted_at)

            stage = "GENERAZIONE_IN_CORSO"
            mark(state, run, job, "GENERATING")
            result = driver.wait_generation(baseline, prompt=prompt)
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
            mark(state, run, job, "IMAGE_READY")
            mark(state, run, job, "DOWNLOAD_PENDING")

            stage = "IMMAGINE_SALVATA"
            mark(state, run, job, "DOWNLOADING")
            saved_path, capture_mode = driver.save_image(result, _output_stem(run, job))
            digest = sha256_file(saved_path)
            mark(
                state,
                run,
                job,
                "IMMAGINE_SALVATA",
                source_image_path=relative_path(saved_path),
                image_path=relative_path(saved_path),
                image_sha256=digest,
                capture_mode=capture_mode,
            )
            mark(
                state,
                run,
                job,
                "DOWNLOADED",
                source_image_path=relative_path(saved_path),
                image_path=relative_path(saved_path),
                image_sha256=digest,
                capture_mode=capture_mode,
            )

            branded_path = apply_brand_to_job(state, run, job, saved_path)

            stage = "COMPLETED"
            mark(state, run, job, "COMPLETED", error=None, image_path=relative_path(branded_path))
            advance_after_completed(state, job, total_queries)
            persist(state, run)
            log(f"Query {job['sequence']} COMPLETED: {relative_path(branded_path)}")
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


def auto_ingest_completed_run(run: dict, *, daily_mode: bool = False) -> dict:
    items = []
    for job in run.get("jobs") or []:
        if job.get("status") not in {"COMPLETED", "READY_TO_PUBLISH", "PUBLISHING", "PUBLISHED", "VERIFYING_PUBLICATION", "PUBLISHED_VERIFIED"} or not job_image_exists(job):
            continue
        communication_id = _daily_communication_id(job) if daily_mode else (
            job.get("query_id") if str(job.get("query_id") or "").startswith("COMM-") else ""
        )
        caption = str(job.get("caption") or "").strip()
        if not caption and daily_mode:
            caption = (
                "Quanto vale davvero casa tua? Scopri il valore reale del tuo immobile "
                "con una valutazione professionale e senza impegno. Scrivi VALUTAZIONE in privato. "
                "#F1Immobiliare #ValleDiSusa #ValutazioneImmobiliare #VendereCasa"
            )
        items.append({
            "image_path": job.get("image_path"),
            "query_id": job.get("query_id"),
            "query": job.get("query"),
            "family": "property",
            "caption": caption or job.get("communication") or job.get("query"),
            "scheduled_at": datetime.now(ROME).isoformat(timespec="seconds") if daily_mode else (
                job.get("scheduled_at") or datetime.now(ROME).isoformat(timespec="seconds")
            ),
            "territory": job.get("territory"),
            "scope": job.get("scope") or ("territory" if job.get("territory") else "network"),
            "platforms": job.get("platforms") or ["facebook", "instagram"],
            "client": job.get("client") or "F1 Immobiliare",
            "communication_id": communication_id,
            "news_id": job.get("news_id"),
            "headline": job.get("headline"),
            "cta": job.get("cta"),
            "category": job.get("category"),
            "source_name": job.get("source_name"),
            "source_url": job.get("source_url"),
            "source_hash": job.get("source_hash"),
            "source_published_at": job.get("source_published_at"),
            "editorial_slot": job.get("editorial_slot"),
            "prompt": job.get("prompt"),
        })
    if not items:
        raise RuntimeError("Nessuna immagine COMPLETED disponibile per l'invio automatico alla pubblicazione")

    body = json.dumps({"items": items}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"http://{INBOX_HOST}:{INBOX_PORT}/api/ingest-generated",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("ok"):
                raise RuntimeError(str(payload.get("error") or "Ingest automatico non riuscito"))
            log(f"AUTO INGEST OK: {len(payload.get('created') or [])} contenuti in coda READY")
            return payload
        except Exception as exc:
            last_error = exc
            log(f"AUTO INGEST tentativo {attempt}/3 fallito: {type(exc).__name__}: {exc}")
            if attempt < 3:
                time.sleep(5 * attempt)
    raise RuntimeError(f"Auto ingest fallito dopo 3 tentativi: {last_error}")


def run(batch_size: int, *, fresh_run: bool = False, communication_id: str | None = None) -> int:
    start_inbox_server()
    queries = load_queries(communication_id)
    if communication_id:
        batch_size = 1
        fresh_run = True
        set_communication_status(communication_id, "PROCESSING")
    state = load_state(STATE_FILE)
    daily_mode = is_daily_f1_mode() and not communication_id
    news_mode = is_news_f1_mode() and not communication_id
    today = datetime.now(ROME).date().isoformat()
    if daily_mode and state.get("last_successful_date") == today:
        log(f"NOOP_ALREADY_COMPLETED_TODAY: {today}")
        return 0

    # Daily/news jobs must resume downstream work instead of generating a
    # second image after IMAGE_READY, DOWNLOADED or READY_TO_PUBLISH.
    if daily_mode or news_mode:
        fresh_run = False

    active = state.get("active_run")
    news_query_id = str((queries[0] if queries else {}).get("id") or "")
    if (
        news_mode
        and isinstance(active, dict)
        and active.get("jobs")
        and str((active.get("jobs") or [{}])[0].get("query_id") or "") == news_query_id
        and str(active.get("status") or "") != "PUBLISHED_VERIFIED"
    ):
        run = active
        run["status"] = "RUNNING"
        run["completed_at"] = None
    elif fresh_run:
        run = create_run(state, queries, batch_size)
    else:
        run = get_or_create_run(state, queries, batch_size)
    run["status"] = "RUNNING"
    run["completed_at"] = None
    persist(state, run, status="RUNNING")

    log(f"RUN START {run['run_id']} - batch {run['batch_size']}")
    driver = ChromeChatGPTDriver(log=log, diagnostic_root=LOG_ROOT)
    downstream_only = all(
        str(job.get("status") or "") in {
            "COMPLETED", "READY_TO_PUBLISH", "PUBLISHING", "PUBLISHED",
            "VERIFYING_PUBLICATION", "PUBLISHED_VERIFIED"
        }
        and _valid_image_path(job.get("image_path")) is not None
        for job in (run.get("jobs") or [])
    )
    try:
        if not downstream_only:
            for job in run.get("jobs") or []:
                if str(job.get("status") or "") not in {
                    "COMPLETED", "READY_TO_PUBLISH", "PUBLISHING", "PUBLISHED",
                    "VERIFYING_PUBLICATION", "PUBLISHED_VERIFIED"
                }:
                    mark(state, run, job, "OPENING_CHATGPT")
            driver.open_gpt()
        else:
            log("Browser non riaperto: asset già generato, riprendo dalla pubblicazione.")
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

    daily_mode = is_daily_f1_mode() and not communication_id
    news_mode = is_news_f1_mode() and not communication_id
    if daily_mode or news_mode:
        final_status = "GRAFICHE_PRONTE" if success == len(run.get("jobs") or []) else "ERRORE"
        run["status"] = final_status
        persist(state, run, status=final_status)
    else:
        final_status = finalize_run(state)
        persist(state, run, status=final_status)
    counts = run_counts(run)
    log(
        "RUN END "
        f"status={final_status} previste={counts['query_previste']} "
        f"riuscite={counts['query_riuscite']} immagini_salvate={counts['immagini_salvate']}"
    )

    if final_status != "GRAFICHE_PRONTE":
        set_communication_status(communication_id, "ERROR", run.get("error") or final_status)
        return 2

    daily_mode = is_daily_f1_mode()
    news_mode = is_news_f1_mode()
    if not communication_id and not daily_mode and not news_mode:
        log("Batch grafico statico legacy completato: nessuna pubblicazione automatica.")
        return 0

    try:
        ingest = auto_ingest_completed_run(run, daily_mode=daily_mode)
        run["autonomous_ingest"] = ingest
        created = list(ingest.get("created") or [])
        effective_communication_id = communication_id
        if daily_mode and run.get("jobs"):
            effective_communication_id = _daily_communication_id(run["jobs"][0])
        elif news_mode and run.get("jobs"):
            candidate = str(run["jobs"][0].get("query_id") or "")
            if candidate.startswith("COMM-NEWS-"):
                effective_communication_id = candidate
        for job in run.get("jobs") or []:
            if job_image_exists(job):
                mark(state, run, job, "READY_TO_PUBLISH", communication_id=effective_communication_id)
        run["status"] = "READY_TO_PUBLISH"
        persist(state, run, status="READY_TO_PUBLISH")
        set_communication_status(communication_id, "QUEUED_FOR_PUBLISH")
        log("PIPELINE LOCALE: grafica verificata e brandizzata -> GitHub -> coda READY")

        if effective_communication_id:
            for job in run.get("jobs") or []:
                if job_image_exists(job):
                    mark(state, run, job, "VERIFYING_PUBLICATION")
            run["status"] = "VERIFYING_PUBLICATION"
            persist(state, run, status="VERIFYING_PUBLICATION")
            published = wait_for_publication_verification(effective_communication_id)
            remote_ids = [
                str(x.get("post_id") or "")
                for x in (published.get("buffer_posts") or [])
                if str(x.get("post_id") or "").strip()
            ]
            remote_urls = list(published.get("published_urls") or [])
            for job in run.get("jobs") or []:
                if job_image_exists(job):
                    mark(
                        state,
                        run,
                        job,
                        "PUBLISHED_VERIFIED",
                        remote_post_id=(remote_ids[0] if remote_ids else ""),
                        remote_post_ids=remote_ids,
                        remote_post_url=(remote_urls[0] if remote_urls else ""),
                        remote_post_urls=remote_urls,
                        published_at=published.get("published_at"),
                    )
            run["status"] = "PUBLISHED_VERIFIED"
            run["published_at"] = published.get("published_at")
            run["remote_post_ids"] = remote_ids
            run["remote_post_urls"] = remote_urls
            state["last_successful_date"] = datetime.now(ROME).date().isoformat()
            persist(state, run, status="PUBLISHED_VERIFIED")
            set_communication_status(communication_id, "PUBLISHED")
            log(
                "F1 DAILY CREATIVE COMPLETATO: download OK -> brand OK -> "
                "pubblicazione remota verificata"
            )
        return 0
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        run["error"] = error
        run["status"] = "ERRORE_PUBBLICAZIONE"
        persist(state, run, status="ERRORE_PUBBLICAZIONE", error=error)
        set_communication_status(communication_id, "ERROR", error)
        log(f"ERRORE passaggio automatico alla pubblicazione: {error}")
        return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--query-file", help="File JSON query alternativo")
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--fresh-run", action="store_true", help="Avvia un nuovo batch senza riprendere quello precedente")
    parser.add_argument("--communication-id", help="Elabora un singolo comunicato inserito dall'utente")
    args = parser.parse_args()

    global QUERY_FILE
    if args.query_file:
        candidate = Path(args.query_file)
        QUERY_FILE = candidate if candidate.is_absolute() else ROOT / candidate

    if args.scheduled and not args.communication_id:
        now = datetime.now(ROME)
        if now.hour != 23:
            print(f"NOOP: ora locale {now:%H:%M}; esecuzione automatica ammessa alle 23:xx Europe/Rome")
            return 0
        pending = pending_communication_ids(max(1, args.batch_size))
        if not pending:
            print("NOOP: nessun comunicato NEW/ERROR/stale da recuperare alle 23:00")
            return 0
        code = 0
        for communication_id in pending:
            try:
                code = max(code, run(1, fresh_run=True, communication_id=communication_id))
            except Exception as exc:
                set_communication_status(communication_id, "ERROR", f"{type(exc).__name__}: {exc}")
                log(f"RECOVERY FATAL {communication_id}: {type(exc).__name__}: {exc}")
                code = max(code, 1)
        return code

    try:
        return run(max(1, args.batch_size), fresh_run=args.fresh_run, communication_id=args.communication_id)
    except Exception as exc:
        log(f"FATAL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
