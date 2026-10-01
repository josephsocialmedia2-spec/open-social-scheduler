# Zero Cost Guard

Questa evoluzione non introduce servizi a pagamento né fallback automatici verso piani a consumo.

## Free Quota Guard effettivo
Il database registra per ogni proprietario:
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

Per `supabase_storage_media` il limite configurato è 1 GiB. Prima di ogni upload il frontend chiama `f1_check_free_quota` con la dimensione del file. Se l'upload proiettato raggiunge il 95%, il caricamento viene rifiutato prima di inviare il file.

L'uso viene aggiornato automaticamente dai record `f1_content_media`; i nuovi proprietari ricevono una riga quota prima del primo upload.

## Regole
- nessun pay-as-you-go attivato dal codice
- nessun trial a pagamento come fallback
- nessun upgrade automatico
- se il guard non riesce a determinare la quota, l'upload fallisce chiuso
- le verifiche/app-review dei provider social restano processi esterni e non vengono sostituite da servizi commerciali

## Stato rilevato nel test 2026-10-01
- 86.13% usato
- 13.87% disponibile
- stato `AVVISO`
- il test di proiezione oltre 95% è stato correttamente bloccato
