from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pyautogui
import pygetwindow as gw
import pyperclip
import uiautomation as auto

GPT_URL = "https://chatgpt.com/g/g-6a9c210485488191b072eb694c2f114c-generatore-grafica-f1"

PROMPT_NAMES = (
    "message chatgpt",
    "ask anything",
    "chiedi qualsiasi cosa",
    "invia un messaggio",
    "scrivi un messaggio",
    "messaggio chatgpt",
)
GENERATING_NAMES = (
    "stop generating",
    "interrompi generazione",
    "interrompi",
    "stop",
    "creating image",
    "generazione immagine",
    "creazione immagine",
)
DOWNLOAD_NAMES = (
    "download",
    "scarica",
    "download image",
    "scarica immagine",
)
ERROR_NAMES = (
    "something went wrong",
    "si è verificato un errore",
    "si e verificato un errore",
    "riprova",
    "try again",
    "rate limit",
    "too many requests",
    "temporarily unavailable",
)
IMAGE_NAMES = (
    "generated image",
    "immagine generata",
    "image generated",
)


@dataclass
class PageSnapshot:
    image_signatures: set[str]
    download_signatures: set[str]
    names: list[str]


@dataclass
class GenerationResult:
    image_control: Any | None
    download_controls: list[Any]
    started_at: float
    completed_at: float


