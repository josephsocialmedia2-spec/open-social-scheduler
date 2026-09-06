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

import pyautogui
import pyperclip

ROOT = Path(__file__).resolve().parents[2]
QUERY_FILE = ROOT / "publisher" / "github_graphics" / "queries.json"
STATE_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "state.json"
LAST_RUN_FILE = ROOT / "publisher" / "chatgpt_query_runner" / "last_run.json"
GPT_URL = "https://chatgpt.com/g/g-6a9c210485488191b072eb694c2f114c-generatore-grafica-f1"
ROME = ZoneInfo("Europe/Rome")
DEFAULT_BATCH_SIZE = int(os.getenv("F1_QUERY_BATCH_SIZE", "4"))
INBOX_HOST = "127.0.0.1"
INBOX_PORT = int(os.getenv("F1_INBOX_PORT", "8877"))
GENERATION_WAIT = int(os.getenv("F1_GENERATION_WAIT_SECONDS", "150"))


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
    env = os.environ.copy()
    env["F1_INBOX_PORT"] = str(INBOX_PORT)
    kwargs = {
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
    raise RuntimeError(f"F1 Inbox non disponibile su porta {INBOX_PORT}")


def activate_chrome() -> None:
    if os.name != "nt":
        return
    cmd = (
        "$ws=New-Object -ComObject WScript.Shell; "
        "$ok=$ws.AppActivate('Google Chrome'); "
        "if(-not $ok){$ok=$ws.AppActivate('Chrome')}; "
        "if(-not $ok){exit 1}"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def open_normal_chrome() -> None:
    subprocess.Popen([chrome_binary(), GPT_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(8)
    activate_chrome()
    pyautogui.hotkey("win", "up")
    time.sleep(1)
    pyautogui.hotkey("ctrl", "l")
    pyperclip.copy(GPT_URL)
    pyautogui.hotkey("ctrl", "v")
    pyautogui.press("enter")
    time.sleep(8)


def focus_prompt() -> None:
    width, height = pyautogui.size()
    # Il box prompt di ChatGPT è stabilmente nella parte bassa centrale della finestra.
    pyautogui.click(int(width * 0.50), int(height * 0.84))
    time.sleep(1)


def send_query(query: str) -> None:
    activate_chrome()
    focus_prompt()
    pyperclip.copy(query)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)
    pyautogui.press("enter")


def open_morning_notice() -> None:
    activate_chrome()
    pyautogui.hotkey("ctrl", "l")
    pyperclip.copy(f"http://{INBOX_HOST}:{INBOX_PORT}/ready")
    pyautogui.hotkey("ctrl", "v")
    pyautogui.press("enter")


def run(batch_size: int) -> int:
    pyautogui.FAILSAFE = True
    start_inbox_server()
    queries = load_queries()
    state = load_state()
    start = int(state.get("next_index", 0))
    if start >= len(queries):
        start = 0

    write_last_run("RUNNING", batch_size=batch_size, start_index=start, browser_mode="normal-chrome-ui")
    open_normal_chrome()

    processed = []
    for offset in range(batch_size):
        idx = start + offset
        if idx >= len(queries):
            break
        row = queries[idx]
        query = str(row.get("query") or "").strip()
        if not query:
            continue

        send_query(query)
        item = {"index": idx, "id": row.get("id"), "query": query}
        processed.append(item)
        state.setdefault("completed", []).append(
            {**item, "submitted_at": datetime.now(ROME).isoformat(timespec="seconds")}
        )
        state["next_index"] = idx + 1
        save_state(state)
        write_last_run("RUNNING", processed=processed, next_index=state.get("next_index"), browser_mode="normal-chrome-ui")
        time.sleep(GENERATION_WAIT)

    write_last_run(
        "GRAFICHE_PRONTE",
        processed=processed,
        processed_count=len(processed),
        next_index=state.get("next_index"),
        completed_at=datetime.now(ROME).isoformat(timespec="seconds"),
        browser_mode="normal-chrome-ui",
    )
    open_morning_notice()
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
        try:
            start_inbox_server()
        except Exception:
            pass
        write_last_run(
            "ERRORE",
            error=f"{type(exc).__name__}: {exc}",
            completed_at=datetime.now(ROME).isoformat(timespec="seconds"),
            browser_mode="normal-chrome-ui",
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
