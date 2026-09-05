#!/usr/bin/env python3
"""Apply publication policy to the active cycle.

F1 Immobiliare is governed by publisher/f1_content_policy.json.
The five F1 positions rotate the institutional service pillars instead of using
owner-acquisition content only. Visual production must use the light F1
white/green/black institutional template; no dark recruiting variant is allowed.

Service 3 (tax/bonus information) is high-risk: this static generator never invents
or freezes tax figures. Until a same-day official-source verifier is wired into the
pipeline, its slot communicates the verification method only and contains no tax
rates, thresholds, deadlines or eligibility claims.

Real Media Pro keeps its existing Shopify Theme Store policy unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
F1_POLICY = ROOT / "publisher" / "f1_content_policy.json"
PHONE = "371 370 8294"
PHONE_FRANCESCA = "371 424 6300"
VALUATION_URL = "https://www.agentpricing.com/j.malafronte"
OFFICIAL_HOME_SOURCE = "https://www.agenziaentrate.gov.it/portale/aree-tematiche/casa"


def load_policy() -> dict:
    policy = json.loads(F1_POLICY.read_text(encoding="utf-8"))
    if policy.get("brand") != "F1 Immobiliare" or policy.get("status") != "binding":
        raise RuntimeError("F1 institutional policy missing or not binding")
    return policy


F1_POSTS = [
    {
        "service_id": "service_1_agent_pricing",
        "title": "QUANTO VALE DAVVERO CASA TUA?",
        "caption": f"""QUANTO VALE DAVVERO CASA TUA?

Una valutazione professionale non nasce da una sensazione. Con Agent Pricing analizziamo dati, immobili comparabili, microzona, concorrenza, domanda e caratteristiche reali della proprietà per costruire una strategia di prezzo comprensibile.

Il nostro obiettivo non è darti il numero che vuoi sentirti dire: è aiutarti a capire su quali elementi si basa la valutazione.

Richiedi una valutazione professionale:
{VALUATION_URL}

