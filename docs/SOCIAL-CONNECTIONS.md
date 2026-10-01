# Social Connections

## Truth rule
A saved URL is not a connection. The UI may show `COLLEGATO` only when the channel is enabled and verified after provider/OAuth checks.

## Providers
- Facebook Pages: Meta OAuth + Pages permissions.
- Instagram: professional account flow through Meta; publishing permission required.
- TikTok: Login Kit / Content Posting API; `video.publish` is required for Direct Post.
- YouTube: Google OAuth 2 + `youtube.upload`.
- LinkedIn Pages: organization permissions, not member-only posting. `w_organization_social` and an eligible Page role are required.

## Connection Doctor
The doctor classifies configuration missing, disconnected account, expired token, reauthorization, missing publishing scope, wrong/shared account and LinkedIn member-vs-organization mismatch. The UI shows a human explanation while technical metadata stays in the health/log tables.

## Client invitation
The administrator creates an expiring URL. Only SHA-256 of its bearer token is stored. The client authorizes on the provider site; the app never asks for the social password.


## Facebook Page Connection Standard
Facebook è trattato come Pages API, non come profilo personale generico. Il broker usa `/me/accounts`, Page ID, Page Access Token, task Pagina e scope realmente concessi. Gli URL `profile.php?id=...` vengono riconosciuti per ID. Vedi `FACEBOOK_PAGE_CONNECTION_STANDARD.md`.
