-- Later Personal Manager: secure client social invitations, connection health and zero-cost guard.
-- Raw invite tokens are NEVER stored. Only SHA-256 hashes are persisted.

create table if not exists public.f1_social_client_invites (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  token_hash text not null unique,
  allowed_platforms text[] not null default '{}'::text[],
  connected_platforms text[] not null default '{}'::text[],
  status text not null default 'ATTIVO',
  expires_at timestamptz not null,
  last_access_at timestamptz,
  completed_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint f1_social_client_invites_status_check
    check (status in ('ATTIVO','COMPLETATO','SCADUTO','REVOCATO')),
  constraint f1_social_client_invites_platforms_check
    check (
      allowed_platforms <@ array['facebook','instagram','tiktok','youtube','linkedin']::text[]
      and connected_platforms <@ array['facebook','instagram','tiktok','youtube','linkedin']::text[]
    )
);

create index if not exists f1_social_client_invites_owner_client_idx
  on public.f1_social_client_invites(owner_id,client_id,created_at desc);
create index if not exists f1_social_client_invites_expires_idx
  on public.f1_social_client_invites(expires_at)
  where status='ATTIVO';

alter table public.f1_social_client_invites enable row level security;
revoke all on table public.f1_social_client_invites from anon, authenticated;
grant select, insert, update, delete on table public.f1_social_client_invites to service_role;

comment on table public.f1_social_client_invites is
  'Single-purpose social OAuth invitation records. Raw bearer invite tokens are never stored; only SHA-256 hashes.';

create table if not exists public.f1_social_connection_health (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  platform text not null,
  status text not null,
  severity text not null,
  code text not null,
  human_message text not null,
  recommended_action text,
  details jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint f1_social_connection_health_platform_check
    check (platform in ('facebook','instagram','linkedin-page','tiktok','youtube')),
  constraint f1_social_connection_health_severity_check
    check (severity in ('ok','warning','critical')),
  constraint f1_social_connection_health_owner_client_platform_key
    unique(owner_id,client_id,platform)
);

create index if not exists f1_social_connection_health_client_idx
  on public.f1_social_connection_health(client_id,severity,checked_at desc);

alter table public.f1_social_connection_health enable row level security;
drop policy if exists "f1_social_connection_health_owner_select" on public.f1_social_connection_health;
create policy "f1_social_connection_health_owner_select"
  on public.f1_social_connection_health
  for select to authenticated
  using (owner_id = auth.uid());
revoke insert, update, delete on table public.f1_social_connection_health from anon, authenticated;
grant select on table public.f1_social_connection_health to authenticated;
grant select, insert, update, delete on table public.f1_social_connection_health to service_role;

create table if not exists public.f1_free_quota_usage (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  service_key text not null,
  plan_name text not null default 'free',
  used_value numeric not null default 0,
  hard_limit numeric,
  unit text not null default 'operations',
  usage_percent numeric generated always as (
    case when hard_limit is null or hard_limit <= 0 then null
         else round((used_value / hard_limit) * 100, 2)
    end
  ) stored,
  blocked boolean not null default false,
  details jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint f1_free_quota_usage_unique unique(owner_id,service_key),
  constraint f1_free_quota_usage_nonnegative check (used_value >= 0 and (hard_limit is null or hard_limit >= 0))
);

alter table public.f1_free_quota_usage enable row level security;
drop policy if exists "f1_free_quota_usage_owner_select" on public.f1_free_quota_usage;
create policy "f1_free_quota_usage_owner_select"
  on public.f1_free_quota_usage
  for select to authenticated
  using (owner_id = auth.uid());
revoke insert, update, delete on table public.f1_free_quota_usage from anon, authenticated;
grant select on table public.f1_free_quota_usage to authenticated;
grant select, insert, update, delete on table public.f1_free_quota_usage to service_role;

comment on table public.f1_free_quota_usage is
  'Free-tier usage registry. A service reaching its configured blocking threshold must stop rather than upgrade to paid usage.';
