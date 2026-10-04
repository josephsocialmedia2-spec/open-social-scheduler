#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

def automation_windows():
    markers = (
        "F1JSBRIDGE:", "F1SESSION:", "F1PROMPT:", "F1IMGCOUNT:",
        "F1URL:", "F1DL:", "F1 AUTOPILOT"
    )
    out = []
    for w in chrome_windows():
        try:
            title = (w.window_text() or "").strip()
        except Exception:
            continue
        if any(marker in title for marker in markers):
            out.append(w)
    return out

def cleanup_duplicate_automation_windows() -> int:
    # Old diagnostic runs may have left ordinary "ChatGPT - Google Chrome"
    # windows after page reloads reset our F1 title marker. Treat those as part
    # of the same automation pool and keep only one ChatGPT top-level window.
    wins = automation_windows()
    known = {getattr(w, "handle", None) for w in wins}
    for w in chrome_windows():
        try:
            title = (w.window_text() or "").strip()
        except Exception:
            continue
        handle = getattr(w, "handle", None)
        if handle in known:
            continue
        if "ChatGPT" in title:
            wins.append(w)
            known.add(handle)

    if len(wins) <= 1:
        print(f"F1_CHATGPT_AUTOMATION_WINDOWS={len(wins)}")
        return 0

    keep = wins[-1]
    closed = 0
    for w in wins[:-1]:
        try:
            w.close()
            closed += 1
        except Exception:
            pass
    print(f"F1_CHATGPT_DUPLICATES_CLOSED={closed}")
    try:
        print(f"F1_CHATGPT_KEEP_HANDLE={keep.handle}")
    except Exception:
        pass
    return closed

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup-only", action="store_true")
    args = ap.parse_args()

    cleanup_duplicate_automation_windows()
    if args.cleanup_only:
        return 0

    exe = chrome_executable()
    current = chrome_windows()
    win = None

    # Reuse an existing automation/ChatGPT Chrome window first.
    marked = automation_windows()
    if marked:
        win = marked[-1]
    if win is None:
        for candidate in current:
            try:
                title = (candidate.window_text() or "").strip()
            except Exception:
                continue
            if "ChatGPT" in title:
                win = candidate
                break

    # Create exactly one new window only when no reusable ChatGPT window exists.
    if win is None:
        before = {w.handle for w in current}
        subprocess.Popen(
            [exe, "--new-window", CHATGPT_URL],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            now = chrome_windows()
            fresh = [w for w in now if w.handle not in before]
            if fresh:
                win = fresh[-1]
                break
            time.sleep(0.5)

    if win is None:
        print("JS_BRIDGE_NO_CHROME_WINDOW")
        return 2

    print(f"JS_BRIDGE_WINDOW_HANDLE={win.handle}")
    navigate(win, CHATGPT_URL)
    time.sleep(7)
    try:
        print(f"JS_BRIDGE_AFTER_NAV={win.window_text()}")
    except Exception:
        pass

    marker = (
        "(()=>{const p=document.querySelector('#prompt-textarea,textarea,[contenteditable=true]');"
        "document.title='F1 AUTOPILOT '+location.host+':'+(p?1:0);void(0)})()"
    )
    run_javascript(win, marker)
    time.sleep(1)

    title = ""
    try:
        title = (win.window_text() or "").strip()
    except Exception:
        pass
    print(f"JS_BRIDGE_RESULT_TITLE={title}")
    if "F1 AUTOPILOT chatgpt.com:1" in title:
        print("JS_BRIDGE_OK")
        return 0

    print("JS_BRIDGE_NOT_CONFIRMED")
    return 3

if __name__ == "__main__":
    raise SystemExit(main())
