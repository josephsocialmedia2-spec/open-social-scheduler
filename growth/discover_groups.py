from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "growth" / "config.json"
GROUPS_PATH = ROOT / "growth" / "groups.json"
SIGNALS_PATH = ROOT / "growth" / "signals.json"
NEW_BATCH_PATH = ROOT / "growth" / "new_batch.json"

GROUP_RE = re.compile(r"facebook\.com/groups/([^/?#]+)", re.I)
POST_URL_RE = re.compile(r"/(posts|permalink)/", re.I)
GENERIC_TITLES = {"popular groups facebook", "facebook", "groups facebook", "gruppi facebook"}
POST_PREFIXES = (
    "cerco urgentemente ", "cerco casa ", "cerco appartamento ", "cerco garage ",
    "renting apartment ", "apartment for rent ", "house for rent ",
    "avigliana apartment for rent ", "vi aspettiamo ", "buongiorno ",
    "ciao a tutti ", "vendo casa ", "vendo appartamento ", "affitto appartamento ",
)
PROPERTY_WORDS = (
    "immobile", "casa", "appartamento", "vendita", "vendo", "affitto", "affitt",
    "valutazione", "garage", "box", "magazzino", "terreno", "capannone",
    "agenzia", "immobiliare", "proprietario", "proprietaria"
)
SPECIAL_ALIASES = {
    "valle di susa": ["valle di susa", "val di susa", "valsusa"],
    "sant antonino di susa": ["sant antonino di susa", "sant antonino"],
    "borgone susa": ["borgone susa", "borgone"],
    "chiusa di san michele": ["chiusa di san michele", "chiusa san michele"],
    "torino ovest": ["torino ovest", "torino"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_title(raw: str) -> str:
    title = (raw or "").strip()
    title = re.sub(r"\s*[-|]\s*Facebook\s*$", "", title, flags=re.I).strip()
    if " | " in title:
        left, right = title.split(" | ", 1)
        if 3 <= len(left.strip()) <= 90 and len(right.strip()) >= 12:
            title = left.strip()
    return title[:180]


def looks_like_post(raw_title: str, source_url: str) -> bool:
    if POST_URL_RE.search(source_url or ""):
        return True
    n = normalize(raw_title)
    if any(n.startswith(normalize(prefix)) for prefix in POST_PREFIXES):
        return True
    if len(raw_title or "") > 115 and " | " not in (raw_title or ""):
        return True
    return False


def has_property_signal(title: str, snippet: str) -> bool:
    text = normalize(f"{title} {snippet}")
    return any(word in text for word in PROPERTY_WORDS)


def territory_aliases(territory: str) -> list[str]:
    key = normalize(territory)
    return SPECIAL_ALIASES.get(key, [key])


def territory_matches(item: dict, territory: str) -> bool:
    title = normalize(item.get("title", ""))
    url = normalize(item.get("url", ""))
    if title in GENERIC_TITLES:
        return False
    haystack = f"{title} {url}"
    return any(alias and alias in haystack for alias in territory_aliases(territory))


def canonical_group_url(url: str) -> str | None:
    if not url:
        return None
    m = GROUP_RE.search(url)
    if not m:
        return None
    slug = m.group(1).strip()
    if not slug or slug.lower() in {"feed", "discover", "groups"}:
        return None
    return f"https://www.facebook.com/groups/{slug}/"


def short_id(prefix: str, value: str) -> str:
    return prefix + hashlib.sha1(value.encode("utf-8")).hexdigest()[:10].upper()


def make_queries(config: dict) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for brand, bcfg in config.get("brands", {}).items():
        for territory in bcfg.get("territories", []):
            for topic in bcfg.get("topics", []):
                rows.append((brand, territory, f'site:facebook.com/groups "{territory}" "{topic}"'))
    return rows


def search_public_web(query: str, max_results: int = 8) -> list[dict]:
    try:
        from ddgs import DDGS
    except Exception as exc:
        raise RuntimeError("Dipendenza ddgs non installata") from exc

    results = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results) or []:
            href = item.get("href") or item.get("url") or ""
            group_url = canonical_group_url(href)
            if not group_url:
                continue
            raw_title = (item.get("title") or "Gruppo Facebook").strip()
            snippet = (item.get("body") or item.get("snippet") or "").strip()
            results.append({
                "url": group_url,
                "source_url": href,
                "raw_title": raw_title,
                "title": clean_title(raw_title),
                "snippet": snippet,
                "kind": "POST" if looks_like_post(raw_title, href) else "GROUP",
            })
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    config = load_json(CONFIG_PATH, {})
    data = load_json(GROUPS_PATH, {"version": 2, "groups": []})
    signals = load_json(SIGNALS_PATH, {"version": 1, "signals": []})
    existing = {canonical_group_url(g.get("url", "")): g for g in data.get("groups", [])}
    existing_signals = {s.get("id") for s in signals.get("signals", [])}
    limit = args.limit or int(config.get("daily_candidate_limit", 40))
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    added: list[dict] = []
    added_signals: list[dict] = []

    for brand, territory, query in make_queries(config):
        if len(added) >= limit:
            break
        try:
            found = search_public_web(query)
        except Exception as exc:
            print(f"WARN search failed: {query}: {exc}")
            continue

        for item in found:
            url = item["url"]
            if item["kind"] == "POST":
                if has_property_signal(item["raw_title"], item["snippet"]):
                    sid = short_id("FBS-", item["source_url"] or f"{url}|{item['raw_title']}")
                    if sid not in existing_signals:
                        signal = {
                            "id": sid,
                            "brand": brand,
                            "territory": territory,
                            "group_url": url,
                            "source_url": item["source_url"],
                            "title": item["raw_title"][:220],
                            "snippet": item["snippet"][:700],
                            "source_query": query,
                            "status": "NEW",
                            "discovered_at": now_iso(),
                        }
                        signals.setdefault("signals", []).append(signal)
                        existing_signals.add(sid)
                        added_signals.append(signal)
                continue

            if url in existing:
                continue
            if not item["title"] or not territory_matches(item, territory):
                continue
            record = {
                "id": short_id("FBG-", url),
                "brand": brand,
                "territory": territory,
                "name": item["title"],
                "url": url,
                "source_query": query,
                "snippet": item["snippet"][:500],
                "status": "PENDING_APPROVAL",
                "batch_id": batch_id,
                "discovered_at": now_iso(),
                "approved_at": None,
                "join_requested_at": None,
                "member_at": None,
                "last_post_at": None,
                "notes": ""
            }
            data.setdefault("groups", []).append(record)
            existing[url] = record
            added.append(record)
            if len(added) >= limit:
                break

    data["updated_at"] = now_iso()
    data["last_batch_id"] = batch_id if added else data.get("last_batch_id")
    signals["updated_at"] = now_iso()
    save_json(GROUPS_PATH, data)
    save_json(SIGNALS_PATH, signals)
    save_json(NEW_BATCH_PATH, {
        "batch_id": batch_id,
        "created_at": now_iso(),
        "groups": added,
        "signals": added_signals,
    })
    print(json.dumps({
        "batch_id": batch_id,
        "new_groups": len(added),
        "new_signals": len(added_signals),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
