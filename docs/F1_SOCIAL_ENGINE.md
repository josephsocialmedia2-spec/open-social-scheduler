# F1 Social Engine

## Obiettivo

Trasformare `open-social-scheduler` in un motore di pubblicazione automatico per F1 Immobiliare. Canva non è il publisher: i contenuti vengono messi in coda nel repository, GitHub Actions li inoltra a Postiz e Postiz pubblica tramite le API ufficiali dei social.

## Architettura

```text
ChatGPT / generatore contenuti
        ↓
publisher/queue.json + media
        ↓
GitHub Actions — F1 Social Publisher
        ↓
Postiz API
        ↓
Facebook Page
Instagram
TikTok
LinkedIn Page
YouTube
Pinterest
```

Il workflow gira su push e anche ogni ora come controllo di sicurezza. Un job viene inviato a Postiz una sola volta per piattaforma e viene marcato `scheduled` dopo l'invio.

## Configurazione obbligatoria una tantum

1. Attivare Postiz Cloud oppure una propria installazione Postiz raggiungibile via HTTPS.
2. Collegare in Postiz gli account ufficiali F1 tramite OAuth.
3. Generare la `POSTIZ_API_KEY`.
4. In GitHub aprire `Settings → Secrets and variables → Actions` del repository `open-social-scheduler` e creare il secret `POSTIZ_API_KEY`.
5. Se si usa Postiz self-hosted, creare anche la variabile Actions `POSTIZ_API_URL`, per esempio `https://postiz.example.it/public/v1`.
6. Per Pinterest indicare nel job anche `pinterest_board`.
7. Se sono collegati più account dello stesso social, usare `account_hint` nel job per selezionare quello corretto.

Non inserire token, password, App Secret o API key dentro file pubblici del repository.

## Strategia contenuti F1 mutuata dai migliori sistemi real-estate

### 1. Attract
Contenuti progettati per raggiungere nuovi proprietari locali:
- curiosità immobiliari locali;
- errori di valutazione;
- cosa incide sul valore;
- quartieri, comuni e microzone;
- mercato locale;
- Reel brevi e caroselli ad alto salvataggio.

### 2. Nurture
Contenuti che dimostrano competenza:
- metodo di valutazione;
- comparabili;
- prezzo richiesto vs prezzo di vendita;
- casi pratici;
- documentazione necessaria;
- spiegazioni semplici di estimo e mercato.

### 3. Convert
Contenuti con un'unica azione richiesta:
- `Scrivi VALORE`;
- valutazione gratuita;
- mini-report locale;
- richiesta di analisi immobile;
- lead magnet proprietario/venditore.

## Programmazione base

Quattro uscite giornaliere:

- 09:00 — Attract / errore / domanda;
- 12:30 — Nurture / contenuto educativo;
- 17:30 — Hyperlocal / comune o microzona;
- 20:30 — Convert / valutazione gratuita.

Gli orari vengono salvati con timezone nel job; Postiz riceve l'orario normalizzato in UTC, evitando problemi di ora legale.

## Moduli da sviluppare dopo il primo test

- Brand Master F1: logo, palette, font, CTA, safe area 9:16;
- generatore automatico 4 contenuti/giorno;
- rotazione comuni;
- market report settimanale;
- listing-to-Reel;
- keyword `VALORE` e gestione lead;
- analytics per post e piattaforma;
- feedback loop: aumentare i format che generano DM, richieste valutazione e lead;
- dashboard stato: bozza → pronto → schedulato → pubblicato → errore.

## File operativi

- `publisher/postiz_publish.py` — publisher Postiz;
- `publisher/queue.json` — coda reale;
- `publisher/queue.example.json` — esempio completo;
- `.github/workflows/social-publisher.yml` — automazione GitHub Actions.
