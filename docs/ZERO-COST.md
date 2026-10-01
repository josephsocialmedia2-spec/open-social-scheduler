# Zero Cost Guard

Questa evoluzione non introduce servizi a pagamento né fallback automatici verso piani a consumo.

## Free Quota Guard effettivo
Il database registra:
- servizio
- piano
- utilizzo
- limite
- percentuale utilizzata
- percentuale disponibile
- stato operativo
- flag di blocco

Soglie:
- <70% → `OK`
- >=70% → `INFORMAZIONE`
- >=85% → `AVVISO`
- >=95% → `BLOCCO`

Per lo Storage Supabase il guard usa il conteggio **project-wide** di `storage.objects`, non soltanto i file referenziati dal Content Hub. Il limite conservativo configurato è 1,000,000,000 byte (1 GB).

Prima di ogni upload il frontend chiama `f1_check_free_quota` con la dimensione del file. Se l'uso corrente o l'upload proiettato raggiunge il 95%, il caricamento viene rifiutato prima di inviare il file.

## Stato rilevato il 2026-10-01
- Storage project-wide: 1,185,481,484 byte
- riferimento configurato: 1,000,000,000 byte
- utilizzo: 118.55%
- disponibile secondo il guard: 0%
- stato: `BLOCCO`
- prova con +1 byte: correttamente rifiutata con `FREE_QUOTA_GUARD_95`

Il guard quindi blocca immediatamente nuovi upload finché lo Storage non torna sotto la soglia di sicurezza. Nessun file esistente viene cancellato automaticamente.

## Regole
- nessun pay-as-you-go attivato dal codice
- nessun trial a pagamento come fallback
- nessun upgrade automatico
- se il guard non riesce a determinare la quota, l'upload fallisce chiuso
- le verifiche/app-review dei provider social restano processi esterni e non vengono sostituite da servizi commerciali
