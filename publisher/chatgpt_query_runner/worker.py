from __future__ import annotations

import argparse
import json
import os
import subprocess
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
CHAT_URL = "https://chatgpt.com/c/6a9af32f-d574-83ed-9232-2b4025e3893c"
ROME = ZoneInfo("Europe/Rome")
DEFAULT_BATCH_SIZE = int(os.getenv("F1_QUERY_BATCH_SIZE", "4"))
GRAPHIC_SUFFIX = "l modello è già allegato qui in chat"


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


def make_driver() -> webdriver.Chrome:
    user_data = Path(os.path.expandvars(r"%LocalAppData%\Google\Chrome\User Data"))
    profile = os.getenv("F1_CHROME_PROFILE", "Default").strip() or "Default"

    options = webdriver.ChromeOptions()
    options.binary_location = chrome_binary()
    options.add_argument(f"--user-data-dir={user_data}")
    options.add_argument(f"--profile-directory={profile}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_experimental_option("detach", True)
    try:
        return webdriver.Chrome(options=options)
    except Exception as exc:
        raise RuntimeError(
            "Chrome non può usare il profilo già aperto. Chiudi tutte le finestre Chrome una volta, "
            "poi rilancia. L'automazione userà lo stesso account già presente nel profilo."
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
    box.send_keys(f"{query}\n{GRAPHIC_SUFFIX}")
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
            return
        else:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since > 45:
                return
        time.sleep(3)
    raise TimeoutException("La generazione non si è conclusa entro il timeout.")


def open_morning_notice(driver: webdriver.Chrome, processed: list[dict]) -> None:
    notice = ROOT / "publisher" / "manual_asset_inbox" / "morning_notice.html"
    if not notice.exists():
        return
    driver.execute_script("window.open(arguments[0], '_blank');", notice.resolve().as_uri())
    time.sleep(2)
    driver.switch_to.window(driver.window_handles[-1])


def run(batch_size: int) -> int:
    queries = load_queries()
    state = load_state()
    start = int(state.get("next_index", 0))
    if start >= len(queries):
        start = 0

    driver = make_driver()
    driver.get("https://www.google.com/")
    time.sleep(2)
    driver.get(CHAT_URL)
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
        processed.append({"index": idx, "id": row.get("id"), "query": query})
        state.setdefault("completed", []).append({
            "index": idx,
            "id": row.get("id"),
            "query": query,
            "submitted_at": datetime.now(ROME).isoformat(timespec="seconds"),
        })
        state["next_index"] = idx + 1
        save_state(state)
        time.sleep(4)

    open_morning_notice(driver, processed)
    print(json.dumps({"status": "OK", "processed": processed, "next_index": state.get("next_index")}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--scheduled", action="store_true")
    args = parser.parse_args()

    if args.scheduled:
        now = datetime.now(ROME)
        if now.hour != 4:
            print(f"NOOP: ora locale {now:%H:%M}, finestra automatica prevista alle 04:xx Europe/Rome")
            return 0
    return run(max(1, args.batch_size))


if __name__ == "__main__":
    raise SystemExit(main())
