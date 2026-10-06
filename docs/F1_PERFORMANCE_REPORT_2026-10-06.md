# F1 PERFORMANCE REPORT — 2026-10-06

## Ambito
F1 Social / F1 Content Hub
Produzione: `f1-content-hub/?client=marta-ruffino`

Punto di ripristino:
- branch: `backup/f1-social-pre-performance-20261006`
- commit pre-intervento: `665d23047d566e593b2c12cd2fb1e27f220ef730`

## Problemi P0 rilevati

### 1. Refresh completo troppo frequente
Il frontend eseguiva `loadAll()` ogni 60 secondi. Ogni ciclo caricava cliente + 14 gruppi dati Supabase, inclusi analytics, Intelligence, browser cloud, immobili, log e storico.

Effetto:
- circa 15 richieste DB per ciclo;
- fino a circa 900 richieste/ora con pagina aperta, prima di eventuali retry;
- possibile rigenerazione completa della UI e delle anteprime.

### 2. Video reinseriti nel DOM
Le tre superfici principali — griglia, rail contenuti e workspace — inserivano direttamente `<video src="signed-url">` durante il rendering.

Anche con `preload="none"`, un refresh/rerender poteva:
- ricreare l'elemento video;
- riassociare il signed URL;
- provocare nuove richieste browser/metadata;
- dare la percezione di video in caricamento continuo.

### 3. Dati secondari bloccavano il percorso iniziale
L'apertura caricava insieme:
- contenuti;
- calendario;
- social;
- coda;
- analytics;
- eventi;
- Intelligence;
- fonti web;
- browser cloud;
- sessioni browser;
- immobili;
- altri dati secondari.

### 4. Azioni comuni ricaricavano tutto
Upload, programmazione, verifica social, selezione account, pubblicazione e altre operazioni richiamavano spesso `loadAll()`, ricaricando dati non pertinenti.

### 5. Service worker troppo esteso
Il service worker intercettava/cachava genericamente le GET. La strategia non era limitata ai soli asset statici dell'app.

### 6. Pre-flight token incompleto
Il pre-flight browser usava soprattutto `enabled/verified` e scope, senza bloccare esplicitamente:
- `reauthorization_required`;
- `token_expires_at` già scaduto.

### 7. Doppio click PUBBLICA
La UI riutilizzava righe calendario esistenti, ma non saltava esplicitamente una piattaforma già `IN PUBBLICAZIONE` / pubblicata per lo stesso hash media.

## Modifiche effettuate

### Caricamento progressivo
Creati:
- `loadCritical()`
- `loadSecondaryData()`
- `f1ScheduleSecondaryLoad()`

Il percorso iniziale ora carica come dati bloccanti:
1. clienti;
2. contenuti recenti;
3. calendario essenziale;
4. stato social persistito;
5. coda pubblicazioni.

I dati secondari vengono caricati dopo il primo rendering tramite `requestIdleCallback` o fallback breve.

### Query Supabase
Prima, apertura/ciclo completo:
- ~15 gruppi query.

Dopo, apertura critica:
- ~5 gruppi query (clienti + 4 dataset critici).

Riduzione del percorso bloccante:
- circa **66,7%** dei gruppi query.

Il caricamento secondario resta disponibile ma non impedisce l'utilizzo iniziale.

### Polling
Prima:
- `loadAll()` ogni 60 secondi;
- ~15 query/ciclo;
- massimo teorico ~900 query/ora, esclusi retry.

Dopo:
- solo `loadCritical({clients:false})` ogni 5 minuti;
- 4 gruppi query/ciclo;
- ~48 query/ora.

Riduzione teorica del polling periodico:
- circa **94,7%**.

### Refresh dopo operazioni
Prima:
- numerose operazioni comuni richiamavano `loadAll()`.

Dopo:
- `loadAll()` resta soltanto per il comando manuale **AGGIORNA**;
- le azioni operative usano `loadCritical()` o un refresh specifico.

### Video
Prima:
- griglia: video con `src`;
- rail: video con `src`;
- workspace: video con `src`.

Dopo:
- nessun video completo viene caricato automaticamente in queste tre superfici;
- viene mostrato **APRI VIDEO / VIDEO**;
- il signed URL e il vero elemento video vengono creati solo al click;
- il video aperto usa `preload="metadata"`.

Download video automatici nel percorso generale:
- **prima:** possibili su tre superfici di rendering;
- **dopo:** **0 fino all'apertura volontaria**.

### Cache media
Conservata la cache runtime dei signed URL.
Il service worker ora usa cache `f1-content-hub-v26-static-only` e tratta solo asset statici same-origin del Content Hub.
Non intercetta più genericamente API, Supabase o media firmati.

### Connessioni social / OAuth
Il database già persiste:
- `connection_status`;
- `last_verified_at`;
- `token_expires_at`;
- `refresh_token_expires_at`;
- `last_refresh_at`;
- `reauthorization_required`;
- scope/account ID.

Il pre-flight ora blocca immediatamente:
- token scaduto;
- riautorizzazione già richiesta;
senza eseguire un nuovo OAuth.

L'Edge Function `f1-social-oauth` implementa refresh server-side per provider con refresh token supportato nel flusso corrente (TikTok, Google/YouTube e LinkedIn) quando la scadenza è a meno di 5 minuti.

Meta/Facebook/Instagram nel codice corrente richiedono riautorizzazione alla scadenza del token; non è stato modificato senza una verifica end-to-end live.

### Caption
La caption è già persistita nel `distribution_plan`.
`itemPlan()` riutilizza il piano/caption esistente.
La rigenerazione avviene tramite azione esplicita `RIGENERA`, non automaticamente a ogni rendering.

