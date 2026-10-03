-- F1 Social · modulo EMAIL multi-cliente
-- Applica una struttura per account, brand kit, grafiche settimanali e campagne email.
-- Migrazione applicata a Supabase il 2026-10-03.

alter table public.f1_content_clients
  add column if not exists email_service_enabled boolean not null default false;

create table if not exists public.f1_client_email_accounts (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  sender_name text not null default '',
  email_address text not null,
  provider text not null check (provider in ('microsoft','gmail')),
  microsoft_account_type text null check (microsoft_account_type is null or microsoft_account_type in ('personal','organization')),
  tenant_id text null,
  connection_status text not null default 'NON_CONFIGURATO'
    check (connection_status in ('NON_CONFIGURATO','DA_CREARE','DA_AUTORIZZARE','COLLEGAMENTO_IN_CORSO','COLLEGATO','ERRORE','TOKEN_SCADUTO','RICONNETTERE','ACCOUNT_DIVERSO')),
  connected_email text null,
  provider_subject text null,
  scope text not null default '',
  expires_at timestamptz null,
  last_connected_at timestamptz null,
  last_test_at timestamptz null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id,client_id,email_address)
);
alter table public.f1_client_email_accounts enable row level security;

create table if not exists public.f1_client_email_oauth_tokens (
  account_id uuid primary key references public.f1_client_email_accounts(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  provider text not null check (provider in ('microsoft','gmail')),
  access_token_ciphertext text null,
  refresh_token_ciphertext text null,
  token_type text null,
  scope text null,
  expires_at timestamptz null,
  refresh_expires_at timestamptz null,
  pending_device_code_ciphertext text null,
  pending_device_expires_at timestamptz null,
  pending_device_interval integer null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.f1_client_email_oauth_tokens enable row level security;

create table if not exists public.f1_client_email_brand_kits (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  logo_storage_path text null,
  primary_color text not null default '#07111F',
  secondary_color text not null default '#2D7FF9',
  text_color text not null default '#142033',
  font_family text not null default 'Arial, Helvetica, sans-serif',
  signature_html text not null default '',
  phone text null,
  website text null,
  social_links jsonb not null default '{}'::jsonb,
  cta_text text null,
  cta_url text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id,client_id)
);
alter table public.f1_client_email_brand_kits enable row level security;

create table if not exists public.f1_client_email_graphics (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  storage_path text not null,
  file_name text not null,
  mime_type text not null,
  file_size bigint null,
  iso_year integer not null check (iso_year between 2020 and 2100),
  iso_week integer not null check (iso_week between 1 and 53),
  status text not null default 'BOZZA'
    check (status in ('BOZZA','DA_APPROVARE','APPROVATA','PROGRAMMATA','ATTIVA','ARCHIVIATA')),
  version integer not null default 1 check (version > 0),
  notes text null,
  active_from timestamptz null,
  active_until timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id,client_id,iso_year,iso_week,version)
);
alter table public.f1_client_email_graphics enable row level security;

create table if not exists public.f1_client_email_templates (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  name text not null,
  default_subject text not null default '',
  header_html text not null default '',
  body_html text not null default '',
  footer_html text not null default '',
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.f1_client_email_templates enable row level security;

create table if not exists public.f1_client_email_suppressions (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  email text not null,
  email_normalized text generated always as (lower(trim(email))) stored,
  reason text not null default 'UNSUBSCRIBED',
  source text not null default 'F1_SOCIAL_EMAIL',
  created_at timestamptz not null default now(),
  unique(owner_id,client_id,email_normalized)
);
alter table public.f1_client_email_suppressions enable row level security;

create table if not exists public.f1_client_email_attachments (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  campaign_id uuid not null references public.email_campaigns(id) on delete cascade,
  storage_path text not null,
  file_name text not null,
  mime_type text not null default 'application/octet-stream',
  file_size bigint null,
  created_at timestamptz not null default now()
);
alter table public.f1_client_email_attachments enable row level security;

alter table public.email_campaigns
  add column if not exists owner_id uuid null references auth.users(id) on delete cascade,
  add column if not exists client_id uuid null references public.f1_content_clients(id) on delete cascade,
  add column if not exists email_account_id uuid null references public.f1_client_email_accounts(id) on delete set null,
  add column if not exists template_id uuid null references public.f1_client_email_templates(id) on delete set null,
  add column if not exists graphic_id uuid null references public.f1_client_email_graphics(id) on delete set null,
  add column if not exists approval_state text not null default 'BOZZA',
  add column if not exists test_sent_at timestamptz null,
  add column if not exists approved_at timestamptz null,
  add column if not exists paused_at timestamptz null,
  add column if not exists compliance_confirmed_at timestamptz null,
  add column if not exists compliance_confirmed_by uuid null references auth.users(id) on delete set null,
  add column if not exists sender_snapshot jsonb not null default '{}'::jsonb,
  add column if not exists design_snapshot jsonb not null default '{}'::jsonb,
  add column if not exists delay_seconds integer not null default 12,
  add column if not exists delay_jitter_seconds integer not null default 5;

alter table public.email_campaign_recipients
  add column if not exists owner_id uuid null references auth.users(id) on delete cascade,
  add column if not exists client_id uuid null references public.f1_content_clients(id) on delete cascade;

alter table public.email_campaign_events
  add column if not exists owner_id uuid null references auth.users(id) on delete cascade,
  add column if not exists client_id uuid null references public.f1_content_clients(id) on delete cascade;

create index if not exists idx_f1_client_email_accounts_client on public.f1_client_email_accounts(owner_id,client_id);
create index if not exists idx_f1_client_email_graphics_week on public.f1_client_email_graphics(owner_id,client_id,iso_year,iso_week,status);
create index if not exists idx_email_campaigns_client on public.email_campaigns(owner_id,client_id,created_at desc);
create index if not exists idx_email_campaign_recipients_client on public.email_campaign_recipients(owner_id,client_id,status);
create index if not exists idx_email_campaign_events_client on public.email_campaign_events(owner_id,client_id,created_at desc);

update public.f1_content_clients
set email_service_enabled=true, updated_at=now()
where slug in ('f1-immobiliare','real-media-pro');

insert into public.f1_client_email_accounts
  (owner_id,client_id,sender_name,email_address,provider,microsoft_account_type,tenant_id,connection_status,metadata)
select owner_id,id,name,
       case slug when 'f1-immobiliare' then 'f1immobiliare@outlook.it'
                 when 'real-media-pro' then 'realmediapro@outlook.it' end,
       'microsoft','personal','consumers','DA_CREARE',
       jsonb_build_object('seeded_by','20261003_f1_client_email_module')
from public.f1_content_clients
where slug in ('f1-immobiliare','real-media-pro')
on conflict (owner_id,client_id,email_address) do nothing;
