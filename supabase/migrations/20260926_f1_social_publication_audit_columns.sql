-- F1 Social multi-tenant ownership and audit hardening.
-- Applied to the live database on 2026-09-26 before this file was committed.
-- This file documents the desired schema for fresh environments.

alter table public.f1_publication_events
  add column if not exists api_sent boolean not null default false,
  add column if not exists external_url text,
  add column if not exists account_expected text,
  add column if not exists account_detected text,
  add column if not exists api_response jsonb not null default '{}'::jsonb;

create index if not exists f1_publication_events_client_platform_created_idx
  on public.f1_publication_events(client_id, platform, created_at desc);

-- Live database also enforces composite ownership:
-- f1_content_clients unique(id, owner_id)
-- f1_client_social_channels (client_id, owner_id) -> f1_content_clients(id, owner_id)
-- f1_social_oauth_tokens (client_id, owner_id) -> f1_content_clients(id, owner_id)
-- f1_content_items (client_id, owner_id) -> f1_content_clients(id, owner_id)
-- f1_content_media (client_id, owner_id) -> f1_content_clients(id, owner_id)
-- f1_content_calendar (client_id, owner_id) -> f1_content_clients(id, owner_id)
-- f1_publication_events (client_id, owner_id) -> f1_content_clients(id, owner_id)