Ottimizzazione aggiunta:
- aggiornamenti delle righe calendario collegate a una caption ora vengono eseguiti con `Promise.all` invece che in sequenza.

### Pubblicazione / idempotenza
Aggiunto controllo prima della rimessa in pubblicazione:
- se la stessa piattaforma ha già una riga `IN PUBBLICAZIONE` / pubblicata / completata;
- e `expected_media_sha256` coincide;
- la piattaforma viene saltata.

Il database dispone inoltre di:
- lock publisher (`locked_at`, `locked_by`, `lock_expires_at`);
- vincolo unico coda su owner/client/content/platform/scheduled_at.

## Test e verifica

Verifiche completate:
- sintassi JavaScript workspace: PASS;
- wiring Content Hub: PASS;
- sintassi JavaScript inline: PASS;
- Content Rail contract: PASS;
- design system: PASS;
- service worker/cache contract: PASS;
- CI performance guardrails: PASS;
- F1 Content Hub UI CI: PASS.

Sono state aggiunte guardie CI che falliscono se vengono reintrodotti:
- polling completo a 60 secondi;
- più di definition + refresh manuale di `loadAll()`;
- video con `src` automatico nel rail/workspace;
- service worker catch-all;
- rimozione del caricamento critico/secondario.

## Stato infrastrutturale aperto

Il test live dell'Edge Function OAuth restituisce attualmente **HTTP 402** dal progetto Supabase.

I test locali/contrattuali OAuth passano, ma il backend live risulta limitato dal servizio/quota Supabase. Questo problema non può essere corretto dal frontend e può bloccare:
- OAuth live;
- refresh token lato Edge Function;
- pubblicazione che dipende dalle Edge Functions;
- altre chiamate backend servite dal progetto limitato.

Serve ripristinare il servizio Supabase lato account/progetto (quota/piano/spend cap) prima di poter certificare end-to-end OAuth e publishing.

## Misurazioni disponibili

| Metrica | Prima | Dopo | Miglioramento |
|---|---:|---:|---:|
| Gruppi query nel caricamento critico | ~15 | ~5 | ~66,7% |
| Polling | ogni 60 s full | ogni 5 min critical | meno frequente e più leggero |
| Query teoriche polling/ora | ~900 | ~48 | ~94,7% |
| Full reload dopo azioni comuni | molte callsite | 0 | eliminato |
| Video automatici griglia/rail/workspace | 3 superfici | 0 | eliminati |
| Caption già esistente | riutilizzata | riutilizzata | invariata/corretta |
| Sync caption su più calendar row | sequenziale | parallelo | latenza ridotta |
| OAuth ad apertura pagina | non necessario | non necessario | stato DB riutilizzato |

Queste sono misure statiche/architetturali derivate dal codice. Le misure reali in millisecondi con sessione autenticata e provider social attivi devono essere ripetute quando il backend Supabase 402 è stato ripristinato.

## Problemi ancora aperti

1. Backend Supabase live limitato con HTTP 402.
2. Test end-to-end reali di publish/OAuth non certificabili finché il punto 1 è attivo.
3. Meta/Facebook/Instagram: ciclo di estensione/refresh del token va verificato contro il provider live prima di modificare l'attuale strategia di riautorizzazione.
4. Thumbnail persistenti server-side per video non ancora introdotte: per ora il sistema usa placeholder e carica il video solo on-demand, eliminando il problema P0 senza aggiungere una nuova pipeline pesante.

## Criterio di chiusura P0

P0 frontend considerato verificato solo per:
- niente video automatici nelle superfici generali;
- niente full polling ogni minuto;
- caricamento iniziale separato critical/secondary;
- full reload eliminati dalle azioni comuni;
- pre-flight token persistito;
- idempotenza client migliorata;
- CI anti-regressione verde.

OAuth/publishing live restano **NON CERTIFICATI** finché Supabase restituisce HTTP 402.


## Storage e quota — verifica reale

Query eseguita sul progetto Supabase:
- bucket `f1-content-media`: **155 oggetti**, circa **1.410 GB / 1444.04 MB**;
- oggetti orfani: **0**;
- tutti i 155 oggetti risultano collegati a `f1_content_media`;
- rilevate **3 coppie di file con ETag e dimensione identici**, circa **19 MB** di duplicazione evitabile.

Il problema di quota non deriva quindi da file orfani, ma dal volume reale dei media, con numerosi PNG da 14–19 MB e video da 15–25 MB.

### Deduplicazione nuovi upload
Aggiunto controllo SHA-256 prima del caricamento:
- calcola hash del file effettivamente destinato allo Storage;
- cerca lo stesso hash per lo stesso cliente;
- se esiste già, non crea un secondo contenuto e non ricarica il file;
- il controllo è non bloccante: se la verifica hash/query non è disponibile, l'upload normale può proseguire;
- i nuovi piani memorizzano `media_sha256` e `media_hash_algorithm=SHA-256`.

### HEIC
Rimossa la conversione HEIC automatica a 350 ms dal rendering del workspace.
La conversione resta disponibile manualmente tramite il pulsante dedicato.
Questo evita download + riconversione + re-upload pesanti provocati dalla sola apertura della pagina.

## Ulteriore riduzione refresh workspace

Nel file `client-workspace.js` erano rimaste 9 chiamate `loadAll()` dopo conversione HEIC, upload, eliminazione, programmazione e automazioni WhatsApp.

Sono state rimosse.
Il workspace ora usa refresh critici o query specifiche e contiene **0 chiamate `loadAll()`**.

## Cache asset versionata

Il service worker statico ora usa la richiesta completa come chiave cache.
I parametri `?v=...` degli asset JavaScript/CSS vengono quindi rispettati realmente: un deploy con nuova versione non resta bloccato dietro una vecchia cache del workspace.
