# Test Report — Later Personal Manager

## Esito finale — 2026-10-01

### Dashboard health engine
8/8 controlli superati:
- verde: profili verificati + programmazione futura + nuovo contenuto
- arancione: un solo profilo scollegato
- rosso: due profili scollegati
- rosso: token scaduto
- rosso: nessuna pubblicazione futura
- rosso: nessun nuovo contenuto
- protezione contro falso positivo con testo stale `COLLEGATO` ma `enabled/verified=false`
- filtro: i clienti archiviati non compaiono nella dashboard

### OAuth
Workflow **Real Media Pro OAuth Smoke** sul commit `0e12379cbea0853761a9611e1ecd41f7a2819b68`: SUCCESS.
- 10/10 test OAuth UI/contract: OK
- broker health: OK
- cifratura server-side: ready
- provider app configuration rilevata: TikTok e YouTube configurati; Facebook, Instagram e LinkedIn richiedono configurazione provider/app

### Frontend e deploy
Workflow **F1 Content Hub UI CI** sul commit `78e852ca5b4edeead796616485a98e7f0f0a94b3`: SUCCESS.
Workflow **Sync Open Social Scheduler Pages** sullo stesso commit: SUCCESS.
Una successiva modifica collega il guard al conteggio project-wide; la relativa CI deve restare verde prima della chiusura definitiva.

### Backend
- migrazione `later_personal_manager`: applicata
- migrazioni Free Quota Guard: applicate
- Edge Function `f1-social-oauth`: versione 17 ACTIVE
- tabelle presenti: `f1_social_client_invites`, `f1_social_connection_health`, `f1_free_quota_usage`

### Free Quota Guard
Il controllo usa `storage.objects` project-wide.
Stato misurato:
- 1,185,481,484 byte usati
- 1,000,000,000 byte riferimento configurato
- 118.55%
- stato `BLOCCO`
- +1 byte proiettato: rifiutato con `FREE_QUOTA_GUARD_95`

### Security
- raw invite token non persistito: database conserva SHA-256
- OAuth provider token/secret non introdotti nel frontend
- inviti service-role only
- connection health/quota con RLS
- LinkedIn Page usa `w_organization_social`
- nessun falso `COLLEGATO` basato sul solo URL
