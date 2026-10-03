create table if not exists public.f1_email_plan_settings (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  active boolean not null default true,
  cadence text not null default 'WEEKLY' check (cadence in ('WEEKLY')),
  send_weekday smallint not null default 4 check (send_weekday between 1 and 7),
  send_time time without time zone not null default '10:00',
  timezone text not null default 'Europe/Rome',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id, client_id)
);

create table if not exists public.f1_email_plan_items (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  scheduled_at timestamptz not null,
  month_label text,
  week_number integer,
  theme text not null default '',
  objective text not null default '',
  subject text not null default '',
  preheader text not null default '',
  body_text text not null default '',
  cta_text text not null default '',
  cta_url text not null default '',
  crm_segment text not null default 'TUTTI_I_CONTATTI',
  status text not null default 'IMPORTATA'
    check (status in ('IMPORTATA','DA_VERIFICARE','APPROVATA','PROGRAMMATA','IN_INVIO','INVIATA','ERRORE')),
  campaign_id uuid references public.email_campaigns(id) on delete set null,
  source_file_name text,
  source_status text,
  metadata jsonb not null default '{}'::jsonb,
  imported_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id, client_id, scheduled_at)
);

create index if not exists f1_email_plan_items_client_schedule_idx
  on public.f1_email_plan_items(owner_id, client_id, scheduled_at);

alter table public.f1_email_plan_settings enable row level security;
alter table public.f1_email_plan_items enable row level security;

create policy f1_email_plan_settings_owner_all
  on public.f1_email_plan_settings
  for all
  using (
    (select auth.uid()) = owner_id
    and exists (
      select 1 from public.f1_content_clients c
      where c.id = client_id and c.owner_id = (select auth.uid())
    )
  )
  with check (
    (select auth.uid()) = owner_id
    and exists (
      select 1 from public.f1_content_clients c
      where c.id = client_id and c.owner_id = (select auth.uid())
    )
  );

create policy f1_email_plan_items_owner_all
  on public.f1_email_plan_items
  for all
  using (
    (select auth.uid()) = owner_id
    and exists (
      select 1 from public.f1_content_clients c
      where c.id = client_id and c.owner_id = (select auth.uid())
    )
  )
  with check (
    (select auth.uid()) = owner_id
    and exists (
      select 1 from public.f1_content_clients c
      where c.id = client_id and c.owner_id = (select auth.uid())
    )
  );

grant select, insert, update, delete on public.f1_email_plan_settings to authenticated;
grant select, insert, update, delete on public.f1_email_plan_items to authenticated;
