#!/usr/bin/env python3
"""Periodic website-source discovery for F1 Content Hub clients.

Reads f1_content_clients.website, discovers sitemap/internal links, stores
deduplicated sources in f1_client_web_sources and updates last_website_sync_at.
It never publishes discovered pages automatically.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
USER_AGENT = "F1-Content-Hub-Website-Sync/1.0"
TIMEOUT = 25
MAX_URLS_PER_CLIENT = int(os.getenv("F1_WEB_MAX_URLS", "80"))
SYNC_HOURS = int(os.getenv("F1_WEB_SYNC_HOURS", "12"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def headers(extra=None):
    h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def api(method: str, table: str, *, params=None, payload=None, prefer=None):
    h = headers({"Prefer": prefer} if prefer else None)
    r = requests.request(method, f"{SUPABASE_URL}/rest/v1/{table}", headers=h, params=params, json=payload, timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(f"{method} {table}: {r.status_code} {r.text[:700]}")
    return r.json() if r.text.strip() else None


def canonical(raw: str) -> str:
    raw = str(raw or "").strip()
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    p = urlparse(raw)
    scheme = "https" if p.scheme in {"http", "https"} else p.scheme
    path = re.sub(r"/+", "/", p.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunparse((scheme, p.netloc.lower(), path, "", p.query, ""))


def same_site(url: str, root: str) -> bool:
    a, b = urlparse(url), urlparse(root)
    return a.netloc.lower().removeprefix("www.") == b.netloc.lower().removeprefix("www.")


def fetch(url: str) -> requests.Response:
    return requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"}, timeout=TIMEOUT, allow_redirects=True)


def sitemap_urls(root: str) -> list[str]:
    queue = [urljoin(root.rstrip("/") + "/", "sitemap.xml")]
    seen_maps, found = set(), []
    while queue and len(found) < MAX_URLS_PER_CLIENT:
        sm = queue.pop(0)
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        try:
            r = fetch(sm)
            if not r.ok:
                continue
            doc = ElementTree.fromstring(r.content)
        except Exception:
            continue
        tag = doc.tag.lower()
        locs = [str(node.text or "").strip() for node in doc.iter() if node.tag.lower().endswith("loc")]
        if tag.endswith("sitemapindex"):
            for loc in locs[:25]:
                if loc and loc not in seen_maps:
                    queue.append(loc)
        else:
            for loc in locs:
                u = canonical(loc)
                if u and same_site(u, root) and u not in found:
                    found.append(u)
                    if len(found) >= MAX_URLS_PER_CLIENT:
                        break
    return found


def homepage_links(root: str) -> list[str]:
    try:
        r = fetch(root)
        if not r.ok:
            return []
        hrefs = re.findall(r"""href\s*=\s*["']([^"'#]+)["']""", r.text, flags=re.I)
    except Exception:
        return []
    out = [canonical(root)]
    for href in hrefs:
        u = canonical(urljoin(root, html.unescape(href)))
        if u and same_site(u, root) and u not in out:
            out.append(u)
        if len(out) >= MAX_URLS_PER_CLIENT:
            break
    return out


def meta_value(text: str, name: str) -> str:
    patterns = [
        rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']',
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def classify(url: str, title: str) -> str:
    value = f"{url} {title}".lower()
    tests = [
        ("IMMOBILE", ("immobil", "annunc", "property", "casa")),
        ("EVENTO", ("event", "matrimon", "cerimoni", "festa")),
        ("ARTICOLO", ("blog", "news", "articol", "magazine")),
        ("PRODOTTO", ("product", "prodot", "shop", "catalog")),
        ("SERVIZIO", ("serviz", "service")),
        ("CONTATTO", ("contatt", "contact")),
    ]
    for kind, needles in tests:
        if any(n in value for n in needles):
            return kind
    return "PAGE"


def inspect_page(url: str) -> dict:
    try:
        r = fetch(url)
        if not r.ok:
            return {"url": url, "canonical_url": url, "page_type": "PAGE", "title": "", "description": "", "image_url": None, "content_hash": None}
        text = r.text[:1_500_000]
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
        title = re.sub(r"\s+", " ", html.unescape(title_match.group(1))).strip() if title_match else ""
        desc = meta_value(text, "description")
        image = meta_value(text, "og:image") or None
        canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', text, flags=re.I)
        canon = canonical(urljoin(url, canonical_match.group(1))) if canonical_match else canonical(url)
        digest = hashlib.sha256(re.sub(r"\s+", " ", text).encode("utf-8", "ignore")).hexdigest()
        return {
            "url": canonical(url),
            "canonical_url": canon or canonical(url),
            "page_type": classify(url, title),
            "title": title[:500],
            "description": desc[:2000],
            "image_url": image,
            "content_hash": digest,
        }
    except Exception:
        return {"url": canonical(url), "canonical_url": canonical(url), "page_type": "PAGE", "title": "", "description": "", "image_url": None, "content_hash": None}


def due(last_sync: str | None) -> bool:
    if not last_sync:
        return True
    try:
        dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - dt >= timedelta(hours=SYNC_HOURS)
    except Exception:
        return True


def main() -> int:
    if not SUPABASE_URL or not SERVICE_KEY:
        print("WEBSITE_SYNC_DISABLED: configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        return 0

    clients = api("GET", "f1_content_clients", params={"select": "id,owner_id,name,slug,website,last_website_sync_at", "status": "eq.ATTIVO", "order": "name.asc"}) or []
    report = []
    for client in clients:
        website = canonical(client.get("website"))
        if not website:
            report.append({"client": client.get("slug"), "status": "WEBSITE_MANCANTE"})
            continue
        if not due(client.get("last_website_sync_at")):
            report.append({"client": client.get("slug"), "status": "NON_DOVUTO"})
            continue

        urls = sitemap_urls(website)
        if not urls:
            urls = homepage_links(website)
        if website not in urls:
            urls.insert(0, website)
        urls = urls[:MAX_URLS_PER_CLIENT]

        saved = 0
        changed = 0
        for url in urls:
            page = inspect_page(url)
            existing = api(
                "GET", "f1_client_web_sources",
                params={
                    "select": "id,content_hash",
                    "owner_id": f"eq.{client['owner_id']}",
                    "client_id": f"eq.{client['id']}",
                    "canonical_url": f"eq.{page['canonical_url']}",
                    "limit": "1",
                },
            ) or []
            if existing and existing[0].get("content_hash") != page.get("content_hash"):
                changed += 1
            payload = {
                "owner_id": client["owner_id"],
                "client_id": client["id"],
                **page,
                "last_checked_at": now_iso(),
                "active": True,
            }
            api(
                "POST", "f1_client_web_sources",
                params={"on_conflict": "owner_id,client_id,canonical_url"},
                payload=payload,
                prefer="resolution=merge-duplicates,return=minimal",
            )
            saved += 1

        api("PATCH", "f1_content_clients", params={"id": f"eq.{client['id']}"}, payload={"last_website_sync_at": now_iso()})
        report.append({"client": client.get("slug"), "status": "OK", "urls": saved, "changed": changed})

    print(json.dumps({"at": now_iso(), "clients": report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
