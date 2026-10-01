#!/usr/bin/env python3
"""F1 Social Intelligence autonomous content + agency worker.

Runs server-side. It:
- scans every active Content Hub tenant;
- keeps real-estate publication behind explicit approval;
- auto-prepares/schedules standard clients when verified channels exist;
- analyzes videos and burns subtitles when speech is detected;
- emits timeline events for the futuristic dashboard;
- processes queued real-estate directory jobs without an operator.

No public-client secrets are used here. SUPABASE_SERVICE_ROLE_KEY is read only
from the server-side environment / GitHub Actions secrets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import requests

try:
    from ddgs import DDGS
except Exception:
    DDGS = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
WHISPER_MODEL_NAME = os.getenv("F1_WHISPER_MODEL", "base").strip() or "base"
HEIC_BATCH_SIZE = max(1, int(os.getenv("F1_HEIC_BATCH_SIZE", "8")))
REQUEST_TIMEOUT = 90
ROME = ZoneInfo("Europe/Rome")
HEIC_EXTS = {".heic", ".heif"}
HEIC_MIMES = {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
CAPTION_PLATFORMS = ("facebook", "instagram", "tiktok", "youtube", "linkedin-page", "pinterest")
GRAPHIC_TEXT_LIMIT = max(300, int(os.getenv("F1_GRAPHIC_TEXT_LIMIT", "2600")))
OCR_MEDIA_LIMIT = max(1, int(os.getenv("F1_OCR_MEDIA_LIMIT", "4")))
PORTAL_DOMAINS = {
    "immobiliare.it", "idealista.it", "casa.it", "subito.it", "wikicasa.it",
    "trovacasa.it", "case24.it", "facebook.com", "instagram.com", "youtube.com",
}
DEFAULT_TIMES = {
    "facebook": "11:00",
    "instagram": "13:30",
    "tiktok": "18:30",
    "youtube": "21:00",
    "linkedin-page": "09:30",
    "pinterest": "16:00",
}
_model = None


class IntelligenceError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require_env() -> None:
    if not SUPABASE_URL or not SERVICE_KEY:
        raise IntelligenceError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY mancanti")


def headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    out = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        out.update(extra)
    return out


def rest_get(table: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers(),
        params=params or {},
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise IntelligenceError(f"GET {table}: {r.status_code} {r.text[:700]}")
    data = r.json()
    return data if isinstance(data, list) else []


def rest_post(
    table: str,
    payload: dict[str, Any] | list[dict[str, Any]],
    params: dict[str, str] | None = None,
    return_rows: bool = False,
) -> list[dict[str, Any]]:
    prefer = "return=representation" if return_rows else "return=minimal"
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": prefer}),
        params=params or {},
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise IntelligenceError(f"POST {table}: {r.status_code} {r.text[:700]}")
    if return_rows and r.text.strip():
        data = r.json()
        return data if isinstance(data, list) else []
    return []


def rest_patch(table: str, match: dict[str, str], payload: dict[str, Any]) -> None:
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params=params,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise IntelligenceError(f"PATCH {table}: {r.status_code} {r.text[:700]}")


def rest_delete(table: str, match: dict[str, str]) -> None:
    params = {k: f"eq.{v}" for k, v in match.items()}
    r = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer": "return=minimal"}),
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise IntelligenceError(f"DELETE {table}: {r.status_code} {r.text[:700]}")


def storage_download(storage_path: str, dest: Path) -> None:
    encoded = "/".join(quote(part, safe="") for part in storage_path.lstrip("/").split("/"))
    r = requests.get(
        f"{SUPABASE_URL}/storage/v1/object/f1-content-media/{encoded}",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
        timeout=180,
    )
    if not r.ok:
        raise IntelligenceError(f"Storage download: {r.status_code} {r.text[:400]}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    if dest.stat().st_size <= 0:
        raise IntelligenceError("Storage download vuoto")


def storage_upload(storage_path: str, src: Path, content_type: str) -> None:
    encoded = "/".join(quote(part, safe="") for part in storage_path.lstrip("/").split("/"))
    with src.open("rb") as fh:
        r = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/f1-content-media/{encoded}",
            headers={
                "apikey": SERVICE_KEY,
                "Authorization": f"Bearer {SERVICE_KEY}",
                "Content-Type": content_type,
                "x-upsert": "false",
            },
            data=fh,
            timeout=300,
        )
    if not r.ok:
        raise IntelligenceError(f"Storage upload: {r.status_code} {r.text[:500]}")


def storage_delete(storage_paths: list[str]) -> None:
    paths = [str(x).lstrip("/") for x in storage_paths if str(x or "").strip()]
    if not paths:
        return
    r = requests.delete(
        f"{SUPABASE_URL}/storage/v1/object/f1-content-media",
        headers=headers(),
        json={"prefixes": paths},
        timeout=REQUEST_TIMEOUT,
    )
    if not r.ok:
        raise IntelligenceError(f"Storage delete: {r.status_code} {r.text[:500]}")


def is_heic(media: dict[str, Any]) -> bool:
    name = str(media.get("file_name") or "")
    path = str(media.get("storage_path") or "")
    mime = str(media.get("mime_type") or "").lower()
    return Path(name).suffix.lower() in HEIC_EXTS or Path(path).suffix.lower() in HEIC_EXTS or mime in HEIC_MIMES


def is_video(media: dict[str, Any]) -> bool:
    mime = str(media.get("mime_type") or "").lower()
    suffix = Path(str(media.get("file_name") or media.get("storage_path") or "")).suffix.lower()
    return mime.startswith("video/") or suffix in VIDEO_EXTS


def is_image(media: dict[str, Any]) -> bool:
    mime = str(media.get("mime_type") or "").lower()
    suffix = Path(str(media.get("file_name") or media.get("storage_path") or "")).suffix.lower()
    return mime.startswith("image/") or suffix in IMAGE_EXTS


def is_real_estate(client: dict[str, Any]) -> bool:
    """Manual approval is reserved for real-estate clients/agencies.

    Do not treat a generic approval flag as proof of sector: the operator's
    policy is sector-based and non-real-estate clients must stay autonomous.
    """
    text = " ".join(
        str(client.get(k) or "") for k in ("category", "business_sector", "name", "slug")
    ).lower()
    return any(token in text for token in ("immobil", "real estate", "agenzia immobiliare"))


def ensure_job(
    owner_id: str,
    client_id: str,
    content_id: str | None,
    job_type: str,
    unique_key: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = rest_get(
        "f1_intelligence_jobs",
        {
            "select": "*",
            "owner_id": f"eq.{owner_id}",
            "unique_key": f"eq.{unique_key}",
            "limit": "1",
        },
    )
    if rows:
        return rows[0]
    created = rest_post(
        "f1_intelligence_jobs",
        {
            "owner_id": owner_id,
            "client_id": client_id,
            "content_id": content_id,
            "job_type": job_type,
            "unique_key": unique_key,
            "payload": payload or {},
        },
        return_rows=True,
    )
    if not created:
        raise IntelligenceError("Impossibile creare intelligence job")
    return created[0]


def parse_iso(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def job_is_available(job: dict[str, Any]) -> bool:
    now = datetime.now(timezone.utc)
    status = str(job.get("status") or "").upper()
    claimed = parse_iso(job.get("claimed_at"))
    run_after = parse_iso(job.get("run_after"))
    if status == "RUNNING" and claimed and claimed > now - timedelta(minutes=30):
        return False
    if status == "WAITING" and run_after and run_after > now:
        return False
    return True


def update_job(job: dict[str, Any], status: str, stage: str, **extra: Any) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "stage": stage,
        "updated_at": now_iso(),
    }
    payload.update(extra)
    rest_patch("f1_intelligence_jobs", {"id": str(job["id"])}, payload)
    job.update(payload)


def emit_event(
    owner_id: str,
    client_id: str,
    content_id: str | None,
    job_id: str | None,
    stage: str,
    status: str,
    message: str,
    progress: int,
    details: dict[str, Any] | None = None,
) -> None:
    params = {
        "select": "id",
        "owner_id": f"eq.{owner_id}",
        "client_id": f"eq.{client_id}",
        "stage": f"eq.{stage}",
        "status": f"eq.{status}",
        "order": "created_at.desc",
        "limit": "1",
    }
    if content_id:
        params["content_id"] = f"eq.{content_id}"
    existing = rest_get("f1_intelligence_events", params)
    if existing and status == "COMPLETED":
        return
    rest_post(
        "f1_intelligence_events",
        {
            "owner_id": owner_id,
            "client_id": client_id,
            "content_id": content_id,
            "job_id": job_id,
            "stage": stage,
            "status": status,
            "message": message,
            "progress": max(0, min(100, int(progress))),
            "details": details or {},
        },
    )


def convert_heic_media(
    client: dict[str, Any],
    item: dict[str, Any],
    media_rows: list[dict[str, Any]],
    job: dict[str, Any],
) -> list[dict[str, Any]]:
    heics = [m for m in media_rows if is_heic(m)]
    if not heics:
        return media_rows
    batch = heics[:HEIC_BATCH_SIZE]

    owner_id = str(item["owner_id"])
    client_id = str(item["client_id"])
    content_id = str(item["id"])
    from PIL import Image, ImageOps
    from pillow_heif import register_heif_opener

    register_heif_opener()
    out_rows = list(media_rows)

    for media in batch:
        emit_event(
            owner_id, client_id, content_id, str(job["id"]),
            "CONVERSIONE_HEIC", "RUNNING",
            f"Conversione automatica {media.get('file_name') or 'HEIC'} → PNG", 34,
        )
        stem = Path(str(media.get("file_name") or "immagine.heic")).stem
        existing = next(
            (
                x for x in out_rows
                if str(x.get("source") or "").upper() == "F1_INTELLIGENCE_HEIC_PNG"
                and Path(str(x.get("file_name") or "")).stem.lower() == stem.lower()
            ),
            None,
        )
        if existing:
            try:
                storage_delete([str(media.get("storage_path") or "")])
                rest_delete("f1_content_media", {"id": str(media["id"]), "owner_id": owner_id, "client_id": client_id})
                out_rows = [x for x in out_rows if str(x.get("id")) != str(media.get("id"))]
            except Exception as exc:
                print(f"WARN HEIC cleanup after reusable PNG: {exc}")
            continue

        with tempfile.TemporaryDirectory(prefix="f1-heic-") as td:
            td_path = Path(td)
            src = td_path / (str(media.get("file_name") or "input.heic"))
            png = td_path / (re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "immagine")
            png = png.with_suffix(".png")
            verify = td_path / "verify.png"

            storage_download(str(media["storage_path"]), src)
            with Image.open(src) as image:
                image = ImageOps.exif_transpose(image)
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                image.save(png, format="PNG", optimize=True)

            if not png.exists() or png.stat().st_size <= 0:
                raise IntelligenceError("Conversione HEIC → PNG ha prodotto un file vuoto")
            with Image.open(png) as check:
                check.verify()
            with Image.open(png) as check:
                width, height = check.size
                if width <= 0 or height <= 0:
                    raise IntelligenceError("PNG convertito senza dimensioni valide")

            filename = png.name
            storage_path = f"{owner_id}/{client_id}/{content_id}/intelligence-{uuid.uuid4().hex[:12]}-{filename}"
            storage_upload(storage_path, png, "image/png")
            storage_download(storage_path, verify)
            with Image.open(verify) as check:
                check.verify()

            created = rest_post(
                "f1_content_media",
                {
                    "owner_id": owner_id,
                    "content_id": content_id,
                    "client_id": client_id,
                    "file_name": filename,
                    "mime_type": "image/png",
                    "storage_path": storage_path,
                    "file_size": png.stat().st_size,
                    "source": "F1_INTELLIGENCE_HEIC_PNG",
                    "whatsapp_message_id": media.get("whatsapp_message_id"),
                },
                return_rows=True,
            )
            if not created:
                try:
                    storage_delete([storage_path])
                finally:
                    raise IntelligenceError("Record PNG convertito non creato")

            try:
                storage_delete([str(media["storage_path"])])
                rest_delete(
                    "f1_content_media",
                    {"id": str(media["id"]), "owner_id": owner_id, "client_id": client_id},
                )
            except Exception:
                # Keep both references rather than losing a successfully verified PNG.
                raise

            out_rows = [
                x for x in out_rows
                if str(x.get("id")) != str(media.get("id"))
            ] + created
            emit_event(
                owner_id, client_id, content_id, str(job["id"]),
                "CONVERSIONE_HEIC", "COMPLETED",
                f"PNG verificato ({width}×{height}); HEIC originale eliminato dal cloud", 44,
                {"media_id": created[0].get("id"), "width": width, "height": height},
            )
    remaining = [m for m in out_rows if is_heic(m)]
    if remaining:
        emit_event(
            owner_id, client_id, content_id, str(job["id"]),
            "CONVERSIONE_HEIC", "WAITING",
            f"Lotto completato; {len(remaining)} HEIC/HEIF restano in coda automatica", 45,
            {"remaining": len(remaining), "batch_size": HEIC_BATCH_SIZE},
        )
    return out_rows


def probe_has_audio(path: Path) -> bool:
    r = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=index", "-of", "csv=p=0", str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(r.stdout.strip())


def get_whisper_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
    return _model


def srt_timestamp(value: float) -> str:
    ms = int(round(max(0.0, value) * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list[Any], dest: Path) -> tuple[str, int]:
    texts: list[str] = []
    lines: list[str] = []
    idx = 1
    for seg in segments:
        text = re.sub(r"\s+", " ", str(getattr(seg, "text", "") or "")).strip()
        if not text:
            continue
        texts.append(text)
        lines.extend([
            str(idx),
            f"{srt_timestamp(float(seg.start))} --> {srt_timestamp(float(seg.end))}",
            text,
            "",
        ])
        idx += 1
    dest.write_text("\n".join(lines), encoding="utf-8")
    joined = " ".join(texts).strip()
    return joined, len(joined.split())


def burn_subtitles(src: Path, srt: Path, dest: Path) -> None:
    subtitle_path = str(srt).replace("\\", "/").replace(":", "\\:")
    vf = (
        "subtitles='" + subtitle_path + "':force_style="
        "'FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,"
        "Alignment=2,MarginV=120'"
    )
    r = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src), "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if r.returncode != 0 or not dest.exists() or dest.stat().st_size < 10_000:
        raise IntelligenceError("Rendering sottotitoli fallito: " + r.stderr[-1200:])


def process_video(
    client: dict[str, Any],
    item: dict[str, Any],
    media_rows: list[dict[str, Any]],
    job: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    owner_id = str(item["owner_id"])
    client_id = str(item["client_id"])
    content_id = str(item["id"])
    processed = [
        m for m in media_rows
        if str(m.get("source") or "").upper() == "F1_INTELLIGENCE_SUBTITLED"
        and is_video(m)
    ]
    if processed:
        return media_rows, {"status": "COMPLETED", "speech_detected": True, "reused": True}

    original = next((m for m in media_rows if is_video(m)), None)
    if not original:
        return media_rows, {"status": "SKIPPED", "speech_detected": False}

    emit_event(owner_id, client_id, content_id, str(job["id"]), "ANALISI_AUDIO", "RUNNING", "Analisi audio del video", 30)
    with tempfile.TemporaryDirectory(prefix="f1-intelligence-") as td:
        td_path = Path(td)
        src = td_path / (str(original.get("file_name") or "video.mp4"))
        storage_download(str(original["storage_path"]), src)
        if not probe_has_audio(src):
            emit_event(owner_id, client_id, content_id, str(job["id"]), "ANALISI_AUDIO", "COMPLETED", "Video senza traccia audio: sottotitoli non necessari", 45)
            return media_rows, {"status": "COMPLETED", "speech_detected": False, "audio_present": False}

        emit_event(owner_id, client_id, content_id, str(job["id"]), "TRASCRIZIONE", "RUNNING", "Rilevamento parlato e trascrizione automatica", 42)
        model = get_whisper_model()
        segments_iter, info = model.transcribe(
            str(src),
            beam_size=1,
            vad_filter=True,
            word_timestamps=False,
        )
        segments = list(segments_iter)
        srt = td_path / "captions.srt"
        transcript, word_count = write_srt(segments, srt)
        speech = word_count >= 4 and len(transcript) >= 12
        if not speech:
            emit_event(owner_id, client_id, content_id, str(job["id"]), "TRASCRIZIONE", "COMPLETED", "Audio presente ma nessun parlato affidabile rilevato", 55, {"word_count": word_count})
            return media_rows, {
                "status": "COMPLETED",
                "speech_detected": False,
                "audio_present": True,
                "language": getattr(info, "language", None),
            }

        emit_event(owner_id, client_id, content_id, str(job["id"]), "TRASCRIZIONE", "COMPLETED", "Parlato rilevato e trascritto", 58, {"language": getattr(info, "language", None), "word_count": word_count})
        emit_event(owner_id, client_id, content_id, str(job["id"]), "SOTTOTITOLAZIONE", "RUNNING", "Rendering automatico dei sottotitoli in safe area", 62)
        out = td_path / "f1-subtitled.mp4"
        burn_subtitles(src, srt, out)

        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(str(original.get("file_name") or "video.mp4")).stem)
        file_name = f"{safe_name}-sottotitolato.mp4"
        storage_path = f"{owner_id}/{client_id}/{content_id}/intelligence-{uuid.uuid4().hex[:12]}-{file_name}"
        storage_upload(storage_path, out, "video/mp4")
        created = rest_post(
            "f1_content_media",
            {
                "owner_id": owner_id,
                "content_id": content_id,
                "client_id": client_id,
                "file_name": file_name,
                "mime_type": "video/mp4",
                "storage_path": storage_path,
                "file_size": out.stat().st_size,
                "source": "F1_INTELLIGENCE_SUBTITLED",
            },
            return_rows=True,
        )
        if not created:
            raise IntelligenceError("Record media sottotitolato non creato")
        media_rows = media_rows + created
        emit_event(owner_id, client_id, content_id, str(job["id"]), "SOTTOTITOLAZIONE", "COMPLETED", "Video parlato sottotitolato e salvato nel cloud", 72, {"language": getattr(info, "language", None), "word_count": word_count})
        return media_rows, {
            "status": "COMPLETED",
            "speech_detected": True,
            "audio_present": True,
            "language": getattr(info, "language", None),
            "transcript": transcript[:5000],
            "processed_media_id": created[0].get("id"),
        }



def graphic_media_fingerprint(media_rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for media in media_rows:
        if not (is_image(media) or is_video(media)):
            continue
        parts.append("|".join([
            str(media.get("id") or ""),
            str(media.get("storage_path") or ""),
            str(media.get("file_size") or ""),
            str(media.get("mime_type") or ""),
            str(media.get("source") or ""),
        ]))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest() if parts else ""


def clean_graphic_text(raw: str) -> str:
    rows: list[str] = []
    seen: set[str] = set()
    for value in StringIOText(raw).splitlines():
        line = re.sub(r"\s+", " ", value).strip(" \t|_")
        if len(line) < 2:
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        rows.append(line)
    return "\n".join(rows)[:GRAPHIC_TEXT_LIMIT].strip()


def StringIOText(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def ocr_image_file(path: Path) -> str:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageOps

    with Image.open(path) as source:
        try:
            source.seek(0)
        except Exception:
            pass
        image = ImageOps.exif_transpose(source).convert("RGB")
        width, height = image.size
        longest = max(width, height)
        if longest and longest < 1800:
            scale = min(3.0, 1800.0 / float(longest))
            image = image.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                Image.Resampling.LANCZOS,
            )
        gray = ImageOps.grayscale(image)
        gray = ImageOps.autocontrast(gray)
        gray = ImageEnhance.Contrast(gray).enhance(1.35)
        try:
            raw = pytesseract.image_to_string(gray, lang="ita+eng", config="--psm 6")
        except Exception:
            raw = pytesseract.image_to_string(gray, lang="eng", config="--psm 6")
    return clean_graphic_text(raw)


def extract_video_frame(path: Path, dest: Path) -> bool:
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", "1", "-i", str(path), "-frames:v", "1", str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def extract_graphic_text(
    item: dict[str, Any],
    media_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    plan = item.get("distribution_plan") if isinstance(item.get("distribution_plan"), dict) else {}
    intelligence = plan.get("intelligence") if isinstance(plan.get("intelligence"), dict) else {}
    previous = intelligence.get("graphic_caption") if isinstance(intelligence.get("graphic_caption"), dict) else {}
    fingerprint = graphic_media_fingerprint(media_rows)

    previous_text = clean_graphic_text(str(previous.get("text") or ""))
    if fingerprint and fingerprint == str(previous.get("media_fingerprint") or "") and previous_text:
        return {
            **previous,
            "text": previous_text,
            "media_fingerprint": fingerprint,
            "reused": True,
        }

    texts: list[str] = []
    media_ids: list[str] = []
    ocr_errors: list[str] = []
    candidates = [m for m in media_rows if is_image(m) or is_video(m)][:OCR_MEDIA_LIMIT]
    with tempfile.TemporaryDirectory(prefix="f1-graphic-caption-") as td:
        root = Path(td)
        for index, media in enumerate(candidates, 1):
            storage_path = str(media.get("storage_path") or "").strip()
            if not storage_path:
                continue
            media_id = str(media.get("id") or "")
            suffix = Path(str(media.get("file_name") or storage_path)).suffix.lower()
            if not suffix:
                suffix = ".mp4" if is_video(media) else ".png"
            local = root / f"source-{index}{suffix}"
            try:
                storage_download(storage_path, local)
                target = local
                if is_video(media):
                    frame = root / f"frame-{index}.png"
                    if not extract_video_frame(local, frame):
                        raise IntelligenceError("frame_video_non_estratto")
                    target = frame
                value = ocr_image_file(target)
                if value:
                    texts.append(value)
                    if media_id:
                        media_ids.append(media_id)
            except Exception as exc:
                ocr_errors.append(f"{media_id or index}: {str(exc)[:180]}")

    combined = clean_graphic_text("\n".join(texts))
    fallback = clean_graphic_text(
        str(item.get("description") or item.get("source_text") or item.get("title") or "")
    )
    text = combined or fallback
    return {
        "text": text,
        "media_fingerprint": fingerprint,
        "media_ids": media_ids,
        "ocr_used": bool(combined),
        "source": "GRAPHIC_TEXT" if combined else "CONTENT_TEXT_FALLBACK",
        "engine": "tesseract_ita_eng",
        "extracted_at": now_iso(),
        "errors": ocr_errors[:6],
        "reused": False,
    }


def caption_text_tokens(value: str) -> list[str]:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()
    return [
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) >= 3
    ]


def meaningful_graphic_lines(graphic_text: str, client: dict[str, Any]) -> list[str]:
    name = re.sub(r"\s+", " ", str(client.get("name") or "")).strip().casefold()
    output: list[str] = []
    seen: set[str] = set()
    for raw in clean_graphic_text(graphic_text).splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" \t|_·:-")
        if not line:
            continue
        low = line.casefold()
        low = re.sub(r"^fl\s+social\b", "f1 social", low)
        if name and low == name:
            continue
        if re.search(r"\bf[1li]\s+social\s+intelligence\b", low):
            continue
        if low in {"attract", "nurture", "convert", "branding", "awareness"}:
            continue
        if "social intelligence for real results" in low:
            continue
        if low.startswith("strategia") and any(x in low for x in ("automazione", "crescita", "intelligence")):
            continue

        tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]+", line)
        if not tokens:
            continue
        if len(tokens) >= 2 and (sum(len(x) for x in tokens) / len(tokens)) <= 1.6:
            continue
        alnum = sum(ch.isalnum() for ch in line)
        if len(line) >= 5 and alnum / max(1, len(line)) < 0.45:
            continue

        key = re.sub(r"[^a-z0-9]+", "", low)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(line)
    return output


def graphic_supports_title(graphic_text: str, title: str) -> bool:
    title_tokens = caption_text_tokens(title)
    if not title_tokens:
        return False
    graphic_tokens = set(caption_text_tokens(graphic_text))
    if not graphic_tokens:
        return False
    hits = sum(1 for token in title_tokens if token in graphic_tokens)
    return hits / len(title_tokens) >= 0.55


def caption_from_graphic(
    platform: str,
    client: dict[str, Any],
    item: dict[str, Any],
    graphic_text: str,
    graphic_source: str = "GRAPHIC_TEXT",
) -> str:
    title = re.sub(r"\s+", " ", str(item.get("title") or "Contenuto")).strip()
    context = clean_graphic_text(str(item.get("description") or item.get("source_text") or ""))
    source = str(graphic_source or "GRAPHIC_TEXT")
    lines = meaningful_graphic_lines(graphic_text, client) if source == "GRAPHIC_TEXT" else []

    headline = title
    body = ""
    if source == "GRAPHIC_TEXT" and lines:
        semantic = " ".join(lines)
        if graphic_supports_title(semantic, title):
            # OCR establishes the subject; use the clean content title/body to
            # avoid reproducing OCR artefacts in the public caption.
            headline = title
            body = context
        else:
            headline = lines[0]
            consumed = 1
            if len(lines) > 1 and len(headline) < 80 and len(headline + " " + lines[1]) <= 140:
                headline = headline + " " + lines[1]
                consumed = 2
            body = "\n".join(lines[consumed:]).strip()
    else:
        headline = title
        body = context

    if not headline:
        headline = title or "Contenuto"
    if body and re.sub(r"\W+", "", body.casefold()) == re.sub(r"\W+", "", headline.casefold()):
        body = ""

    base = headline + (("\n\n" + body) if body else "")
    base = base.strip()
    name = str(client.get("name") or "").strip()
    branded = base
    if name and name.casefold() not in base.casefold():
        branded = base + "\n\n" + name

    if platform == "instagram":
        return branded[:2200].strip()
    if platform == "tiktok":
        return base[:1800].strip()
    if platform == "youtube":
        return base[:4500].strip()
    if platform == "linkedin-page":
        return branded[:3000].strip()
    if platform == "pinterest":
        return base[:800].strip()
    return base[:5000].strip()


def regenerate_graphic_captions(
    client: dict[str, Any],
    item: dict[str, Any],
    media_rows: list[dict[str, Any]],
    calendars: list[dict[str, Any]],
    job: dict[str, Any],
    processing: dict[str, Any],
) -> dict[str, Any]:
    owner_id = str(item["owner_id"])
    client_id = str(item["client_id"])
    content_id = str(item["id"])
    graphic = extract_graphic_text(item, media_rows)

    plan = item.get("distribution_plan") if isinstance(item.get("distribution_plan"), dict) else {}
    plan = dict(plan)
    platforms = plan.get("platforms") if isinstance(plan.get("platforms"), dict) else {}
    platforms = dict(platforms)

    for platform in CAPTION_PLATFORMS:
        current = platforms.get(platform) if isinstance(platforms.get(platform), dict) else {}
        current = dict(current)
        generated = caption_from_graphic(
            platform,
            client,
            item,
            str(graphic.get("text") or ""),
            str(graphic.get("source") or "GRAPHIC_TEXT"),
        )
        current_caption = str(current.get("caption") or "").strip()
        previous_generated = str(current.get("generated_caption") or "").strip()
        legacy_manual = bool(
            "caption_manual" not in current
            and current_caption
            and previous_generated
            and current_caption != previous_generated
        )
        manual = bool(current.get("caption_manual")) or legacy_manual
        current["generated_caption"] = generated
        current["caption_source"] = "MANUAL" if manual else str(graphic.get("source") or "GRAPHIC_TEXT")
        current["graphic_media_fingerprint"] = str(graphic.get("media_fingerprint") or "")
        if not manual or not str(current.get("caption") or "").strip():
            current["caption"] = generated
            current["caption_manual"] = False
        platforms[platform] = current

    intelligence = plan.get("intelligence") if isinstance(plan.get("intelligence"), dict) else {}
    intelligence = dict(intelligence)
    intelligence.update({
        "version": "F1_INTELLIGENCE_V2_GRAPHIC_CAPTION",
        "processed_at": now_iso(),
        "media_processing": processing,
        "approval_required": is_real_estate(client),
        "graphic_caption": graphic,
    })
    plan["platforms"] = platforms
    plan["intelligence"] = intelligence
    plan["caption_autopilot_version"] = "GRAPHIC_TEXT_V2_CLEAN"

    rest_patch(
        "f1_content_items",
        {"id": content_id},
        {"distribution_plan": plan, "updated_at": now_iso()},
    )
    item["distribution_plan"] = plan

    for row in calendars:
        if str(row.get("content_id")) != content_id:
            continue
        if re.search(r"PUBBLICAT|PUBLISHED|COMPLETED", str(row.get("status") or ""), re.I):
            continue
        platform = str(row.get("platform") or "")
        data = platforms.get(platform)
        if not isinstance(data, dict):
            continue
        metadata = row.get("platform_metadata") if isinstance(row.get("platform_metadata"), dict) else {}
        metadata = dict(metadata)
        metadata.update({
            "caption": str(data.get("caption") or ""),
            "generated_caption": str(data.get("generated_caption") or ""),
            "caption_source": str(data.get("caption_source") or ""),
            "graphic_media_fingerprint": str(graphic.get("media_fingerprint") or ""),
            "pipeline_version": "F1_INTELLIGENCE_V2_GRAPHIC_CAPTION",
        })
        rest_patch("f1_content_calendar", {"id": str(row["id"])}, {"platform_metadata": metadata})
        row["platform_metadata"] = metadata

    event_message = (
        "Testo della grafica letto automaticamente e usato per le caption"
        if graphic.get("ocr_used")
        else "Testo grafica non rilevato: caption create dal testo contenuto disponibile"
    )
    emit_event(
        owner_id, client_id, content_id, str(job["id"]),
        "LETTURA_GRAFICA", "COMPLETED", event_message, 72,
        {
            "source": graphic.get("source"),
            "media_ids": graphic.get("media_ids") or [],
            "media_fingerprint": graphic.get("media_fingerprint"),
        },
    )
    emit_event(
        owner_id, client_id, content_id, str(job["id"]),
        "CAPTION_GRAFICA", "COMPLETED",
        "Caption rigenerate automaticamente dalla grafica per tutti i social", 78,
        {"platforms": list(CAPTION_PLATFORMS), "source": graphic.get("source")},
    )
    return plan


def caption_for(platform: str, client: dict[str, Any], item: dict[str, Any]) -> str:
    plan = item.get("distribution_plan") if isinstance(item.get("distribution_plan"), dict) else {}
    platforms = plan.get("platforms") if isinstance(plan.get("platforms"), dict) else {}
    existing = platforms.get(platform) if isinstance(platforms.get(platform), dict) else {}
    if str(existing.get("caption") or "").strip():
        return str(existing["caption"]).strip()
    if str(existing.get("generated_caption") or "").strip():
        return str(existing["generated_caption"]).strip()

    title = re.sub(r"\s+", " ", str(item.get("title") or "Contenuto")).strip()
    body = re.sub(r"\s+", " ", str(item.get("description") or item.get("source_text") or "")).strip()
    base = body or title
    name = str(client.get("name") or "").strip()
    if platform == "instagram":
        return f"{base}\n\n{name}\n#F1Social #ContentMarketing".strip()
    if platform == "tiktok":
        return f"{title}. {base}"[:1800].strip()
    if platform == "youtube":
        return f"{title}\n\n{base}"[:4500].strip()
    if platform == "linkedin-page":
        return f"{title}\n\n{base}\n\n{name}".strip()
    return base


def compatible(platform: str, media: dict[str, Any]) -> bool:
    if is_heic(media):
        return False
    if is_video(media):
        return platform in {"facebook", "instagram", "tiktok", "youtube", "linkedin-page"}
    if is_image(media):
        return platform in {"facebook", "instagram", "linkedin-page", "pinterest", "tiktok"}
    return False


def platform_time(client: dict[str, Any], platform: str) -> str:
    prefs = client.get("publishing_preferences") if isinstance(client.get("publishing_preferences"), dict) else {}
    row = prefs.get(platform) if isinstance(prefs.get(platform), dict) else {}
    raw = str(row.get("time") or DEFAULT_TIMES.get(platform) or "12:00")
    return raw if re.fullmatch(r"\d{2}:\d{2}", raw) else DEFAULT_TIMES.get(platform, "12:00")


def next_slot(
    client: dict[str, Any],
    platform: str,
    occupied: set[tuple[str, str, str]],
) -> datetime:
    tz = ZoneInfo(str(client.get("timezone") or "Europe/Rome"))
    now = datetime.now(tz)
    hh, mm = [int(x) for x in platform_time(client, platform).split(":")]
    for offset in range(0, 30):
        day = (now + timedelta(days=offset)).date()
        candidate = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
        if candidate <= now + timedelta(minutes=5):
            continue
        key = (str(client["id"]), platform, candidate.isoformat())
        if key not in occupied:
            occupied.add(key)
            return candidate
    return now + timedelta(days=1)


def ensure_calendar_for_item(
    client: dict[str, Any],
    item: dict[str, Any],
    media_rows: list[dict[str, Any]],
    channels: list[dict[str, Any]],
    calendars: list[dict[str, Any]],
    occupied: set[tuple[str, str, str]],
    job: dict[str, Any],
) -> int:
    owner_id = str(item["owner_id"])
    client_id = str(item["client_id"])
    content_id = str(item["id"])
    preferred = next(
        (m for m in reversed(media_rows) if str(m.get("source") or "").upper() == "F1_INTELLIGENCE_SUBTITLED"),
        next(
            (m for m in reversed(media_rows) if str(m.get("source") or "").upper() == "F1_INTELLIGENCE_HEIC_PNG"),
            media_rows[0] if media_rows else None,
        ),
    )
    if not preferred:
        emit_event(owner_id, client_id, content_id, str(job["id"]), "MEDIA", "BLOCKED", "Nessun media disponibile", 70)
        return 0
    if is_heic(preferred):
        emit_event(owner_id, client_id, content_id, str(job["id"]), "CONVERSIONE_HEIC", "BLOCKED", "HEIC/HEIF in attesa di conversione PNG", 35)
        return 0

    existing_pairs = {
        (str(c.get("content_id")), str(c.get("platform")))
        for c in calendars
        if str(c.get("status") or "").upper() not in {"ANNULLATO", "CANCELED"}
    }
    verified = [
        ch for ch in channels
        if str(ch.get("client_id")) == client_id
        and bool(ch.get("enabled"))
        and bool(ch.get("verified"))
        and str(ch.get("connection_status") or "").upper() == "COLLEGATO"
    ]
    created = 0
    approval = is_real_estate(client)
    for ch in verified:
        platform = str(ch.get("platform") or "")
        if (content_id, platform) in existing_pairs or not compatible(platform, preferred):
            continue
        publication_at = next_slot(client, platform, occupied)
        caption = caption_for(platform, client, item)
        status = "APPROVAZIONE_RICHIESTA" if approval else "PROGRAMMATO"
        rest_post(
            "f1_content_calendar",
            {
                "owner_id": owner_id,
                "content_id": content_id,
                "client_id": client_id,
                "platform": platform,
                "publication_at": publication_at.isoformat(),
                "status": status,
                "provider": ch.get("provider") or "direct",
                "platform_metadata": {
                    "caption": caption,
                    "generated_caption": True,
                    "intelligence": True,
                    "selected_time": platform_time(client, platform),
                    "pipeline_version": "F1_INTELLIGENCE_V2_GRAPHIC_CAPTION",
                    "media_id": preferred.get("id"),
                },
            },
        )
        existing_pairs.add((content_id, platform))
        created += 1

    if created:
        target_status = "DA APPROVARE" if approval else "PROGRAMMATO"
        rest_patch("f1_content_items", {"id": content_id}, {"status": target_status, "updated_at": now_iso()})
        stage = "PRONTO_PER_APPROVAZIONE" if approval else "PROGRAMMATO"
        message = (
            f"{created} pubblicazioni preparate: conferma richiesta per il settore immobiliare"
            if approval
            else f"{created} pubblicazioni programmate automaticamente"
        )
        emit_event(owner_id, client_id, content_id, str(job["id"]), stage, "COMPLETED", message, 92)
    elif not verified:
        rest_patch("f1_content_items", {"id": content_id}, {"status": "PRONTO", "updated_at": now_iso()})
        emit_event(owner_id, client_id, content_id, str(job["id"]), "SOCIAL", "BLOCKED", "Nessun canale social verificato disponibile", 82)
    return created


def process_content(
    client: dict[str, Any],
    item: dict[str, Any],
    media_rows: list[dict[str, Any]],
    channels: list[dict[str, Any]],
    calendars: list[dict[str, Any]],
    occupied: set[tuple[str, str, str]],
) -> dict[str, int]:
    owner_id = str(item["owner_id"])
    client_id = str(item["client_id"])
    content_id = str(item["id"])
    job = ensure_job(
        owner_id, client_id, content_id, "CONTENT_AUTOPILOT",
        f"content-autopilot:{content_id}",
        {"pipeline": "F1_INTELLIGENCE_V2_GRAPHIC_CAPTION"},
    )
    if not job_is_available(job):
        return {"published": 0, "scheduled": 0, "blocked": 0}
    if str(item.get("status") or "") == "PUBBLICATO":
        emit_event(owner_id, client_id, content_id, str(job["id"]), "PUBBLICATO", "COMPLETED", "Pubblicazione confermata dalla piattaforma", 100)
        update_job(job, "COMPLETED", "PUBBLICATO", completed_at=now_iso(), result={"status": "PUBBLICATO"})
        return {"published": 1, "scheduled": 0, "blocked": 0}

    if str(item.get("status") or "") == "ARCHIVIATO":
        return {"published": 0, "scheduled": 0, "blocked": 0}

    emit_event(owner_id, client_id, content_id, str(job["id"]), "RILEVATO", "COMPLETED", "Contenuto acquisito da F1 Social Intelligence", 10)
    update_job(job, "RUNNING", "ANALISI", claimed_at=job.get("claimed_at") or now_iso())
    emit_event(owner_id, client_id, content_id, str(job["id"]), "ANALISI", "RUNNING", "Analisi automatica formato, media e compatibilità", 20)

    if not media_rows:
        regenerate_graphic_captions(
            client,
            item,
            [],
            calendars,
            job,
            {"status": "MEDIA_MISSING", "caption_source": "CONTENT_TEXT_FALLBACK"},
        )
        emit_event(
            owner_id, client_id, content_id, str(job["id"]),
            "MEDIA", "BLOCKED",
            "MEDIA_MISSING · caption automatica creata dal testo disponibile", 80,
        )
        update_job(
            job,
            "BLOCKED",
            "MEDIA",
            last_error="MEDIA_MISSING",
            result={
                "caption_generated": True,
                "caption_source": "CONTENT_TEXT_FALLBACK",
                "publication_blocked": True,
            },
        )
        return {"published": 0, "scheduled": 0, "blocked": 1}

    if any(is_heic(m) for m in media_rows):
        update_job(job, "RUNNING", "CONVERSIONE_HEIC")
        media_rows = convert_heic_media(client, item, media_rows, job)
        if any(is_heic(m) for m in media_rows):
            update_job(
                job, "WAITING", "CONVERSIONE_HEIC",
                run_after=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                last_error=None,
                result={"remaining_heic": sum(1 for m in media_rows if is_heic(m))},
            )
            return {"published": 0, "scheduled": 0, "blocked": 0}

    processing: dict[str, Any] = {"status": "COMPLETED"}
    if any(is_video(m) for m in media_rows):
        update_job(job, "RUNNING", "VIDEO_INTELLIGENCE")
        media_rows, processing = process_video(client, item, media_rows, job)

    regenerate_graphic_captions(client, item, media_rows, calendars, job, processing)

    created = ensure_calendar_for_item(client, item, media_rows, channels, calendars, occupied, job)
    update_job(
        job,
        "COMPLETED" if created or str(item.get("status") or "") in {"PROGRAMMATO", "DA APPROVARE"} else "WAITING",
        "PRONTO_PER_APPROVAZIONE" if is_real_estate(client) else "PROGRAMMATO",
        completed_at=now_iso() if created else None,
        result={"calendar_rows_created": created, "approval_required": is_real_estate(client)},
        last_error=None,
    )
    return {"published": 0, "scheduled": created, "blocked": 0 if created else 1}


def normalize_domain(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower().strip(".")
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def agency_name_from_title(title: str, domain: str) -> str:
    text = re.sub(r"\s+", " ", title).strip()
    for sep in (" | ", " - ", " – ", " — ", ": "):
        if sep in text:
            head = text.split(sep, 1)[0].strip()
            if 2 <= len(head) <= 90:
                return head
    if domain:
        stem = domain.split(".")[0].replace("-", " ").replace("_", " ")
        return stem.title()
    return text[:90]


def prospect_confidence(title: str, snippet: str, domain: str) -> float:
    hay = f"{title} {snippet} {domain}".lower()
    score = 0.25
    if "agenzia immobiliare" in hay:
        score += 0.45
    if "immobiliare" in hay:
        score += 0.2
    if any(x in hay for x in ("tecnocasa", "tempocasa", "remax", "gabetti", "frimm")):
        score += 0.2
    return min(0.99, score)


def process_directory_jobs(limit: int = 8) -> dict[str, int]:
    if DDGS is None:
        return {"agency_jobs": 0, "agency_prospects": 0, "agency_errors": 0}
    jobs = rest_get(
        "f1_directory_jobs",
        {
            "select": "*",
            "status": "eq.QUEUED",
            "order": "priority.desc,created_at.asc",
            "limit": str(max(1, limit)),
        },
    )
    stats = {"agency_jobs": 0, "agency_prospects": 0, "agency_errors": 0}
    for job in jobs:
        jid = str(job["id"])
        owner_id = str(job["owner_id"])
        attempts = int(job.get("attempts") or 0) + 1
        rest_patch(
            "f1_directory_jobs",
            {"id": jid},
            {"status": "CLAIMED", "attempts": attempts, "claimed_at": now_iso(), "updated_at": now_iso(), "last_error": ""},
        )
        try:
            query = " ".join(
                x for x in [
                    f'"{job.get("via") or ""} {job.get("civico") or ""}"',
                    f'"{job.get("comune") or ""}"',
                    "agenzia immobiliare",
                ] if x.strip()
            )
            results = list(DDGS().text(query, max_results=10))
            found = 0
            for row in results:
                url = str(row.get("href") or row.get("url") or "").strip()
                title = str(row.get("title") or "").strip()
                snippet = str(row.get("body") or row.get("snippet") or "").strip()
                domain = normalize_domain(url)
                if not domain or domain in PORTAL_DOMAINS:
                    continue
                hay = f"{title} {snippet} {domain}".lower()
                if not any(token in hay for token in ("immobil", "agenzia", "tecnocasa", "tempocasa", "remax", "gabetti", "frimm")):
                    continue
                name = agency_name_from_title(title, domain)
                key = hashlib.sha256(f"{owner_id}|{domain}|{name.lower()}".encode("utf-8")).hexdigest()
                existing = rest_get(
                    "f1_agency_prospects",
                    {"select": "id", "owner_id": f"eq.{owner_id}", "unique_key": f"eq.{key}", "limit": "1"},
                )
                payload = {
                    "owner_id": owner_id,
                    "directory_job_id": jid,
                    "opportunity_id": job.get("opportunity_id"),
                    "agency_name": name,
                    "domain": domain,
                    "source_url": url,
                    "source_title": title,
                    "source_snippet": snippet[:1500],
                    "confidence": prospect_confidence(title, snippet, domain),
                    "status": "DISCOVERED",
                    "unique_key": key,
                    "metadata": {
                        "comune": job.get("comune"),
                        "via": job.get("via"),
                        "civico": job.get("civico"),
                        "listing_url": job.get("listing_url"),
                        "query": query,
                    },
                    "updated_at": now_iso(),
                }
                if existing:
                    rest_patch("f1_agency_prospects", {"id": str(existing[0]["id"])}, payload)
                else:
                    rest_post("f1_agency_prospects", payload)
                found += 1
            rest_patch(
                "f1_directory_jobs",
                {"id": jid},
                {
                    "status": "DONE",
                    "result_count": found,
                    "seller_signal": "INDIZIO_AGENZIA" if found else (job.get("seller_signal") or "NON_DETERMINATO"),
                    "completed_at": now_iso(),
                    "updated_at": now_iso(),
                    "last_error": "",
                },
            )
            stats["agency_jobs"] += 1
            stats["agency_prospects"] += found
        except Exception as exc:
            retry = attempts < 3
            rest_patch(
                "f1_directory_jobs",
                {"id": jid},
                {
                    "status": "QUEUED" if retry else "ERROR",
                    "updated_at": now_iso(),
                    "last_error": str(exc)[:1500],
                },
            )
            stats["agency_errors"] += 1
    return stats


def run_content_autopilot(limit: int = 250) -> dict[str, int]:
    clients = rest_get("f1_content_clients", {"select": "*", "status": "eq.ATTIVO", "order": "name.asc"})
    items = rest_get("f1_content_items", {"select": "*", "order": "created_at.asc", "limit": str(limit)})
    media = rest_get("f1_content_media", {"select": "*", "limit": "3000"})
    channels = rest_get("f1_client_social_channels", {"select": "*", "limit": "2000"})
    calendars = rest_get("f1_content_calendar", {"select": "*", "limit": "3000"})

    clients_by_id = {str(c["id"]): c for c in clients}
    media_by_content: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in media:
        media_by_content[str(row.get("content_id"))].append(row)

    occupied: set[tuple[str, str, str]] = set()
    for c in calendars:
        if c.get("publication_at"):
            occupied.add((str(c.get("client_id")), str(c.get("platform")), str(c.get("publication_at"))))

    stats = {"clients": len(clients), "items": 0, "scheduled": 0, "blocked": 0, "published": 0, "errors": 0}
    for item in items:
        client = clients_by_id.get(str(item.get("client_id")))
        if not client:
            continue
        stats["items"] += 1
        try:
            result = process_content(
                client,
                item,
                media_by_content.get(str(item["id"]), []),
                channels,
                calendars,
                occupied,
            )
            stats["scheduled"] += result["scheduled"]
            stats["blocked"] += result["blocked"]
            stats["published"] += result["published"]
        except Exception as exc:
            stats["errors"] += 1
            owner_id = str(item.get("owner_id") or "")
            client_id = str(item.get("client_id") or "")
            content_id = str(item.get("id") or "")
            try:
                job = ensure_job(owner_id, client_id, content_id, "CONTENT_AUTOPILOT", f"content-autopilot:{content_id}")
                update_job(
                    job, "RETRY" if int(job.get("attempts") or 0) < int(job.get("max_attempts") or 3) else "ERROR",
                    "ERROR",
                    attempts=int(job.get("attempts") or 0) + 1,
                    run_after=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
                    last_error=str(exc)[:1500],
                )
                emit_event(owner_id, client_id, content_id, str(job["id"]), "ERRORE", "ERROR", str(exc)[:500], 0)
            except Exception as nested:
                print(f"WARN errore registrazione intelligence: {nested}")
            print(f"ERROR content {content_id}: {exc}")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content-limit", type=int, default=250)
    parser.add_argument("--agency-limit", type=int, default=8)
    parser.add_argument("--skip-agencies", action="store_true")
    parser.add_argument("--skip-content", action="store_true")
    args = parser.parse_args()
    require_env()

    summary: dict[str, Any] = {"run_at": now_iso()}
    if not args.skip_content:
        summary["content"] = run_content_autopilot(args.content_limit)
    if not args.skip_agencies:
        summary["agencies"] = process_directory_jobs(args.agency_limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
