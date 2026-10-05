#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

CHATGPT_URL = os.getenv("F1_CHATGPT_URL", "https://chatgpt.com/")
CHATGPT_IMAGES_URL = os.getenv("F1_CHATGPT_IMAGES_URL", "https://chatgpt.com/images")
SCREENSHOT_ROOT = Path(os.getenv("F1_BROWSER_SCREENSHOT_ROOT", r"C:\F1Social\BrowserScreenshots"))

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

def capture_screenshot(win, label: str) -> Path | None:
    """Mandatory visual evidence after browser actions."""
    try:
        SCREENSHOT_ROOT.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label)[:80]
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = SCREENSHOT_ROOT / f"{stamp}-{safe}.png"
        image = win.capture_as_image()
        image.save(path)
        print(f"F1_SCREENSHOT={path}")
        return path
    except Exception as exc:
        print(f"F1_SCREENSHOT_ERROR={label}:{exc}")
        return None


def uia_snapshot(win, label: str) -> None:
    """Print a compact UIA inventory and always capture a screenshot."""
    capture_screenshot(win, label)
    rows = []
    try:
        controls = win.descendants()
    except Exception as exc:
        print(f"F1_UIA_DESCENDANTS_ERROR={exc}")
        return
    keywords = (
        "message", "messaggio", "prompt", "send", "invia", "create", "crea",
        "image", "immagin", "download", "scarica", "chatgpt", "tools", "strumenti",
    )
    for ctrl in controls:
        try:
            info = ctrl.element_info
            name = (ctrl.window_text() or "").strip()
            control_type = str(getattr(info, "control_type", "") or "")
            auto_id = str(getattr(info, "automation_id", "") or "")
            cls = str(getattr(info, "class_name", "") or "")
            blob = f"{name} {control_type} {auto_id} {cls}".lower()
            if control_type in {"Edit","Button","Document"} or any(k in blob for k in keywords):
                rect = ctrl.rectangle()
                rows.append({
                    "name": name[:180],
                    "type": control_type,
                    "auto_id": auto_id[:140],
                    "class": cls[:120],
                    "rect": [rect.left, rect.top, rect.right, rect.bottom],
                })
        except Exception:
            continue
    import json
    print("F1_UIA_CONTROLS=" + json.dumps(rows[:160], ensure_ascii=False))


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
    time.sleep(2)
    capture_screenshot(win, "after_navigation")

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


def inspect_controls(win) -> int:
    import json
    import pyperclip

    marker = "F1_CONTROLS_PENDING"
    pyperclip.copy(marker)

    script = r"""(()=>{
      const norm=s=>(s||'').replace(/\s+/g,' ').trim();
      const visible=e=>!!(e && (e.offsetWidth||e.offsetHeight||e.getClientRects().length));
      const rows=()=>[...document.querySelectorAll(
        'button,[role="button"],[role="menuitem"],[role="option"]'
      )].filter(visible).map(e=>({
        tag:e.tagName,
        text:norm(e.textContent).slice(0,120),
        aria:norm(e.getAttribute('aria-label')).slice(0,120),
        title:norm(e.getAttribute('title')).slice(0,120),
        testid:norm(e.getAttribute('data-testid')).slice(0,120)
      })).filter(x=>x.text||x.aria||x.title||x.testid);

      const before=rows();
      const lab=e=>(
        (e.getAttribute('aria-label')||'')+' '+
        (e.getAttribute('title')||'')+' '+
        (e.getAttribute('data-testid')||'')+' '+
        (e.textContent||'')
      ).toLowerCase();
      const candidates=[...document.querySelectorAll('button,[role="button"]')].filter(visible);
      const opener=candidates.find(e=>{
        const s=lab(e);
        return s.includes('tool')||s.includes('strument')||s.includes('plus')||
               s.includes('add')||s.includes('allega')||s.includes('aggiungi');
      });
      if(opener) opener.click();

      setTimeout(()=>{
        const after=rows();
        const payload=JSON.stringify({before,after});
        const ta=document.createElement('textarea');
        ta.value=payload;ta.style.position='fixed';ta.style.opacity='0';
        document.body.appendChild(ta);ta.focus();ta.select();
        const ok=document.execCommand('copy');ta.remove();
        document.title='F1CONTROLPROBE:'+(ok?'OK':'FAIL');
      },900);
      void(0);
    })()"""

    run_javascript(win, script)
    time.sleep(1.6)
    raw = str(pyperclip.paste() or "")
    if not raw or raw == marker:
        print("F1_CONTROL_PROBE=NO_CLIPBOARD_DATA")
        return 4
    try:
        data = json.loads(raw)
    except Exception:
        print("F1_CONTROL_PROBE=INVALID_JSON")
        return 5

    def compact(rows):
        out=[]
        for row in rows or []:
            label=" | ".join(
                x for x in [
                    str(row.get("text") or "").strip(),
                    str(row.get("aria") or "").strip(),
                    str(row.get("title") or "").strip(),
                    str(row.get("testid") or "").strip(),
                ] if x
            )
            if not label:
                continue
            low=label.lower()
            if any(k in low for k in (
                "image","immagin","crea","create","generat","genera",
                "tool","strument","plus","add","aggiung","allega","upload"
            )):
                out.append(label[:360])
        return out[:80]

    print("F1_CONTROL_PROBE_BEFORE=" + json.dumps(compact(data.get("before")), ensure_ascii=False))
    print("F1_CONTROL_PROBE_AFTER=" + json.dumps(compact(data.get("after")), ensure_ascii=False))
    return 0

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup-only", action="store_true")
    ap.add_argument("--inspect-controls", action="store_true")
    ap.add_argument("--inspect-uia", action="store_true")
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
    navigate(win, CHATGPT_IMAGES_URL if args.inspect_uia else CHATGPT_URL)
    time.sleep(7)
    capture_screenshot(win, "page_loaded")
    if args.inspect_uia:
        uia_snapshot(win, "uia_inspect")
        return 0
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
        if args.inspect_controls:
            return inspect_controls(win)
        return 0

    print("JS_BRIDGE_NOT_CONFIRMED")
    return 3

if __name__ == "__main__":
    raise SystemExit(main())
