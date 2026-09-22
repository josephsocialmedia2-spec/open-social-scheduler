from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import pyautogui

from publisher.chatgpt_query_runner.ui_driver import (
    ChromeChatGPTDriver,
    _automation_id,
    _control_name,
    _control_type,
    _norm,
)

ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_PATH = ROOT / "publisher" / "chatgpt_query_runner" / "providers.json"


class ProviderUnavailable(RuntimeError):
    pass


class ProviderLimitReached(RuntimeError):
    pass


class ProviderAuthRequired(RuntimeError):
    pass


def load_provider_registry(path: Path = PROVIDERS_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("policy", {})
    payload.setdefault("providers", [])
    return payload


class ConfiguredBrowserImageDriver(ChromeChatGPTDriver):
    """Accessibility-first browser adapter for image generators with similar UX.

    This intentionally reuses the existing Windows Chrome/UIAutomation machinery.
    It never stores credentials, cookies or tokens in the repository.
    """

    def __init__(
        self,
        provider: dict[str, Any],
        *,
        log: Callable[[str], None] | None = None,
        diagnostic_root: Path | None = None,
    ) -> None:
        super().__init__(log=log, diagnostic_root=diagnostic_root)
        self.provider = provider
        self.provider_name = str(provider.get("name") or "provider")
        self.provider_url = str(provider.get("url") or "").strip()
        self.prompt_tokens = tuple(_norm(x) for x in provider.get("prompt_tokens") or ["prompt"])
        self.generate_tokens = tuple(_norm(x) for x in provider.get("generate_tokens") or ["generate"])
        self.generating_tokens = tuple(_norm(x) for x in provider.get("generating_tokens") or ["generating", "stop"])
        self.download_tokens = tuple(_norm(x) for x in provider.get("download_tokens") or ["download"])
        self.limit_tokens = tuple(_norm(x) for x in provider.get("limit_tokens") or ["limit reached", "no credits"])
        self.auth_tokens = tuple(_norm(x) for x in provider.get("auth_tokens") or ["sign in", "log in"])

    def _joined_names(self) -> str:
        return "\n".join(r["name"] for r in self._records() if r.get("name"))

    def _detect_blockers(self) -> None:
        joined = _norm(self._joined_names())
        if any(token and token in joined for token in self.limit_tokens):
            raise ProviderLimitReached(f"{self.provider_name}: free quota/limit reached")
        if any(token and token in joined for token in self.auth_tokens):
            # Auth text can also exist in navigation chrome. Only block when no composer is present.
            if self.find_composer(timeout=1) is None:
                raise ProviderAuthRequired(f"{self.provider_name}: authentication required")

    def open_gpt(self) -> None:
        if not self.provider_url:
            raise ProviderUnavailable(f"{self.provider_name}: URL provider non configurato")
        self.log(f"Apertura provider gratuito: {self.provider_name}")
        windows = self._all_chrome_windows()
        if windows:
            self._chrome_window = windows[-1]
            self.activate_chrome()
            pyautogui.hotkey("ctrl", "l")
            pyautogui.write(self.provider_url, interval=0.001)
            pyautogui.press("enter")
        else:
            subprocess.Popen(
                [self.chrome_binary(), "--new-tab", self.provider_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.time() + 35
            while time.time() < deadline:
                windows = self._all_chrome_windows()
                if windows:
                    self._chrome_window = windows[-1]
                    self.activate_chrome()
                    break
                time.sleep(1)
            else:
                raise ProviderUnavailable(f"{self.provider_name}: Chrome non disponibile")
        time.sleep(4)
        self._detect_blockers()
        self.wait_composer(timeout=30)
        self.log(f"Provider pronto: {self.provider_name}")

    def _is_composer_record(self, record: dict[str, Any]) -> bool:
        aid = record["automation_id"]
        name = record["name"]
        ctype = record["control_type"]
        if aid in {"prompt-textarea", "prompt", "textarea"}:
            return True
        if any(token and token in (name + " " + aid) for token in self.prompt_tokens):
            if any(k in ctype for k in ("edit", "document", "custom", "pane", "group")):
                return True
        return super()._is_composer_record(record)

    def _is_generating_record(self, record: dict[str, Any]) -> bool:
        name = record["name"]
        return any(token and token in name for token in self.generating_tokens) or super()._is_generating_record(record)

    def _is_download_record(self, record: dict[str, Any]) -> bool:
        name = record["name"]
        ctype = record["control_type"]
        return ("button" in ctype or "hyperlink" in ctype) and any(
            token and token in name for token in self.download_tokens
        )

    def _error_text(self, records: list[dict[str, Any]]) -> str | None:
        joined = _norm("\n".join(r["name"] for r in records if r.get("name")))
        for token in self.limit_tokens:
            if token and token in joined:
                return f"PROVIDER_LIMIT:{token}"
        for token in self.auth_tokens:
            if token and token in joined and self.find_composer(timeout=1) is None:
                return f"AUTH_REQUIRED:{token}"
        return super()._error_text(records)

    def wait_generation(self, baseline, prompt: str | None = None):
        try:
            return super().wait_generation(baseline, prompt=prompt)
        except RuntimeError as exc:
            msg = str(exc)
            if "PROVIDER_LIMIT:" in msg:
                raise ProviderLimitReached(f"{self.provider_name}: {msg}") from exc
            if "AUTH_REQUIRED:" in msg:
                raise ProviderAuthRequired(f"{self.provider_name}: {msg}") from exc
            raise


class FreeProviderRouterDriver:
    """Drop-in driver facade used by worker.py.

    The worker sees the same methods as ChromeChatGPTDriver. On quota/auth/provider
    failures the router advances to the next eligible zero-cost provider.
    """

    def __init__(
        self,
        *,
        log: Callable[[str], None] | None = None,
        diagnostic_root: Path | None = None,
        registry_path: Path = PROVIDERS_PATH,
    ) -> None:
        self.log = log or (lambda message: None)
        self.diagnostic_root = diagnostic_root
        self.registry = load_provider_registry(registry_path)
        policy = self.registry.get("policy") or {}
        require_commercial = bool(policy.get("require_commercial_use", True))
        self.max_failures = max(1, int(policy.get("max_provider_failures_per_content", 2)))
        providers = sorted(self.registry.get("providers") or [], key=lambda p: int(p.get("priority", 9999)))
        self.providers = [
            p for p in providers
            if p.get("enabled")
            and p.get("mode") == "browser"
            and p.get("supports_download")
            and p.get("supports_photorealism")
            and (not require_commercial or p.get("commercial_use_allowed") is True)
        ]
        if not self.providers:
            raise ProviderUnavailable("Nessun provider gratuito idoneo configurato")
        self.index = 0
        self._driver = None
        self.failures: dict[str, int] = {}

    @property
    def provider_name(self) -> str:
        return str(self.providers[self.index].get("name") or "provider")

    def _make_driver(self):
        cfg = self.providers[self.index]
        if cfg.get("adapter") == "chatgpt":
            driver = ChromeChatGPTDriver(log=self.log, diagnostic_root=self.diagnostic_root)
            setattr(driver, "provider_name", cfg.get("name"))
            return driver
        return ConfiguredBrowserImageDriver(cfg, log=self.log, diagnostic_root=self.diagnostic_root)

    def _ensure_driver(self):
        if self._driver is None:
            self._driver = self._make_driver()
        return self._driver

    def _advance(self, reason: str) -> None:
        old = self.provider_name
        if self.index + 1 >= len(self.providers):
            raise ProviderUnavailable(f"Tutti i provider gratuiti sono esauriti/non disponibili. Ultimo={old}. Motivo={reason}")
        self.index += 1
        self._driver = None
        self.log(f"FREE_PROVIDER_ROUTER: {old} -> {self.provider_name} ({reason})")

    def open_gpt(self) -> None:
        attempted = 0
        last_error: Exception | None = None
        while attempted < len(self.providers):
            driver = self._ensure_driver()
            try:
                self.log(f"FREE_PROVIDER_ROUTER selezionato: {self.provider_name}")
                driver.open_gpt()
                return
            except (ProviderLimitReached, ProviderAuthRequired, ProviderUnavailable) as exc:
                last_error = exc
                self.failures[self.provider_name] = self.failures.get(self.provider_name, 0) + 1
                attempted += 1
                if self.index + 1 >= len(self.providers):
                    break
                self._advance(type(exc).__name__)
        raise ProviderUnavailable(str(last_error or "Nessun provider disponibile"))

    def handle_failure(self, exc: Exception) -> None:
        name = self.provider_name
        self.failures[name] = self.failures.get(name, 0) + 1
        msg = _norm(str(exc))
        hard_switch = any(token in msg for token in (
            "limit", "quota", "credits", "tokens", "auth", "sign in", "log in", "temporarily unavailable"
        ))
        if hard_switch or self.failures[name] >= self.max_failures:
            if self.index + 1 < len(self.providers):
                self._advance(f"failure={type(exc).__name__}")

    def current_provider_metadata(self) -> dict[str, Any]:
        cfg = dict(self.providers[self.index])
        return {
            "provider": cfg.get("name"),
            "priority": cfg.get("priority"),
            "commercial_use_allowed": cfg.get("commercial_use_allowed"),
            "terms_checked_at": cfg.get("terms_checked_at"),
            "free_limit_type": cfg.get("free_limit_type"),
        }

    def __getattr__(self, name: str):
        return getattr(self._ensure_driver(), name)
