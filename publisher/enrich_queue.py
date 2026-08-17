#!/usr/bin/env python3
"""Enrich prepared social jobs with long captions, local hashtags, phone CTA and ~60s voiceovers."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / 'publisher' / 'queue.json'
PHONE = '371 370 8294'


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def save(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def clean_voice(text: str) -> str:
    text = re.sub(r'https?://\S+', '', str(text or ''))
    text = re.sub(r'#[\wÀ-ÿ]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def local_tag(territory: str) -> str:
    value = re.sub(r'[^A-Za-zÀ-ÿ0-9]+', '', territory or '')
    return '#' + value if value else '#ValleDiSusa'


def f1_hashtags(territory: str) -> list[str]:
    return [
        '#F1Immobiliare', '#ValleDiSusa', local_tag(territory), '#VendereCasa',
        '#CasaInVendita', '#ValutazioneImmobiliare', '#MercatoImmobiliare',
        '#ImmobiliareTorino', '#TorinoOvest', '#PrimaIDati'
    ]


def rmp_hashtags(territory: str) -> list[str]:
    return [
        '#RealMediaPro', '#Shopify', '#SitiShopify', '#Ecommerce', '#SitiWeb',
        '#WebDesign', '#DigitalMarketing', '#MarketingDigitale', local_tag(territory),
        '#Torino', '#ValleDiSusa'
    ]


def ensure_hashtags(caption: str, tags: list[str]) -> str:
    base = re.sub(r'(?:\n\s*)?(?:#[\wÀ-ÿ]+\s*)+$', '', str(caption or '').strip()).strip()
    return base + '\n\n' + ' '.join(dict.fromkeys(tags))


def long_caption(job: dict[str, Any]) -> str:
    cid = str(job.get('client_id') or '')
    title = str(job.get('title') or '').strip()
    territory = str(job.get('territory') or '').strip()
    base = str(job.get('caption') or '').strip()
    if cid == 'f1-immobiliare':
        extra = (
            f"{title}. Quando si vende un immobile non basta pubblicare un annuncio e aspettare. "
            f"In {territory or 'Valle di Susa'} il risultato dipende dal valore reale dell'immobile, dalla microzona, "
            "dalla concorrenza presente in quel momento, dalla qualità della presentazione e dalla strategia con cui viene portato sul mercato. "
            "F1 Immobiliare parte dai dati, verifica il posizionamento e costruisce un percorso di vendita comprensibile e misurabile. "
            "Se stai pensando di vendere casa, prima di decidere il prezzo confrontiamoci sui numeri e sulle condizioni reali del mercato. "
            f"Contatto diretto e WhatsApp: {PHONE}."
        )
        tags = f1_hashtags(territory)
    else:
        extra = (
            f"{title}. Un sito Shopify deve essere più di una bella vetrina: deve spiegare l'offerta, funzionare bene da smartphone, "
            "ridurre i dubbi del cliente e accompagnarlo verso il contatto o l'acquisto. Real Media Pro lavora su struttura, pagine, "
            "user experience, call to action, contenuti, SEO, campagne e misurazione, mantenendo il sito al centro del sistema digitale. "
            "In questa fase i nostri contenuti mostrano soprattutto esempi e logiche applicabili a siti Shopify ed e-commerce. "
            "Se vuoi capire cosa migliorare nel tuo progetto digitale, richiedi un'analisi strategica. "
            f"Contatto diretto e WhatsApp: {PHONE}."
        )
        tags = rmp_hashtags(territory)
    merged = base
    if len(clean_voice(base)) < 430:
        merged = (base + '\n\n' + extra).strip()
    if PHONE not in merged:
        merged += f'\n\nWhatsApp / telefono: {PHONE}.'
    return ensure_hashtags(merged, tags)


def voiceover_60(job: dict[str, Any]) -> str:
    cid = str(job.get('client_id') or '')
    title = str(job.get('title') or '').strip()
    territory = str(job.get('territory') or '').strip()
    original = clean_voice(str(job.get('voiceover') or job.get('caption') or ''))
    if cid == 'f1-immobiliare':
        script = (
            f"{title}. {original} "
            f"Se stai pensando di vendere casa in {territory or 'Valle di Susa'}, fermati un momento prima di scegliere il prezzo o pubblicare l'annuncio. "
            "Due immobili apparentemente simili possono avere valori diversi per posizione, stato, piano, esposizione, domanda reale e concorrenza attiva. "
            "Per questo F1 Immobiliare parte dai dati: analizziamo la microzona, confrontiamo immobili realmente concorrenti, osserviamo il mercato e definiamo il posizionamento più coerente. "
            "Poi prepariamo la comunicazione, selezioniamo i canali e misuriamo le reazioni del mercato. L'obiettivo non è riempire internet di annunci, ma costruire una vendita con una logica precisa. "
            f"Vuoi capire da dove partire? Scrivici o chiama il {PHONE}. F1 Immobiliare: prima i dati, poi la strategia, poi la vendita."
        )
    else:
        script = (
            f"{title}. {original} "
            "Quando costruiamo o analizziamo un sito Shopify non guardiamo soltanto colori e grafica. Partiamo da ciò che deve fare il sito: presentare bene l'offerta, "
            "farsi capire in pochi secondi, funzionare da smartphone e portare il visitatore verso un'azione concreta. Controlliamo home page, pagine prodotto o servizio, navigazione, fiducia, "
            "call to action, velocità, SEO e collegamento con campagne e tracciamento. Un e-commerce può avere traffico e perdere comunque clienti se il percorso è confuso o crea attrito. "
            "Real Media Pro costruisce il sito come parte di un sistema: contenuti, advertising, dati e follow-up devono lavorare insieme. "
            f"Se vuoi capire cosa sta limitando il tuo progetto Shopify, scrivici o chiama il {PHONE} e richiedi un'analisi strategica."
        )
    words = clean_voice(script).split()
    # Keep narration in the range suitable for a 60-second Italian Reel.
    if len(words) > 165:
        words = words[:165]
    return ' '.join(words)


def main() -> int:
    if not QUEUE.exists():
        return 0
    data = load(QUEUE)
    changed = 0
    for job in data.get('jobs', []):
        if str(job.get('client_id') or '') not in {'f1-immobiliare', 'real-media-pro'}:
            continue
        if job.get('status') in {'published', 'disabled'}:
            continue
        job['caption'] = long_caption(job)
        job['voiceover'] = voiceover_60(job)
        job['phone'] = PHONE
        job['target_reel_seconds'] = 60
        changed += 1
    save(QUEUE, data)
    print(f'Enriched {changed} social job(s) with long captions, local hashtags, phone CTA and 60s voiceovers.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
