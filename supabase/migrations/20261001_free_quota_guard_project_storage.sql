-- Strict zero-cost guard: use actual project-wide Supabase Storage usage.
-- Free reference ceiling configured conservatively as 1,000,000,000 bytes (1 GB).

create or replace function public.f1_refresh_media_quota()
returns trigger
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_owner uuid;
  v_used numeric;
  v_limit numeric := 1000000000;
begin
  if tg_op = 'DELETE' then
    v_owner := old.owner_id;
  else
    v_owner := new.owner_id;
  end if;

  select coalesce(sum(coalesce((metadata->>'size')::numeric,0)),0)
    into v_used
    from storage.objects;

  insert into public.f1_free_quota_usage(
    owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details,checked_at,updated_at
  )
  values(
    v_owner,'supabase_storage_project','free',v_used,v_limit,'bytes',
    ((v_used / v_limit) * 100) >= 95,
    jsonb_build_object('source','storage.objects','threshold_percent',95,'scope','project'),
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

create or replace function public.f1_seed_media_quota_for_owner()
returns trigger
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_used numeric;
  v_limit numeric := 1000000000;
begin
  select coalesce(sum(coalesce((metadata->>'size')::numeric,0)),0)
    into v_used
    from storage.objects;

  insert into public.f1_free_quota_usage(
    owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details,checked_at,updated_at
  )
  values(
    new.owner_id,'supabase_storage_project','free',v_used,v_limit,'bytes',
    ((v_used / v_limit) * 100) >= 95,
    jsonb_build_object('source','storage.objects','threshold_percent',95,'scope','project'),
    now(),now()
  )
  on conflict(owner_id,service_key) do nothing;
  return new;
end;
$$;

revoke all on function public.f1_seed_media_quota_for_owner() from public, anon, authenticated;

-- Seed/update actual project-wide storage status for every existing owner.
insert into public.f1_free_quota_usage(
  owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details,checked_at,updated_at
)
select distinct c.owner_id,
       'supabase_storage_project',
       'free',
       s.used_value,
       1000000000,
       'bytes',
       ((s.used_value / 1000000000) * 100) >= 95,
       jsonb_build_object('source','storage.objects','threshold_percent',95,'scope','project'),
       now(),now()
from public.f1_content_clients c
cross join (
  select coalesce(sum(coalesce((metadata->>'size')::numeric,0)),0) as used_value
  from storage.objects
) s
where c.owner_id is not null
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
security definer
set search_path = public, pg_catalog
as $$
declare
  v_owner uuid := auth.uid();
  v_used numeric;
  v_limit numeric := 1000000000;
  v_projected numeric;
  v_percent numeric;
  v_allowed boolean;
begin
  if v_owner is null then
    raise exception 'authentication_required';
  end if;

  if p_service_key not in ('supabase_storage_project','supabase_storage_media') then
    raise exception 'unsupported_quota_service';
  end if;

  select coalesce(sum(coalesce((metadata->>'size')::numeric,0)),0)
    into v_used
    from storage.objects;

  v_projected := greatest(0,v_used + greatest(coalesce(p_incoming_value,0),0));
  v_percent := round((v_projected / v_limit) * 100,2);
  v_allowed := v_percent < 95;

  insert into public.f1_free_quota_usage(
    owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details,checked_at,updated_at
  )
  values(
    v_owner,'supabase_storage_project','free',v_used,v_limit,'bytes',not v_allowed,
    jsonb_build_object('source','storage.objects','threshold_percent',95,'scope','project'),
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

  return jsonb_build_object(
    'allowed',v_allowed,
    'blocked',not v_allowed,
    'reason',case when v_allowed then 'OK' else 'FREE_QUOTA_GUARD_95' end,
    'service_key','supabase_storage_project',
    'used_value',v_used,
    'incoming_value',greatest(coalesce(p_incoming_value,0),0),
    'projected_value',v_projected,
    'hard_limit',v_limit,
    'usage_percent',round((v_used/v_limit)*100,2),
    'projected_percent',v_percent,
    'available_percent',greatest(0,round(100-((v_used/v_limit)*100),2)),
    'status',case
      when ((v_used/v_limit)*100)>=95 then 'BLOCCO'
      when ((v_used/v_limit)*100)>=85 then 'AVVISO'
      when ((v_used/v_limit)*100)>=70 then 'INFORMAZIONE'
      else 'OK'
    end,
    'unit','bytes'
  );
end;
$$;

revoke all on function public.f1_check_free_quota(text,numeric) from public, anon;
grant execute on function public.f1_check_free_quota(text,numeric) to authenticated;

comment on function public.f1_check_free_quota(text,numeric) is
  'Fail-closed zero-cost guard based on actual project-wide storage.objects usage. Blocks projected usage at 95% of 1 GB.';
