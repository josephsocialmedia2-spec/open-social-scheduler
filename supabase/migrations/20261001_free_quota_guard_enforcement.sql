-- Enforce the free-tier guard for F1 Content Hub media storage.
-- Conservative project policy: stop new media uploads at 95% of the configured free storage limit.

create or replace function public.f1_refresh_media_quota()
returns trigger
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_owner uuid;
  v_used numeric;
  v_limit numeric := 1073741824;
begin
  if tg_op = 'DELETE' then
    v_owner := old.owner_id;
  else
    v_owner := new.owner_id;
  end if;

  select coalesce(sum(greatest(coalesce(file_size,0),0)),0)
    into v_used
    from public.f1_content_media
   where owner_id = v_owner;

  insert into public.f1_free_quota_usage(
    owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details,checked_at,updated_at
  )
  values(
    v_owner,'supabase_storage_media','free',v_used,v_limit,'bytes',
    ((v_used / v_limit) * 100) >= 95,
    jsonb_build_object('source','f1_content_media_trigger','threshold_percent',95),
    now(),now()
  )
  on conflict(owner_id,service_key) do update
  set used_value=excluded.used_value,
      hard_limit=excluded.hard_limit,
      unit=excluded.unit,
      blocked=excluded.blocked,
      details=excluded.details,
      checked_at=excluded.checked_at,
      updated_at=excluded.updated_at;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

revoke all on function public.f1_refresh_media_quota() from public, anon, authenticated;

drop trigger if exists f1_content_media_quota_refresh on public.f1_content_media;
create trigger f1_content_media_quota_refresh
after insert or delete or update of file_size
on public.f1_content_media
for each row execute function public.f1_refresh_media_quota();

-- Backfill current tracked media bytes for every owner.
insert into public.f1_free_quota_usage(
  owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details,checked_at,updated_at
)
select owner_id,
       'supabase_storage_media',
       'free',
       coalesce(sum(greatest(coalesce(file_size,0),0)),0),
       1073741824,
       'bytes',
       ((coalesce(sum(greatest(coalesce(file_size,0),0)),0)::numeric / 1073741824) * 100) >= 95,
       jsonb_build_object('source','backfill_f1_content_media','threshold_percent',95),
       now(),now()
from public.f1_content_media
group by owner_id
on conflict(owner_id,service_key) do update
set used_value=excluded.used_value,
    hard_limit=excluded.hard_limit,
    unit=excluded.unit,
    blocked=excluded.blocked,
    details=excluded.details,
    checked_at=excluded.checked_at,
    updated_at=excluded.updated_at;

create or replace function public.f1_check_free_quota(
  p_service_key text,
  p_incoming_value numeric default 0
)
returns jsonb
language plpgsql
security invoker
set search_path = public, pg_catalog
as $$
declare
  v_owner uuid := auth.uid();
  v_row public.f1_free_quota_usage%rowtype;
  v_projected numeric;
  v_percent numeric;
begin
  if v_owner is null then
    raise exception 'authentication_required';
  end if;

  if p_service_key <> 'supabase_storage_media' then
    raise exception 'unsupported_quota_service';
  end if;

  select *
    into v_row
    from public.f1_free_quota_usage
   where owner_id=v_owner
     and service_key=p_service_key;

  if not found then
    return jsonb_build_object(
      'allowed',false,
      'blocked',true,
      'reason','QUOTA_STATUS_UNAVAILABLE',
      'service_key',p_service_key
    );
  end if;

  v_projected := greatest(0,v_row.used_value+greatest(coalesce(p_incoming_value,0),0));
  v_percent := case
    when v_row.hard_limit is null or v_row.hard_limit<=0 then 100
    else round((v_projected/v_row.hard_limit)*100,2)
  end;

  return jsonb_build_object(
    'allowed',(not v_row.blocked and v_percent < 95),
    'blocked',(v_row.blocked or v_percent >= 95),
    'reason',case when (v_row.blocked or v_percent>=95) then 'FREE_QUOTA_GUARD_95' else 'OK' end,
    'service_key',p_service_key,
    'used_value',v_row.used_value,
    'incoming_value',greatest(coalesce(p_incoming_value,0),0),
    'projected_value',v_projected,
    'hard_limit',v_row.hard_limit,
    'usage_percent',v_row.usage_percent,
    'projected_percent',v_percent,
    'unit',v_row.unit
  );
end;
$$;

revoke all on function public.f1_check_free_quota(text,numeric) from public, anon;
grant execute on function public.f1_check_free_quota(text,numeric) to authenticated;

comment on function public.f1_check_free_quota(text,numeric) is
  'Fail-closed free-tier guard. New media uploads are denied at projected 95% of configured free media storage quota.';
