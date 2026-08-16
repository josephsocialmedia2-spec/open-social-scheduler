# Open Social Scheduler — multi-client social publishing engine

Open Social Scheduler ora ha due livelli indipendenti:

1. **CRM locale condiviso** via Google Drive Desktop, mantenuto per clienti/post/backup.
2. **Social Engine cloud** via GitHub Actions + Postiz, per generare, renderizzare, schedulare e misurare contenuti social di più clienti.

## Architettura Social Engine

```text
publisher/clients/<cliente>.json
        +
publisher/content_bank/<cliente>.json
        ↓
build_daily_queue.py
        ↓
render_reels.py → MP4 1080x1920
        ↓
postiz_publish.py
        ↓
Postiz self-hosted / API ufficiali
        ↓
Facebook · Instagram · TikTok · LinkedIn · YouTube · Pinterest
```

Ogni cliente ha ID social espliciti. Il publisher **non indovina mai quale pagina usare**: se l'integration ID del tenant non è configurato, il job resta bloccato.

### Primo tenant di collaudo

`publisher/clients/f1-immobiliare.json`

F1 Immobiliare è configurato con quattro slot giornalieri:
- 09:00 — Attract
- 12:30 — Nurture
- 17:30 — Hyperlocal
- 20:30 — Convert

La banca contenuti iniziale è in `publisher/content_bank/f1-immobiliare.json`.

## Postiz self-hosted

Postiz è tenuto come servizio separato per rispettare la sua licenza AGPL-3.0 e rendere gli aggiornamenti indipendenti dal controller OSS.

```bash
bash postiz-stack/bootstrap_postiz.sh
cp postiz-stack/postiz.env.example postiz-stack/postiz.env
# configura dominio HTTPS e OAuth provider
bash postiz-stack/start_postiz.sh
```

La release applicativa è fissata a `v2.22.1`. Il workflow `Validate Postiz Stack` clona upstream e verifica automaticamente licenza, tag e Docker Compose.

## GitHub Actions

- `Open Social Engine Daily` — crea la coda, renderizza i Reel, riconcilia tenant/media e invia i job pronti a Postiz.
- `F1 Social Publisher` — publisher di compatibilità/event-driven sulla coda.
- `Social Analytics Snapshot` — salva snapshot analytics per le integrazioni configurate.
- `Validate Postiz Stack` — verifica clone e deployment stack Postiz.

Secret richiesto per la pubblicazione:

`POSTIZ_API_KEY`

Variabile consigliata per self-hosted:

`POSTIZ_API_URL=https://<dominio-postiz>/public/v1`

Le credenziali OAuth dei social restano esclusivamente sul server Postiz.

---

## CRM locale condiviso via Google Drive

Il programma salva i dati direttamente nella cartella sincronizzata da **Google Drive per desktop**:

```text
Open Social Scheduler CRM/
├── clients/
├── posts/
├── backups/
└── meta.json
```

Ogni cliente e ogni pubblicazione sono file JSON separati con ID stabile. Un computer non riscrive l'intero archivio dell'altro. Il programma controlla le modifiche ogni 5 secondi e segnala i conflitti se lo stesso record è stato modificato da un altro computer.

### Installazione Windows CRM

1. Installa e configura Google Drive per desktop.
2. Scarica il repository con **Code → Download ZIP**.
3. Estrai completamente lo ZIP.
4. Esegui `INSTALLA.bat`.
5. Il programma individua `Il mio Drive`; se non lo trova, chiede di selezionarlo.
6. Viene creato il collegamento **Open Social Scheduler** sul desktop.

Sul secondo computer esegui lo stesso `INSTALLA.bat` usando lo stesso account Google Drive.
