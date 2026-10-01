# Architecture — Later Personal Manager

## Runtime
- Frontend: GitHub Pages, `f1-content-hub/`.
- Auth/database/storage: existing Supabase project.
- OAuth broker: Supabase Edge Function `f1-social-oauth`.
- Publishing: existing persistent calendar/queue/publisher pipeline. Browser timers are not the source of truth.
- Tests/deploy: GitHub Actions.

## Data mapping
The repository already contains the normalized equivalents of the required model:
- clients → `f1_content_clients`
- social_accounts → `f1_client_social_channels`
- oauth_tokens → `f1_social_oauth_tokens`
- media_assets → `f1_content_media`
- content_items → `f1_content_items`
- scheduled_posts → `f1_content_calendar`
- publication_jobs → `f1_publication_queue`
- publication_attempts/activity log → `f1_publication_events`

This change adds:
- `f1_social_client_invites`
- `f1_social_connection_health`
- `f1_free_quota_usage`

## Security boundary
GitHub Pages never receives provider client secrets or stored OAuth refresh tokens. The Edge Function performs authorization-code exchange, refresh and provider verification server-side. OAuth material is encrypted before persistence.

## UI
The dashboard is intentionally sparse: active clients only, name-only cards, ordered red → orange → green. Detailed connection state lives in the client/Connections workspace.