{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Avigliana #Susa #Condove #Almese #Bussoleno""",
        "hashtags": ["#ValleDiSusa", "#Avigliana", "#Susa", "#Condove", "#Almese", "#Bussoleno"],
        "search": "abitazioni Valle di Susa Piemonte",
        "three_boxes": ["DATI REALI", "ANALISI PROFESSIONALE", "STRATEGIA DI PREZZO"],
        "cta": "RICHIEDI UNA VALUTAZIONE PROFESSIONALE",
    },
    {
        "service_id": "service_2_piano_vendita",
        "title": "NON UN ANNUNCIO. UN PIANO DI VENDITA.",
        "caption": f"""LA TUA CASA NON HA BISOGNO DI UN SEMPLICE ANNUNCIO.

Quando prendiamo in carico un immobile costruiamo un piano di marketing dedicato alla proprietà.

Prepariamo servizio fotografico, video, Reel, planimetrie, descrizione commerciale, cartello, scheda immobile e materiali per le visite. Poi sviluppiamo la presenza online sui principali portali, sul sito F1 e sui nostri canali social, attiviamo banca dati, email, WhatsApp e rete di collaboratori.

Sul territorio possiamo pianificare fino a 2.500 volantini dedicati, con distribuzione progressiva registrata e monitorata. Quando previsto, il piano comprende anche un Open House.

Fotografie, video, portali, social, sito, territorio, banca dati, WhatsApp, email e Open House lavorano come un'unica strategia.

Vuoi sapere come venderemmo la tua casa?
{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Avigliana #Almese #VillarDora #Caprie #BorgoneSusa""",
        "hashtags": ["#ValleDiSusa", "#Avigliana", "#Almese", "#VillarDora", "#Caprie", "#BorgoneSusa"],
        "search": "case Valle di Susa Piemonte",
        "three_boxes": ["PRESENZA ONLINE", "MARKETING TERRITORIALE", "RETE F1"],
        "cta": "VUOI SAPERE COME VENDEREMMO LA TUA CASA?",
    },
    {
        "service_id": "service_4_recruiting",
        "role": "junior",
        "title": "CERCHIAMO TALENTO, NON ESPERIENZA.",
        "caption": f"""F1 IMMOBILIARE CERCA COLLABORATORI / AGENTI IMMOBILIARI JUNIOR.

Vivi in Valle di Susa e vuoi costruire un percorso professionale nel settore immobiliare? Selezioniamo giovani neodiplomati, neolaureati e candidati anche alla prima esperienza.

Non cerchiamo qualcuno che sappia già fare tutto. Cerchiamo persone da formare con un metodo operativo, una zona assegnata e obiettivi chiari.

Il percorso di crescita può svilupparsi da Collaboratore Junior ad Agente, Team Leader e Responsabile. Per i profili che maturano competenze, risultati e responsabilità adeguate può aprirsi anche la possibilità di partecipare allo sviluppo di una nuova sede F1 Immobiliare.

Nessuna promessa automatica: la crescita dipende da formazione, risultati e capacità.

CANDIDATI:
{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Avigliana #Susa #Condove #Almese #Bussoleno""",
        "hashtags": ["#ValleDiSusa", "#Avigliana", "#Susa", "#Condove", "#Almese", "#Bussoleno"],
        "search": "Valle di Susa territorio Piemonte",
        "three_boxes": ["ANCHE PRIMA ESPERIENZA", "FORMAZIONE INTERNA", "PERCORSO DI CRESCITA"],
        "cta": "CANDIDATI",
        "economic_claims": [],
    },
    {
        "service_id": "service_4_recruiting",
        "role": "coordinatrice",
        "title": "CERCHIAMO UNA COORDINATRICE D'UFFICIO",
        "caption": f"""F1 IMMOBILIARE AMPLIA IL TEAM.

Cerchiamo una Coordinatrice d'Ufficio: una figura centrale nell'organizzazione dell'agenzia, non una semplice receptionist.

Il ruolo comprende front office, gestione della banca dati, agenda, richiami, telemarketing operativo, fissazione degli appuntamenti e supporto quotidiano alla squadra.

Cerchiamo precisione, organizzazione, capacità comunicative e dimestichezza con gli strumenti digitali. L'esperienza immobiliare può essere utile, ma non è necessariamente indispensabile se il profilo è adatto al ruolo.

CANDIDATI:
{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Avigliana #Susa #Condove #Almese #Bussoleno""",
        "hashtags": ["#ValleDiSusa", "#Avigliana", "#Susa", "#Condove", "#Almese", "#Bussoleno"],
        "search": "Valle di Susa ufficio immobiliare Piemonte",
        "three_boxes": ["FRONT OFFICE", "BANCA DATI E AGENDA", "SUPPORTO ALLA SQUADRA"],
        "cta": "CANDIDATI",
        "economic_claims": [],
    },
    {
        "service_id": "service_3_bonus_casa",
        "title": "BONUS CASA: PRIMA LE FONTI UFFICIALI",
        "caption": f"""BONUS, AGEVOLAZIONI E PRIMA CASA: LE REGOLE CAMBIANO.

Per questo F1 Immobiliare non pubblica aliquote, soglie ISEE, requisiti o scadenze copiandoli da vecchi articoli o da fonti non istituzionali.

I contenuti informativi del Servizio 3 devono essere verificati sulle pagine ufficiali dell'Agenzia delle Entrate prima della pubblicazione. Finché il controllo giornaliero non conferma un dato, quel dato non viene pubblicato.

Fonte istituzionale di riferimento:
{OFFICIAL_HOME_SOURCE}

Informarsi bene prima di comprare casa è parte di una scelta consapevole.

{PHONE} · {PHONE_FRANCESCA}

#ValleDiSusa #Avigliana #Susa #Condove #Almese #Bussoleno""",
        "hashtags": ["#ValleDiSusa", "#Avigliana", "#Susa", "#Condove", "#Almese", "#Bussoleno"],
        "search": "Agenzia Entrate casa agevolazioni",
        "three_boxes": ["FONTI UFFICIALI", "DATI VERIFICATI", "NESSUNA INFORMAZIONE SCADUTA"],
        "cta": "INFORMATI PRIMA DI COMPRARE",
        "normative_claims": False,
        "official_source": OFFICIAL_HOME_SOURCE,
    },
]

