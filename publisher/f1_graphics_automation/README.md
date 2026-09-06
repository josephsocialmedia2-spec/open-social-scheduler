# F1 Grafiche automatiche ore 23:00

## Flusso operativo

1. Doppio clic su `F1 GRAFICHE` oppure avvio automatico Windows alle 23:00.
2. Viene utilizzato il normale Google Chrome dell'utente, senza profilo dedicato e senza Selenium.
3. Si apre il GPT F1:
   `https://chatgpt.com/g/g-6a9c210485488191b072eb694c2f114c-generatore-grafica-f1`
4. Le query arrivano da `publisher/github_graphics/queries.json`.
5. Ogni query viene trasformata esclusivamente in:
   `Genera un'immagine ultrarealistica, cerchiamo [QUERY].`
6. Il composer viene identificato tramite Windows UI Automation/accessibility tree.
7. Prima di usare Ctrl+A/Backspace viene verificato che il focus sia realmente nel composer.
8. Il testo inserito viene riletto e confrontato con il prompt atteso.
9. Dopo Enter viene verificato l'invio osservando la UI.
10. La generazione viene monitorata; un semplice timeout non viene considerato successo.
11. La query diventa `COMPLETED` solo dopo rilevamento e salvataggio di una nuova immagine.
12. L'immagine viene salvata in `publisher/final_assets/chatgpt_generated/YYYYMMDD/`.
13. La Raccolta F1 su `http://127.0.0.1:8877/` mostra automaticamente le immagini salvate.
14. L'operatore controlla e approva; solo allora il file entra in GitHub e nella coda `READY`.

## Stato per query

`QUERY_CARICATA → PROMPT_COSTRUITO → COMPOSER_TROVATO → TESTO_INSERITO → TESTO_VERIFICATO → PROMPT_INVIATO → INVIO_VERIFICATO → GENERAZIONE_IN_CORSO → GENERAZIONE_TERMINATA → IMMAGINE_RILEVATA → IMMAGINE_SALVATA → COMPLETED`

`next_index` avanza esclusivamente dopo `COMPLETED` con `image_path` valido.

## Stato finale batch

`GRAFICHE_PRONTE` richiede che tutte le query previste siano `COMPLETED` e che tutte le immagini siano state salvate. In caso contrario lo stato è `PARZIALE` oppure `ERRORE`.

## Installazione

Dalla cartella principale del repository:

`INSTALLA_F1_GRAFICHE_23.bat`

L'installatore si eleva come amministratore, installa le dipendenze, registra e verifica:

- `F1_Grafiche_23` ogni giorno alle 23:00;
- `F1_Inbox_Logon` all'accesso Windows;
- `WakeToRun` e `StartWhenAvailable`;
- comando PowerShell, working directory e trigger 23:00;
- health check della Raccolta F1 sulla porta 8877;
- collegamenti desktop.

## Collegamenti Desktop

- `F1 GRAFICHE` — produzione normale/recovery, 4 query.
- `F1 - Prova 1 Query` — nuovo test end-to-end con una query.
- `F1 - Prova 4 Query` — nuovo test end-to-end con quattro query.
- `F1 - Raccolta Grafiche` — apre solo la Raccolta F1.

## Raccolta F1

- Raccolta: `http://127.0.0.1:8877/`
- Stato mattutino: `http://127.0.0.1:8877/ready`
- Health: `http://127.0.0.1:8877/api/health`
- Stato ultima esecuzione: `http://127.0.0.1:8877/api/run-status`
- Grafiche automatiche: `http://127.0.0.1:8877/api/generated`

La porta 8765 non viene usata da F1.

## Retry e recovery

Ogni query dispone di retry limitati. In caso di errore vengono salvati stato, errore, screenshot e accessibility tree. Un batch incompleto viene ripreso al successivo avvio normale; i vecchi record creati dalla precedente logica non verificata non vengono considerati completamenti attendibili.

## Percorsi locali

- Stato: `publisher/chatgpt_query_runner/state.json`
- Ultima esecuzione: `publisher/chatgpt_query_runner/last_run.json`
- Immagini automatiche: `publisher/final_assets/chatgpt_generated/YYYYMMDD/`
- Log: `publisher/f1_graphics_automation/logs/`
- Screenshot errori: `publisher/f1_graphics_automation/logs/screenshots/`
- Accessibility diagnostics: `publisher/f1_graphics_automation/logs/accessibility/`

Questi dati di runtime sono ignorati da Git fino all'approvazione umana.

## Vincoli reali

L'automazione grafica richiede una sessione Windows interattiva perché controlla il normale Chrome dell'utente. `WakeToRun` può riattivare il PC dalla sospensione se Windows/hardware consentono i wake timer; non può eseguire Chrome se il computer è completamente spento. Il normale profilo Chrome deve essere già autenticato a ChatGPT.

## GitHub Actions

`F1 Project Deploy Validation` esegue compilazione, unit test della state machine, verifica del formato prompt, coda e contratti dei launcher. Questi test non sostituiscono la prova end-to-end sul Chrome reale Windows.
