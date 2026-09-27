alter table public.f1_whatsapp_senders
  add column if not exists client_id uuid references public.f1_content_clients(id) on delete set null,
  add column if not exists auto_process boolean not null default true,
  add column if not exists report_recipient boolean not null default false,
  add column if not exists suppress_operational_notifications boolean not null default true;

create index if not exists f1_whatsapp_senders_client_idx
  on public.f1_whatsapp_senders(owner_id, client_id)
  where active = true;

alter table public.f1_content_media
  add column if not exists sha256 text;

create index if not exists f1_content_media_sha256_idx
  on public.f1_content_media(owner_id, client_id, sha256)
  where sha256 is not null;

create table if not exists public.f1_content_inbox (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  client_id uuid references public.f1_content_clients(id) on delete set null,
  source text not null default 'WHATSAPP',
  source_message_id text not null,
  source_sender text,
  content_type text not null default 'ALTRO',
  text_body text not null default '',
  caption text not null default '',
  media_payload jsonb not null default '[]'::jsonb,
  storage_paths jsonb not null default '[]'::jsonb,
  content_hash text,
  received_at timestamptz not null default now(),
  status text not null default 'RECEIVED',
  classification jsonb not null default '{}'::jsonb,
  confidence numeric(5,4),
  retry_count integer not null default 0,
  next_retry_at timestamptz,
  last_error text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id, source, source_message_id)
);

create index if not exists f1_content_inbox_status_idx
  on public.f1_content_inbox(status, next_retry_at, received_at);

create index if not exists f1_content_inbox_hash_idx
  on public.f1_content_inbox(owner_id, client_id, content_hash)
  where content_hash is not null;

alter table public.f1_content_inbox enable row level security;

drop policy if exists f1_content_inbox_owner_select on public.f1_content_inbox;
create policy f1_content_inbox_owner_select
  on public.f1_content_inbox for select
  to authenticated
  using (owner_id = auth.uid());

drop policy if exists f1_content_inbox_owner_insert on public.f1_content_inbox;
create policy f1_content_inbox_owner_insert
  on public.f1_content_inbox for insert
  to authenticated
  with check (owner_id = auth.uid());

drop policy if exists f1_content_inbox_owner_update on public.f1_content_inbox;
create policy f1_content_inbox_owner_update
  on public.f1_content_inbox for update
  to authenticated
  using (owner_id = auth.uid())
  with check (owner_id = auth.uid());

drop policy if exists f1_content_inbox_owner_delete on public.f1_content_inbox;
create policy f1_content_inbox_owner_delete
  on public.f1_content_inbox for delete
  to authenticated
  using (owner_id = auth.uid());

create table if not exists public.f1_social_daily_reports (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  report_date date not null,
  timezone text not null default 'Europe/Rome',
  body text not null default '',
  rows jsonb not null default '[]'::jsonb,
  summary jsonb not null default '{}'::jsonb,
  delivery_channel text,
  delivery_status text not null default 'STORED',
  delivered_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id, report_date)
);

alter table public.f1_social_daily_reports enable row level security;

drop policy if exists f1_social_daily_reports_owner_select on public.f1_social_daily_reports;
create policy f1_social_daily_reports_owner_select
  on public.f1_social_daily_reports for select
  to authenticated
  using (owner_id = auth.uid());

drop policy if exists f1_social_daily_reports_owner_insert on public.f1_social_daily_reports;
create policy f1_social_daily_reports_owner_insert
  on public.f1_social_daily_reports for insert
  to authenticated
  with check (owner_id = auth.uid());

drop policy if exists f1_social_daily_reports_owner_update on public.f1_social_daily_reports;
create policy f1_social_daily_reports_owner_update
  on public.f1_social_daily_reports for update
  to authenticated
  using (owner_id = auth.uid())
  with check (owner_id = auth.uid());

comment on table public.f1_content_inbox is
  'Unified autonomous intake queue for WhatsApp and other sources. No secrets.';
comment on table public.f1_social_daily_reports is
  'One operational F1 Social summary per owner/day.';
comment on column public.f1_whatsapp_senders.client_id is
  'Deterministic client mapping for autonomous WhatsApp intake.';
