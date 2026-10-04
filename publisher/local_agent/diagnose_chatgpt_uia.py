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

def main() -> int:
    from pywinauto import Desktop

    exe = chrome_executable()
    subprocess.Popen([exe, "--new-window", CHATGPT_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(8)

    desktop = Desktop(backend="uia")
    windows = []
    for w in desktop.windows():
        try:
            title = (w.window_text() or "").strip()
        except Exception:
            continue
        if "Chrome" in title or "ChatGPT" in title:
            windows.append((title, w))

    print(f"UIA_WINDOWS={len(windows)}")
    if not windows:
        print("UIA_NO_CHROME_WINDOW")
        return 2

    title, win = windows[-1]
    print(f"UIA_WINDOW={title}")
    try:
        win.set_focus()
    except Exception as exc:
        print(f"UIA_FOCUS_WARN={exc}")

    useful = []
    for ctrl in win.descendants():
        try:
            info = ctrl.element_info
            ctype = str(info.control_type or "")
            name = str(info.name or "").strip()
            auto_id = str(info.automation_id or "").strip()
            if ctype not in {"Edit","Document","Button","Image","Text","Pane","Group","ToolBar","TabItem"}:
                continue
            if not name and not auto_id:
                continue
            low = (name + " " + auto_id).lower()
            if any(k in low for k in (
                "chatgpt","message","messaggio","ask","prompt","send","invia",
                "image","immagine","download","scarica","create","crea","composer"
            )) or ctype in {"Edit","Document"}:
                useful.append((ctype, name[:180], auto_id[:120]))
        except Exception:
            continue

    print(f"UIA_USEFUL_CONTROLS={len(useful)}")
    for ctype, name, auto_id in useful[:250]:
        print(f"UIA_CONTROL type={ctype} name={name!r} id={auto_id!r}")

    edits = [x for x in useful if x[0] == "Edit"]
    docs = [x for x in useful if x[0] == "Document"]
    print(f"UIA_EDITS={len(edits)} UIA_DOCUMENTS={len(docs)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
