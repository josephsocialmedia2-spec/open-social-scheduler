#!/usr/bin/env python3
"""Burn readable subtitles into generated Reel MP4 files.

Subtitles are derived from each job voiceover and split evenly across the actual
video duration. The audio track is preserved while video is re-encoded with
libass subtitles. Carousel media is untouched.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "publisher" / "queue.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def split_text(text: str, pieces: int) -> list[str]:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean or pieces <= 0:
        return []
    words = clean.split()
    pieces = min(pieces, len(words))
    base, extra = divmod(len(words), pieces)
    out: list[str] = []
    pos = 0
    for idx in range(pieces):
        count = base + (1 if idx < extra else 0)
        out.append(" ".join(words[pos:pos + count]))
        pos += count
    return out


def srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_srt(path: Path, text: str, total: float, pieces: int) -> None:
    chunks = split_text(text, pieces)
    if not chunks:
        path.write_text("", encoding="utf-8")
        return
    usable = max(0.5, total - 0.12)
    span = usable / len(chunks)
    lines: list[str] = []
    for idx, chunk in enumerate(chunks, 1):
        start = (idx - 1) * span
        end = min(usable, idx * span)
        lines += [str(idx), f"{srt_time(start)} --> {srt_time(end)}", chunk, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def burn(job: dict[str, Any]) -> bool:
    if str(job.get("format") or "reel").lower() != "reel":
        return False
    text = str(job.get("voiceover") or "").strip()
    media = job.get("media")
    if not text or not isinstance(media, str) or not media.endswith(".mp4"):
        return False
    video = ROOT / media
    if not video.exists() or video.stat().st_size < 10_000:
        return False
    slides = max(1, len(job.get("slides") or []))
    total = duration(video)
    if total <= 0:
        return False

    with tempfile.TemporaryDirectory(prefix="f1-subtitles-") as raw:
        tmp = Path(raw)
        srt = tmp / "subtitles.srt"
        output = tmp / "subtitled.mp4"
        write_srt(srt, text, total, slides)
        style = (
            "FontName=DejaVu Sans,FontSize=15,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,"
            "Alignment=2,MarginV=115"
        )
        escaped = str(srt).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        vf = f"subtitles='{escaped}':force_style='{style}'"
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video), "-vf", vf,
                "-c:v", "libx264", "-profile:v", "high", "-level", "4.0",
                "-crf", "20", "-preset", "medium", "-c:a", "copy",
                "-movflags", "+faststart", str(output),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if not output.exists() or output.stat().st_size < 10_000:
            raise RuntimeError(f"Subtitle render failed for {job.get('id')}")
        shutil.copy2(output, video)
    return True


def main() -> int:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg/ffprobe required")
    if not QUEUE_PATH.exists():
        return 0
    queue = load_json(QUEUE_PATH)
    done = 0
    for job in queue.get("jobs", []):
        if job.get("enabled", True) and burn(job):
            done += 1
            print(f"Subtitles burned: {job.get('id')}")
    print(f"Subtitled {done} Reel(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
