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
NEW_BATCH_PATH = ROOT / "growth" / "new_batch.json"

GROUP_RE = re.compile(r"facebook\.com/groups/([^/?#]+)", re.I)
GENERIC_TITLES = {"popular groups facebook", "facebook", "groups facebook", "gruppi facebook"}
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


def territory_aliases(territory: str) -> list[str]:
    key = normalize(territory)
    return SPECIAL_ALIASES.get(key, [key])


def territory_matches(item: dict, territory: str) -> bool:
    """Accept only results whose visible group title or URL really names the territory.

    Search-engine snippets often echo query words from unrelated page fragments, so
    snippets alone are deliberately not enough to classify a group into a territory.
    """
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


def group_id(url: str) -> str:
    return "FBG-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:10].upper()


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
            url = canonical_group_url(href)
            if not url:
                continue
            results.append({
                "url": url,
                "title": (item.get("title") or "Gruppo Facebook").strip(),
                "snippet": (item.get("body") or item.get("snippet") or "").strip(),
            })
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    config = load_json(CONFIG_PATH, {})
    data = load_json(GROUPS_PATH, {"version": 2, "groups": []})
    existing = {canonical_group_url(g.get("url", "")): g for g in data.get("groups", [])}
    limit = args.limit or int(config.get("daily_candidate_limit", 40))
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    added: list[dict] = []

    for brand, territory, query in make_queries(config):
        if len(added) >= limit:
            break
        try:
            found = search_public_web(query)
        except Exception as exc:
            print(f"WARN search failed: {query}: {exc}")
            continue

        for item in found:
            url = canonical_group_url(item["url"])
            if not url or url in existing:
                continue
            if not territory_matches(item, territory):
                continue
            record = {
                "id": group_id(url),
                "brand": brand,
                "territory": territory,
                "name": item["title"][:180],
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
    save_json(GROUPS_PATH, data)
    save_json(NEW_BATCH_PATH, {"batch_id": batch_id, "created_at": now_iso(), "groups": added})
    print(json.dumps({"batch_id": batch_id, "new_groups": len(added)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
