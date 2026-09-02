#!/usr/bin/env python3
"""Apply the approved publication policy to the active cycle.

F1 Immobiliare
- 5 owner-acquisition / valuation publications;
- Valle di Susa / Piemonte visual requirement;
- bottom presenter strip with Francesca + Joseph;
- hashtags are TERRITORIAL ONLY.

Real Media Pro
- 5 publications inspired ONLY by official Shopify Theme Store themes;
- theme images are never copied or republished;
- the theme description is rewritten in Italian for the caption;
- the renderer creates an ORIGINAL website mockup from the theme concepts;
- no hashtags are used for Real Media Pro.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
PHONE = "371 370 8294"
PHONE_FRANCESCA = "371 424 6300"
VALUATION_URL = "https://www.agentpricing.com/j.malafronte"

F1_POSTS = [
    {
        "title": "CERCASI APPARTAMENTI IN VALLE DI SUSA",
        "caption": f"""CERCASI APPARTAMENTI IN VALLE DI SUSA

Stiamo cercando appartamenti e abitazioni per persone interessate ad acquistare nella nostra zona.

Hai una casa o un appartamento che stai pensando di vendere? Prima di scegliere prezzo e strategia verifichiamo microzona, immobili comparabili, concorrenza e domanda reale.

Prima valutazione gratuita e senza impegno:
{VALUATION_URL}

{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Avigliana #Susa #Condove #Almese #Bussoleno""",
        "hashtags": ["#ValleDiSusa", "#Avigliana", "#Susa", "#Condove", "#Almese", "#Bussoleno"],
        "search": "appartamenti Valle di Susa Piemonte",
    },
    {
        "title": "HAI UN APPARTAMENTO DA VALUTARE?",
        "caption": f"""HAI UN APPARTAMENTO DA VALUTARE?

Il prezzo non si sceglie a sensazione. Si verifica con dati, immobili comparabili, caratteristiche reali, microzona e domanda.

Se possiedi un appartamento in Valle di Susa e vuoi capire quanto può valere oggi, richiedi una prima analisi gratuita.

{VALUATION_URL}

{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Avigliana #Almese #SantAmbrogioDiTorino #VillarDora #Caprie""",
        "hashtags": ["#ValleDiSusa", "#Avigliana", "#Almese", "#SantAmbrogioDiTorino", "#VillarDora", "#Caprie"],
        "search": "abitazioni Avigliana Piemonte",
    },
    {
        "title": "STAI PENSANDO DI VENDERE CASA?",
        "caption": f"""STAI PENSANDO DI VENDERE CASA?

Vendere bene comincia prima dell'annuncio. Prima analizziamo valore, concorrenza, domanda e posizionamento dell'immobile; poi costruiamo la strategia di vendita.

Se hai una casa o un appartamento in Valle di Susa possiamo partire da una valutazione gratuita, chiara e basata sui dati.

{VALUATION_URL}

{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Susa #BorgoneSusa #Bussoleno #SanGiorio #VillarFocchiardo""",
        "hashtags": ["#ValleDiSusa", "#Susa", "#BorgoneSusa", "#Bussoleno", "#SanGiorio", "#VillarFocchiardo"],
        "search": "case Susa Piemonte Italia",
    },
    {
        "title": "LA MICROZONA CAMBIA IL VALORE",
        "caption": f"""LA MICROZONA CAMBIA IL VALORE.

Stesso comune non significa stesso prezzo. Via, piano, esposizione, servizi, accessibilità e domanda possono cambiare il posizionamento di un immobile anche a poche centinaia di metri di distanza.

Per questo una valutazione seria parte dal territorio reale, non da una media generica.

{VALUATION_URL}

{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Oulx #Bardonecchia #SauzeDOulx #CesanaTorinese #Chiomonte""",
        "hashtags": ["#ValleDiSusa", "#Oulx", "#Bardonecchia", "#SauzeDOulx", "#CesanaTorinese", "#Chiomonte"],
        "search": "Oulx abitazioni Piemonte",
    },
    {
        "title": "VALUTAZIONE IMMOBILIARE CON I DATI",
        "caption": f"""VALUTAZIONE IMMOBILIARE CON I DATI.

Comparabili, mercato, microzona e strategia: il valore non è un numero inventato per convincere il proprietario. Deve essere una conclusione che puoi capire.

Richiedi una prima analisi gratuita del tuo immobile.

{VALUATION_URL}

{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Condove #Vaie #ChiusaDiSanMichele #SantAmbrogioDiTorino #Avigliana""",
        "hashtags": ["#ValleDiSusa", "#Condove", "#Vaie", "#ChiusaDiSanMichele", "#SantAmbrogioDiTorino", "#Avigliana"],
        "search": "Valle di Susa case Piemonte",
    },
]

