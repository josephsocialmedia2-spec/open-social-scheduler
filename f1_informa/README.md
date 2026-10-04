# F1 INFORMA

Modulo F1 Immobiliare per creare ogni giorno un carosello source-locked di 10 card a partire da pagine pubbliche dell'Agenzia delle Entrate.

- Orario operativo: 17:00 Europe/Rome.
- Output: `f1-content-hub/f1-informa-data/YYYY-MM-DD/` + ZIP.
- Stato: sempre `DA_APPROVARE`.
- Pubblicazione F1: resta manuale; il modulo non cambia `publisher/clients/f1-immobiliare.json`.
- ChatGPT: il sito copia il prompt e apre ChatGPT; non automatizza login, cookie o sessioni private.
- Fonti: whitelist di domini ufficiali Agenzia delle Entrate, profondità massima 2, pagine archiviate escluse di default.
- Conservazione: 45 giorni di pacchetti per contenere la crescita del repository.
