#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import textwrap
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "publisher" / "news" / "f1_valle_susa_sources.json"
STATE_PATH = ROOT / "publisher" / "news" / "f1_valle_susa_news_state.json"
QUEUE_PATH = ROOT / "publisher" / "final_content_queue.json"
CLIENT_PATH = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
ASSET_DIR = ROOT / "publisher" / "final_assets" / "news_valle_susa"
ROME = ZoneInfo("Europe/Rome")
UA = "F1ValleSusaNewsRadar/1.0 (+https://www.f1immobiliare.com)"

W, H = 1080, 1350
DARK = "#070907"
DARK2 = "#111814"
WHITE = "#F7F7F4"
GREEN = "#92C205"
MUTED = "#C7CDC8"

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
            text = re.sub(r"\s+", " ", " ".join(self._text)).strip()
            if text:
                self.links.append((self._href, text))
            self._href = ""
            self._text = []

def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def font(size: int, bold: bool = False):
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()

def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = word if not current else current + " " + word
        if draw.textbbox((0,0), test, font=fnt)[2] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def draw_logo(draw: ImageDraw.ImageDraw, client: dict[str, Any], x: int, y: int, width: int = 245) -> None:
    vectors = client.get("brand", {}).get("logo_vectors") or {}
    viewbox = vectors.get("viewbox") or [0,0,500,500]
    scale = width / max(1, int(viewbox[2]))
    def transform(shape):
        return [(x + round(px*scale), y + round(py*scale)) for px,py in shape]
    if vectors.get("green") or vectors.get("white"):
        for shape in vectors.get("green") or []:
            draw.polygon(transform(shape), fill=GREEN)
        for shape in vectors.get("white") or []:
            draw.polygon(transform(shape), fill=WHITE)
        draw.text((x, y + 214), "IMMOBILIARE", font=font(24, True), fill=WHITE)
    else:
        draw.text((x,y), "F1", font=font(80, True), fill=GREEN)
        draw.text((x,y+86), "IMMOBILIARE", font=font(24, True), fill=WHITE)

def render_news_card(job_id: str, item: dict[str, Any], client: dict[str, Any]) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / f"{job_id}.png"
    image = Image.new("RGB", (W,H), DARK)
    draw = ImageDraw.Draw(image)

    # Editorial grid / topographic motif: deterministic and source-neutral.
    draw.rectangle((0,0,W,185), fill=DARK2)
    for i in range(7):
        y = 630 + i*78
        draw.arc((-120, y-220, 1180, y+330), 200, 340, fill=(35,50,39), width=3)
    draw.rectangle((0,1130,W,H), fill=DARK2)
    draw.rectangle((0,0,18,H), fill=GREEN)

    draw_logo(draw, client, 60, 20)
    draw.text((60,245), "F1 NEWS · VALLE DI SUSA", font=font(34, True), fill=GREEN)

    category = str(item.get("category") or "immobiliare").upper()
    draw.rounded_rectangle((60,310, 60+min(500, 35+22*len(category)), 370), radius=18, fill=GREEN)
    draw.text((82,326), category, font=font(24, True), fill=DARK)

    headline = str(item.get("headline") or item.get("title") or "NOTIZIA IMMOBILIARE").upper()
    hf = font(70, True)
    y = 430
    for line in wrap(draw, headline, hf, 900)[:4]:
        draw.text((60,y), line, font=hf, fill=WHITE)
        y += 86

    sub = str(item.get("subheadline") or item.get("summary") or "")
    sf = font(34, False)
    y += 28
    for line in wrap(draw, sub, sf, 860)[:5]:
        draw.text((60,y), line, font=sf, fill=MUTED)
        y += 47

    source = str(item.get("source_name") or "Fonte pubblica")
    date = str(item.get("published_at") or datetime.now(ROME).date().isoformat())
    draw.text((60,1165), f"FONTE: {source}", font=font(25, True), fill=WHITE)
    draw.text((60,1207), f"AGGIORNAMENTO: {date}", font=font(23, False), fill=MUTED)
    draw.text((60,1270), "NON A SENSAZIONE. CON I DATI.", font=font(28, True), fill=GREEN)
    draw.text((735,1270), "f1immobiliare.com", font=font(22, False), fill=WHITE)

    image.save(path, "PNG", optimize=True)
    return path

def clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" -|·")
    return value[:180]

