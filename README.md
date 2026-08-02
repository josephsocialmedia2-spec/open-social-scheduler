# Open Social Scheduler

Web app operativa per gestire il calendario editoriale di **20 clienti** con importazione ed esportazione CSV a parametri fissi.

## Funzioni disponibili

- 20 slot cliente fissi, identificati da `C01` a `C20`.
- Dashboard con clienti attivi, contenuti mensili, approvazioni, programmati e pubblicati.
- Calendario mensile multi-cliente.
- Inserimento, modifica, duplicazione ed eliminazione delle pubblicazioni.
- Filtri per cliente, piattaforma, stato e ricerca testuale.
- Importazione CSV con validazione bloccante.
- Esportazione CSV dei risultati filtrati.
- Backup e ripristino JSON.
- Salvataggio locale nel browser tramite `localStorage`.
- Media Lab locale per estrazione audio, trascrizione Whisper e sottotitoli.
- Pubblicazione automatica della web app tramite GitHub Pages.

## Media Lab locale

Il menu principale include la voce **Media Lab locale**. La pagina online apre il motore installato sul computer all’indirizzo:

`http://127.0.0.1:8765`

Il motore è disponibile nella cartella `local-media-lab` e utilizza:

- FFmpeg locale per estrarre audio in MP3, WAV o M4A;
- Whisper locale per trascrivere in italiano;
- output TXT, DOCX e SRT;
- cartella risultati configurabile;
- nessun caricamento di video, audio o trascrizioni su servizi esterni.

Per Windows:

1. scaricare ed estrarre il repository;
2. aprire `local-media-lab`;
3. eseguire `INSTALLA_MEDIA_LAB.bat` una sola volta;
4. eseguire `AVVIA_MEDIA_LAB.bat` quando si deve lavorare.

## Avvio

La pagina principale è `index.html`. Il workflow `.github/workflows/pages.yml` pubblica il progetto su GitHub Pages a ogni aggiornamento del branch `main`.

URL previsto:

`https://josephsocialmedia2-spec.github.io/open-social-scheduler/`

Nel repository deve essere selezionata una sola volta la sorgente **GitHub Actions** in `Settings → Pages → Build and deployment`.

## Parametri CSV fissi

Ordine obbligatorio delle colonne:

```text
cliente_id,data,ora,piattaforma,formato,rubrica,titolo,copy,cta,link_media,stato,responsabile,note
```

### Valori ammessi

**cliente_id**

`C01` fino a `C20`

**piattaforma**

- `FACEBOOK`
- `INSTAGRAM`
- `TIKTOK`
- `LINKEDIN`
- `YOUTUBE`
- `GOOGLE_BUSINESS_PROFILE`

**formato**

- `POST`
- `REEL`
- `STORY`
- `CAROSELLO`
- `VIDEO`
- `SHORT`
- `ARTICOLO`

**stato**

- `BOZZA`
- `DA_APPROVARE`
- `APPROVATO`
- `PROGRAMMATO`
- `PUBBLICATO`
- `SOSPESO`

### Formati data e ora

- `data`: `AAAA-MM-GG`
- `ora`: `HH:MM`, formato 24 ore

Il file `template-pubblicazioni.csv` contiene una riga di esempio pronta da duplicare.

## Struttura

```text
open-social-scheduler/
├── index.html
├── media-lab.html
├── styles.css
├── app.js
├── template-pubblicazioni.csv
├── .nojekyll
├── .github/workflows/pages.yml
├── local-media-lab/
│   ├── server.py
│   ├── requirements.txt
│   ├── INSTALLA_MEDIA_LAB.bat
│   ├── AVVIA_MEDIA_LAB.bat
│   ├── ARRESTA_MEDIA_LAB.bat
│   └── static/
├── backend/
│   ├── app/main.py
│   └── requirements.txt
└── docs/
```

## Limite attuale

La versione operativa gestisce pianificazione, approvazione e archivio editoriale. Non invia ancora automaticamente i contenuti alle API di Facebook, Instagram, TikTok, LinkedIn o YouTube. L’integrazione API potrà essere aggiunta al backend senza modificare il formato CSV o gli ID cliente.
