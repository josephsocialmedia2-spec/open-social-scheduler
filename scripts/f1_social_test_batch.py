#!/usr/bin/env python3
"""One-off controlled social publication test for F1 Content Hub.

Creates one ~60s narrated 9:16 video per configured client from a Pexels
source, burns captions from the exact narration, uploads the assets to
Supabase Storage, creates/updates Content Hub items, and schedules ONLY
channels that are both enabled and verified.

TikTok is deliberately blocked when the same TikTok account is mapped to
multiple clients, preventing cross-client publication.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "publisher" / "media" / "test-social-batch"
RUNTIME = ROOT / "reports" / "f1-social-test-runtime.json"
REPORT = ROOT / "reports" / "f1-social-test-latest.json"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://nqnmlsmeiynxbdojeyjt.supabase.co").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
BUCKET = "f1-content-media"
BATCH = "F1_SOCIAL_TEST_20260926"

CLIENTS: dict[str, dict[str, Any]] = {
    "antica-cappella": {
        "sector": "Ristorazione",
        "territory": "Avigliana · Valle di Susa",
        "pexels_id": 856621,
        "source_url": "https://www.pexels.com/video/time-lapse-video-of-preparing-food-856621/",
        "source_author": "Pexels contributor",
        "title": "Antica Cappella · esperienza e territorio",
        "script": (
            "Ad Avigliana, un'esperienza al ristorante nasce dall'incontro tra cucina, accoglienza e territorio. "
            "Antica Cappella racconta una tradizione gastronomica legata al Piemonte, con attenzione alla tavola, "
            "ai momenti da condividere e agli eventi. Ogni occasione, da una cena a una ricorrenza, merita cura nei "
            "dettagli, tempi giusti e un ambiente capace di far sentire gli ospiti a proprio agio. La cucina non è "
            "soltanto ciò che arriva nel piatto: è anche servizio, atmosfera e piacere di stare insieme. Se stai "
            "organizzando un pranzo, una cena o un evento ad Avigliana e vuoi conoscere proposte e disponibilità, "
            "contatta Antica Cappella e richiedi le informazioni utili per scegliere con calma."
        ),
        "hashtags": "#AnticaCappella #Avigliana #ValleDiSusa #Ristorazione #CucinaPiemontese",
    },
    "cartolibreria-10-e-lode": {
        "sector": "Cartoleria · scuola · cancelleria",
        "territory": "Susa · Valle di Susa",
        "pexels_id": 7055548,
        "source_url": "https://www.pexels.com/video/animation-of-school-supplies-7055548/",
        "source_author": "Kindel Media",
        "title": "10 e Lode · organizzare scuola e lavoro",
        "script": (
            "Una buona organizzazione comincia spesso dalle cose più semplici: una penna che scrive bene, un quaderno "
            "adatto, materiali ordinati e gli strumenti giusti per scuola, studio e lavoro. In cartoleria ogni esigenza "
            "può essere diversa: c'è chi prepara lo zaino, chi organizza l'ufficio, chi cerca materiale creativo o un "
            "piccolo articolo utile per tutti i giorni. Cartolibreria 10 e Lode è un punto di riferimento locale a "
            "Susa per chi vuole scegliere con maggiore attenzione ciò che serve. Prima di acquistare, valuta sempre "
            "l'uso reale del prodotto, la praticità e la possibilità di riutilizzarlo nel tempo. Per disponibilità, "
            "novità e informazioni sui prodotti, contatta direttamente Cartolibreria 10 e Lode."
        ),
        "hashtags": "#Cartolibreria10eLode #Susa #ValleDiSusa #Cartoleria #Scuola #Cancelleria",
    },
    "f1-immobiliare": {
        "sector": "Immobiliare",
        "territory": "Provincia di Torino · Valle di Susa",
        "pexels_id": 34641783,
        "source_url": "https://www.pexels.com/video/modern-green-apartment-building-exterior-34641783/",
        "source_author": "Pexels contributor",
        "title": "F1 Immobiliare · prima i dati",
        "script": (
            "Vendere casa non dovrebbe iniziare da un prezzo scelto a sensazione. Prima servono dati, comparabili, "
            "microzona, concorrenza e domanda reale. F1 Immobiliare lavora in Provincia di Torino e in Valle di Susa "
            "con un principio semplice: prima i dati, poi la strategia, poi la vendita. Il prezzo non si indovina, si "
            "verifica. Una valutazione utile deve aiutare il proprietario a capire perché un immobile può essere "
            "posizionato in un certo modo e quali elementi possono favorire o rallentare la vendita. Anche la "
            "presentazione dell'immobile, il piano di comunicazione e la gestione delle visite fanno parte della "
            "strategia. Se stai pensando di vendere, richiedi un'analisi del valore del tuo immobile e parti da "
            "informazioni verificabili."
        ),
        "hashtags": "#F1Immobiliare #ValleDiSusa #ProvinciaDiTorino #VendereCasa #ValutazioneImmobiliare #Avigliana",
    },
    "immobiliare-la-sacra": {
        "sector": "Immobiliare",
        "territory": "Valle di Susa · Provincia di Torino",
        "pexels_id": 5801020,
        "source_url": "https://www.pexels.com/video/apartment-building-facade-5801020/",
        "source_author": "Peggy Anke",
        "title": "Immobiliare La Sacra · casa e territorio",
        "script": (
            "Quando si vende o si acquista casa, conoscere il territorio è importante quanto conoscere l'immobile. "
            "In Valle di Susa e in Provincia di Torino cambiano microzone, servizi, collegamenti, tipologie abitative "
            "e richieste delle famiglie. Immobiliare La Sacra segue il percorso immobiliare mettendo insieme le "
            "caratteristiche della casa e il contesto in cui si trova. Una visita efficace parte da informazioni "
            "chiare: distribuzione degli spazi, stato dell'immobile, posizione, documentazione disponibile e condizioni "
            "della vendita. Per chi vende, una presentazione ordinata aiuta gli interessati a capire meglio la proposta. "
            "Per chi cerca casa, una selezione coerente evita visite inutili. Se vuoi informazioni su un immobile o "
            "desideri prenotare una visita, contatta Immobiliare La Sacra."
        ),
        "hashtags": "#ImmobiliareLaSacra #ValleDiSusa #ProvinciaDiTorino #SantAmbrogioDiTorino #CasaInVendita",
    },
    "marta-ruffino": {
        "sector": "Salute · riabilitazione del pavimento pelvico",
        "territory": "Provincia di Torino",
        "pexels_id": 8032667,
        "source_url": "https://www.pexels.com/video/exercise-equipment-8032667/",
        "source_author": "MART PRODUCTION",
        "title": "Marta Ruffino · consapevolezza del pavimento pelvico",
        "script": (
            "Parlare di pavimento pelvico significa prima di tutto parlare di consapevolezza del proprio corpo. "
            "È un'area che partecipa a funzioni quotidiane e che merita attenzione nelle diverse fasi della vita. "
            "Non esiste però un esercizio universale adatto a tutte le persone: sintomi, esigenze e storia personale "
            "possono essere differenti. Per questo, quando ci sono dubbi o disturbi, è utile rivolgersi a un "
            "professionista qualificato per una valutazione individuale, evitando soluzioni improvvisate. "
            "Informarsi correttamente aiuta anche a riconoscere quando è il momento di chiedere supporto. Marta Ruffino "
            "si occupa di riabilitazione del pavimento pelvico in Provincia di Torino. Per informazioni sul percorso "
            "professionale e sulle modalità di accesso, richiedi un contatto dedicato."
        ),
        "hashtags": "#MartaRuffino #PavimentoPelvico #RiabilitazionePelvica #ProvinciaDiTorino #SaluteDonna",
    },
    "real-media-pro": {
        "sector": "Web agency · marketing digitale",
        "territory": "Torino · Rivoli · Avigliana · Valle di Susa",
        "pexels_id": 8473808,
        "source_url": "https://www.pexels.com/video/cellphone-on-a-laptop-8473808/",
        "source_author": "Cup of Couple",
        "title": "Real Media Pro · dalla visibilità alla crescita",
        "script": (
            "Pubblicare sui social non significa semplicemente riempire un calendario. Una strategia digitale efficace "
            "collega contenuti, sito, acquisizione dei contatti e misurazione dei risultati. Real Media Pro lavora su "
            "social media, contenuti, siti ed e-commerce con l'obiettivo di costruire un percorso coerente tra ciò che "
            "un'attività comunica e ciò che vuole ottenere. Prima si definiscono pubblico, offerta e messaggio; poi si "
            "producono i contenuti, si distribuiscono sui canali corretti e si osservano i dati. Anche automazione e "
            "organizzazione aiutano a ridurre attività ripetitive e mantenere continuità. Per attività di Torino, Rivoli, "
            "Avigliana e Valle di Susa, il punto di partenza può essere un'analisi della presenza digitale e delle "
            "opportunità concrete di miglioramento."
        ),
        "hashtags": "#RealMediaPro #MarketingDigitale #Torino #Rivoli #Avigliana #ValleDiSusa",
    },
}

PROFILE_URLS = {
    "f1-immobiliare": {
        "facebook": "https://www.facebook.com/F1ImmobiliareValdiSusa",
        "instagram": "https://www.instagram.com/joseph_malafronte/",
        "tiktok": "https://www.tiktok.com/@f1immobiliare",
        "youtube": "https://www.youtube.com/@F1Immobiliare",
        "linkedin-page": "https://www.linkedin.com/in/josephmalafronte/",
    },
    "antica-cappella": {
        "instagram": "https://www.instagram.com/anticacappellaristorante/",
        "facebook": "https://www.facebook.com/profile.php?id=61550077453442",
    },
}

def die(msg: str) -> None:
    raise RuntimeError(msg)

def headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    if not SERVICE_KEY:
        die("SUPABASE_SERVICE_ROLE_KEY missing")
    h = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h

def rest_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers(), params=params, timeout=60)
    if not r.ok:
        die(f"GET {table}: {r.status_code} {r.text[:800]}")
    return r.json()

def rest_post(table: str, payload: Any, *, return_representation: bool = False) -> Any:
    prefer = "return=representation" if return_representation else "return=minimal"
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": prefer}),
        json=payload,
        timeout=60,
    )
    if not r.ok:
        die(f"POST {table}: {r.status_code} {r.text[:1000]}")
    if return_representation:
        data = r.json()
        return data[0] if isinstance(data, list) and data else data
    return None

def rest_patch(table: str, match: dict[str, str], payload: dict[str, Any]) -> None:
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params=params,
        json=payload,
        timeout=60,
    )
    if not r.ok:
        die(f"PATCH {table}: {r.status_code} {r.text[:1000]}")

def storage_upload(path: str, data: bytes, content_type: str) -> None:
    encoded = "/".join(quote(x, safe="") for x in path.split("/"))
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{encoded}"
    h = headers({"Content-Type": content_type, "x-upsert": "true"})
    r = requests.post(url, headers=h, data=data, timeout=300)
    if not r.ok:
        # Some Storage gateways accept PUT for the same endpoint.
        r = requests.put(url, headers=h, data=data, timeout=300)
    if not r.ok:
        die(f"Storage upload {path}: {r.status_code} {r.text[:1000]}")

def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None)

def duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True,
    )
    return float(out.strip())

def download_pexels(video_id: int, page_url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/153 Safari/537.36",
        "Accept": "*/*",
    })
    candidates = [
        f"https://www.pexels.com/download/video/{video_id}/",
        f"https://www.pexels.com/download/video/{video_id}",
    ]
    for url in candidates:
        try:
            with session.get(url, stream=True, allow_redirects=True, timeout=120) as r:
                ctype = r.headers.get("content-type", "").lower()
                if r.ok and ("video" in ctype or "octet-stream" in ctype):
                    with dest.open("wb") as fh:
                        for chunk in r.iter_content(1024 * 1024):
                            if chunk:
                                fh.write(chunk)
                    if dest.stat().st_size > 100_000:
                        return
        except Exception as exc:
            print("WARN direct Pexels download", exc)

    page = session.get(page_url, timeout=60)
    page.raise_for_status()
    urls = re.findall(r'https://videos\.pexels\.com/video-files/[^"\'<> ]+?\.mp4[^"\'<> ]*', page.text)
    if not urls:
        die(f"Could not resolve MP4 for Pexels video {video_id}")
    # Prefer the first downloadable file; the final renderer normalizes it to 9:16 Full HD.
    url = urls[0].replace("\\u0026", "&").replace("&amp;", "&")
    with session.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    fh.write(chunk)
    if dest.stat().st_size < 100_000:
        die(f"Downloaded Pexels video {video_id} is unexpectedly small")

def chunks(text: str, max_words: int = 8) -> list[str]:
    words = text.split()
    out: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        if len(current) >= max_words or re.search(r"[.!?]$", word):
            out.append(" ".join(current))
            current = []
    if current:
        out.append(" ".join(current))
    return out

def srt_time(seconds: float, vtt: bool = False) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"

def make_subtitles(text: str, seconds: float, srt: Path, vtt: Path) -> None:
    parts = chunks(text)
    weights = [max(1, len(p.split())) for p in parts]
    total = sum(weights)
    t = 0.0
    srt_rows: list[str] = []
    vtt_rows: list[str] = ["WEBVTT", ""]
    for idx, (part, weight) in enumerate(zip(parts, weights), 1):
        start = t
        end = seconds if idx == len(parts) else min(seconds, t + seconds * weight / total)
        t = end
        srt_rows += [str(idx), f"{srt_time(start)} --> {srt_time(end)}", part, ""]
        vtt_rows += [f"{srt_time(start, True)} --> {srt_time(end, True)}", part, ""]
    srt.write_text("\n".join(srt_rows), encoding="utf-8")
    vtt.write_text("\n".join(vtt_rows), encoding="utf-8")

def generate_video(slug: str, cfg: dict[str, Any]) -> dict[str, Any]:
    client_dir = WORK / slug
    client_dir.mkdir(parents=True, exist_ok=True)
    stock = client_dir / "stock.mp4"
    wav = client_dir / "voice.wav"
    srt = client_dir / "captions.srt"
    vtt = client_dir / "captions.vtt"
    final = client_dir / "final.mp4"

    download_pexels(int(cfg["pexels_id"]), str(cfg["source_url"]), stock)
    speaker = shutil.which("espeak-ng") or shutil.which("espeak")
    if not speaker:
        die("espeak/espeak-ng missing")
    run([speaker, "-v", "it", "-s", "142", "-w", str(wav), str(cfg["script"])])
    audio_seconds = duration(wav)
    if not 42 <= audio_seconds <= 80:
        print(f"WARN {slug}: narration duration {audio_seconds:.1f}s is outside preferred 45-75s")
    make_subtitles(str(cfg["script"]), audio_seconds, srt, vtt)

    # File paths are simple and under the working directory, so ffmpeg subtitle escaping is deterministic.
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,fps=30,"
        "subtitles=captions.srt:"
        "force_style='FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H80000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=170,Alignment=2'"
    )
    run([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", stock.name, "-i", wav.name,
        "-map", "0:v:0", "-map", "1:a:0", "-vf", vf,
        "-t", f"{audio_seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", final.name,
    ], cwd=client_dir)
    return {
        "final": final,
        "srt": srt,
        "vtt": vtt,
        "stock": stock,
        "duration": duration(final),
    }

def get_clients() -> dict[str, dict[str, Any]]:
    rows = rest_get("f1_content_clients", {
        "select": "id,owner_id,name,slug,auto_publish,approval_required,timezone,facebook,instagram,linkedin,tiktok,youtube",
        "status": "eq.ATTIVO",
        "limit": "100",
    })
    return {str(x["slug"]): x for x in rows if str(x.get("slug")) in CLIENTS}

def get_channels() -> list[dict[str, Any]]:
    return rest_get("f1_client_social_channels", {
        "select": "client_id,platform,provider,external_channel_id,account_name,enabled,verified,connection_status,scopes",
        "limit": "1000",
    })

def normalized_platform(p: str) -> str:
    return "linkedin-page" if p == "linkedin" else p

def connected_targets(client: dict[str, Any], channels: list[dict[str, Any]], duplicate_tiktok_ids: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    rows = [x for x in channels if str(x.get("client_id")) == str(client["id"])]
    for row in rows:
        p = normalized_platform(str(row.get("platform") or ""))
        reason = ""
        if not (row.get("enabled") and row.get("verified")):
            reason = str(row.get("connection_status") or "NON_COLLEGATO")
        elif p == "tiktok" and str(row.get("external_channel_id") or "") in duplicate_tiktok_ids:
            reason = "ACCOUNT_TIKTOK_CONDIVISO_TRA_CLIENTI"
        if reason:
            blocked.append({"platform": p, "reason": reason, "account_name": row.get("account_name")})
            continue
        if p in {"facebook", "instagram", "linkedin-page", "youtube", "tiktok"}:
            selected.append(row)
    return selected, blocked

def upsert_content(client: dict[str, Any], cfg: dict[str, Any], assets: dict[str, Any]) -> str:
    marker = f"{BATCH}:{client['slug']}"
    existing = rest_get("f1_content_items", {
        "select": "id,status",
        "client_id": f"eq.{client['id']}",
        "campaign": f"eq.{marker}",
        "limit": "1",
    })
    caption = str(cfg["script"]).strip() + "\n\n" + str(cfg["hashtags"]).strip()
    notes = (
        f"TEST OPERATIVO. Video stock Pexels: {cfg['source_url']} | "
        f"Licenza: https://www.pexels.com/license/ | autore: {cfg['source_author']} | "
        f"audio: narrazione italiana generata dal testo source_text; sottotitoli SRT/VTT sincronizzati "
        f"e burn-in sul video. Durata: {assets['duration']:.2f}s."
    )
    payload = {
        "owner_id": client["owner_id"],
        "client_id": client["id"],
        "title": cfg["title"],
        "description": caption,
        "content_type": "VIDEO",
        "source": "PEXELS_LICENSED_TEST",
        "status": "APPROVATO",
        "priority": "NORMALE",
        "campaign": marker,
        "tags": [x.lstrip("#") for x in str(cfg["hashtags"]).split() if x.startswith("#")],
        "notes": notes,
        "location": cfg["territory"],
        "source_text": cfg["script"],
        "tiktok_settings": {},
    }
    if existing:
        content_id = str(existing[0]["id"])
        rest_patch("f1_content_items", {"id": content_id}, payload)
        return content_id
    row = rest_post("f1_content_items", payload, return_representation=True)
    return str(row["id"])

def upload_assets(client: dict[str, Any], content_id: str, cfg: dict[str, Any], assets: dict[str, Any]) -> str:
    base = f"{client['owner_id']}/{client['id']}/{content_id}/test-social"
    video_path = f"{base}/{client['slug']}-test.mp4"
    srt_path = f"{base}/{client['slug']}-captions.srt"
    vtt_path = f"{base}/{client['slug']}-captions.vtt"
    storage_upload(video_path, Path(assets["final"]).read_bytes(), "video/mp4")
    storage_upload(srt_path, Path(assets["srt"]).read_bytes(), "application/x-subrip")
    storage_upload(vtt_path, Path(assets["vtt"]).read_bytes(), "text/vtt")

    media = rest_get("f1_content_media", {
        "select": "id",
        "content_id": f"eq.{content_id}",
        "file_name": f"eq.{client['slug']}-test.mp4",
        "limit": "1",
    })
    payload = {
        "owner_id": client["owner_id"],
        "content_id": content_id,
        "client_id": client["id"],
        "file_name": f"{client['slug']}-test.mp4",
        "mime_type": "video/mp4",
        "storage_path": video_path,
        "file_size": Path(assets["final"]).stat().st_size,
        "source": "PEXELS_LICENSED_TEST",
    }
    if media:
        rest_patch("f1_content_media", {"id": str(media[0]["id"])}, payload)
    else:
        rest_post("f1_content_media", payload)
    return video_path

def schedule(client: dict[str, Any], content_id: str, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for ch in targets:
        p = normalized_platform(str(ch["platform"]))
        existing = rest_get("f1_content_calendar", {
            "select": "id,status,external_url,external_post_id",
            "content_id": f"eq.{content_id}",
            "platform": f"eq.{p}",
            "limit": "1",
        })
        if existing and str(existing[0].get("status")) == "PUBBLICATO":
            out.append({"platform": p, "calendar_id": existing[0]["id"], "status": "PUBBLICATO", "reused": True})
            continue
        payload = {
            "owner_id": client["owner_id"],
            "content_id": content_id,
            "client_id": client["id"],
            "platform": p,
            "publication_at": now,
            "status": "PROGRAMMATO",
            "provider": ch.get("provider") or "direct",
            "retry_count": 0,
            "error": None,
            "platform_metadata": {
                "test_batch": BATCH,
                "expected_account_name": ch.get("account_name"),
                "expected_channel_id": ch.get("external_channel_id"),
            },
        }
        if existing:
            cid = str(existing[0]["id"])
            rest_patch("f1_content_calendar", {"id": cid}, payload)
        else:
            row = rest_post("f1_content_calendar", payload, return_representation=True)
            cid = str(row["id"])
        out.append({"platform": p, "calendar_id": cid, "status": "PROGRAMMATO", "provider": ch.get("provider")})
    return out

def generate() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    clients = get_clients()
    missing = sorted(set(CLIENTS) - set(clients))
    if missing:
        die("Missing clients in Supabase: " + ", ".join(missing))
    channels = get_channels()

    # Detect the exact failure mode observed during the audit: one TikTok account mapped to multiple clients.
    tiktok_owners: dict[str, set[str]] = {}
    for row in channels:
        if str(row.get("platform")) != "tiktok" or not row.get("enabled") or not row.get("verified"):
            continue
        ext = str(row.get("external_channel_id") or "")
        if ext:
            tiktok_owners.setdefault(ext, set()).add(str(row.get("client_id")))
    duplicate_tiktok_ids = {k for k, owners in tiktok_owners.items() if len(owners) > 1}

    runtime = {
        "batch": BATCH,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "original_auto_publish": {},
        "clients": {},
        "duplicate_tiktok_ids": sorted(duplicate_tiktok_ids),
    }
    RUNTIME.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for slug, cfg in CLIENTS.items():
        client = clients[slug]
        print(f"\n=== {client['name']} ===")
        assets = generate_video(slug, cfg)
        content_id = upsert_content(client, cfg, assets)
        storage_path = upload_assets(client, content_id, cfg, assets)
        selected, blocked = connected_targets(client, channels, duplicate_tiktok_ids)

        # Enable auto-publish only for this controlled batch, then restore it in an always() workflow step.
        if selected and not bool(client.get("auto_publish")):
            runtime["original_auto_publish"][str(client["id"])] = False
            rest_patch("f1_content_clients", {"id": str(client["id"])}, {"auto_publish": True})

        calendars = schedule(client, content_id, selected)
        runtime["clients"][slug] = {
            "name": client["name"],
            "sector": cfg["sector"],
            "territory": cfg["territory"],
            "source_url": cfg["source_url"],
            "license_url": "https://www.pexels.com/license/",
            "source_author": cfg["source_author"],
            "duration": assets["duration"],
            "transcript": cfg["script"],
            "caption": cfg["script"] + "\n\n" + cfg["hashtags"],
            "storage_path": storage_path,
            "content_id": content_id,
            "calendars": calendars,
            "blocked_channels": blocked,
            "profile_urls": PROFILE_URLS.get(slug, {}),
        }
        RUNTIME.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(runtime, ensure_ascii=False, indent=2))

def restore() -> None:
    if not RUNTIME.exists():
        print("No runtime manifest; nothing to restore.")
        return
    data = json.loads(RUNTIME.read_text(encoding="utf-8"))
    for client_id, original in (data.get("original_auto_publish") or {}).items():
        rest_patch("f1_content_clients", {"id": client_id}, {"auto_publish": bool(original)})
    print("Restored auto_publish flags.")

def report() -> None:
    if not RUNTIME.exists():
        die("Runtime manifest missing")
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    final = {
        "batch": runtime["batch"],
        "reported_at": datetime.now(timezone.utc).isoformat(),
        "clients": {},
    }
    for slug, info in runtime["clients"].items():
        rows = rest_get("f1_content_calendar", {
            "select": "id,platform,status,provider,external_post_id,external_url,error,platform_metadata,last_checked_at",
            "content_id": f"eq.{info['content_id']}",
            "order": "platform.asc",
        })
        final["clients"][slug] = {
            **info,
            "publication_rows": rows,
        }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(final, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["generate", "restore", "report"])
    args = ap.parse_args()
    if args.action == "generate":
        generate()
    elif args.action == "restore":
        restore()
    else:
        report()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
