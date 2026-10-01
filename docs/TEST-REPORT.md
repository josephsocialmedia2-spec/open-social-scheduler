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
- JavaScript workspace: OK
- wiring Content Hub: OK
- JavaScript inline: OK
- media rail/design system: OK
- HEIC → PNG browser conversion: OK
- publisher safety checks: OK

Workflow **Sync Open Social Scheduler Pages** sullo stesso commit: SUCCESS.

### Backend
- migrazione `later_personal_manager`: applicata
- migrazione `free_quota_guard_enforcement`: applicata
- migrazione `free_quota_guard_seed`: applicata
- migrazione `free_quota_guard_status`: applicata
- Edge Function `f1-social-oauth`: versione 17 ACTIVE
- tabelle presenti: `f1_social_client_invites`, `f1_social_connection_health`, `f1_free_quota_usage`

### Free Quota Guard
Stato misurato durante il test:
- media tracciati: 924,832,087 byte
- limite configurato: 1,073,741,824 byte
- utilizzo: 86.13%
- disponibile: 13.87%
- stato: AVVISO

Prove:
- +1 MiB proiettato: consentito (86.23%)
- +150,000,000 byte proiettati: BLOCCATO (`FREE_QUOTA_GUARD_95`)

### Security
- raw invite token non persistito: database conserva SHA-256
- OAuth provider token/secret non introdotti nel frontend
- inviti service-role only
- connection health/quota con RLS
- LinkedIn Page usa `w_organization_social`
- nessun falso `COLLEGATO` basato sul solo URL
