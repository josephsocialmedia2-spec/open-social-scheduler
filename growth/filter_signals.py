from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROUPS_PATH = ROOT / "growth" / "groups.json"
SIGNALS_PATH = ROOT / "growth" / "signals.json"
NEW_BATCH_PATH = ROOT / "growth" / "new_batch.json"

POST_RE = re.compile(r"/(?:posts|permalink)/|permalink\.php|story\.php", re.I)
PROPERTY = (
    "casa", "appartamento", "immobile", "garage", "box", "magazzino", "terreno",
    "capannone", "villa", "rustico", "baita", "bilocale", "trilocale", "quadrilocale",
)
INTENT = (
    "cerco", "cerca", "cerchiamo", "vendo", "vendesi", "vendere", "vendita",
    "affitto", "affittasi", "affittare", "valutazione", "quanto vale", "stima",
)
NON_PROPERTY_TITLE = (
    "gelatiera", "scarpe", "bicicletta", "moto ", "automobile", "auto ", "divano",
    "armadio", "arredamento", "elettrodomest", "telefono", "smartphone", "vestiti",
)
FOREIGN_OR_WRONG_CONTEXT = (
    "milano", "porta susa", "argonne", "citta studi", "salerno", "sicilia", "l aquila",
    "aprilia", "puebla", "nuevo eden", "chapultepec", "new york", "nyc",
)
MAX_AGE_DAYS = 60

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    "gen": 1, "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "mag": 5,
    "maggio": 5, "giu": 6, "giugno": 6, "lug": 7, "luglio": 7, "ago": 8,
    "agosto": 8, "set": 9, "settembre": 9, "ott": 10, "ottobre": 10,
    "novembre": 11, "dic": 12, "dicembre": 12,
}


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def group_key(url: str) -> str:
    m = re.search(r"facebook\.com/groups/([^/?#]+)", url or "", re.I)
    return m.group(1).lower() if m else ""


def parse_date(text: str):
    raw = text or ""
    n = norm(raw)
    now = datetime.now(timezone.utc)

    m = re.search(r"\b(\d{1,3})\s*(day|days|giorno|giorni)\s*(ago|fa)\b", n)
    if m:
        return now - timedelta(days=int(m.group(1)))
    m = re.search(r"\b(\d{1,3})\s*(week|weeks|settimana|settimane)\s*(ago|fa)\b", n)
    if m:
        return now - timedelta(days=7 * int(m.group(1)))
    m = re.search(r"\b(\d{1,3})\s*(month|months|mese|mesi)\s*(ago|fa)\b", n)
    if m:
        return now - timedelta(days=30 * int(m.group(1)))
    if re.search(r"\b[1-9]\d*y\b", n) or re.search(r"\b[1-9]\d*\s*(year|years|anno|anni)\s*(ago|fa)\b", n):
        return now - timedelta(days=366)

    m = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})\b",
        raw, re.I,
    )
    if m:
        month = MONTHS.get(norm(m.group(1)))
        if month:
            return datetime(int(m.group(3)), month, int(m.group(2)), tzinfo=timezone.utc)

    m = re.search(
        r"\b(\d{1,2})\s+(gen(?:naio)?|feb(?:braio)?|mar(?:zo)?|apr(?:ile)?|mag(?:gio)?|giu(?:gno)?|lug(?:lio)?|ago(?:sto)?|set(?:tembre)?|ott(?:obre)?|nov(?:embre)?|dic(?:embre)?)\s+(\d{4})\b",
        raw, re.I,
    )
    if m:
        month = MONTHS.get(norm(m.group(2)))
        if month:
            return datetime(int(m.group(3)), month, int(m.group(1)), tzinfo=timezone.utc)
    return None


def is_recent(signal: dict) -> bool:
    dt = parse_date(f"{signal.get('title', '')} {signal.get('snippet', '')}")
    if not dt:
        return True
    return (datetime.now(timezone.utc) - dt).days <= MAX_AGE_DAYS


def group_looks_local(group: dict, signal: dict) -> bool:
    territory = norm(signal.get("territory", ""))
    text = norm(f"{group.get('territory', '')} {group.get('name', '')} {group.get('snippet', '')}")
    if territory and territory in text:
        return True
    if "valle di susa" in text or "val di susa" in text or "valsusa" in text:
        return True
    return False


def valid_signal(signal: dict, groups: dict[str, dict]) -> bool:
    source = signal.get("source_url", "")
    if not POST_RE.search(source):
        return False

    g = groups.get(group_key(signal.get("group_url") or source))
    if not g or g.get("status") == "REJECTED":
        return False
    if not group_looks_local(g, signal):
        return False
    if not is_recent(signal):
        return False

    title = norm(signal.get("title", ""))
    snippet = norm(signal.get("snippet", ""))
    text = f"{title} {snippet}"

    if any(x in title for x in NON_PROPERTY_TITLE) and not any(x in title for x in PROPERTY):
        return False
    if any(x in text for x in FOREIGN_OR_WRONG_CONTEXT):
        return False
    if "popular groups" in snippet and "find communities for you" in snippet and not any(x in title for x in INTENT):
        return False

    has_property = any(x in text for x in PROPERTY)
    has_intent = any(x in text for x in INTENT)
    return has_property and has_intent


def main():
    groups_data = load(GROUPS_PATH, {"groups": []})
    signals_data = load(SIGNALS_PATH, {"version": 1, "signals": []})
    batch = load(NEW_BATCH_PATH, {})

    groups = {group_key(g.get("url", "")): g for g in groups_data.get("groups", []) if group_key(g.get("url", ""))}
    seen = set()
    kept = []
    removed = []

    for s in signals_data.get("signals", []):
        sid = s.get("id") or ""
        if not sid or sid in seen or not valid_signal(s, groups):
            removed.append(s)
            continue
        seen.add(sid)
        kept.append(s)

    signals_data["signals"] = kept
    signals_data["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    save(SIGNALS_PATH, signals_data)

    if batch:
        valid_ids = {s.get("id") for s in kept}
        batch["signals"] = [s for s in batch.get("signals", []) if s.get("id") in valid_ids]
        batch["removed_bad_signals"] = len(removed)
        save(NEW_BATCH_PATH, batch)

    print(json.dumps({"kept": len(kept), "removed": len(removed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
