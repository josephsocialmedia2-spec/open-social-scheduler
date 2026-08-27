from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

ROOT = Path(__file__).resolve().parent
PORT = 8770
HOST = "127.0.0.1"
OUTPUT_ROOT = ROOT / "ugc_elaborazioni"
INCOMING_ROOT = ROOT / "ugc_incoming"
TTS_PY = ROOT / ".venv_ugc" / "Scripts" / "python.exe"
TTS_SCRIPT = ROOT / "ugc_tts.py"
MUSETALK_ROOT = ROOT / "engines" / "MuseTalk"
MUSETALK_PY = ROOT / ".venv_musetalk" / "Scripts" / "python.exe"
PID_FILE = ROOT / "ugc_server.pid"

app = FastAPI(title="Real Media Pro - UGC Engine Locale", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://josephsocialmedia2-spec.github.io",
        "http://127.0.0.1:8770",
        "http://localhost:8770",
    ],
    allow_origin_regex=r"https://[^/]+\.github\.io|http://(?:localhost|127\.0\.0\.1)(?::\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_processes: dict[str, subprocess.Popen[str]] = {}
_process_lock = threading.Lock()

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}

BRANDS = {
    "f1": {
        "name": "F1 Immobiliare",
        "context": "agenzia immobiliare locale in Valle di Susa, orientata a proprietari che devono vendere casa",
        "cta": "Chiedi una valutazione e fatti spiegare il Piano Vendita F1.",
        "pillars": "valutazione realistica, microzona, preparazione immobile, foto e video, distribuzione, visite qualificate, follow-up",
    },
    "rmp": {
        "name": "Real Media Pro",
        "context": "agenzia di strategia digitale e social media per attività locali e piccole imprese",
        "cta": "Chiedi un'analisi strategica e scopri cosa cambieremmo nella tua comunicazione.",
        "pillars": "strategia, contenuti, Reel, offerte, eventi, campagne, lead generation, siti e automazioni",
    },
}

OBJECTIVES = {
    "lead": "generare contatti realmente interessati",
    "fiducia": "aumentare fiducia e autorevolezza senza sembrare pubblicità",
    "spiegazione": "spiegare in modo semplice come lavora l'azienda e perché il metodo è diverso",
    "offerta": "presentare una proposta concreta e portare l'utente a compiere un'azione",
    "crescita": "far conoscere meglio il brand e trasformare attenzione in richieste commerciali",
}

FORMATS = {
    "talking": "talking head spontaneo, camera frontale, una persona che parla come a un conoscente",
    "problema": "problema-soluzione: parte da un errore o problema reale e spiega cosa fare",
    "tre-errori": "format tre errori, rapido e concreto, senza tono da lista artificiale",
    "storia": "mini storia/caso reale raccontato in prima persona con svolta e conclusione",
    "domanda": "apertura con una domanda diretta che intercetta un dubbio reale del cliente",
    "dietro-le-quinte": "dietro le quinte del metodo e del lavoro che normalmente il cliente non vede",
}


def ensure_dirs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    INCOMING_ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "engines").mkdir(parents=True, exist_ok=True)


def safe_name(value: str, fallback: str = "file") -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(value or fallback).stem).strip("._") or fallback
    suffix = Path(value or "").suffix.lower()
    return f"{stem[:90]}{suffix}"


def ffmpeg() -> str | None:
    choices = [
        shutil.which("ffmpeg"),
        str(ROOT / "ffmpeg" / "bin" / "ffmpeg.exe"),
        str(ROOT / "ffmpeg.exe"),
    ]
    for item in choices:
        if item and Path(item).exists():
            return item
    return None


def ffprobe() -> str | None:
    direct = shutil.which("ffprobe")
    if direct:
        return direct
    f = ffmpeg()
    if f:
        sibling = Path(f).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if sibling.exists():
            return str(sibling)
    return None


def muse_ready() -> bool:
    return (
        MUSETALK_ROOT.exists()
        and MUSETALK_PY.exists()
        and (MUSETALK_ROOT / "models" / "musetalkV15" / "unet.pth").exists()
        and (MUSETALK_ROOT / "models" / "musetalkV15" / "musetalk.json").exists()
    )


