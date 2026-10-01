# Test Report — Later Personal Manager

## Esito 2026-10-01

### Dashboard health engine
8/8 controlli eseguiti direttamente sul sorgente del branch:
- verde: profili verificati + programmazione futura + nuovo contenuto
- arancione: un solo profilo scollegato
- rosso: due profili scollegati
- rosso: token scaduto
- rosso: nessuna pubblicazione futura
- rosso: nessun nuovo contenuto
- protezione contro falso positivo con testo stale `COLLEGATO` ma `enabled/verified=false`
- filtro: i clienti archiviati non compaiono nella dashboard

### Backend
- migrazione `later_personal_manager`: applicata con successo al progetto Supabase
- tabelle verificate: `f1_social_client_invites`, `f1_social_connection_health`, `f1_free_quota_usage`
- Edge Function `f1-social-oauth`: bundle/parse riuscito e versione 17 attiva
- un errore di parsing rilevato al primo tentativo è stato corretto prima dell'attivazione della nuova versione

### Security review
- raw invite token non persistito: solo SHA-256
- inviti service-role only, RLS attivo
- connection health/quota leggibili solo dal proprietario autenticato; scrittura service-role
- nessun token provider aggiunto al frontend/localStorage
- LinkedIn Page usa `w_organization_social`, non `w_member_social`
- l'advisor Supabase segnala anche warning preesistenti nel progetto non introdotti da questa modifica; la tabella inviti compare come RLS-senza-policy perché è intenzionalmente service-role only e i ruoli anon/authenticated sono revocati

### CI
Workflow: `.github/workflows/later-personal-manager-qa.yml`.
Le scritture effettuate tramite il connettore GitHub non hanno generato una run automatica del workflow; la validazione equivalente critica è stata eseguita direttamente (unit health engine + bundling reale della Edge Function).
