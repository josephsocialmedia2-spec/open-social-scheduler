# F1 Social Publisher — OAuth multi-cliente

Questa integrazione prepara YouTube, TikTok e LinkedIn per un consenso OAuth iniziale del proprietario dell'account e per il funzionamento automatico successivo quando la piattaforma consente refresh/rinnovo.

## Stato di sicurezza

- Il broker OAuth è disattivato finché F1_OAUTH_BROKER_ENABLED=true non viene impostato nel workflow GitHub.
- I token non vengono salvati nel repository.
- I token sono cifrati lato server nella tabella f1_social_oauth_tokens, accessibile solo al service role.
- f1_client_social_channels conserva solo metadata/stato della connessione, non token in chiaro.
- Le connessioni Buffer già operative per Facebook/Instagram non vengono modificate.

## Callback da registrare

YouTube / Google:
https://nqnmlsmeiynxbdojeyjt.supabase.co/functions/v1/f1-social-oauth/callback/youtube

TikTok:
https://nqnmlsmeiynxbdojeyjt.supabase.co/functions/v1/f1-social-oauth/callback/tiktok

LinkedIn:
https://nqnmlsmeiynxbdojeyjt.supabase.co/functions/v1/f1-social-oauth/callback/linkedin

## Secret Supabase da configurare soltanto nella fase OAuth finale

Obbligatorio:
- F1_OAUTH_ENCRYPTION_KEY

Google:
- GOOGLE_OAUTH_CLIENT_ID
- GOOGLE_OAUTH_CLIENT_SECRET
- opzionale GOOGLE_OAUTH_SCOPES

TikTok:
- TIKTOK_CLIENT_KEY
- TIKTOK_CLIENT_SECRET
- opzionale TIKTOK_OAUTH_SCOPES

LinkedIn:
- LINKEDIN_CLIENT_ID
- LINKEDIN_CLIENT_SECRET
- opzionale LINKEDIN_OAUTH_SCOPES

Opzionali:
- F1_CONTENT_HUB_URL
- LINKEDIN_VERSION

## GitHub Actions

Lasciare F1_OAUTH_BROKER_ENABLED=false finché:
1. la migration è applicata;
2. la Edge Function è attiva;
3. i client OAuth sono configurati;
4. i callback sono registrati;
5. almeno un account di prova è stato autorizzato e verificato.

Solo dopo impostare la repository variable F1_OAUTH_BROKER_ENABLED=true.

Il workflow mantiene i vecchi GitHub Secrets come fallback finché il broker resta disabilitato.

## Stati

- CONFIGURAZIONE_PRONTA: infrastruttura pronta, consenso non ancora richiesto.
- AUTORIZZAZIONE_RICHIESTA: flusso OAuth avviato.
- COLLEGATO: token valido e account identificato.
- ACCOUNT_DA_SELEZIONARE: token valido ma account/autore non ancora selezionato.
- DA_RIAUTORIZZARE: token non rinnovabile/revocato/scaduto.
- AUTH_REQUIRED: una pubblicazione ha rilevato che serve nuova autorizzazione.
- ERRORE: errore tecnico della connessione.

## Comportamento refresh

- YouTube: il broker usa il refresh token quando Google lo rilascia con accesso offline.
- TikTok: il broker aggiorna anche il refresh token se TikTok lo ruota durante il refresh.
- LinkedIn: il broker usa un refresh token solo quando è realmente disponibile per l'app. Se non è disponibile, alla scadenza imposta DA_RIAUTORIZZARE invece di bloccare gli altri social.

## Regola operativa

Nessun account deve essere autorizzato durante la preparazione tecnica. I pulsanti COLLEGA nella dashboard rappresentano l'ultima fase e aprono il consenso ufficiale della piattaforma.
