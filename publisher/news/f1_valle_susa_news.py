#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "publisher" / "news" / "f1_valle_susa_sources.json"
FINAL_QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
LOCAL_STATE_PATH = ROOT / "publisher" / "news" / "f1_valle_susa_news_state.local.json"
DEFAULT_QUERY_PATH = ROOT / "publisher" / "news" / "f1_news_current.local.json"
ROME = ZoneInfo("Europe/Rome")
UA = "F1ValleSusaNewsRadar/2.0 (+https://www.f1immobiliare.com)"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            label = re.sub(r"\s+", " ", " ".join(self._text)).strip()
            if label:
                self.links.append((self._href, label))
            self._href = ""
            self._text = []


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" -|·")[:180]


def source_hash(item: dict[str, Any]) -> str:
    raw = "|".join([
        str(item.get("source_url") or ""),
        str(item.get("title") or ""),
        str(item.get("published_at") or ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def queue_source_hashes() -> set[str]:
    queue = load_json(FINAL_QUEUE_PATH, {})
    values: set[str] = set()
    for job in queue.get("jobs") or []:
        digest = str(job.get("source_hash") or "").strip().lower()
        if digest:
            values.add(digest)
    return values


def local_selected_hashes() -> set[str]:
    state = load_json(LOCAL_STATE_PATH, {"selected": []})
    return {
        str(x.get("hash") or "").strip().lower()
        for x in state.get("selected") or []
        if str(x.get("status") or "").upper() in {"PUBLISHED_VERIFIED", "PUBLISHED"}
    }


def score_link(text: str, url: str, config: dict[str, Any]) -> int:
    hay = (text + " " + url).casefold()
    score = sum(4 for k in config.get("keywords") or [] if str(k).casefold() in hay)
    score += sum(6 for t in config.get("towns") or [] if str(t).casefold() in hay)
    if any(x in hay for x in ("2026", "settembre", "september")):
        score += 2
    return score


def scan_sources(config: dict[str, Any], excluded_hashes: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for src in config.get("sources") or []:
        try:
            response = requests.get(
                str(src["url"]),
                headers={"User-Agent": UA},
                timeout=20,
            )
            response.raise_for_status()
            parser = LinkParser()
            parser.feed(response.text)
        except Exception:
            continue

        for href, text in parser.links:
            title = clean_title(text)
            if len(title) < 20:
                continue
            url = urljoin(str(src["url"]), href)
            if urlparse(url).scheme not in {"http", "https"}:
                continue
            score = score_link(title, url, config)
            if score < 4:
                continue
            item = {
                "id": "AUTO-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12].upper(),
                "title": title,
                "headline": title[:70],
                "subheadline": "Aggiornamento da fonte pubblica monitorata da F1",
                "category": "notizia immobiliare",
                "area": "Valle di Susa / Piemonte",
                "source_name": str(src.get("name") or "Fonte pubblica"),
                "source_url": url,
                "published_at": datetime.now(ROME).date().isoformat(),
                "summary": title,
                "_score": score,
            }
            if source_hash(item).lower() not in excluded_hashes:
                candidates.append(item)

    candidates.sort(key=lambda x: (-int(x.get("_score") or 0), str(x.get("title") or "")))
    return candidates


def choose_item(config: dict[str, Any]) -> dict[str, Any] | None:
    excluded = queue_source_hashes() | local_selected_hashes()

    featured = [
        dict(row)
        for row in config.get("featured") or []
        if source_hash(row).lower() not in excluded
    ]
    if featured:
        featured.sort(key=lambda x: str(x.get("published_at") or ""), reverse=True)
        return featured[0]

    scanned = scan_sources(config, excluded)
    return scanned[0] if scanned else None


def build_caption(item: dict[str, Any], config: dict[str, Any]) -> str:
    override = str(item.get("caption_override") or "").strip()
    if override:
        return override

    title = clean_title(item.get("title") or "Aggiornamento immobiliare")
    summary = re.sub(r"\s+", " ", str(item.get("summary") or "")).strip()
    source_name = str(item.get("source_name") or "Fonte pubblica").strip()
    source_url = str(item.get("source_url") or "").strip()
    evaluation_url = str(config.get("evaluation_url") or "https://www.agentpricing.com/j.malafronte")
    contact_url = str(config.get("contact_url") or "https://wa.me/393713708294")

    return (
        f"{title.upper()}\n\n"
        f"{summary}\n\n"
        "Per chi vive, vende, compra o cambia casa in Valle di Susa, la notizia conta solo "
        "se viene tradotta in effetti concreti sul territorio. F1 la segnala e la contestualizza "
        "senza trasformare una comunicazione generale in una conclusione sul singolo immobile.\n\n"
        f"Fonte: {source_name}.\n{source_url}\n\n"
        "Non a sensazione. Con i dati.\n\n"
        f"Valutazione immobile: {evaluation_url}\n"
        f"Contatto F1 Immobiliare: {contact_url}"
    )


def build_visual_prompt(item: dict[str, Any]) -> str:
    title = clean_title(item.get("title") or "notizia immobiliare")
    category = clean_title(item.get("category") or "immobiliare")
    area = clean_title(item.get("area") or "Valle di Susa")
    summary = re.sub(r"\s+", " ", str(item.get("summary") or "")).strip()[:420]

    return (
        "Crea un visual fotografico editoriale real-estate per una notizia F1 Immobiliare. "
        f"Argomento: {title}. Categoria: {category}. Area: {area}. Contesto: {summary}. "
        "Trasforma la notizia in una scena fotografica plausibile e concreta, non in un volantino: "
        "architettura e territorio piemontese/Valle di Susa coerenti quando pertinenti, luce naturale, "
        "stile premium ma autentico, composizione verticale social-first 4:5, soggetto o immobile principale "
        "sulla destra e spazio negativo pulito sulla sinistra per il copy successivo. "
        "Non inserire testo, titoli, loghi, CTA, numeri, URL, documenti con testo leggibile o watermark. "
        "Evita look stock, icone, infografiche, card nere, template piatti, mani deformi, prospettive impossibili "
        "e artefatti AI. La fotografia deve essere adatta a una testata locale immobiliare autorevole."
    )


def determine_slot(raw: str, now: datetime) -> str:
    if raw != "auto":
        return raw
    minutes = now.hour * 60 + now.minute
    if 11 * 60 <= minutes <= 13 * 60:
        return "midday"
    if 19 * 60 <= minutes <= 21 * 60:
        return "evening"
    raise SystemExit(f"NOOP_OUTSIDE_WINDOW {now:%H:%M} Europe/Rome")


def prepare_query(slot: str) -> dict[str, Any] | None:
    now = datetime.now(ROME)
    config = load_json(CONFIG_PATH, {})
    item = choose_item(config)
    if not item:
        return None

    digest = source_hash(item)
    news_id = str(item.get("id") or f"NEWS-{digest[:12].upper()}")
    communication_id = (
        f"COMM-NEWS-{now:%Y%m%d}-{slot.upper()}-{digest[:8].upper()}"
    )
    headline = clean_title(item.get("headline") or item.get("title") or "F1 NEWS VALLE DI SUSA")[:70]
    caption = build_caption(item, config)
    prompt = build_visual_prompt(item)

    return {
        "id": communication_id,
        "query": headline,
        "communication": caption,
        "prompt": prompt,
        "caption": caption,
        "client": "F1 Immobiliare",
        "territory": "Valle di Susa",
        "scope": "network",
        "platforms": ["facebook", "instagram"],
        "scheduled_at": now.isoformat(timespec="seconds"),
        "source": "f1-news-valle-susa",
        "news_id": news_id,
        "headline": headline,
        "cta": "SCOPRI COSA CAMBIA",
        "category": str(item.get("category") or "immobiliare"),
        "source_name": str(item.get("source_name") or "Fonte pubblica"),
        "source_url": str(item.get("source_url") or ""),
        "source_hash": digest,
        "source_published_at": str(item.get("published_at") or ""),
        "editorial_slot": slot,
        "publication_status": "QUEUED",
    }


def write_query_file(row: dict[str, Any], destination: Path) -> None:
    payload = {
        "batch": "f1-news-valle-susa-gpt-browser-v2",
        "backend": "chatgpt_browser",
        "strategy": "F1 NEWS VALLE DI SUSA",
        "queries": [row],
    }
    save_json(destination, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["auto", "midday", "evening", "immediate"], default="auto")
    parser.add_argument("--write-query-file", default=str(DEFAULT_QUERY_PATH))
    parser.add_argument("--github-output")
    args = parser.parse_args()

    now = datetime.now(ROME)
    slot = determine_slot(args.slot, now)
    row = prepare_query(slot)
    if row is None:
        print(json.dumps({"status": "NOOP_NO_RELEVANT_NEWS", "slot": slot}, ensure_ascii=False))
        return 0

    destination = Path(args.write_query_file)
    if not destination.is_absolute():
        destination = ROOT / destination
    write_query_file(row, destination)

    output = {
        "status": "PROMPT_READY",
        "slot": slot,
        "query_file": destination.relative_to(ROOT).as_posix(),
        "news_id": row["news_id"],
        "communication_id": row["id"],
        "headline": row["headline"],
        "source_name": row["source_name"],
        "source_url": row["source_url"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    if args.github_output:
        path = Path(args.github_output)
        with path.open("a", encoding="utf-8") as handle:
            for key, value in output.items():
                handle.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
