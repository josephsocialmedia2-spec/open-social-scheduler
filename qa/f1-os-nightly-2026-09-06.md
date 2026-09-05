# F1 OS — Nightly QA — 2026-09-06

Stato finale: **RELEASE BLOCCATA / errori e blocchi residui**

| Componente | Test | Esito | Errore / nota | Correzione applicata | Retest |
|---|---|---|---|---|---|
| Repository GitHub | accesso `main`, commit corrente e struttura | PASS | repository raggiungibile; HEAD verificato `6bb0bdf5a15867f4e45767411a07feee10d4f0ff` | — | PASS |
| GitHub Actions | ultimi run disponibili | PASS PARZIALE | ultimo run osservato `Direct Social Publisher - Automatic` concluso `success`; nessun failure trovato nel campione degli ultimi run recuperati | — | PASS PARZIALE |
| Release gate CI | status check sul commit HEAD | FAIL | nessuno status check associato al commit HEAD (`statuses: []`): non esiste evidenza di un gate globale che certifichi F1 OS prima del rilascio | — | FAIL |
| GitHub Pages | workflow di sync | PASS STRUTTURALE | workflow include `roleplay-immobiliare`, `f1-academy`, `f1-os-mobile`, `f1-os-cloud`, `f1-os-companion` | — | PASS STRUTTURALE |
| GitHub Pages | contenuto `gh-pages` | PASS STRUTTURALE | cartelle e asset F1 risultano presenti sul branch `gh-pages` | — | PASS STRUTTURALE |
| GitHub Pages/PWA | apertura HTTP reale da browser pubblico | BLOCCATO | il runner non ha potuto certificare gli endpoint live GitHub Pages; nessun PASS inventato | — | NON TESTATO LIVE |
| Supabase | tabelle F1 | PASS | `f1_records`, `contacts`, `field_visits`, `f1_daily_backups` presenti con RLS attivo | — | PASS |
| Supabase security | `f1_apply_mobile_action()` | PASS | SECURITY DEFINER ancora presente, ma EXECUTE per `anon` e `authenticated` risulta revocato | — | PASS |
| Supabase / sincronizzazione | dati reali | FAIL CRITICO | `f1_records=0`, `contacts=0`, `field_visits=0`: non è certificabile alcuna sincronizzazione PC ↔ cloud ↔ smartphone con dati reali | nessuna migrazione inventata senza sorgente PC | FAIL |
| Backup cloud | presenza backup giornalieri | FAIL | `f1_daily_backups=0` | — | FAIL |
| F1 OS desktop 1.5 | `python -m py_compile` | PASS | sorgente disponibile compila senza errori | — | PASS |
| Desktop UI | avvio headless | PASS | 17 tab costruite | — | PASS |
| CRM SQLite di test | inserimento contatto + lettura | PASS | CRUD minimo verificato su ambiente isolato | — | PASS |
| Coda prioritaria desktop | generazione da contatto sintetico | PASS | 1 contatto inserito → 1 voce in coda | — | PASS |
| Funnel Engine | valore target negativo | FAIL | con target mensile `-50000` produce `Vendite necessarie: -16/mese` invece di rifiutare input non valido | non patchato senza release desktop canonica + regression test completo | FAIL |
| Funnel Engine | conversione incarico→vendita = 0 | FAIL | produce `Incarichi necessari: 0/mese` invece di segnalare configurazione invalida | non patchato senza release desktop canonica + regression test completo | FAIL |
| Backup desktop di test | creazione + `PRAGMA integrity_check` | PASS | backup creato; integrità SQLite = `ok` | — | PASS |
| Restore desktop | funzione di ripristino | FAIL | nella sorgente 1.5 verificata esiste `backup()` ma non un restore equivalente | — | FAIL |
| Seller Signal → vie limitrofe → Internet → contatti pubblici | implementazione canonica | FAIL CRITICO | `f1-os-cloud/app.js` salva il Seller Signal in `f1_records` e la priorità usa solo i contatti già presenti; ricerca codice del motore microzona/contatti pubblici nel repository corrente non ha restituito risultati | — | FAIL |
| Coda prioritaria cloud | alimentazione automatica da Seller Signal | FAIL CRITICO | nessun flusso nel codice verificato trasforma un Seller Signal in contatti pubblici trovati online nelle vie circostanti | — | FAIL |
| Role Play | asset su `gh-pages` | PASS STRUTTURALE | index, manifest, service worker e pack JS presenti | — | PASS STRUTTURALE |
| Role Play | voce/audio/interazione reale | BLOCCATO | richiede browser/dispositivo/audio reali | — | NON TESTATO |
| App smartphone | asset PWA su `gh-pages` | PASS STRUTTURALE | mobile e companion pubblicati con manifest/service worker/icone disponibili | — | PASS STRUTTURALE |
| App smartphone | sync reale | FAIL/BLOCCATO | cloud senza record reali e dispositivo non disponibile; impossibile certificare sync end-to-end | — | NON CERTIFICATO |
| Motore PC locale | bridge localhost | BLOCCATO | `f1-os-mobile/local-pc-extension.js` usa `http://127.0.0.1:<porta>`; il PC Windows reale non è accessibile dal runner | — | NON TESTATO |

## Test reali eseguiti in questa notte

- Compilazione Python della sorgente desktop 1.5: PASS.
- Avvio UI headless: PASS, 17 tab.
- Bootstrap SQLite: PASS, 18 tabelle.
- Inserimento contatto sintetico e generazione coda: PASS.
- Funnel negativo: FAIL (`-16 vendite/mese`).
- Funnel conversione zero: FAIL (`0 incarichi/mese`).
- Backup SQLite isolato + integrity check: PASS (`ok`).
- Supabase: presenza/RLS delle quattro tabelle F1: PASS.
- Supabase: conteggi reali: tutti 0, quindi sync e backup cloud FAIL.
- Supabase: privilegi diretti su `f1_apply_mobile_action`: anon/authenticated = false.
- Verifica branch `gh-pages`: asset F1 presenti; test HTTP live non certificato.

## Errori / blocchi che impediscono la release

1. **CRITICO — Seller Signal:** manca nel repository canonico verificato il flusso `Seller Signal → vie limitrofe → ricerca Internet → contatti pubblici → coda prioritaria`.
2. **CRITICO — dati cloud:** tutte le tabelle operative F1 verificate sono vuote; nessuna sincronizzazione reale può essere dichiarata funzionante.
3. **FAIL — Funnel:** accetta valori negativi/zero non validi e genera risultati matematicamente inutilizzabili.
4. **FAIL — Restore:** il desktop 1.5 crea backup ma non offre/testa un ripristino equivalente.
5. **FAIL — backup cloud:** zero record in `f1_daily_backups`.
6. **FAIL — release gate:** il commit corrente non presenta status check CI globali associati.
7. **BLOCCATO — Windows/localhost:** bridge PC e servizi locali non possono essere verificati senza esecuzione sul PC reale.
8. **BLOCCATO — Role Play/PWA end-to-end:** asset presenti, ma voce/audio/installazione/offline/sync su dispositivo reale non certificati.

Nessuna correzione applicata automaticamente al codice applicativo in questo run: gli errori residui richiedono una modifica della release canonica e regression test completo; non è stato effettuato un autofix non verificabile.

**Release gate: BLOCCATO.**
