# Open Social Scheduler — Google Drive condiviso, senza API

Questa versione non usa Google Apps Script, `clasp`, Google Sheets API, API key o accessi OAuth.

Il programma salva i dati direttamente nella cartella sincronizzata da **Google Drive per desktop**:

```text
Open Social Scheduler CRM/
├── clients/
├── posts/
├── backups/
└── meta.json
```

Ogni cliente e ogni pubblicazione sono file JSON separati con ID stabile. Un computer non riscrive l'intero archivio dell'altro. Il programma controlla le modifiche ogni 5 secondi e segnala i conflitti se lo stesso record è stato modificato da un altro computer.

## Installazione Windows

1. Installa e configura Google Drive per desktop.
2. Scarica il repository con **Code → Download ZIP**.
3. Estrai completamente lo ZIP.
4. Esegui `INSTALLA.bat`.
5. Il programma individua `Il mio Drive`; se non lo trova, chiede di selezionarlo.
6. Viene creato il collegamento **Open Social Scheduler** sul desktop.

Sul secondo computer esegui lo stesso `INSTALLA.bat` usando lo stesso account Google Drive. Tutti i dati saranno letti dalla cartella condivisa `Open Social Scheduler CRM`.

## Verifiche effettuate

- sintassi Node.js verificata;
- archivio ZIP verificato;
- creazione automatica dei 20 clienti verificata;
- salvataggio del primo cliente verificato;
- persistenza del cliente dopo il riavvio verificata.
