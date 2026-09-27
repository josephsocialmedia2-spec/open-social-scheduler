-- F1 Social cloud browser publisher: per-client browser isolation and durable queue.

create table if not exists public.f1_client_browser_profiles (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  browser_host text not null default 'f1-social-vps',
  profile_path text not null,
  browser_type text not null default 'chromium',
  status text not null default 'DISABLED' check (status in ('READY','AUTH_REQUIRED','EXPIRED','ERROR','DISABLED')),
  google_email text,
  last_started_at timestamptz,
  last_verified_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id,client_id)
);

create table if not exists public.f1_client_browser_social_sessions (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  browser_profile_id uuid not null references public.f1_client_browser_profiles(id) on delete cascade,
  platform text not null check (platform in ('facebook','instagram','tiktok','youtube','linkedin-page')),
  expected_profile_url text,
  expected_account_id text,
  expected_account_name text,
  status text not null default 'NOT_CONFIGURED' check (status in ('CONNECTED','AUTH_REQUIRED','EXPIRED','ACCOUNT_WRONG','BLOCKED','NOT_CONFIGURED')),
  last_verified_at timestamptz,
  last_used_at timestamptz,
  error_code text,
  error_message text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id,client_id,platform)
);

create table if not exists public.f1_publication_queue (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  calendar_id uuid references public.f1_content_calendar(id) on delete set null,
  content_id uuid not null references public.f1_content_items(id) on delete cascade,
  platform text not null check (platform in ('facebook','instagram','tiktok','youtube','linkedin-page')),
  scheduled_at timestamptz not null,
  timezone text not null default 'Europe/Rome',
  content_type text not null default 'post',
  caption text not null default '',
  media_payload jsonb not null default '[]'::jsonb,
  status text not null default 'SCHEDULED' check (status in ('DRAFT','APPROVED','SCHEDULED','DUE','LOCKED','PUBLISHING','PUBLISHED','PARTIAL','ERROR','AUTH_REQUIRED','ACCOUNT_WRONG','DUPLICATE_BLOCKED')),
  approval_status text not null default 'APPROVED' check (approval_status in ('PENDING','APPROVED','REJECTED')),
  publishing_method text check (publishing_method is null or publishing_method in ('API','BROWSER')),
  attempt_count integer not null default 0,
  last_attempt_at timestamptz,
  locked_at timestamptz,
  locked_by text,
  lock_expires_at timestamptz,
  published_at timestamptz,
  external_post_id text,
  external_post_url text,
  error_code text,
  error_message text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(owner_id,client_id,content_id,platform,scheduled_at)
);