def tts_ready() -> bool:
    return TTS_PY.exists() and TTS_SCRIPT.exists()


def ollama_ready() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.2) as response:
            return response.status == 200
    except Exception:
        return False


def set_job(job_id: str, **changes: Any) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(changes)
            _jobs[job_id]["updated_at"] = time.time()


def get_job(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Reel non trovato")
        return dict(job)


def add_log(job_id: str, message: str) -> None:
    with _jobs_lock:
        if job_id not in _jobs:
            return
        logs = list(_jobs[job_id].get("logs", []))
        logs.append(message)
        _jobs[job_id]["logs"] = logs[-60:]
        _jobs[job_id]["updated_at"] = time.time()


def is_stopped(job_id: str) -> bool:
    with _jobs_lock:
        return bool(_jobs.get(job_id, {}).get("stop_requested"))


def stop_process(job_id: str) -> None:
    with _process_lock:
        process = _processes.get(job_id)
    if not process or process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            process.terminate()
    except Exception:
        pass


def run_cancellable(job_id: str, command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    if is_stopped(job_id):
        raise InterruptedError("Elaborazione fermata")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        creationflags=creationflags,
    )
    with _process_lock:
        _processes[job_id] = process
    output_lines: list[str] = []
    assert process.stdout is not None
    try:
        while True:
            if is_stopped(job_id):
                stop_process(job_id)
                raise InterruptedError("Elaborazione fermata")
            line = process.stdout.readline()
            if line:
                text = line.strip()
                if text:
                    output_lines.append(text)
                    if len(output_lines) > 80:
                        output_lines = output_lines[-80:]
                    add_log(job_id, text[:500])
            if process.poll() is not None:
                break
            time.sleep(0.03)
        code = process.wait()
        if code != 0:
            raise RuntimeError("\n".join(output_lines[-20:]) or f"Processo terminato con codice {code}")
        return "\n".join(output_lines)
    finally:
        with _process_lock:
            _processes.pop(job_id, None)


def brand_config(brand: str) -> dict[str, str]:
    return BRANDS.get(brand, BRANDS["f1"])


def fallback_script(brand: str, objective: str, fmt: str, topic: str) -> str:
    cfg = brand_config(brand)
    topic = topic.strip()
    if brand == "f1":
        variants = {
            "problema": f"Se stai pensando di vendere casa, c'è una cosa che eviterei: pubblicare subito senza capire come posizionarla. In {cfg['name']} partiamo dalla microzona, dal prezzo sostenibile e da come presentare davvero l'immobile. Poi costruiamo foto, video e distribuzione per arrivare alle persone giuste, non a chiunque. {topic + '. ' if topic else ''}{cfg['cta']}",
            "tre-errori": f"Tre errori che possono indebolire una vendita: partire da un prezzo deciso a sensazione, usare immagini che non valorizzano la casa e aspettare che il portale faccia tutto da solo. {cfg['name']} lavora al contrario: analisi, preparazione e strategia prima del lancio. {topic + '. ' if topic else ''}{cfg['cta']}",
            "dietro-le-quinte": f"Quando vedi un annuncio online, stai vedendo solo l'ultima parte del lavoro. Prima, in {cfg['name']}, analizziamo zona e concorrenza, controlliamo come presentare l'immobile, prepariamo contenuti e decidiamo a chi mostrarlo. È questo lavoro dietro le quinte che deve creare visite più qualificate. {topic + '. ' if topic else ''}{cfg['cta']}",
        }
        return variants.get(fmt, f"Se vuoi vendere casa, il punto non è semplicemente essere online. {cfg['name']} costruisce un piano: {cfg['pillars']}. {topic + '. ' if topic else ''}L'obiettivo è far percepire bene l'immobile e portare persone più adatte alla visita. {cfg['cta']}")
    variants = {
        "problema": f"Pubblicare contenuti non significa avere una strategia. Se i post sono scollegati da offerte, appuntamenti e obiettivi, possono anche essere belli ma non portare clienti. Con {cfg['name']} partiamo da cosa deve ottenere l'attività e costruiamo contenuti, Reel e campagne intorno a quello. {topic + '. ' if topic else ''}{cfg['cta']}",
        "tre-errori": f"Tre errori che vediamo spesso sui social delle attività locali: parlare sempre del prodotto, pubblicare senza una CTA e ripetere gli stessi contenuti per mesi. {cfg['name']} organizza invece una strategia fatta di format, offerte, eventi, Reel e campagne con uno scopo preciso. {topic + '. ' if topic else ''}{cfg['cta']}",
        "dietro-le-quinte": f"Dietro una pagina social che porta richieste non ci sono post messi a caso. Ci sono ricerca, calendario, format, offerte, creatività, campagne e controllo dei risultati. È questo il lavoro che {cfg['name']} costruisce per le attività locali. {topic + '. ' if topic else ''}{cfg['cta']}",
    }
    return variants.get(fmt, f"Se gestisci un'attività locale, i social devono fare più che riempire il feed. {cfg['name']} usa {cfg['pillars']} per trasformare i contenuti in un percorso che porta persone verso l'azienda. {topic + '. ' if topic else ''}{cfg['cta']}")


def generate_script(brand: str, objective: str, fmt: str, topic: str) -> tuple[str, str]:
    cfg = brand_config(brand)
    objective_text = OBJECTIVES.get(objective, OBJECTIVES["crescita"])
    format_text = FORMATS.get(fmt, FORMATS["talking"])
    fallback = fallback_script(brand, objective, fmt, topic)
    if not ollama_ready():
        return fallback, "template-locale"

    prompt = f"""Sei il copywriter UGC guidato da Joseph, digital strategist. Scrivi SOLO il testo parlato di un Reel italiano da 20-28 secondi.
Brand: {cfg['name']}.
Contesto: {cfg['context']}.
Obiettivo: {objective_text}.
Format: {format_text}.
Tema/offerta: {topic or 'spiegare il valore e il metodo dell azienda'}.
Pilastri reali utilizzabili: {cfg['pillars']}.
CTA finale: {cfg['cta']}
Regole: tono naturale da persona vera; frasi brevi; niente saluti iniziali; hook forte nei primi 2 secondi; niente parole come rivoluzionario, incredibile, leader, soluzione a 360 gradi; non inventare risultati, numeri o testimonianze; non dire di essere un dipendente se non specificato; deve sembrare una raccomandazione/spiegazione spontanea, non uno spot. 75-110 parole. Restituisci solo il parlato."""
    payload = json.dumps({"model": "llama3.2:3b", "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = str(data.get("response", "")).strip().strip('"')
        if len(text) < 80:
            return fallback, "template-locale"
        return text, "ollama"
    except Exception:
        return fallback, "template-locale"


def duration_seconds(path: Path) -> float:
    probe = ffprobe()
    if not probe:
        raise RuntimeError("FFprobe non disponibile")
    result = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Impossibile leggere la durata")
    return max(0.1, float(result.stdout.strip()))


def make_srt(script: str, duration: float, target: Path) -> None:
    words = script.split()
    if not words:
        target.write_text("", encoding="utf-8")
        return
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        if len(current) >= 6 or (word.endswith((".", "!", "?", ",")) and len(current) >= 3):
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    weights = [max(1, len(x)) for x in chunks]
    total_weight = sum(weights)
    cursor = 0.0
    lines: list[str] = []

    def stamp(value: float) -> str:
        ms = int(max(0, value) * 1000)
        h, rem = divmod(ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, milli = divmod(rem, 1000)
        return f"{h:02}:{m:02}:{s:02},{milli:03}"

    for idx, (chunk, weight) in enumerate(zip(chunks, weights), start=1):
        span = duration * weight / total_weight
        end = min(duration, cursor + span)
        lines += [str(idx), f"{stamp(cursor)} --> {stamp(end)}", chunk, ""]
        cursor = end
    target.write_text("\n".join(lines), encoding="utf-8")


def normalize_segment(job_id: str, source: Path, output: Path, start: float, length: float, is_image: bool = False) -> None:
    ff = ffmpeg()
    if not ff:
        raise RuntimeError("FFmpeg non disponibile")
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=25,setsar=1"
    if is_image:
        command = [ff, "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(source), "-t", f"{length:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(output)]
    else:
        command = [ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{max(0,start):.3f}", "-stream_loop", "-1", "-i", str(source), "-t", f"{length:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(output)]
    run_cancellable(job_id, command)


def compose_final(job_id: str, talking_video: Path, voice: Path, brolls: list[Path], srt: Path, output: Path, work: Path) -> None:
    total = duration_seconds(voice)
    usable_broll = brolls[:4]
    if not usable_broll:
        ff = ffmpeg()
        assert ff
        command = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(talking_video), "-i", str(voice), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)]
        run_cancellable(job_id, command)
        return

    each = min(2.7, max(1.7, total * 0.09))
    ratios = [0.25, 0.47, 0.66, 0.80][: len(usable_broll)]
    windows: list[tuple[float, float, Path | None]] = []
    cursor = 0.0
    for ratio, broll in zip(ratios, usable_broll):
        center = total * ratio
        start = max(cursor + 0.2, center - each / 2)
        end = min(total - 0.8, start + each)
        if start > cursor + 0.15:
            windows.append((cursor, start, None))
        windows.append((start, end, broll))
        cursor = end
    if cursor < total:
        windows.append((cursor, total, None))

    segment_files: list[Path] = []
    for index, (start, end, source) in enumerate(windows):
        length = max(0.15, end - start)
        out = work / f"segment_{index:02d}.mp4"
        if source is None:
            normalize_segment(job_id, talking_video, out, start, length, False)
        else:
            normalize_segment(job_id, source, out, 0.0, length, source.suffix.lower() in IMAGE_EXT)
        segment_files.append(out)

    concat_file = work / "concat.txt"
    concat_file.write_text("\n".join(f"file '{p.as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'" for p in segment_files), encoding="utf-8")
    visual = work / "visual.mp4"
    ff = ffmpeg()
    assert ff
    run_cancellable(job_id, [ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(visual)])

    # Prima prova con sottotitoli impressi; se la build FFmpeg non include libass, crea comunque il Reel e lascia l'SRT separato.
    escaped = srt.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    burn = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(visual), "-i", str(voice), "-vf", f"subtitles='{escaped}':force_style='FontSize=17,Outline=2,Shadow=0,Alignment=2,MarginV=120'", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)]
    try:
        run_cancellable(job_id, burn)
    except RuntimeError as exc:
        add_log(job_id, f"Sottotitoli impressi non disponibili, continuo con SRT separato: {exc}")
        run_cancellable(job_id, [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(visual), "-i", str(voice), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)])


def run_ugc_job(job_id: str, job_dir: Path, presenter: Path, voice_ref: Path, brolls: list[Path], script: str) -> None:
    try:
        set_job(job_id, status="processing", progress=5, message="Preparazione Reel")
        if not tts_ready():
            raise RuntimeError("Motore voce non installato. Esegui INSTALLA_UGC_GRATIS.bat")
        if not muse_ready():
            raise RuntimeError("MuseTalk non pronto. Esegui INSTALLA_UGC_GRATIS.bat su un PC con GPU NVIDIA compatibile.")
        if not ffmpeg():
            raise RuntimeError("FFmpeg non disponibile")

        script_file = job_dir / "script_ugc.txt"
        script_file.write_text(script.strip() + "\n", encoding="utf-8")

        set_job(job_id, progress=12, message="Creazione voce femminile italiana")
        voice_out = job_dir / "voce_ugc.wav"
        run_cancellable(job_id, [str(TTS_PY), str(TTS_SCRIPT), "--text-file", str(script_file), "--output", str(voice_out), "--reference", str(voice_ref)])

        total = duration_seconds(voice_out)
        srt_file = job_dir / "sottotitoli_ugc.srt"
        make_srt(script, total, srt_file)

        set_job(job_id, progress=35, message="Lip-sync del modello reale")
        muse_result = job_dir / "musetalk_result"
        muse_result.mkdir(parents=True, exist_ok=True)
        config = job_dir / "musetalk_ugc.yaml"
        config.write_text(
            "task_0:\n"
            f"  video_path: \"{presenter.resolve().as_posix()}\"\n"
            f"  audio_path: \"{voice_out.resolve().as_posix()}\"\n"
            "  result_name: \"talking_ugc.mp4\"\n",
            encoding="utf-8",
        )
        command = [
            str(MUSETALK_PY), "-m", "scripts.inference",
            "--inference_config", str(config),
            "--result_dir", str(muse_result),
            "--unet_model_path", str(MUSETALK_ROOT / "models" / "musetalkV15" / "unet.pth"),
            "--unet_config", str(MUSETALK_ROOT / "models" / "musetalkV15" / "musetalk.json"),
            "--version", "v15",
        ]
        ff = ffmpeg()
        env = os.environ.copy()
        if ff:
            env["PATH"] = str(Path(ff).parent) + os.pathsep + env.get("PATH", "")
            command += ["--ffmpeg_path", str(Path(ff).parent)]
        run_cancellable(job_id, command, cwd=MUSETALK_ROOT, env=env)

        expected = muse_result / "v15" / "talking_ugc.mp4"
        if not expected.exists():
            candidates = sorted(muse_result.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not candidates:
                raise RuntimeError("MuseTalk ha terminato ma non ha prodotto il video")
            expected = candidates[0]

        set_job(job_id, progress=78, message="Montaggio UGC e B-roll")
        final = job_dir / "REEL_UGC_FINALE.mp4"
        compose_final(job_id, expected, voice_out, brolls, srt_file, final, job_dir)

        artifacts = [
            {"name": final.name, "label": "Reel UGC finale", "url": f"/api/jobs/{job_id}/download/{final.name}"},
            {"name": voice_out.name, "label": "Voce italiana", "url": f"/api/jobs/{job_id}/download/{voice_out.name}"},
            {"name": script_file.name, "label": "Script", "url": f"/api/jobs/{job_id}/download/{script_file.name}"},
            {"name": srt_file.name, "label": "Sottotitoli", "url": f"/api/jobs/{job_id}/download/{srt_file.name}"},
        ]
        set_job(job_id, status="completed", progress=100, message="Reel pronto", artifacts=artifacts, video_url=f"/api/jobs/{job_id}/download/{final.name}")
        add_log(job_id, "REEL UGC completato.")
    except InterruptedError:
        set_job(job_id, status="stopped", progress=100, message="Elaborazione fermata")
        add_log(job_id, "STOP ricevuto: processo interrotto.")
    except Exception as exc:
        set_job(job_id, status="failed", progress=100, message="Generazione non riuscita", error=str(exc))
        add_log(job_id, f"ERRORE: {exc}")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "name": "UGC Engine Locale",
        "free": True,
        "ollama": ollama_ready(),
        "tts_chatterbox": tts_ready(),
        "musetalk": muse_ready(),
        "ffmpeg": bool(ffmpeg()),
        "gpu_nvidia": bool(shutil.which("nvidia-smi")),
        "output_dir": str(OUTPUT_ROOT),
    }


@app.post("/api/script")
def script_api(payload: dict[str, Any]) -> dict[str, Any]:
    brand = str(payload.get("brand", "f1")).lower()
    objective = str(payload.get("objective", "crescita")).lower()
    fmt = str(payload.get("format", "talking")).lower()
    topic = str(payload.get("topic", "")).strip()
    text, source = generate_script(brand, objective, fmt, topic)
    return {"script": text, "source": source, "brand": brand_config(brand)["name"]}


@app.post("/api/jobs")
async def create_job(
    presenter_video: UploadFile = File(...),
    voice_reference: UploadFile = File(...),
    brand: str = Form("f1"),
    objective: str = Form("crescita"),
    format: str = Form("talking"),
    topic: str = Form(""),
    script: str = Form(""),
    broll: list[UploadFile] | None = File(None),
) -> dict[str, Any]:
    ensure_dirs()
    brand = brand.lower().strip()
    objective = objective.lower().strip()
    format = format.lower().strip()
    if brand not in BRANDS:
        raise HTTPException(status_code=400, detail="Brand non valido")

    presenter_name = safe_name(presenter_video.filename or "presenter.mp4")
    if Path(presenter_name).suffix.lower() not in VIDEO_EXT:
        raise HTTPException(status_code=400, detail="Il modello deve essere un breve video MP4/MOV/WebM")
    voice_name = safe_name(voice_reference.filename or "voice.wav")
    if Path(voice_name).suffix.lower() not in AUDIO_EXT:
        raise HTTPException(status_code=400, detail="La voce di riferimento deve essere WAV/MP3/M4A/FLAC/OGG")

    job_id = uuid.uuid4().hex
    job_dir = OUTPUT_ROOT / f"{time.strftime('%Y-%m-%d_%H-%M-%S')}_{job_id[:8]}"
    job_dir.mkdir(parents=True, exist_ok=False)
    presenter_path = job_dir / presenter_name
    voice_path = job_dir / voice_name

    async def save_upload(upload: UploadFile, target: Path) -> None:
        try:
            with target.open("wb") as handle:
                while chunk := await upload.read(1024 * 1024):
                    handle.write(chunk)
        finally:
            await upload.close()

    await save_upload(presenter_video, presenter_path)
    await save_upload(voice_reference, voice_path)

    broll_paths: list[Path] = []
    for index, upload in enumerate(broll or []):
        name = safe_name(upload.filename or f"broll_{index}.mp4")
        if Path(name).suffix.lower() not in VIDEO_EXT | IMAGE_EXT:
            await upload.close()
            continue
        target = job_dir / f"broll_{index:02d}_{name}"
        await save_upload(upload, target)
        broll_paths.append(target)

    script_text = script.strip()
    source = "utente"
    if not script_text:
        script_text, source = generate_script(brand, objective, format, topic)

    now = time.time()
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "brand": brand,
            "brand_name": brand_config(brand)["name"],
            "objective": objective,
            "format": format,
            "topic": topic,
            "script": script_text,
            "script_source": source,
            "status": "queued",
            "progress": 0,
            "message": "In coda",
            "error": None,
            "logs": ["File del modello e voce ricevuti."],
            "artifacts": [],
            "video_url": None,
            "output_dir": str(job_dir),
            "created_at": now,
            "updated_at": now,
            "stop_requested": False,
        }
    thread = threading.Thread(target=run_ugc_job, args=(job_id, job_dir, presenter_path, voice_path, broll_paths, script_text), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "queued", "script": script_text}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    return get_job(job_id)


@app.post("/api/jobs/{job_id}/stop")
def stop_job(job_id: str) -> dict[str, Any]:
    get_job(job_id)
    set_job(job_id, stop_requested=True, message="Arresto in corso...")
    stop_process(job_id)
    return {"ok": True, "job_id": job_id}


@app.get("/api/jobs/{job_id}/download/{filename}")
def download(job_id: str, filename: str) -> FileResponse:
    job = get_job(job_id)
    base = Path(str(job["output_dir"])).resolve()
    target = (base / Path(filename).name).resolve()
    if target.parent != base or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(target, filename=target.name)


@app.get("/api/jobs")
def list_jobs() -> dict[str, Any]:
    with _jobs_lock:
        items = [dict(x) for x in _jobs.values()]
    items.sort(key=lambda x: float(x.get("created_at", 0)), reverse=True)
    return {"jobs": items[:30]}


if __name__ == "__main__":
    ensure_dirs()
    PID_FILE.write_text(str(os.getpid()), encoding="ascii")
    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    finally:
        PID_FILE.unlink(missing_ok=True)
