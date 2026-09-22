from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import pyautogui

from publisher.chatgpt_query_runner.ui_driver import ChromeChatGPTDriver, _norm
from publisher.chatgpt_query_runner.ultrarealism import qa_prompt

QA_URL = os.getenv("F1_VISUAL_QA_CHAT_URL", "https://chatgpt.com/")


class BrowserVisualQAError(RuntimeError):
    pass


class ChatGPTBrowserVisualQA:
    """Strict visual QA through the user's already-authenticated ChatGPT browser session.

    No API key is used. Authentication challenges are never bypassed.
    """

    ATTACH_TOKENS = (
        "add files",
        "add photos",
        "attach",
        "upload file",
        "allega",
        "aggiungi file",
        "carica file",
        "foto e file",
    )
    UPLOAD_TOKENS = (
        "upload from computer",
        "upload files",
        "carica dal computer",
        "carica file",
        "from computer",
    )

    def __init__(
        self,
        *,
        log: Callable[[str], None] | None = None,
        diagnostic_root: Path | None = None,
        timeout: int = 180,
    ) -> None:
        self.log = log or (lambda message: None)
        self.timeout = timeout
        self.driver = ChromeChatGPTDriver(log=self.log, diagnostic_root=diagnostic_root)

    def _open_chat(self) -> None:
        windows = self.driver._all_chrome_windows()
        if windows:
            self.driver._chrome_window = windows[-1]
            self.driver.activate_chrome()
            pyautogui.hotkey("ctrl", "l")
            pyautogui.write(QA_URL, interval=0.001)
            pyautogui.press("enter")
        else:
            subprocess.Popen(
                [self.driver.chrome_binary(), "--new-tab", QA_URL],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.time() + 35
            while time.time() < deadline:
                windows = self.driver._all_chrome_windows()
                if windows:
                    self.driver._chrome_window = windows[-1]
                    self.driver.activate_chrome()
                    break
                time.sleep(1)
            else:
                raise BrowserVisualQAError("Chrome non disponibile per Visual QA")
        time.sleep(4)
        try:
            self.driver.wait_composer(timeout=30)
        except Exception as exc:
            raise BrowserVisualQAError(
                "ChatGPT Visual QA non pronto. Se compare login/2FA/CAPTCHA serve autenticazione manuale."
            ) from exc

    def _click_named(self, tokens: tuple[str, ...]) -> bool:
        for record in reversed(self.driver._records()):
            name = _norm(record.get("name"))
            ctype = _norm(record.get("control_type"))
            if not name:
                continue
            if any(token in name for token in tokens) and any(
                kind in ctype for kind in ("button", "hyperlink", "menuitem", "custom")
            ):
                try:
                    record["control"].Click()
                    return True
                except Exception:
                    try:
                        left, top, right, bottom = record["rect"]
                        pyautogui.click((left + right) // 2, (top + bottom) // 2)
                        return True
                    except Exception:
                        continue
        return False

    def _attach_file(self, image_path: Path) -> None:
        image_path = image_path.resolve()
        if not image_path.is_file():
            raise BrowserVisualQAError(f"Immagine QA mancante: {image_path}")
        self.driver.activate_chrome()
        if not self._click_named(self.ATTACH_TOKENS):
            raise BrowserVisualQAError("Pulsante allegato ChatGPT non trovato")
        time.sleep(0.8)
        self._click_named(self.UPLOAD_TOKENS)
        time.sleep(0.8)

        # Native Windows file picker normally focuses the filename field.
        pyautogui.write(str(image_path), interval=0.001)
        pyautogui.press("enter")
        time.sleep(2.5)
        self.log(f"Visual QA: file allegato richiesto {image_path.name}")

    @staticmethod
    def _extract_completed_payload(text: str) -> dict[str, Any] | None:
        marker = "F1_QA_RESULT"
        decoder = json.JSONDecoder()
        start = 0
        candidates: list[dict[str, Any]] = []
        while True:
            idx = text.find(marker, start)
            if idx < 0:
                break
            brace = text.find("{", idx)
            if brace < 0:
                break
            try:
                payload, used = decoder.raw_decode(text[brace:])
                if isinstance(payload, dict):
                    candidates.append(payload)
                start = brace + max(used, 1)
            except Exception:
                start = brace + 1
        for payload in reversed(candidates):
            if payload.get("qa_complete") is True:
                return payload
        return None

    def _wait_qa_result(self) -> dict[str, Any]:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            self.driver.activate_chrome()
            pyautogui.press("end")
            names = "\n".join(r["name"] for r in self.driver._records() if r.get("name"))
            payload = self._extract_completed_payload(names)
            if payload is not None:
                return payload
            time.sleep(1.5)
        raise BrowserVisualQAError("Timeout Visual QA: nessun F1_QA_RESULT completo rilevato")

    def evaluate(
        self,
        image_path: Path,
        *,
        content_id: str,
        brief: str,
        people_expected: bool | None = None,
    ) -> dict[str, Any]:
        self._open_chat()
        self._attach_file(image_path)
        prompt = qa_prompt(content_id, brief, people_expected=people_expected)
        # qa_complete=false exists only in the request; the answer must set true.
        prompt = prompt.replace(
            '"qa_failure_reasons":[]}',
            '"qa_failure_reasons":[],"qa_complete":false}'
        )
        prompt += " Set qa_complete=true in your returned JSON. Do not add prose before or after the required one-line result."

        self.driver.wait_composer(timeout=30)
        self.driver.set_and_verify_prompt(prompt)
        self.driver.send_and_verify(prompt)
        result = self._wait_qa_result()
        result["qa_method"] = "chatgpt_browser_vision"
        self.log(f"Visual QA completata per {content_id}")
        return result
