#!/usr/bin/env python3
"""Apply the four-folder static-photo policy to the active cycle.

Per 4-hour cycle:
- F1 position 1: main F1 image folder / valuation content
- F1 position 2: RIC LAVORO F1 / recruiting content
- RMP position 1: main RMP image folder / digital-business content
- RMP position 2: RIC LAVORO RMP / recruiting content

Only static-photo compatible social destinations are attached to these jobs.
TikTok photo publishing remains disabled until a verified public media URL is
configured for the TikTok app. YouTube is excluded because this pipeline is photo-only.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"

STATIC_PLATFORMS = ["facebook", "instagram", "linkedin", "pinterest"]

F1_HOME_CAPTION = """VUOI VENDERE CASA IN VALLE DI SUSA?\n\nPrima di pubblicare un annuncio, parti da una valutazione immobiliare costruita su dati, caratteristiche reali dell'immobile, microzona e confronto con il mercato.\n\nF1 Immobiliare organizza la vendita partendo dall'analisi, non da un prezzo scelto a sensazione.\n\nRICHIEDI UNA VALUTAZIONE GRATUITA DEL TUO IMMOBILE\n371 370 8294 · 371 424 6300\n\n#F1Immobiliare #ValleDiSusa #VendereCasa #ValutazioneImmobiliare #Susa #Bussoleno #Condove #Avigliana #Almese #Rivoli"""

F1_RECRUIT_CAPTION = """LAVORA CON F1 IMMOBILIARE.\n\nCerchiamo persone motivate che vogliano costruire un percorso professionale nel settore immobiliare, con formazione, strumenti digitali, metodo operativo e affiancamento.\n\nSe hai già esperienza possiamo valorizzarla. Se parti da zero, possiamo valutare insieme il percorso più adatto.\n\nInvia il tuo curriculum a f1immobiliaresusa@outlook.it\nOggetto: CANDIDATURA\n371 370 8294\n\n#F1Immobiliare #LavoraConNoi #AgenteImmobiliare #Immobiliare #ValleDiSusa #TorinoOvest"""

RMP_MAIN_CAPTION = """IL TUO SITO AIUTA DAVVERO A VENDERE?\n\nUn sito efficace non è solo bello: deve rendere chiara l'offerta, guidare la persona e facilitare il contatto o l'acquisto. Real Media Pro collega sito, social, e-commerce e percorso commerciale in una strategia misurabile.\n\nRichiedi un'analisi strategica gratuita.\n371 370 8294\n\n#RealMediaPro #SitiWeb #Ecommerce #Shopify #DigitalMarketing #Torino #ValleDiSusa"""

RMP_RECRUIT_CAPTION = """LAVORA CON REAL MEDIA PRO.\n\nTi interessano social media, comunicazione digitale, siti web, e-commerce e marketing? Real Media Pro valuta nuove collaborazioni con persone concrete, organizzate e interessate a crescere su progetti digitali reali.\n\nSe vuoi proporti, contattaci e presentaci le tue competenze e il tipo di collaborazione che stai cercando.\n\nInformazioni: 371 370 8294\n\n#RealMediaPro #LavoraConNoi #DigitalMarketing #SocialMedia #Ecommerce #SitiWeb #Torino"""


def platform_specs() -> list[dict[str, str]]:
    return [{"platform": p, "integration_id": "direct-api"} for p in STATIC_PLATFORMS]


def main() -> int:
    q = json.loads(QUEUE.read_text(encoding="utf-8"))
    key = q.get("current_cycle")
    jobs = [j for j in q.get("jobs", []) if j.get("cycle_key") == key]
    if len(jobs) != 4:
        raise RuntimeError(f"Expected 4 jobs in current cycle, got {len(jobs)}")

    for j in jobs:
        cid = str(j.get("client_id") or "")
        pos = int(j.get("cycle_position", 1))
        j["format"] = "photo"
        j["publication_ready"] = False
        j["output_type"] = "static-photo"
        j["no_video"] = True
        j["no_audio"] = True
        j["no_reel"] = True
        j["manual_image_required_for_auto_publish"] = True
        j["platforms"] = platform_specs()
        j["auto_publish_skipped_platforms"] = ["tiktok", "youtube"]
        for field in ("image_change_seconds", "reel_duration_seconds", "target_reel_seconds"):
            j.pop(field, None)

        if cid == "f1-immobiliare" and pos == 1:
            j["title"] = "CASE IN VALLE DI SUSA · VALUTAZIONE IMMOBILIARE"
            j["caption"] = F1_HOME_CAPTION
            j["visual_mode"] = "valle-di-susa-homes-photo"
            j["manual_folder"] = "publisher/manual_images/f1-immobiliare"
            j["content_source"] = "F1 MAIN FOLDER"
            j["search_query_override"] = "case in Valle di Susa"
        elif cid == "f1-immobiliare" and pos == 2:
            j["title"] = "LAVORA CON F1 IMMOBILIARE"
            j["caption"] = F1_RECRUIT_CAPTION
            j["visual_mode"] = "f1-recruiting-photo"
            j["manual_folder"] = "publisher/manual_images/f1-immobiliare/RIC LAVORO F1"
            j["content_source"] = "RIC LAVORO F1"
            j["search_query_override"] = "real estate professional office Italy"
        elif cid == "real-media-pro" and pos == 1:
            j["title"] = "REAL MEDIA PRO · STRATEGIA DIGITALE"
            j["caption"] = RMP_MAIN_CAPTION
            j["visual_mode"] = "rmp-ecommerce-photo"
            j["manual_folder"] = "publisher/manual_images/real-media-pro"
            j["content_source"] = "RMP MAIN FOLDER"
            j["design_reference_url"] = "https://themes.shopify.com/?locale=it"
            j["search_query_override"] = "ecommerce website laptop premium workspace"
        elif cid == "real-media-pro" and pos == 2:
            j["title"] = "LAVORA CON REAL MEDIA PRO"
            j["caption"] = RMP_RECRUIT_CAPTION
            j["visual_mode"] = "rmp-recruiting-photo"
            j["manual_folder"] = "publisher/manual_images/real-media-pro/RIC LAVORO RMP"
            j["content_source"] = "RIC LAVORO RMP"
            j["search_query_override"] = "digital marketing professional team workspace"
        else:
            raise RuntimeError(f"Unexpected cycle slot: {cid} position {pos}")

        j["status"] = "awaiting_manual_image"
        j["blocked_reason"] = f"carica una foto in {j['manual_folder']} per abilitare la pubblicazione automatica"

    q["output_policy"] = "4 STATIC PHOTOS - 4 MANUAL FOLDERS - AUTOMATIC SOCIAL PUBLISHING"
    q["photo_policy"] = {
        "contents_per_cycle": 4,
        "f1": ["main folder", "RIC LAVORO F1"],
        "real_media_pro": ["main folder", "RIC LAVORO RMP"],
        "automatic_platforms": STATIC_PLATFORMS,
        "skipped_photo_platforms": ["tiktok", "youtube"],
        "manual_image_required_for_auto_publish": True,
        "video": False,
        "audio": False,
    }
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("4-folder policy applied: 4 static posts; manual image required for automatic publication")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
