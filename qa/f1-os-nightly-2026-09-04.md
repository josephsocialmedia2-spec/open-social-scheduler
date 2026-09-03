# F1 OS — Nightly QA — 2026-09-04

Stato finale: **RELEASE NON CERTIFICATA / errori e blocchi residui**

| Componente | Test | Esito | Errore / nota | Correzione | Retest |
|---|---|---|---|---|---|
| Repository GitHub | accesso repository e branch main | PASS | repository raggiungibile | — | PASS |
| GitHub Actions | ultimo run Social Engine visibile | PASS | ultimo run osservato concluso `success` | — | PASS |
| GitHub Pages sync | presenza `f1-os-cloud` e `f1-os-companion` nel workflow | FAIL -> PASS | il workflow pubblicava `f1-os-mobile` ma ignorava cloud e companion | aggiornato `.github/workflows/pages.yml` | PASS: sync run 33812410247 `success`; Pages build 33812598101 `success`; cartelle presenti su `gh-pages` |
| F1 OS Companion PWA | icona manifest | FAIL -> PASS | `icons: []` | aggiunto `f1-os-companion/icons/icon.svg` e manifest aggiornato | PASS strutturale: icona presente su `gh-pages` |
| F1 OS Companion PWA | installazione reale / offline | BLOCCATO | richiede browser/dispositivo reale | nessuna correzione inventata | NON TESTATO |
| F1 OS Cloud | pubblicazione su `gh-pages` | FAIL -> PASS | cartella non veniva distribuita | inclusa nel workflow Pages | PASS strutturale |
| Supabase | stato progetto | PASS | progetto `nqnmlsmeiynxbdojeyjt` ACTIVE_HEALTHY | — | PASS |
| Supabase | tabella `public.f1_records` | PASS | tabella presente, RLS attivo | — | PASS |
| Supabase / Sync | dati cloud F1 | FAIL | `f1_records` contiene 0 record: CRM/queue cloud non hanno dati sincronizzati da usare | nessuna migrazione automatica eseguita senza sorgente dati PC | FAIL |
| Supabase security | advisor | WARN | 3 tabelle F1 con RLS ma senza policy; `f1_apply_mobile_action()` SECURITY DEFINER eseguibile da anon/authenticated; leaked-password protection disattivata | non modificato automaticamente per rischio regressione autorizzazioni | WARN |
| Desktop F1 OS 1.5 | `python -m py_compile` | PASS | nessun errore sintattico | — | PASS |
| Desktop F1 OS 1.5 | bootstrap database pulito | PASS | create schema completata: 18 tabelle | — | PASS |
| Desktop F1 OS 1.5 | avvio UI headless | PASS | UI costruita correttamente: 17 tab | — | PASS |
| CRM SQLite | create/update/delete su DB di test | PASS | persistenza CRUD verificata | — | PASS |
| Coda prioritaria desktop | generazione con contatto sintetico | PASS | con 1 contatto la coda produce 1 riga; quindi coda vuota su DB vuoto è coerente | — | PASS |
| Coda prioritaria reale | dati del PC dell'utente | BLOCCATO | il database Windows reale non è accessibile a questo runner | — | NON TESTATO |
| Backup desktop | creazione + SQLite `integrity_check` | PASS | backup contiene record di prova e integrità `ok` | — | PASS |
| Restore desktop | ripristino da UI | FAIL | nella release 1.5 esiste `backup()` ma non una funzione di restore equivalente | nessuna modifica applicata al file installato sul PC | FAIL |
| Funnel desktop | formula base presente | PASS PARZIALE | funnel inverso implementato | — | PASS PARZIALE |
| Funnel edge cases | zero / percentuali non valide | FAIL | valori 0 vengono trasformati in output 0 o fallback anziché essere rifiutati esplicitamente; non soddisfa il release gate richiesto | non corretto senza regression test UI completo | FAIL |
| Seller Signal -> contatti pubblici Internet | integrazione automatica | FAIL CRITICO | `f1-os-cloud` salva i segnali ma non esegue ricerca Internet delle vie vicine e non alimenta la coda con contatti pubblici; il motore richiesto non è presente nel repository verificato | nessun finto risultato generato | FAIL |
| Role Play | file/app/manifest/service worker presenti su Pages | PASS STRUTTURALE | asset principali presenti | — | PASS STRUTTURALE |
| Role Play | voce, pause, pulsanti su dispositivo reale | BLOCCATO | richiede browser/audio reale | — | NON TESTATO |
| `OGGI COSA FACCIO` / localhost | servizi Windows e porta 8766 | BLOCCATO | impossibile verificare `127.0.0.1` dal runner cloud | — | NON TESTATO |

## Correzioni applicate in questa esecuzione

1. GitHub Pages ora sincronizza anche `f1-os-cloud/**` e `f1-os-companion/**`.
2. Sync e build GitHub Pages correttivi hanno entrambi conclusione `success`.
3. Aggiunta icona PWA al Companion e pubblicata su `gh-pages`.

## Blocchi / errori da non nascondere

- **CRITICO:** manca ancora il flusso automatico `Seller Signal -> vie limitrofe -> ricerca Internet -> contatti pubblici -> coda prioritaria` nel codice verificato.
- **CRITICO:** il database cloud `f1_records` è attualmente vuoto; non posso certificare sincronizzazione PC-smartphone con dati reali.
- Il desktop Windows reale, localhost/porta 8766 e i pulsanti sul PC restano non certificabili da un runner cloud.
- Restore desktop non presente nella release 1.5.
- Funnel edge-case validation non conforme al gate richiesto.
- Avvisi Supabase security da riesaminare prima di una release definitiva.

**Release gate: BLOCCATO.**
