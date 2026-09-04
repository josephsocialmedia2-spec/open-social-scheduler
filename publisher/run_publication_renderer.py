#!/usr/bin/env python3
"""Run the strict publication renderer with smarter F1 visual selection.

F1 selection policy:
- only approved/local or explicitly residential sources from the client config;
- match the source to the current post subject instead of pure position rotation;
- prefer realistic residential / listing-style imagery;
- prefer town/architecture imagery for microzone/market posts;
- avoid suspicious animal/non-real-estate filenames and credits;
- use image_history.json to reduce immediate repetition between cycles;
- keep polite retry/backoff for Wikimedia HTTP 429 responses.

Real Media Pro remains generated locally from Shopify Theme Store DESCRIPTIONS
only and makes no image requests to Shopify.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import render_photos_only as renderer

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
HISTORY = ROOT / "publisher" / "image_history.json"
F1_CFG = ROOT / "publisher" / "clients" / "f1-immobiliare.json"

_original_get_remote_image = renderer.get_remote_image
_request_count = 0

LOCAL_MARKERS = (
    "avigliana", "valle di susa", "val di susa", "susa", "almese", "sant'ambrogio",
    "oulx", "bardonecchia", "sauze", "condove", "villar dora", "bussoleno",
    "borgone", "chiusa di san michele", "piemonte", "torino",
)
RESIDENTIAL_MARKERS = (
    "residen", "appart", "villa", "villetta", "house", "home", "casa", "palazzina",
    "building", "abitaz", "architecture", "architettura",
)
TOWNSCAPE_MARKERS = (
    "centro storico", "borgo", "street", "piazza", "town", "village", "quartiere",
)
FORBIDDEN_MARKERS = (
    "owl", "gufo", "bird", "uccello", "cat", "gatto", "dog", "cane", "animal", "animale",
    "food", "cibo", "car", "auto", "motor", "portrait", "ritratto",
)


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def source_text(item: dict) -> str:
    return (str(item.get("credit") or "") + " " + str(item.get("url") or "")).lower()


def source_kind(item: dict) -> set[str]:
    text = source_text(item)
    kinds: set[str] = set()
    if any(x in text for x in RESIDENTIAL_MARKERS):
        kinds.add("residential")
    if any(x in text for x in ("villa", "villetta", "house", "home", "casa")):
        kinds.add("house")
    if any(x in text for x in ("appart", "palazzina", "condominio")):
        kinds.add("apartment")
    if any(x in text for x in TOWNSCAPE_MARKERS):
        kinds.add("townscape")
    if any(x in text for x in LOCAL_MARKERS):
        kinds.add("local")
    return kinds


def job_need(job: dict) -> set[str]:
    text = (str(job.get("title") or "") + " " + str(job.get("caption") or "")).lower()
    need = {"residential"}
    if "appartament" in text:
        need.add("apartment")
    if any(x in text for x in ("villa", "villetta", "casa", "abitazione")):
        need.add("house")
    if any(x in text for x in ("microzona", "zona", "mercato", "via, piano", "territorio")):
        need.add("townscape")
    return need


def recent_usage_penalty(url: str, history: dict) -> int:
    rows = history.get("brands", {}).get("f1-immobiliare", {}).get("recent", [])
    url_key = url.strip().lower()
    matching = [r for r in rows if str(r.get("url") or r.get("key") or "").strip().lower() == url_key]
    if not matching:
        return 0
    # The record function keeps the latest use of a URL at the end of the list.
    last = matching[-1]
    try:
        used = datetime.fromisoformat(str(last.get("used_at") or "").replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - used).total_seconds() / 3600
    except Exception:
        return 3
    if age_hours < 4:
        return 12
    if age_hours < 12:
        return 7
    if age_hours < 24:
        return 4
    if age_hours < 72:
        return 2
    return 0


def semantic_score(job: dict, item: dict, history: dict) -> int:
    text = source_text(item)
    if any(x in text for x in FORBIDDEN_MARKERS):
        return -10_000

    kinds = source_kind(item)
    need = job_need(job)
    score = 0

    # Locality and residential credibility are mandatory priorities.
    if "local" in kinds:
        score += 12
    if "residential" in kinds:
        score += 10

    # Match the post subject.
    if "apartment" in need:
        score += 9 if "apartment" in kinds else (4 if "residential" in kinds else -8)
    if "house" in need:
        score += 8 if "house" in kinds else (3 if "residential" in kinds else -6)
    if "townscape" in need:
        score += 10 if "townscape" in kinds else 0
    elif "townscape" in kinds and "residential" not in kinds:
        score -= 4

    # Prefer sources that explicitly look like residential architecture rather than generic scenery.
    if any(x in text for x in ("architettura residenziale", "villa", "house", "home", "abitazione")):
        score += 5
    if "tramonto" in text and "townscape" not in need:
        score -= 2

    score -= recent_usage_penalty(str(item.get("url") or ""), history)
    return score


def smart_f1_candidates() -> list[str]:
    cfg = load_json(F1_CFG, {})
    queue = load_json(QUEUE, {"jobs": []})
    history = load_json(HISTORY, {"brands": {}})
    cycle = queue.get("current_cycle")
    jobs = sorted(
        [j for j in queue.get("jobs", []) if j.get("cycle_key") == cycle and j.get("client_id") == "f1-immobiliare"],
        key=lambda j: int(j.get("cycle_position", 0)),
    )
    if len(jobs) != 5:
        raise RuntimeError(f"F1 smart visual selector expected 5 jobs, got {len(jobs)}")

    sources = []
    for item in cfg.get("brand", {}).get("photo_sources", []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        text = source_text(item)
        if not url or any(x in text for x in FORBIDDEN_MARKERS):
            continue
        kinds = source_kind(item)
        # Accept configured local sources; allow explicit residential sources as a controlled backup.
        if "local" in kinds or "residential" in kinds:
            sources.append(item)

    if len(sources) < 5:
        raise RuntimeError("F1 smart visual selector requires at least five approved residential/local sources")

    # Greedy one-to-one assignment: each post gets the best still-unused source.
    unused = list(sources)
    ordered: list[str] = []
    for job in jobs:
        ranked = sorted(unused, key=lambda item: semantic_score(job, item, history), reverse=True)
        best = ranked[0]
        best_score = semantic_score(job, best, history)
        if best_score < 0:
            raise RuntimeError(
                f"F1 visual policy found no coherent source for {job.get('id')} (best score={best_score})"
            )
        ordered.append(str(best["url"]))
        unused.remove(best)
        print(
            "F1 VISUAL MATCH",
            f"pos={job.get('cycle_position')}",
            f"need={sorted(job_need(job))}",
            f"score={best_score}",
            f"source={best.get('credit') or best.get('url')}",
        )

    # Append remaining valid sources so render_photos_only can still recover if a download fails.
    remaining = sorted(
        unused,
        key=lambda item: max(semantic_score(job, item, history) for job in jobs),
        reverse=True,
    )
    ordered.extend(str(item["url"]) for item in remaining)
    return ordered


def robust_local_get(url: str):
    global _request_count
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
            print(f"WARN HTTP 429 for approved F1 source; retrying without changing source: {url}")
        except Exception as exc:
            last_error = exc
            raise

    assert last_error is not None
    raise last_error


renderer.get_remote_image = robust_local_get
renderer.configured_f1_local_candidates = smart_f1_candidates

if __name__ == "__main__":
    raise SystemExit(renderer.main())
