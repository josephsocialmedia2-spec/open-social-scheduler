from __future__ import annotations

import asyncio
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any


class AudioAdapter:
    """Add generated Italian voice-over and an original low-volume music bed.

    This adapter is independent from the legacy visual renderer. It keeps the
    already-proven F1 TTS fallback strategy while Renderer V2 owns the visuals.
    """

    name = "edge-tts-piper-ffmpeg"

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    async def _edge_save(text: str, out: Path) -> None:
        import edge_tts

        await edge_tts.Communicate(
            text=text,
            voice="it-IT-IsabellaNeural",
            rate="-2%",
            volume="+0%",
        ).save(str(out))

    def _voice(self, text: str, temp: Path) -> Path | None:
        clean = str(text or "").strip()
        if not clean:
            return None
        mp3 = temp / "voice.mp3"
        try:
            asyncio.run(self._edge_save(clean, mp3))
            if mp3.exists() and mp3.stat().st_size > 1000:
                return mp3
        except Exception as exc:
            print(f"WARN Renderer V2 edge_tts: {exc}", file=sys.stderr)

        wav = temp / "voice.wav"
        data_dir = Path(os.getenv("PIPER_DATA_DIR", str(self.root / ".cache" / "piper")))
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "piper",
                    "-m",
                    "it_IT-paola-medium",
                    "--data-dir",
                    str(data_dir),
                    "-f",
                    str(wav),
                    "--",
                    clean,
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if proc.returncode == 0 and wav.exists() and wav.stat().st_size > 1000:
                return wav
            print(
                "WARN Renderer V2 piper: " + (proc.stderr.strip() or f"exit {proc.returncode}"),
                file=sys.stderr,
            )
        except Exception as exc:
            print(f"WARN Renderer V2 piper: {exc}", file=sys.stderr)
        return None

    @staticmethod
    def _music(out: Path, seconds: float) -> Path:
        sr = 22050
        notes = [196.0, 246.94, 293.66, 392.0, 220.0, 277.18, 329.63, 440.0]
        total = int(sr * max(1.0, seconds))
        with wave.open(str(out), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            frames = bytearray()
            for i in range(total):
                t = i / sr
                f0 = notes[int(t / 2.0) % len(notes)]
                sample = (
                    math.sin(2 * math.pi * f0 * t) * 0.50
                    + math.sin(2 * math.pi * f0 * 0.5 * t) * 0.22
                ) * 0.07
                frames += struct.pack("<h", max(-32767, min(32767, int(sample * 32767))))
                if len(frames) >= sr * 2 * 4:
                    wf.writeframes(frames)
                    frames.clear()
            if frames:
                wf.writeframes(frames)
        return out

    def apply(self, video: Path, spec: dict[str, Any]) -> dict[str, Any]:
        audio = spec.get("audio") or {}
        text = str(audio.get("voiceover_text") or "").strip()
        duration = float((spec.get("content") or {}).get("duration_s") or 8)
        if not text and not bool(audio.get("music_bed", False)):
            return {"applied": False, "voice": False, "music": False, "engine": self.name}

        with tempfile.TemporaryDirectory(prefix="f1-renderer-v2-audio-") as td:
            temp = Path(td)
            voice = self._voice(text, temp) if text else None
            music = self._music(temp / "music.wav", duration + 1.0)
            mixed = temp / "mixed.mp4"
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)]
            if voice:
                cmd += ["-i", str(voice)]
                voice_idx = 1
                music_idx = 2
            else:
                voice_idx = None
                music_idx = 1
            cmd += ["-i", str(music)]

            if voice_idx is not None:
                filters = (
                    f"[{voice_idx}:a]volume=1.0,apad[voice];"
                    f"[{music_idx}:a]volume=0.045,apad[music];"
                    "[voice][music]amix=inputs=2:duration=longest:dropout_transition=2[aout]"
                )
            else:
                filters = f"[{music_idx}:a]volume=0.065,apad[aout]"

            cmd += [
                "-filter_complex",
                filters,
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-movflags",
                "+faststart",
                "-t",
                f"{duration:.3f}",
                str(mixed),
            ]
            proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
            if proc.returncode != 0 or not mixed.exists() or mixed.stat().st_size < 40_000:
                raise RuntimeError(
                    "Renderer V2 audio mux failed: "
                    + (proc.stderr.strip() or f"exit {proc.returncode}")
                )
            mixed.replace(video)
        return {
            "applied": True,
            "voice": bool(voice),
            "music": True,
            "engine": self.name,
        }
