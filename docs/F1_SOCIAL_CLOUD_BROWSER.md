# F1 Social Cloud Browser Publisher

## Architettura

F1 Social usa API/OAuth ufficiali come prima scelta. Quando un canale non è disponibile via API, il fallback usa un profilo Chromium persistente e isolato sul VPS. Il PC dell'operatore non è necessario.

Regola: **1 cliente = 1 profilo browser persistente**.

```text
F1 Social / Supabase
        ↓
GitHub Actions
        ↓
API disponibile? ── sì ──> publisher API esistente
        │
        no
        ↓
self-hosted runner F1
        ↓
/srv/f1social/browser-profiles/<CLIENT_UUID>/chrome-profile
        ↓
Playwright + Chromium
        ↓
social del cliente
```

La migration `20260927_f1_social_cloud_browser_publisher.sql` crea:

- `f1_client_browser_profiles`;
- `f1_client_browser_social_sessions`;
- `f1_publication_queue`;
- `f1_publication_audit`;
- RPC `f1_claim_due_publications` con `FOR UPDATE SKIP LOCKED`.

Cookie, password e sessioni non sono salvati nel repository o nelle tabelle: restano nel profilo Chromium del VPS.

## Installazione VPS

Clona il repository sul VPS Ubuntu e avvia:

```bash
cd open-social-scheduler
sudo -E bash scripts/install_f1_social_browser_runner.sh
```

Se manca il token del runner, apri:

`https://github.com/josephsocialmedia2-spec/open-social-scheduler/settings/actions/runners/new`

Poi:

```bash
export GITHUB_RUNNER_TOKEN='TOKEN_TEMPORANEO_GENERATO_DA_GITHUB'
sudo -E bash scripts/install_f1_social_browser_runner.sh
```

Il token è temporaneo e non deve essere salvato nel repository.

## Primo login di ogni cliente

Ogni cliente effettua una sola volta il login nel proprio browser cloud. Password, CAPTCHA, checkpoint e 2FA restano operazioni dell'utente autorizzato.

Sul VPS avvia il desktop di configurazione:

```bash
cd open-social-scheduler
bash scripts/start_f1_browser_desktop.sh
```

Il desktop noVNC ascolta soltanto su `127.0.0.1`. Dal computer dell'operatore crea temporaneamente il tunnel SSH indicato dallo script e apri `http://127.0.0.1:6080/vnc.html`. Questo serve solo alla configurazione iniziale: la pubblicazione ordinaria continuerà sul VPS senza il computer locale.

Poi sul VPS:

```bash
export DISPLAY=:99
source /opt/f1-browser-venv/bin/activate
cd open-social-scheduler
export SUPABASE_SERVICE_ROLE_KEY='...'
python scripts/f1_browser_session.py antica-cappella facebook
```

Lo script apre esclusivamente il profilo persistente del cliente, richiede il login manuale quando necessario e verifica l'identità attesa prima di salvare lo stato `CONNECTED`. Ripeti per i social necessari. Password e cookie non vengono scritti in Supabase o GitHub.

## Attivazione

Quando il runner compare online con label `f1-social-browser`, imposta la repository variable:

```text
F1_BROWSER_FALLBACK_ENABLED=true
```

Finché la variabile non è `true`, la coda viene sincronizzata ma Chromium non viene avviato.

## Sicurezza

Prima di ogni azione il worker confronta:

- `client_id`;
- profilo browser;
- `expected_profile_url`;
- `expected_account_id` se disponibile;
- `expected_account_name`.

Se l'identità non coincide, lo stato diventa `ACCOUNT_WRONG`. Il sistema non cambia account automaticamente.

CAPTCHA, 2FA, checkpoint e verifiche identità producono `AUTH_REQUIRED`.

## Flusso

1. il publisher API esistente resta la prima scelta;
2. la coda cloud viene sincronizzata con `f1_content_calendar`;
3. se il canale è verificato via API, il browser non interviene;
4. se l'API non è disponibile e la sessione browser è `CONNECTED`, Playwright usa il profilo del cliente;
5. media e caption vengono recuperati da F1 Social;
6. il contenuto viene preparato e pubblicato;
7. esito, URL/ID quando disponibili e audit vengono salvati;
8. i file temporanei vengono rimossi.

## Dry run

Avvia manualmente il workflow `F1 Social Cloud Browser Publisher` con `dry_run=true`. Il sistema prepara il compositore ma non preme Pubblica.

## YouTube

Il fallback YouTube carica il video e compila titolo/descrizione, ma non indovina audience o visibilità. Se non sono configurati in modo esplicito, termina con `AUTH_REQUIRED` prima della pubblicazione.

## Backup

Ferma browser/runner prima del backup. Archivia `/srv/f1social/browser-profiles` soltanto in backup cifrati privati. Non caricare i profili Chromium su GitHub.
