from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
QUERY_FILE = ROOT / "publisher" / "github_graphics" / "queries.json"
STATE_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "state.json"
LAST_RUN_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "last_run.json"
GPT_URL = "https://chatgpt.com/g/g-6a9c210485488191b072eb694c2f114c-generatore-grafica-f1"
ROME = ZoneInfo("Europe/Rome")
DEFAULT_BATCH_SIZE = int(os.getenv("F1_QUERY_BATCH_SIZE", "4"))
INBOX_HOST = "127.0.0.1"
INBOX_PORT = int(os.getenv("F1_INBOX_PORT", "8765"))


def write_last_run(status: str, **extra) -> None:
    payload = {
        "status": status,
        "updated_at": datetime.now(ROME).isoformat(timespec="seconds"),
        "gpt_url": GPT_URL,
        "inbox_url": f"http://{INBOX_HOST}:{INBOX_PORT}/",
        **extra,
    }
    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"next_index": 0, "completed": []}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_queries() -> list[dict]:
    payload = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    rows = list(payload.get("queries") or [])
    if not rows:
        raise RuntimeError("Nessuna query disponibile in publisher/github_graphics/queries.json")
    return rows


def chrome_binary() -> str:
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return "chrome.exe"


def chrome_user_data_dir() -> Path:
    override = os.getenv("F1_CHROME_USER_DATA_DIR", "").strip()
    if override:
        return Path(os.path.expandvars(override))
    return Path(os.path.expandvars(r"%LocalAppData%\Google\Chrome\User Data"))


def chrome_profile(user_data: Path) -> str:
    override = os.getenv("F1_CHROME_PROFILE", "").strip()
    if override:
        return override
    local_state = user_data / "Local State"
    try:
        payload = json.loads(local_state.read_text(encoding="utf-8"))
        last_used = str((payload.get("profile") or {}).get("last_used") or "").strip()
        if last_used and (user_data / last_used).exists():
            return last_used
    except Exception:
        pass
    return "Default"


def make_driver() -> webdriver.Chrome:
    user_data = chrome_user_data_dir()
    profile = chrome_profile(user_data)

    options = webdriver.ChromeOptions()
    options.binary_location = chrome_binary()
    options.add_argument(f"--user-data-dir={user_data}")
    options.add_argument(f"--profile-directory={profile}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_experimental_option("detach", True)
    try:
        driver = webdriver.Chrome(options=options)
        write_last_run("RUNNING", chrome_profile=profile)
        return driver
    except Exception as exc:
        raise RuntimeError(
            f"Chrome non può usare il profilo '{profile}'. L'automazione usa automaticamente l'ultimo profilo Chrome attivo. "
            "Se alle 23:00 lo stesso profilo è già aperto in un'altra finestra Chrome, chiudilo prima dell'orario oppure configura un profilo dedicato."
        ) from exc


def prompt_box(driver: webdriver.Chrome, timeout: int = 90):
    wait = WebDriverWait(driver, timeout)
    selectors = [
        (By.ID, "prompt-textarea"),
        (By.CSS_SELECTOR, "textarea"),
        (By.CSS_SELECTOR, "div[contenteditable='true']"),
    ]
    last = None
    for by, selector in selectors:
        try:
            el = wait.until(EC.presence_of_element_located((by, selector)))
            if el.is_displayed():
                return el
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Casella prompt ChatGPT non trovata: {last}")


def send_query(driver: webdriver.Chrome, query: str) -> None:
    box = prompt_box(driver)
    box.click()
    try:
        box.send_keys(Keys.CONTROL, "a")
        box.send_keys(Keys.BACKSPACE)
    except Exception:
        pass
    box.send_keys(query)
    box.send_keys(Keys.ENTER)


def wait_generation(driver: webdriver.Chrome, timeout: int = 900) -> None:
    end = time.time() + timeout
    saw_stop = False
    stable_since = None
    while time.time() < end:
        buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'stop') "
            "or contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'interrompi')]",
        )
        visible = [b for b in buttons if b.is_displayed()]
        if visible:
            saw_stop = True
            stable_since = None
        elif saw_stop:
            time.sleep(8)
            return
        else:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since > 45:
                return
        time.sleep(3)
    raise TimeoutException("La generazione non si è conclusa entro il timeout.")


def inbox_is_up() -> bool:
    try:
        with socket.create_connection((INBOX_HOST, INBOX_PORT), timeout=1):
            return True
    except OSError:
        return False


def start_inbox_server() -> None:
    if inbox_is_up():
        return
    server = ROOT / "publisher" / "manual_asset_inbox" / "server.py"
    if not server.exists():
        return
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
    for _ in range(30):
        if inbox_is_up():
            return
        time.sleep(0.5)


def open_morning_notice(driver: webdriver.Chrome) -> None:
    start_inbox_server()
    url = f"http://{INBOX_HOST}:{INBOX_PORT}/ready"
    driver.execute_script("window.open(arguments[0], '_blank');", url)
    time.sleep(2)
    driver.switch_to.window(driver.window_handles[-1])


def run(batch_size: int) -> int:
    queries = load_queries()
    state = load_state()
    start = int(state.get("next_index", 0))
    if start >= len(queries):
        start = 0

    write_last_run("RUNNING", batch_size=batch_size, start_index=start)
    start_inbox_server()

    driver = make_driver()
    driver.get("https://www.google.com/")
    time.sleep(2)
    driver.get(GPT_URL)
    prompt_box(driver, timeout=90)

    processed: list[dict] = []
    for offset in range(batch_size):
        idx = start + offset
        if idx >= len(queries):
            break
        row = queries[idx]
        query = str(row.get("query") or "").strip()
        if not query:
            continue

        send_query(driver, query)
        wait_generation(driver)
        item = {"index": idx, "id": row.get("id"), "query": query}
        processed.append(item)
        state.setdefault("completed", []).append(
            {**item, "submitted_at": datetime.now(ROME).isoformat(timespec="seconds")}
        )
        state["next_index"] = idx + 1
        save_state(state)
        write_last_run("RUNNING", processed=processed, next_index=state.get("next_index"))
        time.sleep(4)

    write_last_run(
        "GRAFICHE_PRONTE",
        processed=processed,
        processed_count=len(processed),
        next_index=state.get("next_index"),
        completed_at=datetime.now(ROME).isoformat(timespec="seconds"),
    )
    open_morning_notice(driver)
    print(json.dumps(json.loads(LAST_RUN_FILE.read_text(encoding="utf-8")), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--scheduled", action="store_true")
    args = parser.parse_args()

    if args.scheduled:
        now = datetime.now(ROME)
        if now.hour != 23:
            print(f"NOOP: ora locale {now:%H:%M}, finestra automatica prevista alle 23:xx Europe/Rome")
            return 0

    try:
        return run(max(1, args.batch_size))
    except Exception as exc:
        start_inbox_server()
        write_last_run("ERRORE", error=str(exc), completed_at=datetime.now(ROME).isoformat(timespec="seconds"))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
