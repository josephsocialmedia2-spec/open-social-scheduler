#!/usr/bin/env python3
"""Enrich queue jobs with fresh-query captions, natural voiceover and premium visual plans."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
RESEARCH = ROOT / "publisher" / "research" / "latest.json"
PHONE = "371 370 8294"
FRANCESCA_PHONE = "371 424 6300"


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


def ensure_hashtags(caption: str, tags: list[str]) -> str:
    base = re.sub(r"(?:\n\s*)?(?:#[\wÀ-ÿ]+\s*)+$", "", str(caption or "").strip()).strip()
    return base + "\n\n" + " ".join(dict.fromkeys(tags))


def f1_hashtags(territory: str) -> list[str]:
    return ["#F1Immobiliare", "#ValleDiSusa", local_tag(territory), "#VendereCasa",
            "#ValutazioneImmobiliare", "#MercatoImmobiliare", "#CasaInVendita"]


def rmp_hashtags(territory: str) -> list[str]:
    return ["#RealMediaPro", "#DigitalMarketing", "#SocialMediaMarketing", "#Ecommerce",
            "#SitiWeb", "#LeadGeneration", local_tag(territory)]


def research_queries(cid: str) -> list[str]:
    if not RESEARCH.exists():
        return []
    try:
        data = load(RESEARCH)
        rows = data.get("brands", {}).get(cid, {}).get("fresh_queries", [])
        return [str(x).strip() for x in rows if str(x).strip()]
    except Exception:
        return []


def research_sources(cid: str) -> list[str]:
    if not RESEARCH.exists():
        return []
    try:
        data = load(RESEARCH)
        rows = data.get("brands", {}).get(cid, {}).get("official_sources", [])
        return [str(x).strip() for x in rows if str(x).strip()]
    except Exception:
        return []


def f1_angle(query: str) -> dict[str, Any]:
    q = query.lower()
    if "omi" in q or "valori immobiliari" in q:
        return {"title": "I VALORI OMI BASTANO DAVVERO?", "lead": "Le quotazioni OMI sono una bussola statistica, non il prezzo automatico della tua casa.", "points": ["OMI = intervallo di zona", "microzona", "stato dell'immobile", "piano e luminosità", "spazi esterni", "concorrenza attiva", "domanda reale", "posizionamento finale"]}
    if "eredit" in q:
        return {"title": "VENDERE UNA CASA EREDITATA: DA DOVE PARTIRE?", "lead": "Prima della pubblicazione bisogna chiarire documenti, situazione fiscale e valore di mercato.", "points": ["successione", "titolarità", "documentazione", "stato catastale", "valore di mercato", "eventuali imposte", "strategia di vendita", "tempi realistici"]}
    if "tass" in q or "plusval" in q or "impost" in q:
        return {"title": "VENDERE CASA: QUALI COSTI DEVI CONOSCERE?", "lead": "La parte fiscale va verificata prima, non alla fine della trattativa.", "points": ["quando hai acquistato", "tipo di immobile", "prima casa", "eventuale plusvalenza", "documenti", "costi da prevedere", "valore netto atteso", "strategia"]}
    if "catast" in q or "rendita" in q:
        return {"title": "CATASTO E VALORE DI MERCATO NON SONO LA STESSA COSA", "lead": "Il dato catastale ha una funzione amministrativa e fiscale; il mercato ragiona diversamente.", "points": ["rendita catastale", "dati tecnici", "microzona", "condizioni reali", "comparabili", "domanda", "offerta", "prezzo di uscita"]}
    if "atto" in q or "dichiarat" in q:
        return {"title": "COSA RACCONTANO LE COMPRAVENDITE REALI?", "lead": "Gli atti e i dati di mercato aiutano a capire cosa è successo davvero, non cosa si sperava.", "points": ["vendite concluse", "prezzi dichiarati", "zona", "tipologia", "superficie", "stato", "tempo di vendita", "confronto con l'immobile"]}
    if "prima casa" in q or "acquisto" in q or "comprare" in q:
        return {"title": "COMPRARE O VENDERE CASA: I DATI DA GUARDARE PRIMA", "lead": "Una decisione immobiliare importante parte da informazioni verificabili.", "points": ["budget", "imposte", "zona", "documentazione", "stato immobile", "comparabili", "domanda", "strategia"]}
    return {"title": "IL PREZZO GIUSTO NON SI INVENTA", "lead": "Una valutazione credibile nasce dall'incrocio tra dati, immobile e mercato reale.", "points": ["microzona", "comparabili", "stato casa", "piano", "esposizione", "spazi esterni", "concorrenza", "domanda"]}


def rmp_angle(query: str) -> dict[str, Any]:
    q = query.lower()
    if "shopify" in q or "ecommerce" in q or "e-commerce" in q:
        return {"title": "IL TUO E-COMMERCE AIUTA DAVVERO A VENDERE?", "lead": "La piattaforma conta, ma il risultato nasce da esperienza, fiducia e percorso d'acquisto.", "points": ["mobile", "pagina prodotto", "chiarezza offerta", "fiducia", "checkout", "velocità", "traffico qualificato", "misurazione"]}
    if "lead" in q or "contatt" in q:
        return {"title": "I SOCIAL PORTANO CONTATTI O SOLO VISUALIZZAZIONI?", "lead": "Un contenuto utile deve accompagnare la persona da attenzione a contatto.", "points": ["target", "hook", "problema reale", "prova", "CTA", "landing", "follow-up", "misurazione"]}
    if "fattur" in q or "vendit" in q:
        return {"title": "COME I SOCIAL POSSONO INCIDERE SULLE VENDITE", "lead": "I social funzionano quando fanno parte di un sistema commerciale, non quando restano isolati.", "points": ["attenzione", "fiducia", "traffico", "sito", "contatto", "follow-up", "vendita", "analisi"]}
    if "sito" in q or "conversion" in q or "funnel" in q:
        return {"title": "IL TUO SITO CONVERTE O FA SOLO PRESENZA?", "lead": "Un sito efficace deve rendere semplice capire, fidarsi e agire.", "points": ["proposta chiara", "mobile", "velocità", "prova sociale", "CTA", "pagine servizio", "tracking", "conversione"]}
    if "follower" in q or "contenut" in q or "reel" in q:
        return {"title": "DA FOLLOWER A CLIENTE: COSA DEVE SUCCEDERE?", "lead": "La crescita utile non è solo audience: è capacità di trasformare attenzione in relazione commerciale.", "points": ["contenuto", "fiducia", "ripetizione", "profilo", "CTA", "sito", "contatto", "vendita"]}
    return {"title": "PERCHÉ I SOCIAL FANNO CRESCERE UN'AZIENDA?", "lead": "Perché possono creare attenzione, fiducia e domanda, se collegati a un percorso misurabile.", "points": ["visibilità", "target", "fiducia", "contenuti", "traffico", "lead", "vendite", "misurazione"]}


def f1_visuals() -> list[str]:
    return ["villa residenziale moderna esterno giorno", "quartiere residenziale italiano curato", "soggiorno luminoso premium", "cucina moderna di qualità", "terrazzo abitabile con vista", "camera matrimoniale elegante", "bagno contemporaneo premium", "facciata e ingresso immobile", "dettaglio architettonico e giardino", "villa residenziale al tramonto"]


def rmp_visuals() -> list[str]:
    return ["imprenditore con laptop in ufficio moderno", "smartphone con interfaccia social professionale", "sito ecommerce premium su laptop", "pagina prodotto pulita da smartphone", "dashboard marketing e analytics realistica", "team digitale al lavoro", "checkout ecommerce semplice", "analisi dati business su schermo", "imprenditore che controlla risultati", "workspace digitale premium con laptop e smartphone"]


def carousel_slides(angle: dict[str, Any], cid: str) -> list[str]:
    points = list(angle["points"])[:8]
    slides = [angle["title"]]
    slides.extend(str(p).upper() for p in points)
    slides.append("RICHIEDI UNA VALUTAZIONE GRATUITA DEL TUO IMMOBILE" if cid == "f1-immobiliare" else "RICHIEDI UN'ANALISI STRATEGICA GRATUITA")
    return slides[:10]


def f1_caption(angle: dict[str, Any], query: str, territory: str) -> str:
    body = (f"{angle['title']}\n\n{angle['lead']} Se stai pensando di vendere casa in {territory or 'Valle di Susa'}, una valutazione seria non nasce da una cifra presa isolatamente. Bisogna leggere la microzona, le caratteristiche reali dell'immobile, ciò che è effettivamente in concorrenza e la domanda presente. I dati pubblici sono utili quando vengono interpretati nel contesto corretto. Per questo il prezzo di uscita deve essere comprensibile, difendibile e coerente con il mercato.\n\nRichiedi una valutazione gratuita del tuo immobile. Joseph {PHONE} · Francesca {FRANCESCA_PHONE}.")
    return ensure_hashtags(body, f1_hashtags(territory))


def rmp_caption(angle: dict[str, Any], query: str, territory: str) -> str:
    body = (f"{angle['title']}\n\n{angle['lead']} Un'azienda cresce online quando contenuti, social, sito e processo commerciale lavorano insieme. La metrica importante non è soltanto quante persone vedono un post, ma quante capiscono l'offerta, si fidano, visitano il sito, lasciano un contatto o acquistano. Per questo ogni contenuto deve avere una funzione nel percorso del cliente e ogni risultato deve poter essere misurato.\n\nRichiedi un'analisi strategica gratuita. Real Media Pro · {PHONE}.")
    return ensure_hashtags(body, rmp_hashtags(territory))


def f1_voice(angle: dict[str, Any], territory: str) -> str:
    return clean_voice(f"{angle['title']} {angle['lead']} Se stai pensando di vendere casa in {territory or 'Valle di Susa'}, il punto è questo: un numero, da solo, non racconta il valore reale di un immobile. Contano la posizione precisa, lo stato della casa, il piano, la luce, gli spazi esterni, gli immobili davvero concorrenti e la domanda che esiste in quel momento. I dati pubblici servono come riferimento, ma devono essere letti insieme al mercato reale. Il prezzo corretto non è quello che ci piacerebbe ottenere: è quello che permette alla casa di essere posizionata bene, difesa con argomenti concreti e presentata alle persone giuste. Se vuoi capire da dove partire, richiedi una valutazione gratuita con F1 Immobiliare. Joseph {PHONE}, Francesca {FRANCESCA_PHONE}. Prima i dati, poi la strategia, poi la vendita.")


def rmp_voice(angle: dict[str, Any]) -> str:
    return clean_voice(f"{angle['title']} {angle['lead']} Il punto non è pubblicare di più. È costruire un percorso in cui ogni contenuto abbia una funzione. Prima attiri l'attenzione della persona giusta. Poi fai capire il problema e la tua proposta. Costruisci fiducia con esempi, prove e chiarezza. Porti il traffico verso un sito o una pagina che funziona bene da smartphone e rende semplice fare il passo successivo. Infine misuri contatti, richieste e vendite, così capisci cosa migliorare. Quando social, sito e processo commerciale sono scollegati, arrivano numeri ma pochi risultati. Quando lavorano insieme, il digitale diventa una leva concreta di crescita. Se vuoi capire cosa migliorare nella tua azienda, richiedi un'analisi strategica gratuita a Real Media Pro al {PHONE}.")


def main() -> int:
    if not QUEUE.exists():
        return 0
    data = load(QUEUE)
    grouped_index: dict[str, int] = {"f1-immobiliare": 0, "real-media-pro": 0}
    changed = 0
    for job in sorted(data.get("jobs", []), key=lambda j: str(j.get("scheduled_at") or "")):
        cid = str(job.get("client_id") or "")
        if cid not in grouped_index or job.get("status") in {"published", "disabled"}:
            continue
        queries = research_queries(cid)
        idx = grouped_index[cid]
        query = queries[idx % len(queries)] if queries else str(job.get("title") or "")
        grouped_index[cid] += 1
        territory = str(job.get("territory") or "").strip()
        angle = f1_angle(query) if cid == "f1-immobiliare" else rmp_angle(query)

        job["research_query"] = query
        job["title"] = angle["title"]
        job["visuals"] = f1_visuals() if cid == "f1-immobiliare" else rmp_visuals()
        job["slides"] = carousel_slides(angle, cid) if str(job.get("format")) == "carousel" else [""] * 10
        if str(job.get("format")) == "carousel":
            media = job.get("media")
            if isinstance(media, list) and media:
                parent = str(Path(str(media[0])).parent).replace("\\", "/")
                job["media"] = [f"{parent}/slide-{i:02d}.jpg" for i in range(1, 11)]

        if cid == "f1-immobiliare":
            job["caption"] = f1_caption(angle, query, territory)
            job["voiceover"] = f1_voice(angle, territory)
            job["phone"] = PHONE
            job["secondary_phone"] = FRANCESCA_PHONE
            job["visual_rule"] = "premium_residential_property_only"
        else:
            job["caption"] = rmp_caption(angle, query, territory)
            job["voiceover"] = rmp_voice(angle)
            job["phone"] = PHONE
            job["visual_rule"] = "pixabay_canva_business_ecommerce_only"

        job["target_reel_seconds"] = 60
        job["production_status"] = "DA CONTROLLARE"
        job["publish_decision"] = "manual"
        job["research_mode"] = "google_suggestions_plus_official_sources"
        job["research_basis"] = [{"url": u} for u in research_sources(cid)]
        job["no_subtitles"] = True
        job["visual_count"] = 10
        changed += 1

    save(QUEUE, data)
    print(f"Enriched {changed} candidate(s) with fresh query, premium caption, 10 visuals and natural voiceover.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
