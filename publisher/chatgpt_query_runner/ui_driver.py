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
from PIL import Image, UnidentifiedImageError

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
    image_count: int = 0
    download_count: int = 0
    max_image_bottom: int = 0
    max_download_bottom: int = 0


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
        return int(r.left), int(r.top), int(r.right), int(r.bottom)
    except Exception:
        return 0, 0, 0, 0


def _runtime_id(control: Any) -> str:
    try:
        rid = control.GetRuntimeId()
        if rid:
            return ".".join(str(x) for x in rid)
    except Exception:
        pass
    return ""


def _signature(control: Any) -> str:
    runtime = _runtime_id(control)
    if runtime:
        return "runtime:" + runtime
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
        self._coordinate_composer_point: tuple[int, int] | None = None
        self._gpt_session_opened = False
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
                time.sleep(0.7)
                return
            except Exception:
                continue
        raise RuntimeError("Chrome è stato avviato ma non riesco ad attivare la sua finestra.")

    def open_gpt(self) -> None:
        # Reuse the same ChatGPT tab/window across retries. Opening a new tab on
        # every retry can create duplicate generations and makes UIA attach to
        # the wrong tab.
        if not self._gpt_session_opened:
            windows = self._all_chrome_windows()
            if windows:
                self._chrome_window = windows[-1]
                try:
                    self.activate_chrome()
                    current = self.current_url() or ""
                    if current.startswith(GPT_URL) or "chatgpt.com/g/g-6a9c210485488191b072eb694c2f114c" in current:
                        self.log("Riutilizzo la scheda Generatore Grafica F1 già aperta")
                        self.wait_composer(timeout=30)
                        self._gpt_session_opened = True
                        return
                except Exception:
                    pass

        if self._gpt_session_opened and self._chrome_window is not None:
            self.log("Riutilizzo la scheda ChatGPT esistente")
            self.activate_chrome()
            current = self.current_url() or ""
            if "chatgpt.com" not in current:
                pyautogui.hotkey("ctrl", "l")
                pyautogui.write(GPT_URL, interval=0.001)
                pyautogui.press("enter")
                time.sleep(3)
            self.wait_composer(timeout=30)
            self.log("Scheda ChatGPT riutilizzata e composer verificato")
            return

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

        pyautogui.hotkey("ctrl", "l")
        pyautogui.write(GPT_URL, interval=0.001)
        pyautogui.press("enter")
        time.sleep(5)
        self.wait_composer(timeout=25)
        self._gpt_session_opened = True
        self.log("GPT pronto e campo messaggio verificato")

    def _uia_window(self):
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
        if any(token in name for token in PROMPT_NAMES) and any(
            token in ctype for token in ("edit", "document", "custom", "pane", "group")
        ):
            return True
        # Chrome/ChatGPT a volte espone il composer senza nome. Accetta un editor
        # sufficientemente grande nella parte bassa della finestra.
        left, top, right, bottom = record["rect"]
        width, height = right - left, bottom - top
        if any(token in ctype for token in ("edit", "document")) and width >= 350 and height >= 35:
            screen_h = pyautogui.size().height
            if top >= int(screen_h * 0.62):
                return True
        return False

    def find_composer(self, timeout: int = 8):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.activate_chrome()
            for record in self._records():
                if self._is_composer_record(record):
                    return record["control"]
            time.sleep(0.8)
        return None

    def _window_geometry(self) -> tuple[int, int, int, int]:
        self.activate_chrome()
        window = self._chrome_window
        if window is not None:
            try:
                left = int(window.left)
                top = int(window.top)
                width = int(window.width)
                height = int(window.height)
                if width > 600 and height > 400:
                    return left, top, width, height
            except Exception:
                pass
        size = pyautogui.size()
        return 0, 0, int(size.width), int(size.height)

    def _candidate_composer_points(self) -> list[tuple[int, int]]:
        left, top, width, height = self._window_geometry()
        xs = (0.50, 0.46, 0.54)
        ys = (0.90, 0.86, 0.82, 0.94)
        points = []
        for y_ratio in ys:
            for x_ratio in xs:
                points.append((left + int(width * x_ratio), top + int(height * y_ratio)))
        return points

    @staticmethod
    def _clipboard_selected_text() -> str | None:
        sentinel = "__F1_CLIPBOARD_SENTINEL__"
        pyperclip.copy(sentinel)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.25)
        copied = _safe_text(pyperclip.paste())
        return None if copied == sentinel else copied

    def _probe_coordinate_composer(self) -> tuple[int, int] | None:
        if self._coordinate_composer_point is not None:
            return self._coordinate_composer_point
        self.activate_chrome()
        marker = "F1-COMPOSER-TEST-94731"
        for point in self._candidate_composer_points():
            try:
                pyautogui.click(*point)
                time.sleep(0.25)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.press("backspace")
                pyperclip.copy(marker)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.35)
                copied = self._clipboard_selected_text()
                if _norm(copied) == _norm(marker):
                    pyautogui.press("backspace")
                    self._coordinate_composer_point = point
                    self.log(f"Composer verificato con fallback coordinate: {point[0]},{point[1]}")
                    return point
                pyautogui.press("esc")
            except Exception:
                try:
                    pyautogui.press("esc")
                except Exception:
                    pass
        return None

    def wait_composer(self, timeout: int = 25):
        # Prima prova l'albero accessibile, ma non resta bloccato 60 secondi.
        composer = self.find_composer(timeout=min(timeout, 8))
        if composer is not None:
            return composer
        point = self._probe_coordinate_composer()
        if point is not None:
            return point
        raise RuntimeError(
            "COMPOSER_TROVATO=FALSE: né UI Automation né il fallback verificato sul box della chat riescono a identificare il campo messaggio."
        )

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
            return _control_name(focused) == _control_name(expected) and _control_type(focused) == _control_type(expected)
        except Exception:
            return False

    def _read_focused_text(self, composer: Any) -> str | None:
        try:
            pattern = composer.GetValuePattern()
            value = _safe_text(getattr(pattern, "Value", ""))
            if value:
                return value
        except Exception:
            pass
        if not self._focused_is(composer):
            return None
        copied = self._clipboard_selected_text()
        pyautogui.press("end")
        return copied

    def _set_prompt_by_coordinate(self, prompt: str) -> str:
        point = self._probe_coordinate_composer()
        if point is None:
            raise RuntimeError("Fallback coordinate: campo messaggio non verificabile.")
        self.activate_chrome()
        pyautogui.click(*point)
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        pyperclip.copy(prompt)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        actual = self._clipboard_selected_text()
        if _norm(actual) != _norm(prompt):
            raise RuntimeError(f"TESTO_VERIFICATO=FALSE nel fallback coordinate. Atteso: {prompt!r}. Presente: {actual!r}")
        pyautogui.press("end")
        self.log("Testo nel composer verificato con fallback coordinate")
        return "coordinate-verified+clipboard"

    def set_and_verify_prompt(self, prompt: str) -> str:
        composer = self.find_composer(timeout=5)
        if composer is None:
            return self._set_prompt_by_coordinate(prompt)
        try:
            composer.SetFocus()
        except Exception:
            return self._set_prompt_by_coordinate(prompt)
        time.sleep(0.35)
        if not self._focused_is(composer):
            return self._set_prompt_by_coordinate(prompt)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        pyperclip.copy(prompt)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        actual = self._read_focused_text(composer)
        if _norm(actual) != _norm(prompt):
            # Se la lettura UIA è inaffidabile, prova lo stesso box via coordinate.
            return self._set_prompt_by_coordinate(prompt)
        pyautogui.press("end")
        self.log("Testo nel composer verificato tramite UI Automation")
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
        images = [r for r in records if self._is_image_record(r)]
        downloads = [r for r in records if self._is_download_record(r)]
        return PageSnapshot(
            image_signatures={r["signature"] for r in images},
            download_signatures={r["signature"] for r in downloads},
            names=[r["name"] for r in records if r["name"]],
            image_count=len(images),
            download_count=len(downloads),
            max_image_bottom=max((r["rect"][3] for r in images), default=0),
            max_download_bottom=max((r["rect"][3] for r in downloads), default=0),
        )

    def _page_contains_prompt(self, prompt: str) -> bool:
        expected = _norm(prompt)
        names = "\n".join(r["name"] for r in self._records() if r["name"])
        return expected in _norm(names)

    def _coordinate_composer_text(self) -> str | None:
        point = self._coordinate_composer_point
        if point is None:
            return None
        try:
            self.activate_chrome()
            pyautogui.click(*point)
            time.sleep(0.2)
            copied = self._clipboard_selected_text()
            pyautogui.press("end")
            return copied
        except Exception:
            return None

    def send_and_verify(self, prompt: str) -> None:
        self.activate_chrome()
        pyautogui.press("enter")
        time.sleep(0.8)
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
            current = self._coordinate_composer_text()
            if current is not None and not current.strip():
                self.log("Invio verificato: composer coordinate svuotato")
                return
            time.sleep(0.8)
        raise RuntimeError("PROMPT_INVIATO non verificato entro 25 secondi.")

    def _error_text(self, records: list[dict[str, Any]]) -> str | None:
        joined = "\n".join(r["name"] for r in records if r["name"])
        for token in ERROR_NAMES:
            if token in joined:
                return token
        return None

    def wait_generation(self, baseline: PageSnapshot, prompt: str | None = None) -> GenerationResult:
        wait_started = time.time()
        start_deadline = wait_started + self.start_timeout
        overall_deadline = wait_started + self.generation_timeout
        started_at = 0.0
        last_scroll = 0.0
        last_debug = 0.0

        while time.time() < overall_deadline:
            self.activate_chrome()
            if time.time() - last_scroll > 6:
                pyautogui.press("end")
                last_scroll = time.time()
                time.sleep(0.35)

            records = self._records()
            error = self._error_text(records)
            if error:
                raise RuntimeError(f"ChatGPT segnala un errore durante la generazione: {error}")

            generating = any(self._is_generating_record(r) for r in records)
            all_images = [r for r in records if self._is_image_record(r)]
            all_downloads = [r for r in records if self._is_download_record(r)]
            new_images = [r for r in all_images if r["signature"] not in baseline.image_signatures]
            new_downloads = [r for r in all_downloads if r["signature"] not in baseline.download_signatures]

            image_count_increased = len(all_images) > baseline.image_count
            download_count_increased = len(all_downloads) > baseline.download_count
            max_image_bottom = max((r["rect"][3] for r in all_images), default=0)
            max_download_bottom = max((r["rect"][3] for r in all_downloads), default=0)
            bottom_advanced = (
                max_image_bottom > baseline.max_image_bottom + 24
                or max_download_bottom > baseline.max_download_bottom + 24
            )
            result_changed = bool(
                new_images
                or new_downloads
                or image_count_increased
                or download_count_increased
                or bottom_advanced
            )

            if generating and not started_at:
                started_at = time.time()
                self.log("Generazione iniziata")

            if result_changed and not started_at:
                started_at = time.time()
                self.log("Generazione iniziata: risultato visuale nuovo o spostato rilevato")

            # Primary completion path: generation was observed and a result exists.
            if started_at and not generating and (all_images or all_downloads):
                latest_image = max(all_images, key=lambda r: r["rect"][3])["control"] if all_images else None
                latest_downloads = [
                    r["control"]
                    for r in sorted(all_downloads, key=lambda r: r["rect"][3])
                ]
                self.log(
                    "Generazione terminata: risultato disponibile "
                    f"(images={len(all_images)}, downloads={len(all_downloads)}, changed={result_changed})"
                )
                return GenerationResult(
                    image_control=latest_image,
                    download_controls=latest_downloads,
                    started_at=started_at,
                    completed_at=time.time(),
                )

            # Resilience path for ChatGPT UI updates that recycle the same
            # accessibility node/signature. If the submitted prompt is present,
            # enough time has elapsed and a large result is visible at the end of
            # the conversation, accept the latest image even if its runtime ID
            # did not change.
            elapsed = time.time() - wait_started
            if (
                not generating
                and elapsed >= 12
                and (all_images or all_downloads)
                and (prompt is None or self._page_contains_prompt(prompt))
            ):
                screen_h = pyautogui.size().height
                latest_bottom = max(max_image_bottom, max_download_bottom)
                if latest_bottom >= int(screen_h * 0.45):
                    latest_image = max(all_images, key=lambda r: r["rect"][3])["control"] if all_images else None
                    latest_downloads = [
                        r["control"]
                        for r in sorted(all_downloads, key=lambda r: r["rect"][3])
                    ]
                    self.log(
                        "Generazione terminata via fallback resiliente: "
                        "risultato visibile dopo prompt inviato"
                    )
                    return GenerationResult(
                        image_control=latest_image,
                        download_controls=latest_downloads,
                        started_at=started_at or wait_started,
                        completed_at=time.time(),
                    )

            if time.time() - last_debug > 10:
                self.log(
                    "Attesa generazione: "
                    f"generating={generating} images={len(all_images)} "
                    f"downloads={len(all_downloads)} changed={result_changed}"
                )
                last_debug = time.time()

            if not started_at and time.time() > start_deadline:
                raise RuntimeError(
                    "GENERAZIONE_IN_CORSO non rilevata: nessun nuovo risultato accessibile "
                    "entro il timeout iniziale."
                )
            time.sleep(1.5)

        raise RuntimeError("Timeout: generazione immagine non completata entro il limite massimo.")

    @staticmethod
    def _validate_image_file(path: Path) -> tuple[int, int, str]:
        if not path.exists() or not path.is_file():
            raise RuntimeError(f"File immagine non trovato: {path}")
        size = path.stat().st_size
        if size < 10_000:
            raise RuntimeError(f"File immagine troppo piccolo: {size} byte")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
                fmt = str(image.format or "").upper()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise RuntimeError(f"File scaricato non è un'immagine leggibile: {path.name}: {exc}") from exc
        if fmt not in {"PNG", "JPEG", "WEBP"}:
            raise RuntimeError(f"Formato immagine non ammesso: {fmt or 'sconosciuto'}")
        if width < 180 or height < 180:
            raise RuntimeError(f"Dimensioni immagine non plausibili: {width}x{height}")
        return width, height, fmt


    def _latest_image_control(self):
        self.activate_chrome()
        pyautogui.press("end")
        time.sleep(0.6)
        candidates = [r for r in self._records() if self._is_image_record(r)]
        if not candidates:
            return None
        # Prefer the lowest/largest visible image: the latest generated result is
        # normally the last large image in the active conversation.
        candidates.sort(
            key=lambda r: (
                r["rect"][1],
                (r["rect"][2] - r["rect"][0]) * (r["rect"][3] - r["rect"][1]),
            )
        )
        return candidates[-1]["control"]

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

    def _wait_download(self, since: float, timeout: int = 12) -> Path | None:
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
                    width, height, fmt = self._validate_image_file(target)
                    self.log(f"Immagine salvata e verificata dal download: {target} ({width}x{height} {fmt})")
                    return target, "download"
            except Exception as exc:
                self.log(f"Download UI non riuscito, provo fallback: {exc}")
        control = result.image_control
        # UIA can expose the download button before the image control, or a
        # previously captured control can become stale after the page updates.
        # Rescan the active conversation before giving up.
        if control is None or _rect(control) == (0, 0, 0, 0):
            control = self._latest_image_control()
        if control is None:
            raise RuntimeError("Immagine generata visibile ma nessun controllo immagine acquisibile è stato trovato dopo il rescan.")
        try:
            control.ScrollIntoView()
            time.sleep(0.8)
        except Exception:
            pass
        left, top, right, bottom = _rect(control)
        width, height = right - left, bottom - top
        if width < 180 or height < 180:
            control = self._latest_image_control()
            if control is not None:
                left, top, right, bottom = _rect(control)
                width, height = right - left, bottom - top
        if width < 180 or height < 180:
            raise RuntimeError(f"Rettangolo immagine non valido dopo rescan: {left},{top},{right},{bottom}")
        screen = pyautogui.size()
        left = max(0, min(left, screen.width - 1))
        top = max(0, min(top, screen.height - 1))
        width = min(width, screen.width - left)
        height = min(height, screen.height - top)
        target = destination_without_ext.with_suffix(".png")
        shot = pyautogui.screenshot(region=(left, top, width, height))
        shot.save(target)
        width, height, fmt = self._validate_image_file(target)
        self.log(f"Immagine salvata da screenshot e verificata: {target} ({width}x{height} {fmt})")
        return target, "screenshot"

    def open_new_tab(self, url: str) -> None:
        subprocess.Popen([self.chrome_binary(), "--new-tab", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
            "coordinate_composer_point": self._coordinate_composer_point,
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
