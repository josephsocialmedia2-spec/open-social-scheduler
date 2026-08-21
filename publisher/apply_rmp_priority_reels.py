#!/usr/bin/env python3
"""Lock Real Media Pro Reel slots to original Shopify-Theme-Store-inspired ecommerce visuals.

The Shopify Theme Store is a DESIGN REFERENCE only. The renderer must create original
layouts from reusable/licensed product photography; it must never copy a Shopify theme
preview pixel-for-pixel or republish protected theme screenshots.

Every RMP Reel: 10 original frames, hard image change every 2 seconds, 20 seconds total.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
PHONE = "371 370 8294"
REFERENCE = "https://themes.shopify.com/?locale=it"


def load() -> dict:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def caption_site() -> str:
    return (
        "IL TUO SITO PORTA CLIENTI O È SOLO BELLO DA VEDERE?\n\n"
        "Un e-commerce efficace deve essere chiaro, veloce da smartphone e costruito per accompagnare "
        "la persona dalla scoperta del prodotto fino al contatto o all'acquisto. Design, pagine prodotto, "
        "fiducia, checkout e misurazione devono lavorare insieme.\n\n"
        "Real Media Pro progetta siti ed e-commerce con una logica commerciale, non semplicemente grafica.\n\n"
        f"Richiedi un'analisi strategica: {PHONE}\n\n"
        "#RealMediaPro #Shopify #Ecommerce #SitiWeb #DigitalMarketing #MarketingDigitale #AziendeLocali"
    )


def caption_shopify() -> str:
    return (
        "SHOPIFY È GIUSTO PER LA TUA ATTIVITÀ?\n\n"
        "La piattaforma è solo una parte del risultato. Prima servono una proposta chiara, un catalogo ben "
        "organizzato, pagine prodotto credibili, un'esperienza mobile semplice e un percorso di acquisto senza "
        "attriti. Poi si collegano traffico, social e misurazione.\n\n"
        "Real Media Pro costruisce il sistema digitale intorno agli obiettivi reali dell'azienda.\n\n"
        f"Richiedi un'analisi strategica: {PHONE}\n\n"
        "#RealMediaPro #Shopify #Ecommerce #SitiWeb #SocialMediaManager #DigitalMarketing #Torino #ValleDiSusa"
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
            and str(j.get("client_id") or "") == "real-media-pro"
            and str(j.get("format") or "") == "reel"
        ],
        key=lambda j: int(j.get("cycle_position", 0)),
    )
    if len(reels) != 2:
        raise SystemExit(f"Expected exactly 2 RMP reels in current cycle, got {len(reels)}")

    common = {
        "visual_mode": "shopify-theme-inspired-original",
        "design_reference_url": REFERENCE,
        "design_reference_rule": "Use Shopify Theme Store only for high-level layout inspiration. Create original visuals; never copy theme screenshots or branding.",
        "source_mode": "original-ecommerce-layout-from-licensed-product-photography",
        "images_per_reel": 10,
        "reel_duration_seconds": 20,
        "image_change_seconds": 2,
        "fixed_header_text": "REAL MEDIA PRO",
        "fixed_contact_text": f"SITI • ECOMMERCE • SHOPIFY  |  {PHONE}",
        "show_presenter": False,
        "slides": [""] * 10,
        "search_queries": [
            "fashion product minimal ecommerce",
            "skincare cosmetics product minimal",
            "jewelry accessories product minimal",
            "home decor furniture minimal product",
            "stationery notebook product minimal",
            "tech accessories product minimal",
            "gourmet food product minimal",
            "wellness beauty product minimal",
            "creator digital tools workspace minimal",
            "home living lifestyle product minimal",
        ],
    }

    first = reels[0]
    first.update(common)
    first.update({
        "content_pillar": "website-conversion",
        "title": "IL TUO SITO PORTA CLIENTI?",
        "research_query": "Shopify Theme Store ecommerce design conversion",
        "caption": caption_site(),
        "voiceover": (
            "Il tuo sito porta clienti o è solo bello da vedere? Un e-commerce efficace deve essere chiaro, "
            "veloce da smartphone e semplice da usare. Pagina prodotto, fiducia, checkout e percorso d'acquisto "
            "devono lavorare insieme. Real Media Pro costruisce siti ed e-commerce con una logica commerciale."
        ),
        "production_status": "RMP SHOPIFY-INSPIRED ORIGINAL REEL - 2 SEC PER IMMAGINE",
    })

    second = reels[1]
    second.update(common)
    second.update({
        "content_pillar": "shopify-ecommerce",
        "title": "SHOPIFY È GIUSTO PER LA TUA ATTIVITÀ?",
        "research_query": "Shopify ecommerce business mobile product checkout",
        "caption": caption_shopify(),
        "voiceover": (
            "Shopify è giusto per la tua attività? La piattaforma da sola non basta. Servono catalogo chiaro, "
            "pagine prodotto credibili, esperienza mobile semplice, checkout senza attriti e una strategia per "
            "portare traffico qualificato. Real Media Pro costruisce il sistema digitale intorno agli obiettivi dell'azienda."
        ),
        "production_status": "RMP SHOPIFY-INSPIRED ORIGINAL REEL - 2 SEC PER IMMAGINE",
    })

    data["rmp_reel_policy"] = {
        "reels_per_cycle": 2,
        "design_reference": REFERENCE,
        "reference_is_inspiration_only": True,
        "original_images_required": True,
        "images_per_reel": 10,
        "image_change_seconds": 2,
        "duration_seconds": 20,
        "captions_ready_for_publication": True,
    }
    data["updated_by"] = "F1 + RMP priority Reel policy"
    save(data)
    print("RMP current cycle locked: 2 original Shopify-inspired Reels, 10 images x 2 seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