def _safe_text(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", _safe_text(value)).strip().lower()


def _rect(control: Any) -> tuple[int, int, int, int]:
    try:
        r = control.BoundingRectangle
        left, top, right, bottom = int(r.left), int(r.top), int(r.right), int(r.bottom)
        return left, top, right, bottom
    except Exception:
        return 0, 0, 0, 0


def _signature(control: Any) -> str:
    left, top, right, bottom = _rect(control)
    return "|".join(
        [
            _norm(getattr(control, "ControlTypeName", "")),
            _norm(getattr(control, "AutomationId", "")),
            _norm(getattr(control, "Name", "")),
            f"{left},{top},{right},{bottom}",
        ]
    )


def _control_type(control: Any) -> str:
    return _norm(getattr(control, "ControlTypeName", ""))


def _control_name(control: Any) -> str:
    return _norm(getattr(control, "Name", ""))


def _automation_id(control: Any) -> str:
    return _norm(getattr(control, "AutomationId", ""))


def _walk_controls(root: Any, max_nodes: int = 7000, max_depth: int = 18):
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


class ChromeChatGPTDriver:
    def __init__(
        self,
        *,
        log: Callable[[str], None] | None = None,
        diagnostic_root: Path | None = None,
        generation_timeout: int = 720,
        start_timeout: int = 75,
    ) -> None:
        self.log = log or (lambda message: None)
        self.diagnostic_root = diagnostic_root or Path.cwd() / "logs"
        self.generation_timeout = generation_timeout
        self.start_timeout = start_timeout
        self._chrome_window = None
        pyautogui.FAILSAFE = True

    def chrome_binary(self) -> str:
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return "chrome.exe"

    def _all_chrome_windows(self):
        result = []
        try:
            for window in gw.getAllWindows():
                title = _norm(getattr(window, "title", ""))
                if "chrome" in title:
                    result.append(window)
        except Exception:
            pass
        return result

    def activate_chrome(self) -> None:
        candidates = []
        if self._chrome_window is not None:
            candidates.append(self._chrome_window)
        candidates.extend(reversed(self._all_chrome_windows()))
        for window in candidates:
            try:
                if window.isMinimized:
                    window.restore()
                window.activate()
                try:
                    window.maximize()
                except Exception:
                    pass
                self._chrome_window = window
                time.sleep(0.8)
                return
            except Exception:
                continue
        raise RuntimeError("Chrome è stato avviato ma non riesco ad attivare la sua finestra.")

    def open_gpt(self) -> None:
        self.log("Apertura GPT nel Chrome normale dell'utente")
        subprocess.Popen(
            [self.chrome_binary(), "--new-tab", GPT_URL],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 35
        while time.time() < deadline:
            windows = self._all_chrome_windows()
            if windows:
                self._chrome_window = windows[-1]
                try:
                    self.activate_chrome()
                    break
                except Exception:
                    pass
            time.sleep(1)
        else:
            raise RuntimeError("Google Chrome non è comparso entro 35 secondi.")

        # Forza la destinazione senza usare la clipboard nel composer.
        pyautogui.hotkey("ctrl", "l")
        pyautogui.write(GPT_URL, interval=0.001)
        pyautogui.press("enter")
        time.sleep(4)
        self.wait_composer(timeout=60)
        self.log("GPT pronto e composer rilevato")

    def _uia_window(self):
        # Preferisce il vero HWND della finestra attiva, evitando altre finestre Chrome.
        window = self._chrome_window
        if window is not None:
            hwnd = getattr(window, "_hWnd", None)
            if hwnd:
                try:
                    return auto.ControlFromHandle(hwnd)
                except Exception:
                    pass
        root = auto.GetRootControl()
        candidates = []
        try:
            for child in root.GetChildren():
                name = _norm(getattr(child, "Name", ""))
                class_name = _norm(getattr(child, "ClassName", ""))
                if "chrome_widgetwin" in class_name or "google chrome" in name:
                    candidates.append(child)
        except Exception:
            pass
        return candidates[-1] if candidates else None

    def _records(self) -> list[dict[str, Any]]:
        root = self._uia_window()
        if root is None:
            return []
        records = []
        for control in _walk_controls(root):
            records.append(
                {
                    "control": control,
                    "name": _control_name(control),
                    "automation_id": _automation_id(control),
                    "control_type": _control_type(control),
                    "rect": _rect(control),
                    "signature": _signature(control),
                }
            )
        return records

    @staticmethod
    def _is_composer_record(record: dict[str, Any]) -> bool:
        if record["automation_id"] == "prompt-textarea":
            return True
        name = record["name"]
        ctype = record["control_type"]
        return any(token in name for token in PROMPT_NAMES) and any(
            token in ctype for token in ("edit", "document", "custom", "pane", "group")
        )

    def find_composer(self, timeout: int = 25):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.activate_chrome()
            for record in self._records():
                if self._is_composer_record(record):
                    return record["control"]
            time.sleep(1)
        return None

    def wait_composer(self, timeout: int = 60):
        composer = self.find_composer(timeout=timeout)
        if composer is None:
            raise RuntimeError("COMPOSER_TROVATO=FALSE: il GPT è aperto ma il campo messaggio non è identificabile.")
        return composer

    def _focused_is(self, expected: Any) -> bool:
        try:
            focused = auto.GetFocusedControl()
            if focused is None:
                return False
            if _automation_id(expected) and _automation_id(focused) == _automation_id(expected):
                return True
            er = _rect(expected)
            fr = _rect(focused)
            if er != (0, 0, 0, 0) and fr == er:
                return True
            if _control_name(focused) == _control_name(expected) and _control_type(focused) == _control_type(expected):
                return True
        except Exception:
            return False
        return False

    def _read_focused_text(self, composer: Any) -> str | None:
        # Prima usa ValuePattern, se disponibile.
        try:
            pattern = composer.GetValuePattern()
            value = _safe_text(getattr(pattern, "Value", ""))
            if value:
                return value
        except Exception:
            pass
        # Fallback tastiera, ma solo dopo verifica esplicita del focus sul composer.
        if not self._focused_is(composer):
            return None
        sentinel = "__F1_CLIPBOARD_SENTINEL__"
        pyperclip.copy(sentinel)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.25)
        copied = _safe_text(pyperclip.paste())
        pyautogui.press("end")
        return None if copied == sentinel else copied

    def set_and_verify_prompt(self, prompt: str) -> str:
        composer = self.wait_composer(timeout=35)
        try:
            composer.SetFocus()
        except Exception as exc:
            raise RuntimeError(f"Composer trovato ma SetFocus è fallito: {exc}") from exc
        time.sleep(0.4)
        if not self._focused_is(composer):
            raise RuntimeError("Composer trovato ma il focus tastiera non è sul composer.")

        # Ctrl+A/Backspace è consentito solo dopo la verifica del focus.
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        pyperclip.copy(prompt)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)

        actual = self._read_focused_text(composer)
        if actual is None:
            raise RuntimeError("Non riesco a leggere il testo dal composer dopo l'inserimento.")
        if re.sub(r"\s+", " ", actual).strip() != re.sub(r"\s+", " ", prompt).strip():
            raise RuntimeError(f"TESTO_VERIFICATO=FALSE. Atteso: {prompt!r}. Presente: {actual!r}")
        pyautogui.press("end")
        self.log("Testo nel composer verificato")
        return "uia-focus+clipboard"

    @staticmethod
    def _is_generating_record(record: dict[str, Any]) -> bool:
        name = record["name"]
        ctype = record["control_type"]
        return "button" in ctype and any(token == name or token in name for token in GENERATING_NAMES)

    @staticmethod
    def _is_download_record(record: dict[str, Any]) -> bool:
        name = record["name"]
        ctype = record["control_type"]
        return "button" in ctype and any(token == name or token in name for token in DOWNLOAD_NAMES)

    @staticmethod
    def _is_image_record(record: dict[str, Any]) -> bool:
        left, top, right, bottom = record["rect"]
        width, height = right - left, bottom - top
        if width < 180 or height < 180:
            return False
        name = record["name"]
        ctype = record["control_type"]
        return "image" in ctype or any(token in name for token in IMAGE_NAMES)

    def snapshot(self) -> PageSnapshot:
        records = self._records()
        return PageSnapshot(
            image_signatures={r["signature"] for r in records if self._is_image_record(r)},
            download_signatures={r["signature"] for r in records if self._is_download_record(r)},
            names=[r["name"] for r in records if r["name"]],
        )

    def _page_contains_prompt(self, prompt: str) -> bool:
        expected = re.sub(r"\s+", " ", prompt).strip().lower()
        names = "\n".join(r["name"] for r in self._records() if r["name"])
        return expected in re.sub(r"\s+", " ", names).lower()

    def send_and_verify(self, prompt: str) -> None:
        self.activate_chrome()
        pyautogui.press("enter")
        deadline = time.time() + 25
        while time.time() < deadline:
            records = self._records()
            if self._page_contains_prompt(prompt):
                self.log("Invio verificato: prompt presente nella conversazione")
                return
            if any(self._is_generating_record(r) for r in records):
                self.log("Invio verificato: controllo di generazione rilevato")
                return
            composer = self.find_composer(timeout=1)
            if composer is not None:
                try:
                    composer.SetFocus()
                    current = self._read_focused_text(composer)
                    if current is not None and not current.strip():
                        self.log("Invio verificato: composer svuotato")
                        return
                except Exception:
                    pass
            time.sleep(1)
        raise RuntimeError("PROMPT_INVIATO non verificato entro 25 secondi.")

    def _error_text(self, records: list[dict[str, Any]]) -> str | None:
        names = [r["name"] for r in records if r["name"]]
        joined = "\n".join(names)
        for token in ERROR_NAMES:
            if token in joined:
                return token
        return None

    def wait_generation(self, baseline: PageSnapshot) -> GenerationResult:
        start_deadline = time.time() + self.start_timeout
        overall_deadline = time.time() + self.generation_timeout
        started_at = 0.0
        last_scroll = 0.0

        while time.time() < overall_deadline:
            self.activate_chrome()
            if time.time() - last_scroll > 8:
                pyautogui.press("end")
                last_scroll = time.time()
                time.sleep(0.4)

            records = self._records()
            error = self._error_text(records)
            if error:
                raise RuntimeError(f"ChatGPT segnala un errore durante la generazione: {error}")

            generating = any(self._is_generating_record(r) for r in records)
            images = [r for r in records if self._is_image_record(r) and r["signature"] not in baseline.image_signatures]
            downloads = [r for r in records if self._is_download_record(r) and r["signature"] not in baseline.download_signatures]

            if generating and not started_at:
                started_at = time.time()
                self.log("Generazione iniziata")

            # Un'immagine/download nuovo è prova sufficiente che la generazione è partita,
            # anche se il controllo Stop è scomparso troppo rapidamente.
            if (images or downloads) and not started_at:
                started_at = time.time()
                self.log("Generazione iniziata: nuovo risultato immagine rilevato")

            if started_at and not generating and (images or downloads):
                self.log("Generazione terminata e immagine rilevata")
                return GenerationResult(
                    image_control=images[-1]["control"] if images else None,
                    download_controls=[r["control"] for r in downloads],
                    started_at=started_at,
                    completed_at=time.time(),
                )

            if not started_at and time.time() > start_deadline:
                raise RuntimeError("GENERAZIONE_IN_CORSO non rilevata entro il timeout iniziale.")
            time.sleep(2.5)

        raise RuntimeError("Timeout: generazione immagine non completata entro il limite massimo.")

    def _downloads_dir(self) -> Path:
        return Path(os.path.expandvars(r"%USERPROFILE%\Downloads"))

    @staticmethod
    def _recent_image_files(folder: Path, since: float) -> list[Path]:
        if not folder.exists():
            return []
        allowed = {".png", ".jpg", ".jpeg", ".webp"}
        result = []
        for path in folder.iterdir():
            try:
                if path.is_file() and path.suffix.lower() in allowed and path.stat().st_mtime >= since - 2:
                    result.append(path)
            except OSError:
                continue
        return sorted(result, key=lambda p: p.stat().st_mtime, reverse=True)

    def _wait_download(self, since: float, timeout: int = 60) -> Path | None:
        folder = self._downloads_dir()
        deadline = time.time() + timeout
        last_size = None
        stable_count = 0
        candidate = None
        while time.time() < deadline:
            files = self._recent_image_files(folder, since)
            if files:
                candidate = files[0]
                try:
                    size = candidate.stat().st_size
                except OSError:
                    size = 0
                if size > 10_000 and size == last_size:
                    stable_count += 1
                    if stable_count >= 2:
                        return candidate
                else:
                    stable_count = 0
                    last_size = size
            time.sleep(1)
        return candidate if candidate and candidate.exists() and candidate.stat().st_size > 10_000 else None

    def save_image(self, result: GenerationResult, destination_without_ext: Path) -> tuple[Path, str]:
        destination_without_ext.parent.mkdir(parents=True, exist_ok=True)

        # Strategia primaria: pulsante Download accessibile di ChatGPT.
        for control in reversed(result.download_controls):
            try:
                try:
                    control.ScrollIntoView()
                except Exception:
                    pass
                clicked_at = time.time()
                control.Click()
                downloaded = self._wait_download(clicked_at)
                if downloaded:
                    ext = downloaded.suffix.lower() if downloaded.suffix else ".png"
                    target = destination_without_ext.with_suffix(ext)
                    shutil.copy2(downloaded, target)
                    if target.stat().st_size > 10_000:
                        self.log(f"Immagine salvata dal download: {target}")
                        return target, "download"
            except Exception as exc:
                self.log(f"Download UI non riuscito, provo fallback: {exc}")

        # Fallback: acquisizione dell'area dell'immagine realmente rilevata.
        control = result.image_control
        if control is None:
            raise RuntimeError("Immagine rilevata tramite UI ma nessun controllo immagine acquisibile è disponibile.")
        try:
            control.ScrollIntoView()
            time.sleep(0.8)
        except Exception:
            pass
        left, top, right, bottom = _rect(control)
        width, height = right - left, bottom - top
        if width < 180 or height < 180:
            raise RuntimeError(f"Rettangolo immagine non valido: {left},{top},{right},{bottom}")
        target = destination_without_ext.with_suffix(".png")
        shot = pyautogui.screenshot(region=(left, top, width, height))
        shot.save(target)
        if not target.exists() or target.stat().st_size < 10_000:
            raise RuntimeError("Fallback screenshot creato ma file immagine non valido.")
        self.log(f"Immagine salvata da screenshot verificato: {target}")
        return target, "screenshot"

    def open_new_tab(self, url: str) -> None:
        subprocess.Popen(
            [self.chrome_binary(), "--new-tab", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def current_url(self) -> str | None:
        try:
            self.activate_chrome()
            sentinel = "__F1_URL_SENTINEL__"
            pyperclip.copy(sentinel)
            pyautogui.hotkey("ctrl", "l")
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.2)
            value = _safe_text(pyperclip.paste())
            pyautogui.press("esc")
            return None if value == sentinel else value
        except Exception:
            return None

    def save_diagnostics(self, *, stage: str, query: str, retry_count: int, error: str) -> dict[str, str]:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe_stage = re.sub(r"[^A-Za-z0-9_-]+", "-", stage)[:48]
        base = self.diagnostic_root / "screenshots"
        base.mkdir(parents=True, exist_ok=True)
        screenshot_path = base / f"{stamp}-{safe_stage}-retry{retry_count}.png"
        try:
            pyautogui.screenshot().save(screenshot_path)
        except Exception:
            screenshot_path = Path("")

        tree_dir = self.diagnostic_root / "accessibility"
        tree_dir.mkdir(parents=True, exist_ok=True)
        tree_path = tree_dir / f"{stamp}-{safe_stage}-retry{retry_count}.json"
        payload = {
            "timestamp": stamp,
            "stage": stage,
            "query": query,
            "retry_count": retry_count,
            "error": error,
            "url": self.current_url(),
            "controls": [],
        }
        try:
            for record in self._records()[:5000]:
                if record["name"] or record["automation_id"]:
                    payload["controls"].append(
                        {
                            "name": record["name"],
                            "automation_id": record["automation_id"],
                            "control_type": record["control_type"],
                            "rect": record["rect"],
                        }
                    )
        except Exception as exc:
            payload["accessibility_error"] = str(exc)
        tree_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "screenshot": str(screenshot_path) if screenshot_path else "",
            "accessibility": str(tree_path),
        }
