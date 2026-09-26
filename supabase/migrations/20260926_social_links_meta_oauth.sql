-- Snapshot existing social configuration before any schema/data changes.
create table if not exists public.f1_social_config_snapshots (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  label text not null,
  snapshot jsonb not null
);
alter table public.f1_social_config_snapshots enable row level security;

insert into public.f1_social_config_snapshots(label,snapshot)
select 'before_social_links_meta_oauth_20260926',
jsonb_build_object(
  'clients', (select coalesce(jsonb_agg(to_jsonb(c) order by c.name),'[]'::jsonb) from public.f1_content_clients c),
  'social_channels', (select coalesce(jsonb_agg(to_jsonb(s) order by s.client_id,s.platform),'[]'::jsonb) from public.f1_client_social_channels s),
  'oauth_tokens_metadata', (
    select coalesce(jsonb_agg(
      jsonb_build_object(
        'id',t.id,'owner_id',t.owner_id,'client_id',t.client_id,'platform',t.platform,
        'token_type',t.token_type,'scope',t.scope,'expires_at',t.expires_at,
        'refresh_expires_at',t.refresh_expires_at,'provider_subject',t.provider_subject,
        'metadata',t.metadata,'created_at',t.created_at,'updated_at',t.updated_at
      ) order by t.client_id,t.platform
    ),'[]'::jsonb)
    from public.f1_social_oauth_tokens t
  )
);

alter table public.f1_client_social_channels
  add column if not exists profile_url text;

create index if not exists f1_social_channels_platform_external_idx
  on public.f1_client_social_channels(platform, external_channel_id)
  where external_channel_id is not null;

create index if not exists f1_social_channels_platform_profile_idx
  on public.f1_client_social_channels(platform, profile_url)
  where profile_url is not null;

-- Preserve existing connected/Buffer rows. Only unconnected Meta-capable rows move to broker.
update public.f1_client_social_channels
set provider='oauth_broker', updated_at=now()
where platform in ('facebook','instagram')
  and provider='direct'
  and enabled=false
  and verified=false;

-- Seed known URLs from client data when available, never overwrite a channel URL.
update public.f1_client_social_channels s
set profile_url = case s.platform
  when 'facebook' then nullif(c.facebook,'')
  when 'instagram' then nullif(c.instagram,'')
  when 'linkedin-page' then nullif(c.linkedin,'')
  when 'tiktok' then nullif(c.tiktok,'')
  when 'youtube' then nullif(c.youtube,'')
  else s.profile_url
end,
updated_at=now()
from public.f1_content_clients c
where s.client_id=c.id
  and s.owner_id=c.owner_id
  and s.profile_url is null
  and (
    (s.platform='facebook' and nullif(c.facebook,'') is not null) or
    (s.platform='instagram' and nullif(c.instagram,'') is not null) or
    (s.platform='linkedin-page' and nullif(c.linkedin,'') is not null) or
    (s.platform='tiktok' and nullif(c.tiktok,'') is not null) or
    (s.platform='youtube' and nullif(c.youtube,'') is not null)
  );

create or replace function public.f1_seed_social_channels()
returns trigger
language plpgsql
set search_path to 'public'
as $function$
begin
  insert into public.f1_client_social_channels
    (owner_id, client_id, platform, provider, enabled, verified, connection_status)
  values
    (new.owner_id, new.id, 'facebook', 'oauth_broker', false, false, 'CANALE_DA_COLLEGARE'),
    (new.owner_id, new.id, 'instagram', 'oauth_broker', false, false, 'CANALE_DA_COLLEGARE'),
    (new.owner_id, new.id, 'linkedin-page', 'oauth_broker', false, false, 'CANALE_DA_COLLEGARE'),
    (new.owner_id, new.id, 'tiktok', 'oauth_broker', false, false, 'CANALE_DA_COLLEGARE'),
    (new.owner_id, new.id, 'youtube', 'oauth_broker', false, false, 'CANALE_DA_COLLEGARE')
  on conflict (owner_id, client_id, platform) do nothing;
  return new;
end;
$function$;
