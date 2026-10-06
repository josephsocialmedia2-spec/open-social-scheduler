-- F1 Social Supabase recovery guardrails.
-- Free-plan Storage thresholds: 70/80/90/95. No paid-plan activation.
insert into public.f1_system_settings(setting_key,setting_value,updated_at)
values(
  'storage_quota_policy',
  jsonb_build_object(
    'plan','free',
    'hard_limit_bytes',1000000000,
    'info_percent',70,
    'warning_percent',80,
    'archive_percent',90,
    'block_percent',95
  ),
  now()
)
on conflict(setting_key) do update
set setting_value=excluded.setting_value,updated_at=excluded.updated_at;

create or replace function public.f1_check_free_quota(
  p_service_key text,
  p_incoming_value numeric default 0
)
returns jsonb
language plpgsql
security definer
set search_path to 'public','storage','pg_catalog'
as $function$
declare
  v_owner uuid := auth.uid();
  v_used numeric;
  v_cfg jsonb := '{}'::jsonb;
  v_plan text := 'free';
  v_limit numeric := 1000000000;
  v_info numeric := 70;
  v_warning numeric := 80;
  v_archive numeric := 90;
  v_block numeric := 95;
  v_projected numeric;
  v_usage_percent numeric;
  v_projected_percent numeric;
  v_allowed boolean;
  v_level text;
begin
  if v_owner is null then
    raise exception 'authentication_required';
  end if;

  if p_service_key not in ('supabase_storage_project','supabase_storage_media') then
    raise exception 'unsupported_quota_service';
  end if;

  select setting_value into v_cfg
  from public.f1_system_settings
  where setting_key='storage_quota_policy';

  v_cfg := coalesce(v_cfg,'{}'::jsonb);
  v_plan := coalesce(nullif(v_cfg->>'plan',''),'free');
  v_limit := coalesce(nullif(v_cfg->>'hard_limit_bytes','')::numeric,1000000000);
  v_info := coalesce(nullif(v_cfg->>'info_percent','')::numeric,70);
  v_warning := coalesce(nullif(v_cfg->>'warning_percent','')::numeric,80);
  v_archive := coalesce(nullif(v_cfg->>'archive_percent','')::numeric,90);
  v_block := coalesce(nullif(v_cfg->>'block_percent','')::numeric,95);

  select coalesce(sum(coalesce((metadata->>'size')::numeric,0)),0)
    into v_used
    from storage.objects;

  v_projected := greatest(0,v_used + greatest(coalesce(p_incoming_value,0),0));
  v_usage_percent := case when v_limit>0 then round((v_used/v_limit)*100,2) else 100 end;
  v_projected_percent := case when v_limit>0 then round((v_projected/v_limit)*100,2) else 100 end;
  v_allowed := v_limit>0 and v_projected_percent < v_block;

  v_level := case
    when v_limit<=0 or v_projected_percent>=v_block then 'BLOCCO'
    when v_projected_percent>=v_archive then 'ARCHIVIAZIONE_PRIORITARIA'
    when v_projected_percent>=v_warning then 'ATTENZIONE'
    when v_projected_percent>=v_info then 'INFORMAZIONE'
    else 'OK'
  end;

  insert into public.f1_free_quota_usage(
    owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details,checked_at,updated_at
  )
  values(
    v_owner,'supabase_storage_project',v_plan,v_used,v_limit,'bytes',not v_allowed,
    jsonb_build_object(
      'source','storage.objects',
      'thresholds',jsonb_build_object(
        'info_percent',v_info,'warning_percent',v_warning,
        'archive_percent',v_archive,'block_percent',v_block
      ),
      'scope','project',
      'policy_key','storage_quota_policy'
    ),
    now(),now()
  )
  on conflict(owner_id,service_key) do update
  set used_value=excluded.used_value,
      hard_limit=excluded.hard_limit,
      plan_name=excluded.plan_name,
      unit=excluded.unit,
      blocked=excluded.blocked,
      details=excluded.details,
      checked_at=excluded.checked_at,
      updated_at=excluded.updated_at;

  return jsonb_build_object(
    'allowed',v_allowed,
    'blocked',not v_allowed,
    'reason',case when v_allowed then 'OK' else 'STORAGE_QUOTA_GUARD' end,
    'service_key','supabase_storage_project',
    'plan',v_plan,
    'used_value',v_used,
    'incoming_value',greatest(coalesce(p_incoming_value,0),0),
    'projected_value',v_projected,
    'hard_limit',v_limit,
    'usage_percent',v_usage_percent,
    'projected_percent',v_projected_percent,
    'available_percent',case when v_limit>0 then greatest(0,round(100-v_usage_percent,2)) else 0 end,
    'level',v_level,
    'status',v_level,
    'thresholds',jsonb_build_object(
      'info_percent',v_info,'warning_percent',v_warning,
      'archive_percent',v_archive,'block_percent',v_block
    ),
    'unit','bytes'
  );
end;
$function$;
