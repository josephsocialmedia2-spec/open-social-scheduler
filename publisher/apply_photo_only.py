#!/usr/bin/env python3
"""Apply the final static-photo policy to the active cycle.

F1: three owner-acquisition posts tied to Valle di Susa and property valuation.
RMP: three static posts built from media extracted from configured Shopify storefront
pages and transformed into Real Media Pro branded creatives. No video fields survive.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
PHONE = "371 370 8294"
VALUATION_URL = "https://www.agentpricing.com/j.malafronte"

F1_TITLES = [
    "CERCASI APPARTAMENTI IN VALLE DI SUSA",
    "HAI UN APPARTAMENTO DA VALUTARE?",
    "STAI PENSANDO DI VENDERE CASA?",
]

F1_CAPTIONS = [
f"""CERCASI APPARTAMENTI IN VALLE DI SUSA

Stiamo cercando appartamenti e abitazioni da proporre a persone che vogliono acquistare in Valle di Susa.

Hai un appartamento che stai pensando di vendere? Prima di decidere prezzo e strategia, verifichiamo valore, microzona, concorrenza e domanda reale.

Richiedi una prima valutazione gratuita e senza impegno:
{VALUATION_URL}

{PHONE} · 371 424 6300

#F1Immobiliare #ValleDiSusa #CercasiAppartamenti #VendereCasa #ValutazioneImmobiliare #Avigliana #Susa #Bussoleno #Condove #Almese""",
f"""HAI UN APPARTAMENTO DA VALUTARE?

Il prezzo non si sceglie a sensazione. Si verifica con dati, immobili comparabili, caratteristiche reali, microzona e domanda.

Se possiedi un appartamento in Valle di Susa e vuoi capire quanto può valere oggi, richiedi un'analisi iniziale gratuita.

Valutazione:
{VALUATION_URL}

{PHONE} · 371 424 6300

#F1Immobiliare #ValleDiSusa #ValutazioneCasa #Appartamento #VenditaImmobiliare #Avigliana #Susa #Oulx #Bardonecchia""",
f"""STAI PENSANDO DI VENDERE CASA?

Vendere bene comincia prima dell'annuncio. Prima si analizzano valore, concorrenza, domanda e posizionamento dell'immobile; poi si costruisce la strategia di vendita.

Se hai una casa o un appartamento in Valle di Susa, possiamo partire da una valutazione gratuita e comprensibile, basata sui dati.

Richiedila qui:
{VALUATION_URL}

{PHONE} · 371 424 6300

#F1Immobiliare #VendereCasa #ValleDiSusa #ValutazioneImmobiliare #CasaInVendita #PrimaIDati #NonASensazione""",
]

RMP_TITLES = [
    "SITI WEB: MOSTRA IL LAVORO REALE",
    "SHOPIFY: DAL PRODOTTO ALLA CONVERSIONE",
    "SOCIAL + SITO + VENDITE",
]

RMP_CAPTIONS = [
"""UN SITO NON SI PRESENTA CON UNA FOTO STOCK.

Per raccontare come lavoriamo preferiamo mostrare elementi reali dei progetti e delle pagine Shopify che gestiamo: immagini, prodotto, struttura, gerarchia e percorso mobile vengono rielaborati in una creatività Real Media Pro.

L'obiettivo non è avere un sito semplicemente bello. Deve rendere chiara l'offerta e facilitare contatto o acquisto.

Richiedi un'analisi strategica gratuita.
371 370 8294

#RealMediaPro #Shopify #SitiWeb #Ecommerce #WebDesign #Torino #ValleDiSusa""",
"""SHOPIFY: IL PRODOTTO DEVE PORTARE ALL'AZIONE.

Partiamo dalle pagine e dagli asset reali dello store, poi li riorganizziamo per mostrare prodotto, fiducia, vantaggi, esperienza mobile e percorso verso il checkout.

Real Media Pro lavora su sito, contenuti e conversione come un unico sistema commerciale.

Richiedi un'analisi strategica gratuita.
371 370 8294

#RealMediaPro #ShopifyItalia #Ecommerce #ConversionRate #SitiShopify #MarketingDigitale""",
"""SOCIAL, SITO E VENDITE DEVONO PARLARE LA STESSA LINGUA.

Il contenuto attira attenzione. Il sito deve trasformarla in interesse, richiesta o acquisto. Per questo nelle nostre creatività utilizziamo anche materiale reale delle pagine Shopify autorizzate, rielaborato per spiegare concretamente il lavoro.

Richiedi un'analisi strategica gratuita.
371 370 8294

#RealMediaPro #Shopify #SocialMediaMarketing #Ecommerce #LeadGeneration #SitiWeb #Torino""",
]


def main() -> int:
    q = json.loads(QUEUE.read_text(encoding="utf-8"))
    key = q.get("current_cycle")
    jobs = [j for j in q.get("jobs", []) if j.get("cycle_key") == key]
    if len(jobs) != 6:
        raise RuntimeError(f"Expected 6 jobs in current cycle, got {len(jobs)}")

    for j in jobs:
        cid = j.get("client_id")
        pos = int(j.get("cycle_position", 1))
        idx = max(0, min(2, pos - 1))
        j["format"] = "photo"
        j["publication_ready"] = True
        j["output_type"] = "static-photo"
        j["no_video"] = True
        j["no_audio"] = True
        j["no_reel"] = True
        j.pop("image_change_seconds", None)
        j.pop("reel_duration_seconds", None)
        j.pop("target_reel_seconds", None)

        if cid == "f1-immobiliare":
            j["title"] = F1_TITLES[idx]
            j["caption"] = F1_CAPTIONS[idx]
            j["visual_mode"] = "valle-di-susa-local-property-photo"
            j["local_visual_required"] = True
            j["reject_generic_foreign_property_visuals"] = True
            j["search_query_override"] = [
                "appartamenti Valle di Susa Piemonte",
                "abitazioni Avigliana Piemonte",
                "case Susa Piemonte Italia",
            ][idx]
            j["search_queries"] = [
                "Avigliana abitazioni Piemonte",
                "Valle di Susa case Piemonte",
                "Susa centro abitazioni Piemonte",
                "Oulx appartamenti Piemonte",
                "Bardonecchia abitazioni Piemonte",
            ]
        elif cid == "real-media-pro":
            j["title"] = RMP_TITLES[idx]
            j["caption"] = RMP_CAPTIONS[idx]
            j["visual_mode"] = "rmp-shopify-storefront-photo"
            j["shopify_asset_required"] = True
            j["shopify_transform_required"] = True
            j["design_reference_rule"] = "Use only media extracted from configured, authorised public Shopify storefront sources; transform it into an original Real Media Pro composition."
            j["search_query_override"] = ""
            j["search_queries"] = []

    q["output_policy"] = "STATIC PHOTOS ONLY - F1 LOCAL VALLE DI SUSA + RMP SHOPIFY STOREFRONT - JPG/PNG"
    q["photo_policy"] = {
        "contents_per_cycle": 6,
        "f1": "3 owner-acquisition / valuation posts with local Valle di Susa visual requirement",
        "real_media_pro": "3 branded static posts sourced from configured Shopify storefront media",
        "video": False,
        "audio": False,
    }
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PHOTO policy applied: F1 local property acquisition + RMP Shopify storefront visuals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
