-- F1 Social annual email plan imported from approved CSV workflow.
create table if not exists public.f1_client_email_plans (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  period_start date not null,
  period_end date not null,
  frequency text not null default 'WEEKLY',
  status text not null default 'ATTIVA',
  source_filename text,
  source_type text not null default 'CSV',
  imported_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id, client_id, period_start, period_end)
);
create table if not exists public.f1_client_email_plan_items (
  id uuid primary key default gen_random_uuid(),
  plan_id uuid not null references public.f1_client_email_plans(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  send_at timestamptz not null,
  month_label text,
  week_no integer,
  theme text,
  objective text,
  subject text not null,
  preheader text,
  body_text text not null,
  cta_text text,
  cta_url text,
  crm_segment text not null default 'TUTTI_I_CONTATTI',
  status text not null default 'PROGRAMMATA',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists f1_email_plans_owner_client_idx on public.f1_client_email_plans(owner_id, client_id);
create index if not exists f1_email_plan_items_owner_client_idx on public.f1_client_email_plan_items(owner_id, client_id);
create index if not exists f1_email_plan_items_plan_send_idx on public.f1_client_email_plan_items(plan_id, send_at);
alter table public.f1_client_email_plans enable row level security;
alter table public.f1_client_email_plan_items enable row level security;
grant select, insert, update, delete on public.f1_client_email_plans to authenticated;
grant select, insert, update, delete on public.f1_client_email_plan_items to authenticated;
drop policy if exists "f1_client_email_plans_owner_all" on public.f1_client_email_plans;
create policy "f1_client_email_plans_owner_all" on public.f1_client_email_plans for all to authenticated
using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id);
drop policy if exists "f1_client_email_plan_items_owner_all" on public.f1_client_email_plan_items;
create policy "f1_client_email_plan_items_owner_all" on public.f1_client_email_plan_items for all to authenticated
using ((select auth.uid()) = owner_id) with check ((select auth.uid()) = owner_id);
