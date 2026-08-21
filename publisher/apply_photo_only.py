#!/usr/bin/env python3
"""Apply the final static-photo policy to the active cycle.

F1: Valle di Susa property/valuation photography + one recruiting photo post.
RMP: static business/ecommerce photography inspired by modern Shopify presentation,
without copying Shopify themes. No video fields survive this policy.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"

F1_HOME_CAPTION = """VUOI VENDERE CASA IN VALLE DI SUSA?\n\nPrima di pubblicare un annuncio, parti da una valutazione immobiliare costruita su dati, caratteristiche reali dell'immobile, microzona e confronto con il mercato.\n\nF1 Immobiliare organizza la vendita partendo dall'analisi, non da un prezzo scelto a sensazione.\n\nRichiedi una valutazione gratuita del tuo immobile.\n371 370 8294 · 371 424 6300\n\n#F1Immobiliare #ValleDiSusa #VendereCasa #ValutazioneImmobiliare #Susa #Bussoleno #Condove #Avigliana #Almese #Rivoli"""

F1_RECRUIT_CAPTION = """LAVORA CON F1 IMMOBILIARE.\n\nCerchiamo collaboratori e collaboratrici da formare e affiancare, oltre ad agenti immobiliari già abilitati.\n\nPer chi non è ancora abilitato, il percorso iniziale riguarda presidio della zona, contatto con residenti e proprietari, ricerca immobili, appuntamenti e raccolta delle informazioni iniziali, sempre con affiancamento. Le attività riservate alla mediazione e alla negoziazione vengono svolte da professionisti abilitati.\n\nInvia il curriculum a f1immobiliaresusa@outlook.it\n371 370 8294\n\n#F1Immobiliare #LavoraConNoi #Immobiliare #ValleDiSusa #TorinoOvest"""

RMP_CAPTIONS = [
"""IL TUO SITO AIUTA DAVVERO A VENDERE?\n\nUn sito efficace non è solo bello: deve rendere chiara l'offerta, guidare la persona e facilitare il contatto o l'acquisto. Real Media Pro analizza presenza digitale, sito, social e percorso commerciale per individuare cosa migliorare.\n\nRichiedi un'analisi strategica gratuita.\n371 370 8294\n\n#RealMediaPro #SitiWeb #Ecommerce #Shopify #DigitalMarketing #Torino #ValleDiSusa""",
"""ECOMMERCE: DESIGN E CONVERSIONE DEVONO LAVORARE INSIEME.\n\nUna vetrina digitale moderna deve essere leggibile da smartphone, veloce e costruita per accompagnare il cliente dal prodotto al checkout. Real Media Pro progetta strategie digitali orientate a contatti e vendite.\n\nRichiedi un'analisi strategica gratuita.\n371 370 8294\n\n#RealMediaPro #Ecommerce #Shopify #SitiWeb #MarketingDigitale #AziendeLocali""",
"""SOCIAL, SITO E VENDITE: UN UNICO PERCORSO.\n\nI social attirano attenzione. Il sito deve trasformarla in interesse, richiesta o acquisto. Se i due sistemi sono scollegati, si perdono opportunità. Real Media Pro costruisce un percorso digitale misurabile.\n\nRichiedi un'analisi strategica gratuita.\n371 370 8294\n\n#RealMediaPro #SocialMediaMarketing #Ecommerce #SitiWeb #LeadGeneration #Torino""",
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
            if pos == 2:
                j["title"] = "LAVORA CON F1 IMMOBILIARE"
                j["caption"] = F1_RECRUIT_CAPTION
                j["visual_mode"] = "f1-recruiting-photo"
                j["search_query_override"] = "real estate professional office Italy"
                j["search_queries"] = [
                    "real estate agent office Italy",
                    "property consultant office professional",
                    "business team real estate meeting",
                ]
            else:
                j["title"] = "CASE IN VALLE DI SUSA · VALUTAZIONE IMMOBILIARE"
                j["caption"] = F1_HOME_CAPTION
                j["visual_mode"] = "valle-di-susa-homes-photo"
                j["search_query_override"] = "case in Valle di Susa"
                j["search_queries"] = [
                    "case in Valle di Susa",
                    "casa alpina Piemonte",
                    "villa montagna Piemonte",
                    "casa con giardino montagne Italia",
                    "borgo alpino casa pietra Italia",
                ]
        elif cid == "real-media-pro":
            j["title"] = ["SITO CHE VENDE", "ECOMMERCE CHE CONVERTE", "SOCIAL + SITO + VENDITE"][pos-1]
            j["caption"] = RMP_CAPTIONS[pos-1]
            j["visual_mode"] = "rmp-ecommerce-photo"
            j["design_reference_url"] = "https://themes.shopify.com/?locale=it"
            j["design_reference_rule"] = "inspired by modern ecommerce presentation only; never copy a Shopify theme"
            j["search_query_override"] = [
                "ecommerce website laptop premium workspace",
                "online store product page laptop smartphone",
                "digital business ecommerce analytics workspace",
            ][pos-1]
            j["search_queries"] = [
                "ecommerce website laptop premium workspace",
                "online shop smartphone laptop business",
                "digital marketing ecommerce workspace",
                "product photography ecommerce desk",
            ]

    q["output_policy"] = "STATIC PHOTOS ONLY - JPG/PNG - NO REELS - NO MP4"
    q["photo_policy"] = {
        "contents_per_cycle": 6,
        "f1": "2 Valle di Susa property/valuation photos + 1 recruiting photo",
        "real_media_pro": "3 static ecommerce/business photos",
        "video": False,
        "audio": False,
    }
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PHOTO-ONLY policy applied: 6 static posts, no reels, no mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
