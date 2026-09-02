#!/usr/bin/env python3
"""Run the strict publication renderer with polite retry/backoff for local F1 sources.

This wrapper does not relax the visual policy. It only spaces requests to the
approved local Wikimedia sources so a temporary HTTP 429 cannot force a generic
fallback. Real Media Pro remains generated locally from Shopify Theme Store
DESCRIPTIONS only and makes no image requests to Shopify.
"""
from __future__ import annotations

import time

import requests

import render_photos_only as renderer

_original_get_remote_image = renderer.get_remote_image
_request_count = 0


def robust_local_get(url: str):
    global _request_count
    # Wikimedia's public endpoints can rate-limit burst traffic. Keep the cycle
    # deliberately slow rather than changing image source or falling back.
    if _request_count:
        time.sleep(5)
    _request_count += 1

    last_error: Exception | None = None
    for attempt, extra_wait in enumerate((0, 12, 25), start=1):
        if extra_wait:
            print(f"WAIT local F1 source retry {attempt}: {extra_wait}s")
            time.sleep(extra_wait)
        try:
            return _original_get_remote_image(url)
        except requests.HTTPError as exc:
            last_error = exc
            status = getattr(exc.response, "status_code", None)
            if status != 429:
                raise
            print(f"WARN HTTP 429 for approved local F1 source; retrying without changing source: {url}")
        except Exception as exc:
            last_error = exc
            # Non-rate-limit errors are source-specific; preserve the renderer's
            # normal behavior so it can try another APPROVED local URL.
            raise

    assert last_error is not None
    raise last_error


renderer.get_remote_image = robust_local_get

if __name__ == "__main__":
    raise SystemExit(renderer.main())