RMP_POSTS = [
    {
        "theme": "Shapes",
        "theme_url": "https://themes.shopify.com/themes/shapes/presets/shapes?locale=it",
        "title": "SHOPIFY: DAL PRODOTTO ALLA CONVERSIONE",
        "theme_description_it": "Shapes punta su una presentazione creativa e molto flessibile, con elementi grafici modulari, acquisto rapido, comparazione prodotto e strumenti pensati per rendere la scoperta del catalogo più immediata.",
        "caption": """SHOPIFY: DAL PRODOTTO ALLA CONVERSIONE.

Un e-commerce deve rendere semplice capire il prodotto, confrontare le alternative e arrivare all'azione. Prendiamo ispirazione dalle logiche del tema Shopify Shapes: struttura creativa, sezioni modulari, quick buy e percorso di scoperta chiaro.

La grafica che mostriamo è originale: non copiamo immagini o creatività del tema.

Real Media Pro progetta siti Shopify orientati a navigazione, prodotto e conversione.

Analisi strategica gratuita: 371 370 8294""",
        "layout_profile": "creative_modular",
    },
    {
        "theme": "Broadcast",
        "theme_url": "https://themes.shopify.com/themes/broadcast/presets/broadcast?locale=it",
        "title": "MOBILE FIRST, PERCORSO CHIARO",
        "theme_description_it": "Broadcast è un tema ricco di funzionalità con oltre 30 sezioni personalizzabili, strumenti di upsell, acquisto rapido e una struttura ottimizzata per dispositivi mobili e velocità.",
        "caption": """MOBILE FIRST, PERCORSO CHIARO.

Il tema Shopify Broadcast mette al centro sezioni personalizzabili, velocità, mobile, acquisto rapido e strumenti che accompagnano il cliente verso la vendita.

Da questa logica costruiamo un concept Real Media Pro completamente originale: gerarchia chiara, CTA visibili, navigazione veloce e meno attrito da smartphone.

Nessuna immagine del tema viene copiata o ripubblicata.

Analisi strategica gratuita: 371 370 8294""",
        "layout_profile": "mobile_speed",
    },
    {
        "theme": "Prestige",
        "theme_url": "https://themes.shopify.com/themes/prestige/presets/prestige?locale=it",
        "title": "DESIGN PREMIUM, PRESTAZIONI VELOCI",
        "theme_description_it": "Prestige è progettato per brand premium e di fascia alta, con oltre 30 sezioni configurabili, forte valorizzazione del prodotto, prestazioni rapide e attenzione all'accessibilità.",
        "caption": """DESIGN PREMIUM, PRESTAZIONI VELOCI.

Prestige mostra come un e-commerce premium possa combinare immagine di marca, prodotto, sezioni configurabili, velocità e accessibilità.

Real Media Pro traduce questi principi in un progetto originale costruito sull'identità del cliente: nessuna copia del tema, ma una struttura pensata per far percepire valore e facilitare l'acquisto.

Analisi strategica gratuita: 371 370 8294""",
        "layout_profile": "premium",
    },
    {
        "theme": "Allure",
        "theme_url": "https://themes.shopify.com/themes/allure/presets/allure?locale=it",
        "title": "SITI WEB CHE VALORIZZANO IL BRAND",
        "theme_description_it": "Allure combina raffinatezza e semplicità con una vetrina moderna, dinamica e orientata alla scoperta dei prodotti, alla visibilità del catalogo e a pagine progettate per sostenere la vendita.",
        "caption": """SITI WEB CHE VALORIZZANO IL BRAND.

Allure unisce semplicità, impatto visivo, scoperta dei prodotti e una struttura pensata per sostenere la vendita. È un riferimento utile per capire quanto design e percorso commerciale debbano lavorare insieme.

Noi partiamo da questi principi per creare un sito originale, coerente con il brand e costruito attorno ai suoi prodotti e clienti.

Nessuna immagine Shopify viene copiata.

Analisi strategica gratuita: 371 370 8294""",
        "layout_profile": "brand_story",
    },
    {
        "theme": "Vivid",
        "theme_url": "https://themes.shopify.com/themes/vivid/presets/vivid?locale=it",
        "title": "SEZIONI MODULARI PER VENDERE MEGLIO",
        "theme_description_it": "Vivid combina design moderno, personalizzazione, funzioni avanzate per merchandising e scoperta del prodotto, ricerca e filtri, con una struttura pulita pensata per adattarsi al brand.",
        "caption": """SEZIONI MODULARI PER VENDERE MEGLIO.

Vivid mette insieme struttura pulita, personalizzazione, ricerca, filtri e sezioni dedicate alla scoperta dei prodotti.

Per Real Media Pro il punto non è replicare il tema: è utilizzare queste logiche per progettare un'esperienza originale che aiuti l'utente a trovare, capire e scegliere più facilmente.

Nessuna immagine del Theme Store viene riutilizzata.

Analisi strategica gratuita: 371 370 8294""",
        "layout_profile": "catalog_discovery",
    },
]


