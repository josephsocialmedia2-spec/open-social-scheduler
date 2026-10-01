# F1 Immobiliare — Pubblicazione manuale

## Regola definitiva

Le grafiche F1 Immobiliare vengono create e approvate dall'operatore.

Il sistema non genera, non ritocca, non impagina e non rigenera immagini.

**PIXEL IN → PIXEL OUT.**

## Flusso operativo

1. Aprire il pannello F1 su `http://127.0.0.1:8877/`.
2. Caricare una grafica definitiva PNG, JPG/JPEG o WEBP.
3. Inserire o verificare caption, piattaforme e data/ora.
4. Approvare il pacchetto.
5. Il server verifica tecnicamente il file e calcola SHA256.
6. Il file viene salvato senza modifiche in `publisher/final_assets/manual_inbox/YYYYMMDD/`.
7. Il contenuto entra in `publisher/final_content_queue.json`.
8. `f1-final-assets-publisher.yml` seleziona esclusivamente job F1 `manual_only`.
9. Il publisher invia il contenuto ai social configurati.
10. Lo stato viene verificato e aggiornato fino a `PUBLISHED_VERIFIED` quando disponibile.

## Cosa è disabilitato

Per F1 Immobiliare non vengono più usati:

- GPT Generatore Grafica F1;
- ChatGPT browser automation;
- Leonardo;
- Adobe Firefly;
- OpenAI Images API;
- free provider router;
- ultrarealism/regeneration loop;
- brand layer automatico;
- renderer F1 automatici;
- generazione news grafica;
- generazione notturna alle 23:00;
- generazione automatica di caption nel workspace F1.

I moduli legacy possono rimanere nel repository per compatibilità o storico, ma la configurazione
`publisher/clients/f1-immobiliare.json` impedisce loro di entrare nel runtime F1.

## Installazione Windows

I vecchi nomi dei launcher sono mantenuti solo per compatibilità con collegamenti già esistenti.

`INSTALLA_F1_GRAFICHE_23.bat` ora installa **soltanto** il pubblicatore manuale.

L'installatore:

- rimuove `F1_Grafiche_23`;
- rimuove `F1_News_ValleSusa`;
- rimuove `F1_News_GitHub_Poller`;
- mantiene/crea soltanto `F1_Inbox_Logon`;
- crea il collegamento Desktop `F1 PUBBLICA GRAFICHE`;
- avvia il pannello locale sulla porta 8877.

Nessun task Windows viene registrato per generare grafiche.

## Pannello

- Pubblicatore: `http://127.0.0.1:8877/`
- Stato: `http://127.0.0.1:8877/ready`
- Health: `http://127.0.0.1:8877/api/health`
- Stato coda manuale: `http://127.0.0.1:8877/api/queue-status`

L'endpoint di health deve riportare:

- `service = f1-manual-asset-inbox`
- `mode = manual-publish-only`
- `ai_image_generation = false`

## Stati principali

Per i nuovi contenuti manuali vengono usati gli stati operativi del publisher, tra cui:

- `HOLD / CAPTION_MISSING`;
- `HOLD / DA_APPROVARE`;
- `READY / READY_TO_PUBLISH`;
- `SCHEDULED`;
- `PUBLISHED`;
- `PUBLISHED_VERIFIED`;
- `ERROR`.

Gli stati legacy di generazione AI non vengono creati dai nuovi contenuti F1.

## Sicurezza anti-duplicato

Ogni file riceve SHA256. Una grafica con hash già presente nella coda viene rifiutata come duplicato.

Il publisher ricontrolla l'hash prima della consegna.

## Test

I controlli principali sono:

- `publisher/test_f1_manual_publish_only.py`;
- `.github/workflows/f1-manual-publish-only-ci.yml`;
- `.github/workflows/project-deploy.yml`;
- `.github/workflows/f1-bootstrap-validation.yml`.

I test verificano tra l'altro:

- SHA256 invariato;
- file corrotti rifiutati;
- caption mancante in HOLD;
- selezione publisher solo di asset manuali;
- generatori F1 disabilitati;
- workflow grafici archiviati;
- task Windows legacy rimossi;
- nessuna dipendenza da browser AI per la pubblicazione manuale.

## Principio operativo

**L'OPERATORE CREA LA GRAFICA. F1 LA PUBBLICA.**
