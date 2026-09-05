import os
import json
import shutil
import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
INPUT_XLSX = ROOT / "publisher" / "f1_graphics_hourly" / "queries.xlsx"
STATE_FILE = ROOT / "publisher" / "f1_graphics_hourly" / "state.json"
OUTPUT_DIR = ROOT / "publisher" / "final_assets"
CAPTION_DIR = OUTPUT_DIR / "captions"
DOWNLOAD_DIR = ROOT / "publisher" / "f1_graphics_hourly" / "downloads"
PROFILE_DIR = Path.home() / ".f1_chatgpt_chrome_profile"

CHAT_URL = "https://chatgpt.com/g/g-6a9c210485488191b072eb694c2f114c-generatore-grafica-f1/c/6a9c2a0a-abdc-83eb-9bf4-3a4dbeb6f82f"
GRAPHIC_SUFFIX = "l modello è già allegato qui in chat"

DEFAULT_REFERENCES = """F1 Immobiliare
Valutazione gratuita: https://www.agentpricing.com/j.malafronte
Telefono: +39 371 370 8294
Secondo telefono: +39 371 424 6300
Email: f1immobiliaresusa@outlook.it"""
REFERENCES = os.getenv("F1_CAPTION_REFERENCES", DEFAULT_REFERENCES).strip()

F1_CAPTION_POLICY = """
Le caption devono spiegare il lavoro concreto svolto da F1 Immobiliare. Non limitarti mai a dire che un immobile viene pubblicato online.

PRINCIPI OBBLIGATORI:
1. Spiega che prima di promuovere un immobile F1 studia immobile, concorrenza, mercato locale, fascia di prezzo, posizione, servizi, target e motivazioni d'acquisto.
2. Quando pertinente cita attività concrete: fotografie curate, video e Reel, planimetrie leggibili, render, caroselli, contenuti social, annuncio e scheda completa, promozione territoriale, Google, Pinterest, gruppi locali, WhatsApp, database acquirenti.
3. Fai capire che un annuncio non è una campagna: la strategia deve attirare l'acquirente corretto, comunicare i punti di forza, rispondere alle domande, differenziare l'immobile e trasformare interesse in visite.
4. Quando pertinente parla della preparazione prima della pubblicità: ordine, luce, inquadrature, presentazione ambienti, criticità, documentazione, home staging e render.
5. Per immobili da ristrutturare o da valorizzare, mostra il potenziale con render realistici, ipotesi distributive, arredo virtuale, prima/dopo e fasce indicative dei lavori, sempre con trasparenza sullo stato attuale.
6. Spiega la promozione geolocalizzata: il messaggio va adattato a famiglie, coppie, investitori, seconde case o persone che vogliono trasferirsi nel territorio.
7. Dopo la pubblicazione il lavoro continua: F1 controlla visualizzazioni, salvataggi, clic, richieste, contatti qualificati, visite, feedback e proposte. Se i risultati non arrivano, valuta prezzo, presentazione, comunicazione o distribuzione.
8. Non inventare dati, risultati, numeri, clienti, visite o performance non forniti.
9. Mantieni un tono professionale, concreto e comprensibile. Evita frasi vuote come 'massima visibilità', 'pubblicità a 360 gradi' o 'siamo i migliori'.
10. Ogni caption deve essere coerente con la QUERY e con il comune o la tipologia immobiliare citata. Non deve sembrare un testo generico riciclato.

STRUTTURA CONSIGLIATA:
HOOK -> problema/desiderio -> cosa fa concretamente F1 -> perché serve -> CTA -> riferimenti -> hashtag.

RUOTA NATURALMENTE TRA QUESTI 6 ANGOLI, scegliendo quello più coerente con la query e senza ripetere sempre lo stesso schema:
A. Come promuoviamo il tuo immobile.
B. Non basta pubblicare un annuncio.
C. Preparazione prima della pubblicità.
D. Promozione geolocalizzata e target corretto.
E. Valorizzazione di immobili da ristrutturare.
F. Controllo dei risultati dopo la pubblicazione.

CTA PREFERITA:
Invita a richiedere una valutazione gratuita tramite https://www.agentpricing.com/j.malafronte

HASHTAG BASE, da adattare senza esagerare:
#F1Immobiliare #VendereCasa #ValleDiSusa #MarketingImmobiliare #ValutazioneImmobiliare
""".strip()


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


def make_driver():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(DOWNLOAD_DIR.resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    return webdriver.Chrome(options=options)


def prompt_box(driver, timeout=60):
    wait = WebDriverWait(driver, timeout)
    selectors = [
        (By.ID, "prompt-textarea"),
        (By.CSS_SELECTOR, "textarea"),
        (By.CSS_SELECTOR, "div[contenteditable='true']"),
    ]
    last_error = None
    for by, selector in selectors:
        try:
            el = wait.until(EC.presence_of_element_located((by, selector)))
            if el.is_displayed():
                return el
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Casella prompt ChatGPT non trovata: {last_error}")


def send_prompt(driver, text):
    box = prompt_box(driver)
    box.click()
    try:
        box.send_keys(Keys.CONTROL, "a")
        box.send_keys(Keys.BACKSPACE)
    except Exception:
        pass
    box.send_keys(text)
    box.send_keys(Keys.ENTER)


def wait_until_generation_finishes(driver, timeout=600):
    end = time.time() + timeout
    saw_stop = False
    while time.time() < end:
        stop_buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'stop') or contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'interrompi')]",
        )
        visible = [b for b in stop_buttons if b.is_displayed()]
        if visible:
            saw_stop = True
        elif saw_stop:
            return
        time.sleep(3)
    if saw_stop:
        raise TimeoutException("La generazione ChatGPT non si è conclusa entro il timeout.")


