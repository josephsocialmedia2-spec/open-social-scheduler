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
- Pubblicazione automatica della web app tramite GitHub Pages.

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
├── styles.css
├── app.js
├── template-pubblicazioni.csv
├── .nojekyll
├── .github/workflows/pages.yml
├── backend/
│   ├── app/main.py
│   └── requirements.txt
└── docs/
```

## Limite attuale

La versione operativa gestisce pianificazione, approvazione e archivio editoriale. Non invia ancora automaticamente i contenuti alle API di Facebook, Instagram, TikTok, LinkedIn o YouTube. L’integrazione API potrà essere aggiunta al backend senza modificare il formato CSV o gli ID cliente.
