# F1 Grafiche automatiche ore 23:00

## Obiettivo
Ogni giorno alle 23:00 Windows avvia automaticamente il sistema grafico F1.

Flusso operativo:

1. Windows avvia `RUN_NOTTURNO_23.ps1`.
2. Parte la Inbox locale su `http://127.0.0.1:8765/`.
3. Viene aperto Google Chrome con l'ultimo profilo Chrome utilizzato, salvo override `F1_CHROME_PROFILE`.
4. Chrome apre Google e poi il GPT:
   `https://chatgpt.com/g/g-6a9c210485488191b072eb694c2f114c-generatore-grafica-f1`
5. Le query di `publisher/github_graphics/queries.json` vengono inviate una alla volta.
6. Il sistema aspetta la fine della generazione prima di inviare la query successiva.
7. Il batch normale contiene 4 query.
8. A fine ciclo viene aperta la schermata:
   `http://127.0.0.1:8765/ready`
9. La mattina l'operatore scarica le immagini dal GPT e le trascina nella pagina Raccolta Grafiche.
10. Dopo approvazione esplicita, i file vengono salvati in GitHub e aggiunti a `publisher/final_content_queue.json` con stato `READY`.

## Installazione una volta sola
Dalla cartella principale del repository eseguire:

`INSTALLA_F1_GRAFICHE_23.bat`

L'installatore:

- installa Selenium e Flask;
- registra `F1_Grafiche_23` in Utilità di pianificazione alle 23:00;
- abilita `WakeToRun`;
- abilita `StartWhenAvailable`;
- registra `F1_Inbox_Logon` all'accesso Windows;
- crea sul desktop `F1 - Raccolta Grafiche`;
- crea sul desktop `F1 - Prova Automazione Grafiche`.

## Pagine locali

- Raccolta Grafiche: `http://127.0.0.1:8765/`
- Schermata mattutina: `http://127.0.0.1:8765/ready`
- Stato ultima esecuzione: `http://127.0.0.1:8765/api/run-status`

## Test immediato
Usare il collegamento desktop `F1 - Prova Automazione Grafiche` oppure eseguire:

`publisher/f1_graphics_automation/PROVA_ORA.bat`

Il test invia una sola query.

## Requisiti operativi

- Windows deve avere una sessione utente aperta per consentire a Selenium di interagire con Chrome.
- Il PC può essere in sospensione: l'attività pianificata usa `WakeToRun`.
- Se il PC è spento alle 23:00, `StartWhenAvailable` consente il recupero quando il sistema torna disponibile.
- Chrome deve essere autenticato a ChatGPT nel profilo utilizzato.
- Il programma rileva automaticamente l'ultimo profilo Chrome utilizzato. È possibile forzarlo tramite variabile `F1_CHROME_PROFILE`.
- Se lo stesso profilo Chrome è già aperto e viene bloccato da Chrome, Selenium può non riuscire ad avviarsi; in questo caso la schermata mattutina mostrerà `ERRORE`.

## Log
I log locali vengono salvati in:

`publisher/f1_graphics_automation/logs/`

Questa cartella è ignorata da Git.

## GitHub Actions
Il precedente scheduling notturno GitHub è stato disattivato per evitare doppie partenze. Il workflow `F1 ChatGPT Query Manual Recovery` resta disponibile solo come recovery manuale sul runner Windows.