def latest_assistant_container(driver):
    candidates = driver.find_elements(By.CSS_SELECTOR, "article")
    visible = [x for x in candidates if x.is_displayed()]
    return visible[-1] if visible else driver.find_element(By.TAG_NAME, "body")


def newest_image(driver):
    container = latest_assistant_container(driver)
    images = container.find_elements(By.TAG_NAME, "img")
    usable = []
    for img in images:
        try:
            size = img.size
            if size.get("width", 0) >= 300 and size.get("height", 0) >= 300 and img.is_displayed():
                usable.append(img)
        except Exception:
            continue
    if usable:
        return usable[-1]

    all_images = driver.find_elements(By.TAG_NAME, "img")
    for img in reversed(all_images):
        try:
            size = img.size
            if size.get("width", 0) >= 300 and size.get("height", 0) >= 300 and img.is_displayed():
                return img
        except Exception:
            continue
    raise RuntimeError("Grafica generata non trovata nella pagina.")


def wait_for_new_download(before, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        current = {p for p in DOWNLOAD_DIR.iterdir() if p.is_file() and not p.name.endswith(".crdownload")}
        new_files = sorted(current - before, key=lambda p: p.stat().st_mtime, reverse=True)
        if new_files:
            return new_files[0]
        time.sleep(2)
    return None


def download_latest_graphic(driver, final_path):
    before = {p for p in DOWNLOAD_DIR.iterdir() if p.is_file()}
    img = newest_image(driver)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", img)
    img.click()
    time.sleep(2)

    xpaths = [
        "//button[contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'download')]",
        "//button[contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'scarica')]",
        "//*[@role='button' and contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'download')]",
        "//*[@role='button' and contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'scarica')]",
        "//button[contains(translate(@title,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'download')]",
        "//button[contains(translate(@title,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'scarica')]",
    ]

    clicked = False
    for xpath in xpaths:
        for button in driver.find_elements(By.XPATH, xpath):
            if button.is_displayed():
                try:
                    button.click()
                    clicked = True
                    break
                except Exception:
                    pass
        if clicked:
            break

    if clicked:
        downloaded = wait_for_new_download(before)
        if downloaded:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            if final_path.exists():
                final_path.unlink()
            shutil.move(str(downloaded), str(final_path))
            return

    final_path.parent.mkdir(parents=True, exist_ok=True)
    img.screenshot(str(final_path))


def capture_latest_text(driver):
    container = latest_assistant_container(driver)
    text = container.text.strip()
    if not text:
        raise RuntimeError("La risposta caption di ChatGPT è vuota.")
    return text


def build_caption_prompt(query):
    return (
        "Crea una caption social finale per F1 Immobiliare.\n\n"
        f"QUERY DI PARTENZA:\n{query}\n\n"
        f"LINEE GUIDA OBBLIGATORIE:\n{F1_CAPTION_POLICY}\n\n"
        f"RIFERIMENTI DA INSERIRE:\n{REFERENCES}\n\n"
        "Regole finali: restituisci esclusivamente la caption pronta da pubblicare; non spiegare il ragionamento; "
        "non creare immagini; non inventare dati; evita di ripetere meccanicamente la query; rendi il testo specifico, concreto e diverso dalle caption precedenti."
    )


def ensure_logged_in(driver):
    driver.get(CHAT_URL)
    time.sleep(5)
    try:
        prompt_box(driver, timeout=30)
    except Exception as exc:
        raise RuntimeError(
            "ChatGPT non è pronto. Apri manualmente Chrome con il profilo dedicato, accedi a ChatGPT una volta e rilancia il workflow."
        ) from exc


def main():
    if not INPUT_XLSX.exists():
        raise RuntimeError(f"File Excel mancante: {INPUT_XLSX}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CAPTION_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
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
    driver = None
    try:
        driver = make_driver()
        ensure_logged_in(driver)

        send_prompt(driver, f"{query}\n\n{GRAPHIC_SUFFIX}")
        time.sleep(300)
        wait_until_generation_finishes(driver, timeout=300)
        download_latest_graphic(driver, image_path)

        send_prompt(driver, build_caption_prompt(query))
        wait_until_generation_finishes(driver, timeout=300)
        time.sleep(3)
        caption = capture_latest_text(driver)
        caption_path.write_text(caption, encoding="utf-8")

        state.setdefault("completed", []).append(
            {
                "excel_index": idx,
                "excel_row": idx + 2,
                "query": query,
                "image": str(image_path.relative_to(ROOT)),
                "caption": str(caption_path.relative_to(ROOT)),
            }
        )
        state["next_row"] = idx + 1
        save_state(state)
        print(f"Creato {image_path.name} e relativa caption.")
    finally:
        if driver:
            try:
                driver.quit()
            except WebDriverException:
                pass


if __name__ == "__main__":
    main()
