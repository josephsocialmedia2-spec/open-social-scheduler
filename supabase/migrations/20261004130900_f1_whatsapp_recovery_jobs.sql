create table if not exists public.f1_whatsapp_recovery_jobs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  whatsapp_number text not null,
  date_from timestamptz not null,
  date_to timestamptz,
  timezone text not null default 'Europe/Rome',
  status text not null default 'QUEUED',
  local_archive_path text,
  manifest_json_path text,
  manifest_csv_path text,
  checkpoint jsonb not null default '{}'::jsonb,
  stats jsonb not null default '{}'::jsonb,
  last_error text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists f1_whatsapp_recovery_jobs_owner_client_idx
  on public.f1_whatsapp_recovery_jobs(owner_id, client_id, created_at desc);

create index if not exists f1_whatsapp_recovery_jobs_status_idx
  on public.f1_whatsapp_recovery_jobs(status, created_at);

alter table public.f1_whatsapp_recovery_jobs enable row level security;

drop policy if exists f1_whatsapp_recovery_jobs_owner_select on public.f1_whatsapp_recovery_jobs;
create policy f1_whatsapp_recovery_jobs_owner_select
  on public.f1_whatsapp_recovery_jobs for select
  to authenticated
  using ((select auth.uid()) = owner_id);

drop policy if exists f1_whatsapp_recovery_jobs_owner_insert on public.f1_whatsapp_recovery_jobs;
create policy f1_whatsapp_recovery_jobs_owner_insert
  on public.f1_whatsapp_recovery_jobs for insert
  to authenticated
  with check ((select auth.uid()) = owner_id);

drop policy if exists f1_whatsapp_recovery_jobs_owner_update on public.f1_whatsapp_recovery_jobs;
create policy f1_whatsapp_recovery_jobs_owner_update
  on public.f1_whatsapp_recovery_jobs for update
  to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);

drop policy if exists f1_whatsapp_recovery_jobs_owner_delete on public.f1_whatsapp_recovery_jobs;
create policy f1_whatsapp_recovery_jobs_owner_delete
  on public.f1_whatsapp_recovery_jobs for delete
  to authenticated
  using ((select auth.uid()) = owner_id);
