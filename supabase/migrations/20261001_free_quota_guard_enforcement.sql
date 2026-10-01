-- Enforce the free-tier guard for F1 Content Hub media storage.
-- Conservative project policy: stop new media uploads at 95% of the configured free storage limit.

create or replace function public.f1_quota_media_delta()
returns trigger
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_owner uuid;
  v_delta numeric := 0;
  v_limit numeric := 1073741824; -- 1 GiB configured free storage ceiling
  v_used numeric;
begin
  if tg_op = 'INSERT' then
    v_owner := new.owner_id;
    v_delta := greatest(coalesce(new.file_size,0),0);
  elsif tg_op = 'DELETE' then
    v_owner := old.owner_id;
    v_delta := -greatest(coalesce(old.file_size,0),0);
  else
    if new.owner_id = old.owner_id then
      v_owner := new.owner_id;
      v_delta := greatest(coalesce(new.file_size,0),0) - greatest(coalesce(old.file_size,0),0);
    else
      insert into public.f1_free_quota_usage(owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details)
      values(old.owner_id,'supabase_storage_media','free',0,v_limit,'bytes',false,'{"source":"f1_content_media_trigger"}'::jsonb)
      on conflict(owner_id,service_key) do nothing;
      update public.f1_free_quota_usage
         set used_value=greatest(0,used_value-greatest(coalesce(old.file_size,0),0)),
             blocked=((greatest(0,used_value-greatest(coalesce(old.file_size,0),0))/nullif(hard_limit,0))*100)>=95),
             checked_at=now(),updated_at=now()
       where owner_id=old.owner_id and service_key='supabase_storage_media';
      v_owner := new.owner_id;
      v_delta := greatest(coalesce(new.file_size,0),0);
    end if;
  end if;

  insert into public.f1_free_quota_usage(owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details)
  values(v_owner,'supabase_storage_media','free',0,v_limit,'bytes',false,'{"source":"f1_content_media_trigger"}'::jsonb)
  on conflict(owner_id,service_key) do nothing;

  update public.f1_free_quota_usage
     set used_value=greatest(0,used_value+v_delta),
         blocked=((greatest(0,used_value+v_delta)/nullif(hard_limit,0))*100)>=95),
         checked_at=now(),updated_at=now(),
         details=coalesce(details,'{}'::jsonb)||jsonb_build_object('source','f1_content_media_trigger','threshold_percent',95)
   where owner_id=v_owner and service_key='supabase_storage_media'
   returning used_value into v_used;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

revoke all on function public.f1_quota_media_delta() from public, anon, authenticated;

drop trigger if exists f1_content_media_quota_delta on public.f1_content_media;
create trigger f1_content_media_quota_delta
after insert or delete or update of file_size,owner_id
on public.f1_content_media
for each row execute function public.f1_quota_media_delta();

-- Backfill current tracked media bytes for every owner.
insert into public.f1_free_quota_usage(owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details)
select owner_id,
       'supabase_storage_media',
       'free',
       coalesce(sum(greatest(coalesce(file_size,0),0)),0),
       1073741824,
       'bytes',
       (coalesce(sum(greatest(coalesce(file_size,0),0)),0)::numeric/1073741824*100)>=95,
       jsonb_build_object('source','backfill_f1_content_media','threshold_percent',95)
from public.f1_content_media
group by owner_id
on conflict(owner_id,service_key) do update
set used_value=excluded.used_value,
    hard_limit=excluded.hard_limit,
    unit=excluded.unit,
    blocked=excluded.blocked,
    details=excluded.details,
    checked_at=now(),
    updated_at=now();

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

  select * into v_row
  from public.f1_free_quota_usage
  where owner_id=v_owner and service_key=p_service_key;

  if not found then
    return jsonb_build_object(
      'allowed',false,'blocked',true,'reason','QUOTA_STATUS_UNAVAILABLE',
      'service_key',p_service_key
    );
  end if;

  v_projected := greatest(0,v_row.used_value+greatest(coalesce(p_incoming_value,0),0));
  v_percent := case when v_row.hard_limit is null or v_row.hard_limit<=0 then 100
                    else round((v_projected/v_row.hard_limit)*100,2) end;

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