create table if not exists public.f1_publication_audit (
  id uuid primary key default gen_random_uuid(),
  publication_id uuid references public.f1_publication_queue(id) on delete set null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  client_id uuid not null references public.f1_content_clients(id) on delete cascade,
  platform text not null,
  method text,
  expected_account text,
  actual_account text,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  media_count integer not null default 0,
  github_run_id text,
  github_sha text,
  browser_profile_id uuid references public.f1_client_browser_profiles(id) on delete set null,
  external_post_id text,
  external_post_url text,
  status text not null,
  error_code text,
  error_message text,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists f1_browser_profiles_client_idx on public.f1_client_browser_profiles(client_id);
create index if not exists f1_browser_sessions_client_platform_idx on public.f1_client_browser_social_sessions(client_id,platform);
create index if not exists f1_publication_queue_due_idx on public.f1_publication_queue(status,approval_status,scheduled_at);
create index if not exists f1_publication_queue_client_platform_idx on public.f1_publication_queue(client_id,platform,scheduled_at desc);
create index if not exists f1_publication_audit_pub_idx on public.f1_publication_audit(publication_id,created_at desc);

alter table public.f1_client_browser_profiles enable row level security;
alter table public.f1_client_browser_social_sessions enable row level security;
alter table public.f1_publication_queue enable row level security;
alter table public.f1_publication_audit enable row level security;

drop policy if exists "browser_profiles_owner_read" on public.f1_client_browser_profiles;
create policy "browser_profiles_owner_read" on public.f1_client_browser_profiles for select to authenticated using (owner_id=auth.uid());
drop policy if exists "browser_sessions_owner_read" on public.f1_client_browser_social_sessions;
create policy "browser_sessions_owner_read" on public.f1_client_browser_social_sessions for select to authenticated using (owner_id=auth.uid());
drop policy if exists "publication_queue_owner_read" on public.f1_publication_queue;
create policy "publication_queue_owner_read" on public.f1_publication_queue for select to authenticated using (owner_id=auth.uid());
drop policy if exists "publication_audit_owner_read" on public.f1_publication_audit;
create policy "publication_audit_owner_read" on public.f1_publication_audit for select to authenticated using (owner_id=auth.uid());

grant select on public.f1_client_browser_profiles, public.f1_client_browser_social_sessions, public.f1_publication_queue, public.f1_publication_audit to authenticated;
grant all on public.f1_client_browser_profiles, public.f1_client_browser_social_sessions, public.f1_publication_queue, public.f1_publication_audit to service_role;

create or replace function public.f1_seed_cloud_browser_for_client()
returns trigger language plpgsql security definer set search_path=public as $$
declare profile_uuid uuid;
begin
  insert into public.f1_client_browser_profiles(owner_id,client_id,profile_path,status)
  values(new.owner_id,new.id,'/srv/f1social/browser-profiles/'||new.id::text||'/chrome-profile','DISABLED')
  on conflict(owner_id,client_id) do update set profile_path=excluded.profile_path,updated_at=now()
  returning id into profile_uuid;
  if profile_uuid is null then select id into profile_uuid from public.f1_client_browser_profiles where owner_id=new.owner_id and client_id=new.id limit 1; end if;
  insert into public.f1_client_browser_social_sessions(owner_id,client_id,browser_profile_id,platform,expected_profile_url,expected_account_name,status)
  values
    (new.owner_id,new.id,profile_uuid,'facebook',nullif(new.facebook,''),new.name,'NOT_CONFIGURED'),
    (new.owner_id,new.id,profile_uuid,'instagram',nullif(new.instagram,''),new.name,'NOT_CONFIGURED'),
    (new.owner_id,new.id,profile_uuid,'tiktok',nullif(new.tiktok,''),new.name,'NOT_CONFIGURED'),
    (new.owner_id,new.id,profile_uuid,'youtube',nullif(new.youtube,''),new.name,'NOT_CONFIGURED'),
    (new.owner_id,new.id,profile_uuid,'linkedin-page',nullif(new.linkedin,''),new.name,'NOT_CONFIGURED')
  on conflict(owner_id,client_id,platform) do update set
    browser_profile_id=excluded.browser_profile_id,
    expected_profile_url=coalesce(excluded.expected_profile_url,public.f1_client_browser_social_sessions.expected_profile_url),
    expected_account_name=excluded.expected_account_name,
    updated_at=now();
  return new;
end $$;

drop trigger if exists f1_content_clients_seed_cloud_browser on public.f1_content_clients;
create trigger f1_content_clients_seed_cloud_browser
after insert or update of facebook,instagram,tiktok,youtube,linkedin,name on public.f1_content_clients
for each row execute function public.f1_seed_cloud_browser_for_client();

insert into public.f1_client_browser_profiles(owner_id,client_id,profile_path,status)
select owner_id,id,'/srv/f1social/browser-profiles/'||id::text||'/chrome-profile','DISABLED'
from public.f1_content_clients
on conflict(owner_id,client_id) do nothing;

insert into public.f1_client_browser_social_sessions(owner_id,client_id,browser_profile_id,platform,expected_profile_url,expected_account_name,status)
select c.owner_id,c.id,b.id,p.platform,
  case p.platform
    when 'facebook' then nullif(c.facebook,'')
    when 'instagram' then nullif(c.instagram,'')
    when 'tiktok' then nullif(c.tiktok,'')
    when 'youtube' then nullif(c.youtube,'')
    when 'linkedin-page' then nullif(c.linkedin,'')
  end,
  c.name,'NOT_CONFIGURED'
from public.f1_content_clients c
join public.f1_client_browser_profiles b on b.owner_id=c.owner_id and b.client_id=c.id
cross join (values('facebook'),('instagram'),('tiktok'),('youtube'),('linkedin-page')) p(platform)
on conflict(owner_id,client_id,platform) do nothing;

create or replace function public.f1_claim_due_publications(p_worker text,p_limit integer default 10)
returns setof public.f1_publication_queue language plpgsql security definer set search_path=public as $$
begin
  return query
  with picked as (
    select q.id from public.f1_publication_queue q
    where q.approval_status='APPROVED'
      and q.status in ('SCHEDULED','DUE','ERROR')
      and q.scheduled_at<=now()
      and (q.lock_expires_at is null or q.lock_expires_at<now())
      and q.published_at is null
      and (q.status<>'ERROR' or q.error_code in ('NETWORK_ERROR','UPLOAD_TIMEOUT','TEMPORARY_PLATFORM_ERROR'))
    order by q.scheduled_at asc
    for update skip locked
    limit greatest(1,least(coalesce(p_limit,10),50))
  )
  update public.f1_publication_queue q
  set status='LOCKED',locked_at=now(),locked_by=left(coalesce(p_worker,'worker'),200),
      lock_expires_at=now()+interval '20 minutes',attempt_count=q.attempt_count+1,
      last_attempt_at=now(),updated_at=now()
  from picked where q.id=picked.id
  returning q.*;
end $$;

revoke all on function public.f1_claim_due_publications(text,integer) from public,anon,authenticated;
grant execute on function public.f1_claim_due_publications(text,integer) to service_role;
