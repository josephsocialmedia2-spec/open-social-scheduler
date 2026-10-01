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
Workflow **F1 Content Hub UI CI** sul commit finale frontend `d1fb18c59dbd43e80ea2fcd74d9579198530bd4d`: SUCCESS.
Workflow **Sync Open Social Scheduler Pages** sullo stesso commit: SUCCESS.
La versione pubblicata include il Free Quota Guard project-wide.

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


## Facebook Page Standard — Antica Cappella

### Ricerca e diagnosi
- URL Facebook previsto: `https://www.facebook.com/profile.php?id=61550077453442`
- Page ID atteso ricavato dall'URL: `61550077453442`
- prima della correzione: nessun `external_channel_id`, nessun OAuth token Meta, `enabled=false`, `verified=false`, stato `CANALE_DA_COLLEGARE`
- Instagram Antica Cappella: provider `buffer`, `enabled=true`, `verified=true`, stato `COLLEGATO`; invariato dopo il lavoro

### Modifiche verificate
- Facebook OAuth separato da Instagram OAuth
- scope Facebook Pages dedicati
- verifica permessi Meta realmente concessi
- matching diretto di `profile.php?id=PAGE_ID`
- Page task validation
- `PAGINA_NON_ACCESSIBILE`, `PAGINA_DA_SELEZIONARE`, `PERMESSI_INSUFFICIENTI`
- publisher riceve Page Access Token solo dopo verifica server-side

### CI finale
PR #117: merged.
Main merge commit: `3f0ab082fecfc8d654524c73ccbba2cd35d491cc`.
- Real Media Pro OAuth Smoke: SUCCESS — 15/15
- F1 Content Hub UI CI: SUCCESS
- Direct API Visibility Engine CI: SUCCESS
- F1 Project Deploy Validation: SUCCESS
- Sync Open Social Scheduler Pages: SUCCESS
- Edge Function `f1-social-oauth`: version 18 ACTIVE

### Blocco esterno residuo
Il broker live segnala `RMP_OAUTH_PROVIDER_CONFIGURATION_REQUIRED=facebook,instagram,linkedin`.
Per Facebook mancano quindi ancora le credenziali applicative Meta server-side (`META_APP_ID` e `META_APP_SECRET`). Antica Cappella non viene marcata `COLLEGATO` finché un OAuth reale non conferma il Page ID tramite Meta.
