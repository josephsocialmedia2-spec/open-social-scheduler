from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import ugc_server as base

ORIGINAL_RUN_UGC_JOB = base.run_ugc_job
ROOT = Path(__file__).resolve().parent
ACADEMY_ROOT = ROOT.parent / "f1-academy"


def run_academy_job(job_id: str, job_dir: Path, presenter: Path, voice_ref: Path, brolls: list[Path], script: str) -> None:
    """Use full MuseTalk UGC when available; otherwise create a narrated continuity video."""
    if base.muse_ready():
        ORIGINAL_RUN_UGC_JOB(job_id, job_dir, presenter, voice_ref, brolls, script)
        return

    try:
        base.set_job(job_id, status="processing", progress=5, message="Modalità continuità Academy")
        if not base.tts_ready():
            raise RuntimeError("Motore voce non installato. Esegui INSTALLA_UGC_GRATIS.bat")
        if not base.ffmpeg():
            raise RuntimeError("FFmpeg non disponibile. Esegui INSTALLA_UGC_GRATIS.bat")

        script_file = job_dir / "script_ugc.txt"
        script_file.write_text(script.strip() + "\n", encoding="utf-8")

        base.set_job(job_id, progress=15, message="Creazione voce italiana locale")
        voice_out = job_dir / "voce_ugc.wav"
        base.run_cancellable(
            job_id,
            [str(base.TTS_PY), str(base.TTS_SCRIPT), "--text-file", str(script_file), "--output", str(voice_out), "--reference", str(voice_ref)],
        )

        total = base.duration_seconds(voice_out)
        srt_file = job_dir / "sottotitoli_ugc.srt"
        base.make_srt(script, total, srt_file)

        base.set_job(job_id, progress=48, message="Preparazione presenter e B-roll")
        presenter_loop = job_dir / "presenter_continuity.mp4"
        base.normalize_segment(job_id, presenter, presenter_loop, 0.0, max(total, 1.0), False)

        base.set_job(job_id, progress=75, message="Montaggio video narrato")
        final = job_dir / "REEL_UGC_FINALE.mp4"
        base.compose_final(job_id, presenter_loop, voice_out, brolls, srt_file, final, job_dir)

        artifacts = [
            {"name": final.name, "label": "Video Academy finale", "url": f"/api/jobs/{job_id}/download/{final.name}"},
            {"name": voice_out.name, "label": "Voce italiana", "url": f"/api/jobs/{job_id}/download/{voice_out.name}"},
            {"name": script_file.name, "label": "Script", "url": f"/api/jobs/{job_id}/download/{script_file.name}"},
            {"name": srt_file.name, "label": "Sottotitoli", "url": f"/api/jobs/{job_id}/download/{srt_file.name}"},
        ]
        base.set_job(
            job_id,
            status="completed",
            progress=100,
            message="Video Academy pronto — modalità continuità senza lip-sync",
            artifacts=artifacts,
            video_url=f"/api/jobs/{job_id}/download/{final.name}",
        )
        base.add_log(job_id, "Video Academy completato senza MuseTalk: presenter/B-roll + voce + sottotitoli.")
    except InterruptedError:
        base.set_job(job_id, status="stopped", progress=100, message="Elaborazione fermata")
        base.add_log(job_id, "STOP ricevuto: processo interrotto.")
    except Exception as exc:
        base.set_job(job_id, status="failed", progress=100, message="Generazione non riuscita", error=str(exc))
        base.add_log(job_id, f"ERRORE ACADEMY: {exc}")


base.run_ugc_job = run_academy_job

if ACADEMY_ROOT.exists():
    base.app.mount("/academy", StaticFiles(directory=str(ACADEMY_ROOT), html=True), name="academy")

    @base.app.get("/")
    def academy_root() -> RedirectResponse:
        return RedirectResponse(url="/academy/")


if __name__ == "__main__":
    base.ensure_dirs()
    base.PID_FILE.write_text(str(os.getpid()), encoding="ascii")
    try:
        # Accessible from the office PC and phones/tablets on the same private Wi-Fi/LAN.
        uvicorn.run(base.app, host="0.0.0.0", port=base.PORT, log_level="info")
    finally:
        base.PID_FILE.unlink(missing_ok=True)