def source_hash(item: dict[str, Any]) -> str:
    raw = "|".join([
        str(item.get("source_url") or ""),
        str(item.get("title") or ""),
        str(item.get("published_at") or ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def seen_hashes(state: dict[str, Any]) -> set[str]:
    return {str(x.get("hash") or "") for x in state.get("seen") or []}

def score_link(text: str, url: str, config: dict[str, Any]) -> int:
    hay = (text + " " + url).casefold()
    score = sum(4 for k in config.get("keywords") or [] if k.casefold() in hay)
    score += sum(6 for t in config.get("towns") or [] if t.casefold() in hay)
    if any(x in hay for x in ("2026","settembre","september")):
        score += 2
    return score

def scan_sources(config: dict[str, Any], seen: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for src in config.get("sources") or []:
        try:
            r = requests.get(src["url"], headers={"User-Agent":UA}, timeout=20)
            r.raise_for_status()
            parser = LinkParser()
            parser.feed(r.text)
        except Exception:
            continue
        for href, text in parser.links:
            title = clean_title(text)
            if len(title) < 20:
                continue
            url = urljoin(src["url"], href)
            if urlparse(url).scheme not in {"http","https"}:
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
                "source_name": src["name"],
                "source_url": url,
                "published_at": datetime.now(ROME).date().isoformat(),
                "summary": title,
                "_score": score,
            }
            if source_hash(item) not in seen:
                candidates.append(item)
    candidates.sort(key=lambda x: (-int(x.get("_score") or 0), x["title"]))
    return candidates

def choose_item(config: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    seen = seen_hashes(state)
    featured = []
    for row in config.get("featured") or []:
        if source_hash(row) not in seen:
            featured.append(dict(row))
    if featured:
        featured.sort(key=lambda x: str(x.get("published_at") or ""), reverse=True)
        return featured[0]
    scanned = scan_sources(config, seen)
    return scanned[0] if scanned else None

def build_caption(item: dict[str, Any], config: dict[str, Any]) -> str:
    override = str(item.get("caption_override") or "").strip()
    if override:
        return override
    title = str(item.get("title") or "Aggiornamento immobiliare")
    summary = str(item.get("summary") or "").strip()
    return (
        f"{title.upper()}\n\n"
        f"{summary}\n\n"
        "F1 segnala questo aggiornamento perché riguarda casa, immobili o pianificazione del territorio. "
        "Prima di attribuirgli effetti su un immobile specifico occorre verificare l'atto e il Comune interessato.\n\n"
        f"Fonte: {item.get('source_name')}.\n{item.get('source_url')}\n\n"
        "Non a sensazione. Con i dati.\n\n"
        f"Valutazione immobile: {config['evaluation_url']}\n"
        f"Contatto F1 Immobiliare: {config['contact_url']}"
    )

def determine_slot(raw: str, now: datetime) -> str:
    if raw != "auto":
        return raw
    hm = now.hour * 60 + now.minute
    if 11*60 <= hm <= 13*60:
        return "midday"
    if 19*60 <= hm <= 21*60:
        return "evening"
    raise SystemExit(f"NOOP_OUTSIDE_WINDOW {now:%H:%M} Europe/Rome")

def already_has_slot(queue: dict[str, Any], day: str, slot: str) -> bool:
    prefix = f"F1-NEWS-{day.replace('-','')}-"
    return any(
        str(j.get("id") or "").startswith(prefix)
        and str(j.get("editorial_slot") or "") == slot
        and str(j.get("status") or "") not in {"ERROR","HOLD"}
        for j in queue.get("jobs") or []
    )

def create_job(slot: str, force: bool = False) -> tuple[dict[str, Any] | None, str]:
    now = datetime.now(ROME)
    config = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {"version":1,"seen":[],"last_runs":[]})
    queue = load_json(QUEUE_PATH, {"version":3,"pipeline":"f1-final-assets","brand":"F1 Immobiliare","asset_policy":"immutable-final-layout","jobs":[]})
    client = load_json(CLIENT_PATH, {})
    day = now.date().isoformat()

    if slot != "immediate" and already_has_slot(queue, day, slot) and not force:
        return None, "NOOP_ALREADY_CREATED"

    item = choose_item(config, state)
    if not item:
        return None, "NOOP_NO_RELEVANT_NEWS"

    digest = source_hash(item)
    tag = slot.upper() if slot != "immediate" else "NOW"
    job_id = f"F1-NEWS-{now:%Y%m%d-%H%M}-{tag}-{digest[:8].upper()}"
    if any(str(j.get("id") or "") == job_id for j in queue.get("jobs") or []):
        return None, "NOOP_DUPLICATE_JOB"

    asset = render_news_card(job_id, item, client)
    caption = build_caption(item, config)
    comm_id = f"COMM-NEWS-{now:%Y%m%d-%H%M%S}-{digest[:8]}"
    job = {
        "id": job_id,
        "communication_id": comm_id,
        "title": item.get("title"),
        "objective": "LOCAL NEWS / AUTHORITY",
        "pillar": "F1 News Valle di Susa",
        "source_name": item.get("source_name"),
        "source_url": item.get("source_url"),
        "source_hash": digest,
        "source_published_at": item.get("published_at"),
        "category": item.get("category"),
        "caption": caption,
        "format": "photo",
        "assets": [asset.relative_to(ROOT).as_posix()],
        "platforms": ["facebook","instagram"],
        "scope": "network",
        "territory": "Valle di Susa",
        "editorial_slot": slot,
        "scheduled_at": now.isoformat(timespec="seconds"),
        "status": "READY",
        "approval_required": False,
        "manual_approval_required": False,
        "autonomous_publish": True,
        "created_by": "f1-valle-susa-news-radar",
        "created_at": now.isoformat(timespec="seconds"),
    }
    queue.setdefault("jobs", []).append(job)
    queue["updated_at"] = now.isoformat(timespec="seconds")
    save_json(QUEUE_PATH, queue)

    state.setdefault("seen", []).append({
        "hash": digest,
        "source_url": item.get("source_url"),
        "title": item.get("title"),
        "job_id": job_id,
        "queued_at": now.isoformat(timespec="seconds"),
    })
    state["seen"] = state["seen"][-500:]
    state.setdefault("last_runs", []).append({
        "at": now.isoformat(timespec="seconds"),
        "slot": slot,
        "job_id": job_id,
        "source_url": item.get("source_url"),
    })
    state["last_runs"] = state["last_runs"][-60:]
    save_json(STATE_PATH, state)
    return job, "CREATED"

def recover_existing_job(job_id: str) -> tuple[dict[str, Any], str]:
    config = load_json(CONFIG_PATH, {})
    queue = load_json(QUEUE_PATH, {})
    client = load_json(CLIENT_PATH, {})
    job = next((x for x in queue.get("jobs") or [] if str(x.get("id") or "") == job_id), None)
    if job is None:
        raise SystemExit(f"RECOVERY_JOB_NOT_FOUND {job_id}")

    digest = str(job.get("source_hash") or "")
    item = next(
        (dict(x) for x in (config.get("featured") or []) if source_hash(x) == digest),
        None,
    )
    if item is None:
        item = {
            "title": job.get("title") or "F1 News Valle di Susa",
            "headline": job.get("title") or "F1 NEWS VALLE DI SUSA",
            "subheadline": "Aggiornamento immobiliare da fonte pubblica",
            "category": job.get("category") or "notizia immobiliare",
            "source_name": job.get("source_name") or "Fonte pubblica",
            "source_url": job.get("source_url") or "",
            "published_at": job.get("source_published_at") or datetime.now(ROME).date().isoformat(),
            "summary": str(job.get("title") or ""),
        }

    asset = render_news_card(job_id, item, client)
    job["assets"] = [asset.relative_to(ROOT).as_posix()]
    # Preserve provider history and publication state. If a previous attempt
    # failed, publisher recovery decides which service can be retried.
    save_json(QUEUE_PATH, queue)
    return job, "RECOVERED_EXISTING"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=["auto","midday","evening","immediate"], default="auto")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--recover-job-id", help="Recreate the deterministic asset for an existing queue job without creating a duplicate")
    ap.add_argument("--github-output")
    args = ap.parse_args()
    now = datetime.now(ROME)
    if args.recover_job_id:
        slot = "recovery"
        job, status = recover_existing_job(args.recover_job_id)
    else:
        slot = determine_slot(args.slot, now)
        job, status = create_job(slot, force=args.force)
    payload = {"status":status, "slot":slot, "job":job}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.github_output:
        p = Path(args.github_output)
        with p.open("a", encoding="utf-8") as f:
            f.write(f"status={status}\n")
            f.write(f"job_id={job['id'] if job else ''}\n")
            f.write(f"asset={(job.get('assets') or [''])[0] if job else ''}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
