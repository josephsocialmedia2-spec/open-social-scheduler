-- Persist server-side social analytics snapshots for F1 Social.
-- Raw provider metrics are stored without inventing cross-platform normalization.

create table if not exists public.f1_social_analytics_snapshots (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  platform text not null,
  provider text not null default 'postiz',
  integration_id text,
  lookback_days integer not null default 30 check (lookback_days between 1 and 730),
  metrics jsonb not null default '{}'::jsonb,
  error text,
  snapshot_date date not null default ((now() at time zone 'UTC')::date),
  captured_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (client_id, platform, provider, lookback_days, snapshot_date)
);

alter table public.f1_social_analytics_snapshots enable row level security;

create policy "owners_read_social_analytics_snapshots"
on public.f1_social_analytics_snapshots
for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy "owners_manage_social_analytics_snapshots"
on public.f1_social_analytics_snapshots
for all
to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

revoke all on table public.f1_social_analytics_snapshots from anon;
grant select, insert, update, delete on table public.f1_social_analytics_snapshots to authenticated;
grant all on table public.f1_social_analytics_snapshots to service_role;

create index if not exists f1_social_analytics_client_captured_idx
  on public.f1_social_analytics_snapshots (client_id, captured_at desc);

create index if not exists f1_social_analytics_platform_captured_idx
  on public.f1_social_analytics_snapshots (platform, captured_at desc);
