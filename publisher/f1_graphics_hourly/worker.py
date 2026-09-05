import os
import json
import base64
from pathlib import Path

import pandas as pd
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
INPUT_XLSX = ROOT / "publisher" / "f1_graphics_hourly" / "queries.xlsx"
STATE_FILE = ROOT / "publisher" / "f1_graphics_hourly" / "state.json"
OUTPUT_DIR = ROOT / "publisher" / "final_assets"
CAPTION_DIR = ROOT / "publisher" / "final_assets" / "captions"

IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5.6-terra")
REFERENCES = os.getenv("F1_CAPTION_REFERENCES", "").strip()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"next_row": 0, "completed": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def find_query_column(df):
    normalized = {str(c).strip().lower(): c for c in df.columns}
    for candidate in ("query", "queries", "prompt", "testo", "ricerca"):
        if candidate in normalized:
            return normalized[candidate]
    if len(df.columns) == 1:
        return df.columns[0]
    raise RuntimeError("Nessuna colonna query trovata. Usa una colonna chiamata QUERY.")


def build_caption(query):
    prompt = f"""Crea una caption social professionale per F1 Immobiliare partendo dalla seguente query.\n\nQUERY:\n{query}\n\nRIFERIMENTI OBBLIGATORI:\n{REFERENCES or '[nessun riferimento configurato]'}\n\nRestituisci solo la caption finale, senza spiegazioni."""
    response = client.responses.create(model=TEXT_MODEL, input=prompt)
    return response.output_text.strip()


def build_graphic_prompt(query):
    return (
        f"{query}\n\n"
        "Il modello grafico di riferimento deve essere rispettato fedelmente: stile F1 Immobiliare, "
        "gerarchia chiara, testo perfettamente leggibile, composizione social premium. "
        "Genera una singola grafica finale pronta per la pubblicazione."
    )


def generate_image(query, out_path):
    result = client.images.generate(
        model=IMAGE_MODEL,
        prompt=build_graphic_prompt(query),
        size="1024x1024",
    )
    item = result.data[0]
    if getattr(item, "b64_json", None):
        out_path.write_bytes(base64.b64decode(item.b64_json))
        return
    if getattr(item, "url", None):
        import requests
        r = requests.get(item.url, timeout=120)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        return
    raise RuntimeError("La generazione immagine non ha restituito dati utilizzabili.")


def main():
    if not INPUT_XLSX.exists():
        raise RuntimeError(f"File Excel mancante: {INPUT_XLSX}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CAPTION_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(INPUT_XLSX)
    col = find_query_column(df)
    state = load_state()
    idx = int(state.get("next_row", 0))

    if idx >= len(df):
        print("Tutte le righe del file Excel sono state elaborate.")
        return

    raw = df.iloc[idx][col]
    if pd.isna(raw) or not str(raw).strip():
        raise RuntimeError(f"Riga Excel {idx + 2} vuota: arresto per non saltare nessuna riga.")

    query = str(raw).strip()
    number = idx + 1
    stem = f"F1-{number:03d}"
    image_path = OUTPUT_DIR / f"{stem}.png"
    caption_path = CAPTION_DIR / f"{stem}.txt"

    print(f"Elaboro riga {idx + 2}: {query}")
    caption = build_caption(query)
    generate_image(query, image_path)
    caption_path.write_text(caption, encoding="utf-8")

    state.setdefault("completed", []).append({
        "excel_index": idx,
        "excel_row": idx + 2,
        "query": query,
        "image": str(image_path.relative_to(ROOT)),
        "caption": str(caption_path.relative_to(ROOT)),
    })
    state["next_row"] = idx + 1
    save_state(state)
    print(f"Creato {image_path.name} e relativa caption.")


if __name__ == "__main__":
    main()
