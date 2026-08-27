from __future__ import annotations

import argparse
from pathlib import Path

import torch
import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS


def device_name() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera voce UGC italiana locale con Chatterbox Multilingual")
    parser.add_argument("--text-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--reference", default="")
    parser.add_argument("--exaggeration", type=float, default=0.42)
    parser.add_argument("--cfg-weight", type=float, default=0.35)
    parser.add_argument("--temperature", type=float, default=0.72)
    args = parser.parse_args()

    text = Path(args.text_file).read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit("Testo vuoto")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    reference = Path(args.reference).resolve() if args.reference else None
    if reference is not None and not reference.exists():
        raise SystemExit(f"Voce di riferimento non trovata: {reference}")

    device = device_name()
    print(f"[UGC-TTS] Device: {device}", flush=True)
    print("[UGC-TTS] Caricamento Chatterbox Multilingual...", flush=True)
    model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")

    kwargs = {
        "language_id": "it",
        "exaggeration": max(0.25, min(1.2, args.exaggeration)),
        "cfg_weight": max(0.2, min(1.0, args.cfg_weight)),
        "temperature": max(0.2, min(1.5, args.temperature)),
    }
    if reference is not None:
        kwargs["audio_prompt_path"] = str(reference)
        print("[UGC-TTS] Clonazione timbro dalla voce femminile fornita.", flush=True)
    else:
        print("[UGC-TTS] Nessun riferimento: uso voce predefinita del modello.", flush=True)

    wav = model.generate(text, **kwargs)
    ta.save(str(output), wav, model.sr)
    print(f"[UGC-TTS] Creato: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