def main() -> int:
    q = json.loads(QUEUE.read_text(encoding="utf-8"))
    key = q.get("current_cycle")
    jobs = [j for j in q.get("jobs", []) if j.get("cycle_key") == key]
    if len(jobs) != 10:
        raise RuntimeError(f"Expected 10 jobs in current cycle, got {len(jobs)}")

    for j in jobs:
        cid = str(j.get("client_id") or "")
        pos = int(j.get("cycle_position", 1))
        idx = max(0, min(4, pos - 1))
        j["format"] = "photo"
        j["publication_ready"] = True
        j["output_type"] = "static-photo"
        j["no_video"] = True
        j["no_audio"] = True
        j["no_reel"] = True
        j["people_footer_required"] = True
        j.pop("image_change_seconds", None)
        j.pop("reel_duration_seconds", None)
        j.pop("target_reel_seconds", None)

        if cid == "f1-immobiliare":
            post = F1_POSTS[idx]
            j["title"] = post["title"]
            j["caption"] = post["caption"]
            j["hashtags"] = post["hashtags"]
            j["visual_mode"] = "valle-di-susa-local-property-plus-presenters"
            j["local_visual_required"] = True
            j["reject_generic_foreign_property_visuals"] = True
            j["search_query_override"] = post["search"]
            j["search_queries"] = [
                "Avigliana abitazioni Piemonte",
                "Valle di Susa case Piemonte",
                "Susa centro abitazioni Piemonte",
                "Oulx appartamenti Piemonte",
                "Bardonecchia abitazioni Piemonte",
            ]
            for forbidden in ("shopify_theme_required", "theme_source_url", "theme_name", "layout_profile"):
                j.pop(forbidden, None)

        elif cid == "real-media-pro":
            post = RMP_POSTS[idx]
            j["title"] = post["title"]
            j["caption"] = post["caption"]
            j["hashtags"] = []
            j["visual_mode"] = "rmp-original-shopify-theme-inspired-mockup"
            j["shopify_theme_required"] = True
            j["shopify_theme_store_only"] = True
            j["copy_shopify_images"] = False
            j["generated_original_mockup"] = True
            j["theme_name"] = post["theme"]
            j["theme_source_url"] = post["theme_url"]
            j["theme_description_it"] = post["theme_description_it"]
            j["layout_profile"] = post["layout_profile"]
            j["design_reference_rule"] = "Use only the official Shopify Theme Store as inspiration. Never download, copy, crop, trace or republish theme screenshots or theme imagery. Generate an original ecommerce mockup from the described design principles."
            j["search_query_override"] = ""
            j["search_queries"] = []
            j["visual_asset_urls"] = [post["theme_url"]]
            j["visual_source"] = "shopify-theme-store-description-only"
            j.pop("shopify_asset_required", None)
            j.pop("shopify_transform_required", None)

    q["output_policy"] = "10 STATIC PUBLICATIONS - 5 F1 LOCAL + 5 RMP SHOPIFY THEME STORE ORIGINAL MOCKUPS"
    q["photo_policy"] = {
        "contents_per_cycle": 10,
        "f1": "5 owner-acquisition / valuation posts; verified Valle di Susa imagery; territorial hashtags only; Francesca + Joseph footer",
        "real_media_pro": "5 original ecommerce mockups inspired only by official Shopify Theme Store descriptions; zero copied theme images; no hashtags; Francesca + Joseph footer",
        "video": False,
        "audio": False,
    }
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PUBLICATION policy applied: 5 F1 territorial + 5 RMP Shopify Theme Store original mockups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
