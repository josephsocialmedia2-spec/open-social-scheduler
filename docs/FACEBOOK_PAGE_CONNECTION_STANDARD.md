# Facebook Page Connection Standard

## Conclusione tecnica
Una Pagina Facebook non deve essere trasformata automaticamente in una generica "pagina aziendale" per essere gestita dalla Pages API. Il flusso corretto parte da un utente Facebook autorizzato, recupera le Pagine accessibili tramite `/me/accounts`, legge il relativo Page ID, Page Access Token e i task della Pagina, quindi verifica i permessi di pubblicazione.

La documentazione Meta ufficiale via Postman mostra che `/me/accounts?fields=name,access_token,tasks` restituisce le Pagine gestite dall'utente e il relativo Page Access Token. Il criterio tecnico è quindi l'accesso alla Pagina e i permessi/task disponibili, non l'etichetta commerciale della Pagina.

## Flusso standard F1 Social
1. Il cliente ha un URL Facebook previsto.
2. Se l'URL è `profile.php?id=PAGE_ID`, F1 ricava direttamente l'ID atteso.
3. COLLEGA avvia OAuth **solo Facebook** con scope Pages.
4. Il broker verifica i permessi realmente concessi tramite `/me/permissions`.
5. Il broker legge `/me/accounts`.
6. Se il Page ID atteso è presente, lo seleziona automaticamente.
7. Se non esiste un ID atteso e ci sono più Pagine, la UI mostra **SELEZIONA PAGINA**.
8. Se esiste un Page ID atteso ma Meta non lo restituisce, stato `PAGINA_NON_ACCESSIBILE`.
9. Il canale diventa `COLLEGATO` solo dopo verifica ID, scope di pubblicazione e assenza di collisioni.
10. Il publisher ottiene un Page Access Token server-side e pubblica come Pagina.

## Scope
Facebook:
- `pages_show_list`
- `pages_read_engagement`
- `pages_manage_posts`

Instagram usa un flusso separato e non viene incluso automaticamente nell'autorizzazione Facebook.

Variabili opzionali:
- `META_FACEBOOK_OAUTH_SCOPES`
- `META_INSTAGRAM_OAUTH_SCOPES`

Compatibilità: `META_OAUTH_SCOPES` resta supportata come fallback.

## Task Pagina
Quando Meta restituisce i task della Pagina, F1 accetta come capacità di pubblicazione almeno:
- `CREATE_CONTENT`
- `MANAGE`
- `PROFILE_PLUS_CREATE_CONTENT`
- `PROFILE_PLUS_MANAGE`
- `PROFILE_PLUS_FULL_CONTROL`

## Stati Connection Doctor
- `PAGINA_DA_SELEZIONARE`
- `PAGINA_NON_ACCESSIBILE`
- `PERMESSI_INSUFFICIENTI`
- `TOKEN_SCADUTO`
- `ACCOUNT_ERRATO`
- `ACCOUNT_CONDIVISO`
- `SERVER_CONFIG_MISSING`

`APP_REVIEW_REQUIRED` e `BUSINESS_VERIFICATION_REQUIRED` non devono essere mostrati automaticamente: vanno usati solo quando Meta restituisce o il pannello sviluppatori conferma quel requisito.

## Antica Cappella
URL previsto:
`https://www.facebook.com/profile.php?id=61550077453442`

Il parser ricava come Page ID atteso:
`61550077453442`

Questo ID viene usato per selezionare la Pagina corretta quando compare in `/me/accounts`. Non viene salvato come account verificato finché OAuth non ha confermato l'accesso.

Instagram Antica Cappella resta sul provider Buffer e non viene modificato dal flusso Facebook.


## Fonti ufficiali Meta
Ricerca verificata il 2026-10-01:
- Meta official Facebook API workspace (Postman): https://www.postman.com/meta/facebook/overview
- Facebook API — Get Access Tokens of Pages You Manage: https://www.postman.com/meta/facebook/request/bqfxwbp/get-access-tokens-of-pages-you-manage
- Facebook API documentation / Tokens: https://www.postman.com/meta/facebook/documentation/r56bjfd/facebook-api
- Meta official Instagram API documentation, per distinguere il flusso Instagram da Facebook: https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api

La documentazione ufficiale Facebook mostra `/me/accounts?fields=name,access_token,tasks` con User Access Token per ottenere Pagine gestite, Page ID, Page Access Token e task. Il sistema non usa l'etichetta "pagina aziendale" come criterio tecnico di collegamento.
