#!/usr/bin/env python3
"""Turn prepared jobs into simple, research-informed daily content candidates.

The output is intentionally conservative: three candidates per brand per day,
manual publication only, no copying of third-party creatives. Public research
signals influence the topic and the source links are stored on each job.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
RESEARCH = ROOT / "publisher" / "research" / "latest.json"
PHONE = "371 370 8294"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_voice(text: str) -> str:
    text = re.sub(r"https?://\S+", "", str(text or ""))
    text = re.sub(r"#[\wÀ-ÿ]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def local_tag(territory: str) -> str:
    value = re.sub(r"[^A-Za-zÀ-ÿ0-9]+", "", territory or "")
    return "#" + value if value else "#ValleDiSusa"


def f1_hashtags(territory: str) -> list[str]:
    return [
        "#F1Immobiliare", "#ValleDiSusa", local_tag(territory), "#VendereCasa",
        "#CasaInVendita", "#ValutazioneImmobiliare", "#MercatoImmobiliare",
        "#ImmobiliareTorino", "#TorinoOvest", "#PrimaIDati",
    ]


def rmp_hashtags(territory: str) -> list[str]:
    return [
        "#RealMediaPro", "#Shopify", "#Ecommerce", "#SitiWeb", "#ConversionRate",
        "#DigitalMarketing", "#MarketingDigitale", local_tag(territory), "#Torino",
    ]


def ensure_hashtags(caption: str, tags: list[str]) -> str:
    base = re.sub(r"(?:\n\s*)?(?:#[\wÀ-ÿ]+\s*)+$", "", str(caption or "").strip()).strip()
    return base + "\n\n" + " ".join(dict.fromkeys(tags))


def research_for(cid: str) -> list[dict[str, str]]:
    if not RESEARCH.exists():
        return []
    try:
        data = load(RESEARCH)
        rows = data.get("brands", {}).get(cid, {}).get("signals", [])
        return [x for x in rows if isinstance(x, dict)][:5]
    except Exception:
        return []


def set_slides(job: dict[str, Any], slides: list[str]) -> None:
    job["slides"] = slides
    if str(job.get("format") or "") != "carousel":
        return
    media = job.get("media")
    if isinstance(media, list) and media:
        parent = str(Path(str(media[0])).parent).replace("\\", "/")
        job["media"] = [f"{parent}/slide-{i:02d}.jpg" for i in range(1, len(slides) + 1)]


def rmp_live_topic(signals: list[dict[str, str]]) -> tuple[str, str]:
    text = " ".join(str(x.get("title") or "") for x in signals).lower()
    checks = [
        (("speed", "veloc"), "VELOCITÀ DEL SITO", "IL TUO SITO È TROPPO LENTO?"),
        (("review", "recension", "trust", "fiducia"), "FIDUCIA E RECENSIONI", "IL TUO E-COMMERCE ISPIRA FIDUCIA?"),
        (("conversion", "cro", "convert"), "CONVERSIONE", "IL TUO SITO CONVERTE DAVVERO?"),
        (("agentic", "agent", " intelligenza artificiale", " ai "), "AI COMMERCE", "IL TUO E-COMMERCE È PRONTO PER L'AI?"),
        (("product page", "pagina prodotto", "prodotto"), "PAGINA PRODOTTO", "LA TUA PAGINA PRODOTTO FA COMPRARE?"),
    ]
    for keys, topic, hook in checks:
        if any(k in text for k in keys):
            return topic, hook
    return "SHOPIFY / ECOMMERCE", "IL TUO SITO PORTA CLIENTI?"


def apply_simple_plan(job: dict[str, Any], signals: list[dict[str, str]]) -> None:
    cid = str(job.get("client_id") or "")
    category = str(job.get("category") or "")
    territory = str(job.get("territory") or "").strip() or "Valle di Susa"

    if cid == "f1-immobiliare":
        if category == "data":
            title = f"QUANTO VALE OGGI UNA CASA A {territory.upper()}?"
            set_slides(job, [
                title,
                "IL PREZZO MEDIO NON BASTA",
                "CONTA LA MICROZONA",
                "CONTA LO STATO DELLA CASA",
                "CONTA LA CONCORRENZA ATTIVA",
                "CONTA LA DOMANDA REALE",
                f"F1 IMMOBILIARE | {PHONE}",
            ])
        elif category == "error":
            title = "IL PREZZO SBAGLIATO BLOCCA LA VENDITA?"
            set_slides(job, [
                title,
                "TROPPO ALTO = MENO CONTATTI",
                "TROPPO BASSO = VALORE PERSO",
                "I PRIMI GIORNI CONTANO",
                "CONFRONTA IMMOBILI REALMENTE CONCORRENTI",
                "PRIMA I DATI. POI LA STRATEGIA.",
                f"F1 IMMOBILIARE | {PHONE}",
            ])
        else:
            title = "PRIMA DI VENDERE CASA: 5 CONTROLLI"
            set_slides(job, [
                title,
                "1 · VALORE E MICROZONA",
                "2 · CONCORRENZA ATTIVA",
                "3 · DOCUMENTAZIONE",
                "4 · PRESENTAZIONE DELL'IMMOBILE",
                "5 · STRATEGIA DI USCITA",
                f"F1 IMMOBILIARE | {PHONE}",
            ])
        job["title"] = title
        job["visual_rule"] = "residential_property_only"
    else:
        topic, live_hook = rmp_live_topic(signals)
        job["research_topic"] = topic
        if category == "attract":
            title = live_hook
            set_slides(job, [
                title,
                "HOME CHIARA IN POCHI SECONDI",
                "MOBILE PRIMA DI TUTTO",
                "PAGINE PRODOTTO SEMPLICI",
                "FIDUCIA E PROVE REALI",
                "CTA VISIBILE",
                "MISURA COSA SUCCEDE",
                f"REAL MEDIA PRO | {PHONE}",
            ])
        elif category == "nurture":
            title = "5 CONTROLLI PER UN E-COMMERCE CHE DEVE VENDERE"
            set_slides(job, [
                title,
                "1 · SI CAPISCE SUBITO COSA VENDI?",
                "2 · DA MOBILE FUNZIONA BENE?",
                "3 · LA PAGINA PRODOTTO RISPONDE AI DUBBI?",
                "4 · IL PERCORSO È SEMPLICE?",
                "5 · STAI MISURANDO LE CONVERSIONI?",
                f"REAL MEDIA PRO | {PHONE}",
            ])
        else:
            title = "IL TUO SITO PORTA CLIENTI?"
            set_slides(job, [
                title,
                "BELLO NON BASTA",
                "DEVE FAR CAPIRE L'OFFERTA",
                "DEVE RIDURRE L'ATTRITO",
                "DEVE PORTARE A UN'AZIONE",
                "DEVE ESSERE MISURABILE",
                "PARTIAMO DA UN'ANALISI",
                f"REAL MEDIA PRO | {PHONE}",
            ])
        job["title"] = title
        job["visual_rule"] = "owned_generated_or_reusable_ecommerce_visuals_only"


def caption_for(job: dict[str, Any]) -> str:
    cid = str(job.get("client_id") or "")
    title = str(job.get("title") or "").strip()
    territory = str(job.get("territory") or "").strip()
    if cid == "f1-immobiliare":
        body = (
            f"{title}\n\n"
            f"Se stai pensando di vendere casa in {territory or 'Valle di Susa'}, il punto di partenza non è scegliere un numero a sensazione. "
            "Bisogna leggere la microzona, gli immobili realmente concorrenti, lo stato della casa, la domanda presente e il modo in cui l'immobile verrà presentato. "
            "Una comunicazione semplice funziona quando dietro c'è un posizionamento corretto. F1 Immobiliare parte dai dati e costruisce la strategia di vendita da lì.\n\n"
            f"Per un confronto sul tuo immobile: WhatsApp / telefono {PHONE}."
        )
        return ensure_hashtags(body, f1_hashtags(territory))
    body = (
        f"{title}\n\n"
        "Un sito o un e-commerce non deve sembrare complicato per essere efficace. Deve far capire rapidamente cosa offri, funzionare bene da smartphone, ridurre i dubbi e accompagnare la persona verso un'azione concreta. "
        "Per questo guardiamo struttura, pagine prodotto o servizio, velocità, fiducia, call to action e misurazione. I contenuti della giornata partono da segnali pubblici e temi attuali del settore, ma la creatività viene ricostruita da zero: niente copie di post o video di terzi.\n\n"
        f"Per un'analisi del progetto: WhatsApp / telefono {PHONE}."
    )
    return ensure_hashtags(body, rmp_hashtags(territory))


def voiceover_60(job: dict[str, Any]) -> str:
    cid = str(job.get("client_id") or "")
    title = str(job.get("title") or "").strip()
    territory = str(job.get("territory") or "").strip()
    if cid == "f1-immobiliare":
        script = (
            f"{title} Se stai pensando di vendere casa in {territory or 'Valle di Susa'}, prima di pubblicare un annuncio serve capire dove si trova davvero il valore. "
            "Il prezzo medio del comune non basta. Contano microzona, stato dell'immobile, piano, esposizione, qualità degli spazi, concorrenza attiva e domanda reale. "
            "Il punto non è riempire internet di pubblicità: è presentare bene la casa, con un prezzo coerente e una strategia comprensibile. "
            "F1 Immobiliare parte dai dati, confronta il mercato e costruisce il percorso di vendita. Se vuoi capire da dove partire, scrivici o chiama il 371 370 8294. "
            "Prima i dati. Poi la strategia. Poi la vendita."
        )
    else:
        script = (
            f"{title} Quando analizziamo un sito Shopify o un e-commerce, non partiamo dagli effetti speciali. Partiamo da domande semplici. "
            "In pochi secondi si capisce cosa vendi? Da smartphone il percorso è chiaro? La pagina prodotto risponde ai dubbi? Il cliente trova facilmente la call to action? Il sito è veloce e stai misurando quello che succede? "
            "Sono questi i controlli che incidono sull'esperienza e sulla conversione. Real Media Pro usa contenuti semplici, esempi originali e dati verificabili, senza copiare creatività di altri brand. "
            "Se vuoi capire cosa migliorare nel tuo progetto digitale, scrivici o chiama il 371 370 8294 e richiedi un'analisi strategica."
        )
    words = clean_voice(script).split()
    return " ".join(words[:165])


def main() -> int:
    if not QUEUE.exists():
        return 0
    data = load(QUEUE)
    changed = 0
    for job in data.get("jobs", []):
        cid = str(job.get("client_id") or "")
        if cid not in {"f1-immobiliare", "real-media-pro"}:
            continue
        if job.get("status") in {"published", "disabled"}:
            continue
        signals = research_for(cid)
        apply_simple_plan(job, signals)
        job["caption"] = caption_for(job)
        job["voiceover"] = voiceover_60(job)
        job["phone"] = PHONE
        job["target_reel_seconds"] = 60
        job["production_status"] = "DA CONTROLLARE"
        job["publish_decision"] = "manual"
        job["research_mode"] = "public_signals_and_official_guidance"
        job["research_basis"] = [
            {"title": str(x.get("title") or ""), "url": str(x.get("url") or "")}
            for x in signals[:3]
        ]
        changed += 1
    save(QUEUE, data)
    print(f"Enriched {changed} daily candidate(s) with simple plans, research basis, phone CTA and 60s voiceovers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
