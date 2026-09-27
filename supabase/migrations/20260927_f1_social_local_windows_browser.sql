-- Switch F1 Social browser fallback from VPS paths to the always-on local Windows PC.
-- Passwords, cookies and browser sessions remain local to that PC.

update public.f1_client_browser_profiles
set
  browser_host = 'local-windows',
  profile_path = client_id::text || '/chrome-profile',
  status = case when status = 'READY' then 'READY' else 'AUTH_REQUIRED' end,
  metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
    'execution_mode','local_windows_pc',
    'profile_root_env','F1_BROWSER_ROOT',
    'runner_label','f1-social-local-pc'
  ),
  updated_at = now();

create or replace function public.f1_seed_cloud_browser_for_client()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  profile_uuid uuid;
begin
  insert into public.f1_client_browser_profiles(
    owner_id,client_id,browser_host,profile_path,status,metadata
  )
  values(
    new.owner_id,
    new.id,
    'local-windows',
    new.id::text || '/chrome-profile',
    'AUTH_REQUIRED',
    jsonb_build_object(
      'execution_mode','local_windows_pc',
      'profile_root_env','F1_BROWSER_ROOT',
      'runner_label','f1-social-local-pc'
    )
  )
  on conflict(owner_id,client_id) do update
    set browser_host='local-windows',
        profile_path=excluded.profile_path,
        metadata=coalesce(public.f1_client_browser_profiles.metadata,'{}'::jsonb) || excluded.metadata,
        updated_at=now()
  returning id into profile_uuid;

  if profile_uuid is null then
    select id into profile_uuid
    from public.f1_client_browser_profiles
    where owner_id=new.owner_id and client_id=new.id
    limit 1;
  end if;

  insert into public.f1_client_browser_social_sessions(
    owner_id,client_id,browser_profile_id,platform,
    expected_profile_url,expected_account_name,status
  )
  values
    (new.owner_id,new.id,profile_uuid,'facebook',nullif(new.facebook,''),new.name,'NOT_CONFIGURED'),
    (new.owner_id,new.id,profile_uuid,'instagram',nullif(new.instagram,''),new.name,'NOT_CONFIGURED'),
    (new.owner_id,new.id,profile_uuid,'tiktok',nullif(new.tiktok,''),new.name,'NOT_CONFIGURED'),
    (new.owner_id,new.id,profile_uuid,'youtube',nullif(new.youtube,''),new.name,'NOT_CONFIGURED'),
    (new.owner_id,new.id,profile_uuid,'linkedin-page',nullif(new.linkedin,''),new.name,'NOT_CONFIGURED')
  on conflict(owner_id,client_id,platform) do update
    set browser_profile_id=excluded.browser_profile_id,
        expected_profile_url=coalesce(
          excluded.expected_profile_url,
          public.f1_client_browser_social_sessions.expected_profile_url
        ),
        expected_account_name=excluded.expected_account_name,
        updated_at=now();

  return new;
end
$$;

revoke all on function public.f1_seed_cloud_browser_for_client() from public,anon,authenticated;
grant execute on function public.f1_seed_cloud_browser_for_client() to service_role;


-- Backfill browser account identity from the social channel registry when available.
update public.f1_client_browser_social_sessions bs
set
  expected_profile_url = s.profile_url,
  expected_account_id = coalesce(bs.expected_account_id,s.external_channel_id),
  expected_account_name = coalesce(nullif(bs.expected_account_name,''),s.account_name),
  updated_at = now()
from public.f1_client_social_channels s
where s.client_id=bs.client_id
  and s.owner_id=bs.owner_id
  and s.platform=bs.platform
  and s.profile_url is not null
  and (bs.expected_profile_url is null or bs.expected_profile_url='');
