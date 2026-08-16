# Visibility Engine — setup senza scheduler a pagamento

Il repository usa GitHub Actions come motore e le API ufficiali dei social come trasporto. Postiz non è richiesto per la pubblicazione.

## Flusso operativo

1. GitHub prepara una settimana di contenuti e media.
2. Il lunedì apre una issue `[SOCIAL-WEEK] YYYY-WNN`.
3. Prima della conferma, i job restano `awaiting_approval`.
4. Il proprietario del repository scrive `CONFERMO` nella issue.
5. Gli slot approvati diventano pubblicabili.
6. `Direct Social Publisher` controlla ogni 15 minuti e invia solo i job approvati e già scaduti.
7. `REVOCA` blocca i job della settimana non ancora pubblicati.

## F1 Immobiliare — GitHub Secrets

Configurare in **Settings → Secrets and variables → Actions** solo le piattaforme che si vogliono attivare:

- `F1_FACEBOOK_PAGE_ACCESS_TOKEN`
- `F1_INSTAGRAM_ACCESS_TOKEN`
- `F1_INSTAGRAM_USER_ID`
- `F1_TIKTOK_ACCESS_TOKEN`
- `F1_LINKEDIN_ACCESS_TOKEN`
- `F1_LINKEDIN_AUTHOR_URN`
- `F1_YOUTUBE_CLIENT_ID`
- `F1_YOUTUBE_CLIENT_SECRET`
- `F1_YOUTUBE_REFRESH_TOKEN`
- `F1_PINTEREST_ACCESS_TOKEN`
- `F1_PINTEREST_BOARD_ID`

Variabili consigliate:

- `META_GRAPH_VERSION=v23.0` oppure la versione Graph scelta per l'app Meta
- `LINKEDIN_VERSION=202604`
- `TIKTOK_PRIVACY_LEVEL=SELF_ONLY` durante i test
- `YOUTUBE_PRIVACY_STATUS=private` durante i test
- `F1_PINTEREST_LINK=https://f1immobiliare.com/`

## Real Media Pro

Il tenant è già predisposto ma resta `active: false` finché non vengono forniti i suoi URL social e completate le credenziali OAuth. I secret usano lo stesso schema con prefisso `RMP_`.

## Formati

- Facebook: Reel video; per i caroselli il fallback corrente pubblica la prima slide come immagine.
- Instagram: Reel e carosello; i media approvati vengono esposti temporaneamente tramite un asset GitHub Release e rimossi dopo l'invio.
- TikTok: Reel/video tramite Content Posting API; configurazione di test prudente `SELF_ONLY`.
- LinkedIn: post organico testuale sul Member/Organization URN configurato.
- YouTube: video/Short tramite upload resumable; test iniziali privati.
- Pinterest: Pin immagine dalla prima slide dei contenuti carosello.

## Gruppi Facebook

Il radar gruppi è separato dal publisher. GitHub può cercare gruppi pubblicamente indicizzati, deduplicarli, classificarli e tenere lo storico. Le azioni che richiedono la sessione personale Facebook — richiesta di ingresso, risposte alle domande dell'admin e pubblicazione nel gruppo — restano azioni esplicite dell'utente nel sito Facebook.

Comandi di stato nelle issue `[FB-GROUPS]`:

- `/approve all`
- `/approve FBG-...`
- `/reject FBG-...`
- `/joined FBG-...`
- `/member FBG-...`

## Sicurezza

Non inserire password, access token, refresh token o client secret nei file del repository. Le credenziali devono restare esclusivamente nei GitHub Actions Secrets.
