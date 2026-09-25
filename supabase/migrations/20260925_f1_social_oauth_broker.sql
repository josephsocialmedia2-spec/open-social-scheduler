-- F1 Social Publisher - centralized OAuth metadata and encrypted token store.
-- Token plaintext never lives in public.f1_client_social_channels or in GitHub.
-- f1_social_oauth_tokens is service-role only; ciphertext is produced by the Edge Function.

alter table public.f1_client_social_channels
  add column if not exists account_name text,
  add column if not exists scopes text[] not null default '{}'::text[],
  add column if not exists token_expires_at timestamptz,
  add column if not exists refresh_token_expires_at timestamptz,
  add column if not exists last_refresh_at timestamptz,
  add column if not exists reauthorization_required boolean not null default false,
  add column if not exists oauth_subject text,
  add column if not exists oauth_metadata jsonb not null default '{}'::jsonb;

create table if not exists public.f1_social_oauth_tokens (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  platform text not null,
  access_token_ciphertext text,
  refresh_token_ciphertext text,
  token_type text,
  scope text,
  expires_at timestamptz,
  refresh_expires_at timestamptz,
  provider_subject text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint f1_social_oauth_tokens_platform_check
    check (platform in ('youtube','tiktok','linkedin','facebook','instagram')),
  constraint f1_social_oauth_tokens_owner_client_platform_key
    unique (owner_id, client_id, platform)
);

alter table public.f1_social_oauth_tokens enable row level security;
revoke all on table public.f1_social_oauth_tokens from anon, authenticated;
grant select, insert, update, delete on table public.f1_social_oauth_tokens to service_role;

create index if not exists f1_social_oauth_tokens_client_platform_idx
  on public.f1_social_oauth_tokens(client_id, platform);

create or replace function public.f1_seed_social_channels()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  insert into public.f1_client_social_channels
    (owner_id, client_id, platform, provider, enabled, verified, connection_status)
  values
    (new.owner_id, new.id, 'facebook', 'direct', false, false, 'CANALE_DA_COLLEGARE'),
    (new.owner_id, new.id, 'instagram', 'direct', false, false, 'CANALE_DA_COLLEGARE'),
    (new.owner_id, new.id, 'linkedin-page', 'oauth_broker', false, false, 'CONFIGURAZIONE_PRONTA'),
    (new.owner_id, new.id, 'tiktok', 'oauth_broker', false, false, 'CONFIGURAZIONE_PRONTA'),
    (new.owner_id, new.id, 'youtube', 'oauth_broker', false, false, 'CONFIGURAZIONE_PRONTA')
  on conflict (owner_id, client_id, platform) do nothing;
  return new;
end;
$$;

drop trigger if exists f1_content_clients_seed_social_channels on public.f1_content_clients;
create trigger f1_content_clients_seed_social_channels
after insert on public.f1_content_clients
for each row execute function public.f1_seed_social_channels();

-- Backfill missing rows without changing existing Buffer/direct connections.
insert into public.f1_client_social_channels
  (owner_id, client_id, platform, provider, enabled, verified, connection_status, secret_prefix)
select
  c.owner_id,
  c.id,
  p.platform,
  p.provider,
  false,
  false,
  'CONFIGURAZIONE_PRONTA',
  case
    when c.slug='f1-immobiliare' then 'F1'
    when c.slug='real-media-pro' then 'RMP'
    when c.slug='immobiliare-la-sacra' then 'LASACRA'
    when c.slug='antica-cappella' then 'ANTICACAPPELLA'
    when c.slug='marta-ruffino' then 'MARTA'
    when c.slug='cartolibreria-10-e-lode' then 'CARTOLIBRERIA10ELODE'
    else upper(regexp_replace(c.slug, '[^a-z0-9]+', '', 'g'))
  end
from public.f1_content_clients c
cross join (
  values
    ('linkedin-page'::text, 'oauth_broker'::text),
    ('tiktok'::text, 'oauth_broker'::text),
    ('youtube'::text, 'oauth_broker'::text)
) as p(platform, provider)
where c.status='ATTIVO'
on conflict (owner_id, client_id, platform) do nothing;

comment on table public.f1_social_oauth_tokens is
  'Encrypted OAuth token material for F1 Social Publisher. Service-role only; plaintext is encrypted/decrypted in f1-social-oauth Edge Function.';
