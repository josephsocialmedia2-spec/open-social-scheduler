#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

CHATGPT_URL = os.getenv("F1_CHATGPT_URL", "https://chatgpt.com/")

def chrome_executable() -> str:
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    raise RuntimeError("Google Chrome non trovato")

def chrome_windows():
    from pywinauto import Desktop
    out = []
    for w in Desktop(backend="uia").windows():
        try:
            title = (w.window_text() or "").strip()
        except Exception:
            continue
        if "Chrome" in title or "ChatGPT" in title:
            out.append(w)
    return out

def paste_text(text: str) -> None:
    import pyperclip
    from pywinauto.keyboard import send_keys
    pyperclip.copy(text)
    send_keys("^v")

def navigate(win, url: str) -> None:
    from pywinauto.keyboard import send_keys
    win.set_focus()
    send_keys("^l")
    paste_text(url)
    send_keys("{ENTER}")

def run_javascript(win, code: str) -> None:
    from pywinauto.keyboard import send_keys
    win.set_focus()
    send_keys("^l")
    # Chrome blocks pasted javascript: URLs. Type the scheme and paste only
    # the code body so this behaves like a real keyboard action.
    send_keys("javascript:", with_spaces=True)
    paste_text(code)
    send_keys("{ENTER}")

def main() -> int:
    exe = chrome_executable()
    before = {w.handle for w in chrome_windows()}
    subprocess.Popen([exe, "--new-window", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    deadline = time.time() + 15
    win = None
    while time.time() < deadline:
        current = chrome_windows()
        fresh = [w for w in current if w.handle not in before]
        if fresh:
            win = fresh[-1]
            break
        if current:
            win = current[-1]
        time.sleep(0.5)

    if win is None:
        print("JS_BRIDGE_NO_CHROME_WINDOW")
        return 2

    print(f"JS_BRIDGE_WINDOW_HANDLE={win.handle}")
    navigate(win, CHATGPT_URL)
    time.sleep(8)
    try:
        print(f"JS_BRIDGE_AFTER_NAV={win.window_text()}")
    except Exception:
        pass

    marker = (
        "document.title='F1JSBRIDGE:'+location.host+':'"
        "+document.querySelectorAll('#prompt-textarea,textarea,[contenteditable=true]').length;"
        "void(0)"
    )
    run_javascript(win, marker)
    time.sleep(2)

    title = ""
    try:
        title = (win.window_text() or "").strip()
    except Exception:
        pass
    print(f"JS_BRIDGE_RESULT_TITLE={title}")
    if "F1JSBRIDGE:chatgpt.com:" in title:
        print("JS_BRIDGE_OK")
        return 0

    print("JS_BRIDGE_NOT_CONFIRMED")
    return 3

if __name__ == "__main__":
    raise SystemExit(main())
