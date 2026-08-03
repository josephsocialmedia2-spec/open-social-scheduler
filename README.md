# Open Social Scheduler — CRM condiviso V4

Versione ricostruita con la stessa logica stabile del CRM operativo F1/RMP:

- database centrale Google Sheets;
- una riga per cliente e una riga per pubblicazione;
- identificativi stabili;
- nessuna sovrascrittura dell'intero archivio dal browser;
- accesso dalla stessa Web App su qualsiasi computer;
- installazione automatica del progetto Apps Script, del database e della Web App;
- backup automatico su Google Drive.

## Installazione Windows

1. Scarica il repository con **Code → Download ZIP**.
2. Estrai completamente lo ZIP.
3. Esegui `INSTALLA.bat`.
4. Accedi una sola volta all'account Google e abilita Google Apps Script API quando richiesto.

Il programma installa gli strumenti necessari, crea il progetto Apps Script, carica il CRM, pubblica la Web App e salva il link in `OPEN_SOCIAL_SCHEDULER_URL.txt`.

Il database viene creato automaticamente con i fogli `CLIENTI`, `PUBBLICAZIONI` e `META`.
