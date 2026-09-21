#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from publisher.news.f1_valle_susa_news import (
    CONFIG_PATH,
    build_caption,
    build_visual_prompt,
    load_json,
    scan_sources,
    source_hash,
)

ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = ROOT / "publisher" / "news" / "f1_news_browser_queue.json"
FINAL_QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
ROME = ZoneInfo("Europe/Rome")
UA = "F1ValleSusaBrowserControl/1.0 (+https://www.f1immobiliare.com)"


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_queue() -> dict[str, Any]:
    data = load_json(QUEUE_PATH, {"version": 1, "items": [], "updated_at": None})
    data.setdefault("items", [])
    return data


def strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def verify_source(item: dict[str, Any]) -> dict[str, Any]:
    url = str(item.get("source_url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("SOURCE_URL_INVALID")

    response = requests.get(
        url,
        timeout=(8, 25),
        allow_redirects=True,
        headers={"User-Agent": UA},
    )
    response.raise_for_status()
    ctype = str(response.headers.get("content-type") or "").lower()
    if "html" not in ctype and "text" not in ctype:
        raise RuntimeError(f"SOURCE_UNSUPPORTED_CONTENT_TYPE:{ctype}")

    text = strip_html(response.text)
    if len(text) < 250:
        raise RuntimeError("SOURCE_CONTENT_TOO_SHORT")

    expected = str(item.get("title") or "").casefold()
    tokens = [
        t
        for t in re.findall(r"[a-zà-ÿ0-9]+", expected)
        if len(t) >= 5 and t not in {"della", "delle", "degli", "dello", "nella", "nelle", "anche", "comuni"}
    ]
    body = text.casefold()
    matched = sorted({t for t in tokens if t in body})
    if tokens and not matched:
        raise RuntimeError("SOURCE_TITLE_NOT_CONFIRMED")

    return {
        "http_status": response.status_code,
        "final_url": response.url,
        "domain": urlparse(response.url).netloc,
        "content_sha256": hashlib.sha256(response.content).hexdigest(),
        "matched_title_terms": matched[:12],
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def final_queue_index() -> dict[str, dict[str, Any]]:
    payload = load_json(FINAL_QUEUE_PATH, {})
    result: dict[str, dict[str, Any]] = {}
    for job in payload.get("jobs") or []:
        cid = str(job.get("communication_id") or "").strip()
        if cid:
            result[cid] = job
    return result


def reconcile(queue: dict[str, Any]) -> bool:
    changed = False
    finals = final_queue_index()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for item in queue.get("items") or []:
        cid = str(item.get("id") or "")
        remote = finals.get(cid)
        if not remote:
            continue
        status = str(remote.get("status") or "")
        mapping = {
            "READY": "READY_TO_PUBLISH",
            "SCHEDULED": "PUBLISHED",
            "PUBLISHED": "PUBLISHED",
            "PUBLISHED_VERIFIED": "PUBLISHED_VERIFIED",
            "ERROR": "FAILED_RETRYABLE",
        }
        new_status = mapping.get(status, item.get("status"))
        if new_status and new_status != item.get("status"):
            item["status"] = new_status
            item["updated_at"] = now
            changed = True
        for key in (
            "remote_post_id",
            "remote_post_ids",
            "remote_post_url",
            "remote_post_urls",
            "published_at",
            "published_urls",
        ):
            value = remote.get(key)
            if value not in (None, "", []):
                if item.get(key) != value:
                    item[key] = value
                    changed = True
    return changed


def resolve_slot(now: datetime, requested: str) -> tuple[str, str] | None:
    if requested == "midday":
        return "MIDDAY", f"{now.date().isoformat()}|MIDDAY"
    if requested == "evening":
        return "EVENING", f"{now.date().isoformat()}|EVENING"
    if requested == "next":
        current = now.hour * 60 + now.minute
        if current < 19 * 60 + 30:
            return "EVENING", f"{now.date().isoformat()}|EVENING"
        tomorrow = now.date() + timedelta(days=1)
        return "MIDDAY", f"{tomorrow.isoformat()}|MIDDAY"
    if requested == "immediate":
        return "IMMEDIATE", f"{now.date().isoformat()}|IMMEDIATE"

    # GitHub prepares each slot well before the Windows task starts.
    minutes = now.hour * 60 + now.minute
    if 9 * 60 + 30 <= minutes <= 13 * 60:
        return "MIDDAY", f"{now.date().isoformat()}|MIDDAY"
    if 17 * 60 + 30 <= minutes <= 21 * 60:
        return "EVENING", f"{now.date().isoformat()}|EVENING"
    return None


def existing_slot(queue: dict[str, Any], slot_key: str) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in queue.get("items") or []
            if str(row.get("slot_key") or "") == slot_key
            and str(row.get("status") or "") not in {"FAILED_FINAL", "CANCELLED"}
        ),
        None,
    )


def excluded_hashes(queue: dict[str, Any]) -> set[str]:
    hashes = {
        str(row.get("source_hash") or "").strip().lower()
        for row in queue.get("items") or []
        if str(row.get("source_hash") or "").strip()
    }
    final = load_json(FINAL_QUEUE_PATH, {})
    hashes |= {
        str(row.get("source_hash") or "").strip().lower()
        for row in final.get("jobs") or []
        if str(row.get("source_hash") or "").strip()
    }
    return hashes


def featured_candidates(config: dict[str, Any], excluded: set[str]) -> list[dict[str, Any]]:
    featured = [
        dict(row)
        for row in config.get("featured") or []
        if source_hash(row).lower() not in excluded
    ]
    featured.sort(key=lambda x: str(x.get("published_at") or ""), reverse=True)
    return featured


def make_row(now: datetime, slot_name: str, slot_key: str, item: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    digest = source_hash(item)
    cid = f"COMM-NEWS-{slot_key[:10].replace('-','')}-{slot_name}-{digest[:8].upper()}"
    config = load_json(CONFIG_PATH, {})
    caption = build_caption(item, config)
    prompt = build_visual_prompt(item)
    return {
        "id": cid,
        "communication_id": cid,
        "query": str(item.get("headline") or item.get("title") or "F1 NEWS VALLE DI SUSA")[:72],
        "communication": caption,
        "caption": caption,
        "prompt": prompt,
        "client": "F1 Immobiliare",
        "territory": "Valle di Susa",
        "scope": "network",
        "platforms": ["facebook", "instagram"],
        "source": "f1-news-browser-control",
        "news_id": str(item.get("id") or f"NEWS-{digest[:12].upper()}"),
        "headline": str(item.get("headline") or item.get("title") or "F1 NEWS VALLE DI SUSA")[:72],
        "cta": "SCOPRI COSA CAMBIA",
        "category": str(item.get("category") or "immobiliare"),
        "source_name": str(item.get("source_name") or "Fonte pubblica"),
        "source_url": str(item.get("source_url") or ""),
        "source_hash": digest,
        "source_published_at": str(item.get("published_at") or ""),
        "source_verification": verification,
        "editorial_slot": slot_name.lower(),
        "slot_key": slot_key,
        "status": "QUEUED_FOR_PC",
        "created_at": now.isoformat(timespec="seconds"),
        "updated_at": now.isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["auto", "next", "midday", "evening", "immediate"], default="auto")
    parser.add_argument("--github-output")
    args = parser.parse_args()

    now = datetime.now(ROME)
    queue = load_queue()
    changed = reconcile(queue)

    slot_info = resolve_slot(now, args.slot)
    if slot_info is None:
        if changed:
            queue["updated_at"] = now.isoformat(timespec="seconds")
            save_json(QUEUE_PATH, queue)
        print(json.dumps({"status": "NOOP_OUTSIDE_PREP_WINDOW"}, ensure_ascii=False))
        return 0

    slot_name, slot_key = slot_info
    existing = existing_slot(queue, slot_key)
    if existing is not None:
        if changed:
            queue["updated_at"] = now.isoformat(timespec="seconds")
            save_json(QUEUE_PATH, queue)
        payload = {
            "status": "NOOP_SLOT_ALREADY_QUEUED",
            "job_id": existing.get("id"),
            "slot_key": slot_key,
            "queue_status": existing.get("status"),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    config = load_json(CONFIG_PATH, {})
    rejected: list[dict[str, Any]] = []
    selected = None
    verification = None
    excluded = excluded_hashes(queue)
    featured = featured_candidates(config, excluded)

    for item in featured:
        try:
            verification = verify_source(item)
            selected = item
            break
        except Exception as exc:
            rejected.append(
                {
                    "source_url": item.get("source_url"),
                    "source_name": item.get("source_name"),
                    "source_hash": source_hash(item),
                    "error": f"{type(exc).__name__}: {exc}"[:1000],
                }
            )

    if selected is None:
        known = excluded | {source_hash(x).lower() for x in featured}
        for item in scan_sources(config, known)[:25]:
            try:
                verification = verify_source(item)
                selected = item
                break
            except Exception as exc:
                rejected.append(
                    {
                        "source_url": item.get("source_url"),
                        "source_name": item.get("source_name"),
                        "source_hash": source_hash(item),
                        "error": f"{type(exc).__name__}: {exc}"[:1000],
                    }
                )

    if selected is None or verification is None:
        queue.setdefault("rejected", []).extend(rejected)
        queue["rejected"] = queue["rejected"][-100:]
        queue["updated_at"] = now.isoformat(timespec="seconds")
        save_json(QUEUE_PATH, queue)
        print(json.dumps({"status": "NOOP_NO_VERIFIABLE_SOURCE", "checked": len(rejected)}, ensure_ascii=False))
        return 0

    row = make_row(now, slot_name, slot_key, selected, verification)
    queue.setdefault("items", []).append(row)
    queue.setdefault("rejected", []).extend(rejected)
    queue["rejected"] = queue["rejected"][-100:]
    queue["updated_at"] = now.isoformat(timespec="seconds")
    save_json(QUEUE_PATH, queue)

    payload = {
        "status": "QUEUED_FOR_PC",
        "job_id": row["id"],
        "slot_key": slot_key,
        "headline": row["headline"],
        "source_url": row["source_url"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            for key, value in payload.items():
                handle.write(f"{key}={str(value).replace(chr(10), ' ')}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
