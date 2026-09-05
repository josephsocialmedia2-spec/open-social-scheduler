from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class PillowFallbackAdapter:
    name = "legacy-pillow-fallback"

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _font(size: int, bold: bool = False):
        path = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    def _frame(self, spec: dict[str, Any], path: Path, vertical: bool) -> Path:
        width, height = (1080, 1920) if vertical else (1080, 1350)
        brand = spec.get("brand") or {}
        content = spec.get("content") or {}
        bg = str(brand.get("background") or "#07100A")
        fg = str(brand.get("foreground") or "#FFFFFF")
        green = str(brand.get("primary") or "#66C500")
        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)
        margin = 64
        draw.rounded_rectangle(
            (margin, margin, width - margin, height - margin),
            radius=36,
            outline=green,
            width=6,
        )
        draw.rectangle((margin, margin, width - margin, margin + 22), fill=green)
        draw.text(
            (width // 2, int(height * 0.13)),
            str(brand.get("name") or "F1 IMMOBILIARE"),
            font=self._font(54, True),
            fill=fg,
            anchor="mm",
        )
        title = str(content.get("title") or "F1 IMMOBILIARE").upper()
        subtitle = str(content.get("subtitle") or content.get("body") or "")
        draw.multiline_text(
            (width // 2, int(height * 0.42)),
            title,
            font=self._font(68 if vertical else 58, True),
            fill=fg,
            anchor="mm",
            align="center",
            spacing=16,
        )
        draw.multiline_text(
            (width // 2, int(height * 0.62)),
            subtitle[:280],
            font=self._font(34 if vertical else 30),
            fill="#D6DDD7",
            anchor="mm",
            align="center",
            spacing=12,
        )
        cta = str(content.get("cta") or brand.get("phone_primary") or "371 370 8294")
        draw.text(
            (width // 2, int(height * 0.84)),
            cta,
            font=self._font(38, True),
            fill=green,
            anchor="mm",
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "JPEG", quality=93, optimize=True)
        return path

    def render(self, spec: dict[str, Any], output: Path) -> list[Path]:
        kind = str(spec.get("type") or "static")
        if kind in {"reel", "video", "story", "ugc"}:
            frame = output.with_suffix(".fallback.jpg")
            self._frame(spec, frame, vertical=True)
            duration = float((spec.get("content") or {}).get("duration_s") or 8)
            cmd = [
                "ffmpeg", "-y", "-loglevel", "error", "-loop", "1",
                "-i", str(frame), "-t", str(duration), "-r", "30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-vf", "scale=1080:1920", "-movflags", "+faststart", str(output),
            ]
            proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
            frame.unlink(missing_ok=True)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or "FFmpeg fallback failed")
            return [output]
        return [self._frame(spec, output, vertical=False)]
