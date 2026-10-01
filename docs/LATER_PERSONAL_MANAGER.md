# F1 Social — Later Personal Manager

## Scopo
Questa evoluzione mantiene l'architettura multi-cliente esistente e aggiunge una home operativa a semaforo, un flusso OAuth più semplice e un Connection Doctor. L'interfaccia è originale: Later è usato solo come riferimento di workflow (media library, calendario, profili e composer), non come sorgente di asset o codice.

## Dashboard clienti
La dashboard mostra esclusivamente clienti con stato `ATTIVO`. La card contiene solo il nome.

Ordine: rosso → arancione → verde, poi alfabetico.

- Verde: tutti i profili previsti sono verificati, esiste almeno una pubblicazione futura programmata e almeno un nuovo contenuto lavorabile.
- Arancione: esattamente un profilo è semplicemente da collegare, mentre programmazione e contenuti sono presenti.
- Rosso: almeno due profili sono scollegati, manca una programmazione futura, manca nuovo contenuto, oppure esiste uno stato bloccante (token scaduto, riautorizzazione, permessi, account errato/condiviso, errore).

## Principio connessioni
Un URL salvato non equivale a una connessione. Lo stato `COLLEGATO` deve derivare da `enabled=true` + `verified=true` e dai controlli OAuth/provider già presenti nel broker.

## Zero cost
Questa modifica non introduce servizi a pagamento. Riusa GitHub Pages/Actions e il progetto Supabase esistente. Nessuna logica abilita automaticamente upgrade, trial o pay-as-you-go. Il funzionamento resta subordinato ai limiti dei piani gratuiti e alle verifiche/app-review imposte dai provider social.

## Sicurezza
Token OAuth e segreti restano server-side. Non vengono aggiunti token a localStorage, GitHub Pages o repository.
