#!/usr/bin/env python3
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "facebook-groups-data.json"

LOCATIONS = [
    "Avigliana", "Almese", "Buttigliera Alta", "Bussoleno", "Susa", "Rosta",
    "Condove", "Sant'Antonino di Susa", "Alpignano", "Rivoli", "Villar Dora",
    "Caprie", "Novaretto", "Chiusa di San Michele", "Vaie",
    "Sant'Ambrogio di Torino", "San Valeriano", "Villar Focchiardo", "Borgone Susa"
]

KEYWORDS = [
    "immobili", "case", "vendo casa", "cerco casa", "affitti", "mercatino",
    "compro vendo", "sei di", "residenti", "Valle di Susa"
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
GROUP_RE = re.compile(r"https?://(?:www\.)?facebook\.com/groups/[A-Za-z0-9._-]+/?(?:\?[^\"'<>\s]*)?", re.I)
TITLE_RE = re.compile(r'<a[^>]+class="result__a"[^>]*>(.*?)</a>', re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


def load_data():
    if not DATA_FILE.exists():
        return {"updated_at": None, "total": 0, "groups": []}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"updated_at": None, "total": 0, "groups": []}


def clean_group_url(url: str) -> str:
    url = urllib.parse.unquote(url)
    if "uddg=" in url:
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if qs.get("uddg"):
                url = qs["uddg"][0]
        except Exception:
            pass
    m = GROUP_RE.search(url)
    if not m:
        return ""
    clean = m.group(0).split("?")[0].rstrip("/")
    return clean


def fetch_search(query: str) -> str:
    params = urllib.parse.urlencode({"q": query})
    url = "https://html.duckduckgo.com/html/?" + params
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9,en;q=0.6"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def extract_results(html: str, query: str, location: str):
    results = []
    seen = set()

    # Direct Facebook group URLs present in the result HTML.
    for raw in GROUP_RE.findall(html):
        url = clean_group_url(raw)
        if url and url not in seen:
            seen.add(url)
            results.append({"url": url, "name": "", "query": query, "location": location})

    # DuckDuckGo redirect links often contain the real URL in the uddg parameter.
    for href in re.findall(r'href="([^"]+)"', html, flags=re.I):
        url = clean_group_url(href)
        if url and url not in seen:
            seen.add(url)
            results.append({"url": url, "name": "", "query": query, "location": location})

    titles = [TAG_RE.sub("", t).replace("&amp;", "&").replace("&#x27;", "'").strip() for t in TITLE_RE.findall(html)]
    for idx, title in enumerate(titles):
        if idx < len(results) and title:
            results[idx]["name"] = title

    return results


def main():
    data = load_data()
    groups = data.get("groups", [])
    by_url = {g.get("url", "").rstrip("/"): g for g in groups if g.get("url")}
    now = datetime.now(timezone.utc).isoformat()

    for location in LOCATIONS:
        for keyword in KEYWORDS:
            query = f'site:facebook.com/groups "{location}" "{keyword}"'
            try:
                html = fetch_search(query)
                found = extract_results(html, query, location)
            except Exception as exc:
                print(f"WARN {location} / {keyword}: {exc}")
                continue

            for item in found:
                url = item["url"].rstrip("/")
                if url in by_url:
                    existing = by_url[url]
                    existing["last_seen"] = now
                    if item.get("name") and not existing.get("name"):
                        existing["name"] = item["name"]
                    locations = set(existing.get("locations", []))
                    locations.add(location)
                    existing["locations"] = sorted(locations)
                    queries = set(existing.get("queries", []))
                    queries.add(query)
                    existing["queries"] = sorted(queries)
                else:
                    record = {
                        "url": url,
                        "name": item.get("name") or "Gruppo Facebook",
                        "locations": [location],
                        "queries": [query],
                        "first_seen": now,
                        "last_seen": now,
                        "source": "DuckDuckGo public web search",
                        "status": "DA_VERIFICARE"
                    }
                    groups.append(record)
                    by_url[url] = record
                    print("NEW", url)

            time.sleep(1.1)

    groups.sort(key=lambda g: (g.get("last_seen") or "", g.get("url") or ""), reverse=True)
    output = {
        "updated_at": now,
        "total": len(groups),
        "groups": groups
    }
    DATA_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(groups)} groups")


if __name__ == "__main__":
    main()
