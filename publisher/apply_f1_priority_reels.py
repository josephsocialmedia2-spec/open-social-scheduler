#!/usr/bin/env python3
"""Lock the two F1 Reel slots of the active cycle to the approved pillars.

F1 Reel 1: valuation / homes in Valle di Susa.
F1 Reel 2: recruiting, inclusive and compliant with the distinction between
           non-licensed support activities and licensed mediation.

The renderer reads the metadata written here to choose the correct imagery and
to cut to a new image exactly every two seconds.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
EMAIL = "f1immobiliaresusa@outlook.it"
PHONE_1 = "371 370 8294"
PHONE_2 = "371 424 6300"


def load() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def houses_caption() -> str:
    return (
        "CASE IN VALLE DI SUSA: QUANTO VALE DAVVERO LA TUA?\n\n"
        "Se stai pensando di vendere, il punto di partenza non è l'annuncio: è una valutazione "
        "costruita sulla zona precisa, sulle caratteristiche dell'immobile, sullo stato della casa, "
        "sugli immobili realmente concorrenti e sulla domanda presente.\n\n"
        "F1 Immobiliare analizza il mercato della Valle di Susa e costruisce una strategia di vendita "
        "coerente con il tuo immobile.\n\n"
        f"Richiedi una valutazione gratuita. {PHONE_1} · {PHONE_2}\n\n"
        "#F1Immobiliare #ValleDiSusa #VendereCasa #ValutazioneImmobiliare #MercatoImmobiliare #CasaInVendita"
    )


def recruiting_caption() -> str:
    return (
        "LAVORA CON F1 IMMOBILIARE\n\n"
        "Selezioniamo collaboratori e collaboratrici per la Valle di Susa. Valutiamo sia persone da "
        "formare e affiancare, anche senza abilitazione, sia agenti immobiliari già abilitati.\n\n"
        "Per chi entra senza abilitazione, il percorso iniziale riguarda presidio della zona, contatto "
        "con residenti e proprietari, ricerca immobili, appuntamenti e raccolta delle informazioni e "
        "della documentazione iniziale, sempre con affiancamento. Le attività di mediazione e "
        "negoziazione riservate dalla normativa sono svolte dai soggetti abilitati.\n\n"
        "Cerchiamo attitudine ai rapporti umani, costanza, capacità organizzativa e orientamento agli obiettivi.\n\n"
        f"Invia il curriculum a {EMAIL}\n\n"
        "#F1Immobiliare #LavoraConNoi #ValleDiSusa #Immobiliare #RicercaPersonale #AgenteImmobiliare"
    )


def main() -> int:
    data = load()
    current = str(data.get("current_cycle") or "")
    if not current:
        raise SystemExit("current_cycle is missing")

    reels = sorted(
        [
            j for j in data.get("jobs", [])
            if str(j.get("cycle_key") or "") == current
            and str(j.get("client_id") or "") == "f1-immobiliare"
            and str(j.get("format") or "") == "reel"
        ],
        key=lambda j: int(j.get("cycle_position", 0)),
    )
    if len(reels) != 2:
        raise SystemExit(f"Expected exactly 2 F1 reels in current cycle, got {len(reels)}")

    houses = reels[0]
    houses.update({
        "content_pillar": "valuation-homes",
        "visual_mode": "valle-di-susa-homes",
        "research_query": "case in Valle di Susa",
        "search_query_override": "case in Valle di Susa",
        "search_queries": [
            "case in Valle di Susa",
            "ville Valle di Susa",
            "case montagna Piemonte",
            "casa con giardino Valle di Susa",
            "appartamenti Valle di Susa",
        ],
        "title": "CASE IN VALLE DI SUSA: QUANTO VALE DAVVERO LA TUA?",
        "caption": houses_caption(),
        "voiceover": (
            "Hai una casa in Valle di Susa e stai pensando di venderla? Prima dell'annuncio serve una "
            "valutazione basata su zona, caratteristiche, stato dell'immobile, concorrenza e domanda reale. "
            "F1 Immobiliare analizza il mercato e costruisce una strategia di vendita. Richiedi una valutazione gratuita."
        ),
        "visuals": [
            "villa con giardino ai piedi delle montagne della Valle di Susa",
            "casa in pietra e legno in borgo alpino piemontese",
            "appartamento con balcone e vista sulle montagne",
            "villa contemporanea in contesto alpino",
            "casa indipendente con giardino in valle",
            "terrazza panoramica di abitazione in montagna",
            "interno moderno con vista sul verde e montagne",
            "quartiere residenziale verde in valle alpina",
            "casa tradizionale piemontese ristrutturata",
            "villa in pietra al tramonto con panorama alpino",
        ],
        "slides": [""] * 10,
        "fixed_header_text": "RICHIEDI UNA VALUTAZIONE GRATUITA DEL TUO IMMOBILE",
        "fixed_contact_text": f"{PHONE_1}  •  {PHONE_2}",
        "show_presenter": False,
        "reel_duration_seconds": 20,
        "image_change_seconds": 2,
        "production_status": "F1 REEL CASE VALLE DI SUSA - 2 SEC PER IMMAGINE",
    })

    recruiting = reels[1]
    recruiting.update({
        "content_pillar": "real-estate-recruiting",
        "visual_mode": "f1-recruiting",
        "research_query": "lavoro immobiliare Valle di Susa",
        "search_query_override": "lavoro immobiliare Valle di Susa",
        "search_queries": [
            "real estate agent team office Italy",
            "real estate professional meeting client office",
            "property consultant neighborhood work",
            "real estate team training office",
            "real estate agent showing house client",
        ],
        "title": "LAVORA CON F1 IMMOBILIARE",
        "caption": recruiting_caption(),
        "voiceover": (
            "F1 Immobiliare cerca collaboratori e collaboratrici per la Valle di Susa, sia persone da formare "
            "sia agenti immobiliari già abilitati. Per chi inizia: territorio, contatti, ricerca immobili e appuntamenti, "
            "sempre in affiancamento. Se vuoi crescere nel settore immobiliare, invia il curriculum a "
            "f1immobiliaresusa chiocciola outlook punto it."
        ),
        "visuals": [
            "team immobiliare professionale in ufficio moderno",
            "professionista immobiliare che parla con un proprietario",
            "collaboratore immobiliare al lavoro sul territorio",
            "riunione di formazione di un team immobiliare",
            "professionista con smartphone e agenda durante attività di zona",
            "accoglienza cliente in agenzia immobiliare",
            "visita immobiliare con cliente e professionista",
            "team misto che pianifica obiettivi commerciali",
            "professionista immobiliare davanti a una casa residenziale",
            "colloquio professionale in ufficio immobiliare",
        ],
        "slides": [""] * 10,
        "fixed_header_text": "LAVORA CON F1 IMMOBILIARE",
        "fixed_contact_text": f"CV: {EMAIL}",
        "show_presenter": False,
        "reel_duration_seconds": 20,
        "image_change_seconds": 2,
        "recruitment_compliance": (
            "Selezione inclusiva senza requisiti di sesso o eta; candidati con o senza abilitazione. "
            "I non abilitati svolgono attivita di supporto, ricerca, territorio e appuntamenti; mediazione e "
            "negoziazione riservate ai soggetti abilitati."
        ),
        "production_status": "F1 REEL RICERCA PERSONALE - 2 SEC PER IMMAGINE",
    })

    data["f1_reel_policy"] = {
        "reels_per_cycle": 2,
        "reel_1": "case in Valle di Susa / valutazione immobiliare",
        "reel_2": "ricerca personale immobiliare",
        "images_per_reel": 10,
        "image_change_seconds": 2,
        "duration_seconds": 20,
    }
    data["updated_by"] = "F1 priority Reel policy"
    save(data)
    print("F1 current cycle locked: 1 homes Reel + 1 recruiting Reel, 10 images x 2 seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
