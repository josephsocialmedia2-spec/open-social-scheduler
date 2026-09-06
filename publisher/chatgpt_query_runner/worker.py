from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pyautogui
import pygetwindow as gw
import pyperclip
import uiautomation as auto

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
PROMPT_NAMES = (
    "message chatgpt",
    "ask anything",
    "chiedi qualsiasi cosa",
    "invia un messaggio",
    "scrivi un messaggio",
    "messaggio chatgpt",
)


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


def _chrome_windows():
    windows = []
    try:
        for window in gw.getAllWindows():
            title = (window.title or "").lower()
            if "chrome" in title:
                windows.append(window)
    except Exception:
        pass
    return windows


def activate_chrome() -> None:
    activated = False
    for window in reversed(_chrome_windows()):
        try:
            if window.isMinimized:
                window.restore()
            window.activate()
            try:
                window.maximize()
            except Exception:
                pass
            activated = True
            break
        except Exception:
            continue

    if not activated and os.name == "nt":
        cmd = (
            "$ws=New-Object -ComObject WScript.Shell; "
            "$ok=$ws.AppActivate('Google Chrome'); "
            "if(-not $ok){$ok=$ws.AppActivate('Chrome')}; "
            "if(-not $ok){exit 1}"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", cmd],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    time.sleep(1)


def open_normal_chrome() -> None:
    subprocess.Popen(
        [chrome_binary(), "--force-renderer-accessibility", GPT_URL],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(8)
    activate_chrome()
    pyautogui.hotkey("win", "up")
    time.sleep(1)
    pyautogui.hotkey("ctrl", "l")
    pyperclip.copy(GPT_URL)
    pyautogui.hotkey("ctrl", "v")
    pyautogui.press("enter")
    time.sleep(10)


def _find_chrome_uia_window():
    root = auto.GetRootControl()
    candidates = []
    try:
        for child in root.GetChildren():
            try:
                name = (child.Name or "").lower()
                class_name = (child.ClassName or "").lower()
                if "chrome_widgetwin" in class_name or "google chrome" in name:
                    candidates.append(child)
            except Exception:
                continue
    except Exception:
        return None
    return candidates[-1] if candidates else None


def _walk_controls(root, max_nodes: int = 5000, max_depth: int = 15):
    queue = deque([(root, 0)])
    seen = 0
    while queue and seen < max_nodes:
        control, depth = queue.popleft()
        seen += 1
        yield control
        if depth >= max_depth:
            continue
        try:
            children = control.GetChildren()
        except Exception:
            children = []
        for child in children:
            queue.append((child, depth + 1))


def _looks_like_prompt(control) -> bool:
    try:
        automation_id = (control.AutomationId or "").strip().lower()
    except Exception:
        automation_id = ""
    try:
        name = (control.Name or "").strip().lower()
    except Exception:
        name = ""
    try:
        control_type = (control.ControlTypeName or "").strip().lower()
    except Exception:
        control_type = ""

    if automation_id == "prompt-textarea":
        return True
    if any(token in name for token in PROMPT_NAMES):
        return any(kind in control_type for kind in ("edit", "document", "pane", "group", "custom"))
    return False


def _uia_prompt(timeout: int = 25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        window = _find_chrome_uia_window()
        if window is not None:
            for control in _walk_controls(window):
                if _looks_like_prompt(control):
                    return control
        time.sleep(1)
    return None


def _verify_focused_textbox_with_probe() -> bool:
    probe = "__F1_PROMPT_FOCUS_TEST_7A91__"
    sentinel = "__F1_CLIPBOARD_SENTINEL__"
    try:
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        pyperclip.copy(probe)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.4)

        pyperclip.copy(sentinel)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.3)
        copied = pyperclip.paste()

        if copied == probe:
            pyautogui.press("backspace")
            return True

        pyautogui.press("backspace")
    except Exception:
        pass
    return False


def focus_prompt() -> str:
    activate_chrome()

    control = _uia_prompt(timeout=20)
    if control is not None:
        try:
            control.SetFocus()
            time.sleep(0.5)
            if _verify_focused_textbox_with_probe():
                return "uia"
        except Exception:
            pass

    width, height = pyautogui.size()
    points = [
        (int(width * 0.50), max(50, height - 130)),
        (int(width * 0.50), max(50, height - 165)),
        (int(width * 0.50), int(height * 0.88)),
        (int(width * 0.50), int(height * 0.82)),
        (int(width * 0.58), max(50, height - 130)),
        (int(width * 0.42), max(50, height - 130)),
    ]
    for x, y in points:
        activate_chrome()
        pyautogui.click(x, y)
        time.sleep(0.5)
        if _verify_focused_textbox_with_probe():
            return f"verified-click:{x},{y}"

    raise RuntimeError(
        "La chat F1 è aperta ma non riesco a mettere il cursore nel campo del messaggio. "
        "La query NON è stata segnata come eseguita."
    )


def send_query(query: str) -> str:
    focus_method = focus_prompt()

    pyperclip.copy(query)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)

    sentinel = "__F1_QUERY_VERIFY_SENTINEL__"
    pyperclip.copy(sentinel)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.3)
    copied = pyperclip.paste()

    if copied.strip() != query.strip():
        pyautogui.press("esc")
        raise RuntimeError(
            "Il campo ChatGPT è stato individuato, ma la query non risulta incollata correttamente. "
            "Invio annullato."
        )

    pyautogui.press("right")
    time.sleep(0.2)
    pyautogui.press("enter")
    return focus_method


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

    write_last_run("RUNNING", batch_size=batch_size, start_index=start, browser_mode="normal-chrome-ui-verified")
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

        focus_method = send_query(query)
        item = {"index": idx, "id": row.get("id"), "query": query, "focus_method": focus_method}
        processed.append(item)
        state.setdefault("completed", []).append(
            {**item, "submitted_at": datetime.now(ROME).isoformat(timespec="seconds")}
        )
        state["next_index"] = idx + 1
        save_state(state)
        write_last_run("RUNNING", processed=processed, next_index=state.get("next_index"), browser_mode="normal-chrome-ui-verified")
        time.sleep(GENERATION_WAIT)

    write_last_run(
        "GRAFICHE_PRONTE",
        processed=processed,
        processed_count=len(processed),
        next_index=state.get("next_index"),
        completed_at=datetime.now(ROME).isoformat(timespec="seconds"),
        browser_mode="normal-chrome-ui-verified",
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
            browser_mode="normal-chrome-ui-verified",
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