RMP_POSTS = [
    {
        "theme": "Shapes",
        "theme_url": "https://themes.shopify.com/themes/shapes/presets/shapes?locale=it",
        "title": "SHOPIFY: DAL PRODOTTO ALLA CONVERSIONE",
        "theme_description_it": "Shapes punta su una presentazione creativa e molto flessibile, con elementi grafici modulari, acquisto rapido, comparazione prodotto e strumenti pensati per rendere la scoperta del catalogo più immediata.",
        "caption": """SHOPIFY: DAL PRODOTTO ALLA CONVERSIONE.\n\nUn e-commerce deve rendere semplice capire il prodotto, confrontare le alternative e arrivare all'azione. Prendiamo ispirazione dalle logiche del tema Shopify Shapes: struttura creativa, sezioni modulari, quick buy e percorso di scoperta chiaro.\n\nLa grafica che mostriamo è originale: non copiamo immagini o creatività del tema.\n\nReal Media Pro progetta siti Shopify orientati a navigazione, prodotto e conversione.\n\nAnalisi strategica gratuita: 371 370 8294""",
        "layout_profile": "creative_modular",
    },
    {
        "theme": "Broadcast",
        "theme_url": "https://themes.shopify.com/themes/broadcast/presets/broadcast?locale=it",
        "title": "MOBILE FIRST, PERCORSO CHIARO",
        "theme_description_it": "Broadcast è un tema ricco di funzionalità con oltre 30 sezioni personalizzabili, strumenti di upsell, acquisto rapido e una struttura ottimizzata per dispositivi mobili e velocità.",
        "caption": """MOBILE FIRST, PERCORSO CHIARO.\n\nIl tema Shopify Broadcast mette al centro sezioni personalizzabili, velocità, mobile, acquisto rapido e strumenti che accompagnano il cliente verso la vendita.\n\nDa questa logica costruiamo un concept Real Media Pro completamente originale: gerarchia chiara, CTA visibili, navigazione veloce e meno attrito da smartphone.\n\nNessuna immagine del tema viene copiata o ripubblicata.\n\nAnalisi strategica gratuita: 371 370 8294""",
        "layout_profile": "mobile_speed",
    },
    {
        "theme": "Prestige",
        "theme_url": "https://themes.shopify.com/themes/prestige/presets/prestige?locale=it",
        "title": "DESIGN PREMIUM, PRESTAZIONI VELOCI",
        "theme_description_it": "Prestige è progettato per brand premium e di fascia alta, con oltre 30 sezioni configurabili, forte valorizzazione del prodotto, prestazioni rapide e attenzione all'accessibilità.",
        "caption": """DESIGN PREMIUM, PRESTAZIONI VELOCI.\n\nPrestige mostra come un e-commerce premium possa combinare immagine di marca, prodotto, sezioni configurabili, velocità e accessibilità.\n\nReal Media Pro traduce questi principi in un progetto originale costruito sull'identità del cliente: nessuna copia del tema, ma una struttura pensata per far percepire valore e facilitare l'acquisto.\n\nAnalisi strategica gratuita: 371 370 8294""",
        "layout_profile": "premium",
    },
    {
        "theme": "Allure",
        "theme_url": "https://themes.shopify.com/themes/allure/presets/allure?locale=it",
        "title": "SITI WEB CHE VALORIZZANO IL BRAND",
        "theme_description_it": "Allure combina raffinatezza e semplicità con una vetrina moderna, dinamica e orientata alla scoperta dei prodotti, alla visibilità del catalogo e a pagine progettate per sostenere la vendita.",
        "caption": """SITI WEB CHE VALORIZZANO IL BRAND.\n\nAllure unisce semplicità, impatto visivo, scoperta dei prodotti e una struttura pensata per sostenere la vendita. È un riferimento utile per capire quanto design e percorso commerciale debbano lavorare insieme.\n\nNoi partiamo da questi principi per creare un sito originale, coerente con il brand e costruito attorno ai suoi prodotti e clienti.\n\nNessuna immagine Shopify viene copiata.\n\nAnalisi strategica gratuita: 371 370 8294""",
        "layout_profile": "brand_story",
    },
    {
        "theme": "Vivid",
        "theme_url": "https://themes.shopify.com/themes/vivid/presets/vivid?locale=it",
        "title": "SEZIONI MODULARI PER VENDERE MEGLIO",
        "theme_description_it": "Vivid combina design moderno, personalizzazione, funzioni avanzate per merchandising e scoperta del prodotto, ricerca e filtri, con una struttura pulita pensata per adattarsi al brand.",
        "caption": """SEZIONI MODULARI PER VENDERE MEGLIO.\n\nVivid mette insieme struttura pulita, personalizzazione, ricerca, filtri e sezioni dedicate alla scoperta dei prodotti.\n\nPer Real Media Pro il punto non è replicare il tema: è utilizzare queste logiche per progettare un'esperienza originale che aiuti l'utente a trovare, capire e scegliere più facilmente.\n\nNessuna immagine del Theme Store viene riutilizzata.\n\nAnalisi strategica gratuita: 371 370 8294""",
        "layout_profile": "catalog_discovery",
    },
]


def main() -> int:
    policy = load_policy()
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
            j["f1_policy_version"] = policy["version"]
            j["service_id"] = post["service_id"]
            j["brand_template"] = "light_f1_institutional"
            j["title"] = post["title"]
            j["caption"] = post["caption"]
            j["hashtags"] = post["hashtags"]
            j["three_boxes"] = post["three_boxes"]
            j["cta"] = post["cta"]
            j["visual_mode"] = "f1-light-institutional"
            j["light_template_required"] = True
            j["dark_template_forbidden"] = True
            j["allowed_palette"] = ["#4E9E15", "#000000", "#FFFFFF"]
            j["local_visual_required"] = True
            j["reject_generic_foreign_property_visuals"] = True
            j["search_query_override"] = post["search"]
            j["search_queries"] = [post["search"]]
            j["official_tax_data_required"] = post["service_id"] == "service_3_bonus_casa" and bool(post.get("normative_claims"))
            j["official_tax_source"] = post.get("official_source")
            j["recruiting_fixed_starting_salary_forbidden"] = post["service_id"] == "service_4_recruiting"
            j["competitor_brand_mentions_forbidden"] = True
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

    q["output_policy"] = "10 STATIC PUBLICATIONS - 5 F1 INSTITUTIONAL SERVICES + 5 RMP SHOPIFY THEME STORE ORIGINAL MOCKUPS"
    q["f1_content_policy_version"] = policy["version"]
    q["photo_policy"] = {
        "contents_per_cycle": 10,
        "f1": "5 institutional F1 posts across Agent Pricing, Piano di Vendita, Recruiting and official-source information policy; light white-green-black template only",
        "real_media_pro": "5 original ecommerce mockups inspired only by official Shopify Theme Store descriptions; zero copied theme images; no hashtags; Francesca + Joseph footer",
        "video": False,
        "audio": False,
    }
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PUBLICATION policy applied: F1 institutional services + RMP Shopify Theme Store")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
