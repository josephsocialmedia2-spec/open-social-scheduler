-- Marta Digital Hub - verified Buffer routing for Facebook/Instagram
-- Applied in production on 2026-10-05.
-- Connected Buffer channels are automatic; every other approved social uses level-4 manual fallback.

create or replace function public.marta_schedule_content(
  p_content_id uuid,
  p_when timestamp with time zone
) returns setof public.marta_schedules
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare uid uuid := auth.uid(); inserted_count int;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  if p_when is null or p_when <= now() then raise exception 'Scegli una data futura'; end if;
  if not exists(select 1 from public.marta_contents where id=p_content_id and owner_id=uid and status='APPROVATO') then
    raise exception 'Il contenuto deve essere APPROVATO';
  end if;
  perform pg_advisory_xact_lock(hashtext('marta_schedule:'||uid::text||':'||p_content_id::text));
  insert into public.marta_schedules(owner_id,content_id,platform,scheduled_for,status,fallback_level)
  select uid,p_content_id,v.platform,p_when,
    case when v.platform in ('facebook','instagram') and exists(
      select 1 from public.marta_integrations i
      where i.owner_id=uid and i.platform=v.platform and i.enabled=true and i.status='CONNESSO' and i.provider='buffer'
    ) then 'PROGRAMMATO' else 'MANUALE_ASSISTITO' end,
    case when v.platform in ('facebook','instagram') and exists(
      select 1 from public.marta_integrations i
      where i.owner_id=uid and i.platform=v.platform and i.enabled=true and i.status='CONNESSO' and i.provider='buffer'
    ) then 1 else 4 end
  from public.marta_social_variants v
  where v.content_id=p_content_id and v.owner_id=uid and v.status='APPROVATO' and v.approved_at is not null
    and not exists(
      select 1 from public.marta_schedules s
      where s.content_id=p_content_id and s.owner_id=uid and s.platform=v.platform
        and s.status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO','PUBBLICATO')
    )
  on conflict do nothing;
  get diagnostics inserted_count=row_count;
  if inserted_count=0 then raise exception 'Nessuna caption approvata disponibile o contenuto già programmato'; end if;
  update public.marta_contents set status='PROGRAMMATO',updated_at=now() where id=p_content_id and owner_id=uid;
  return query select * from public.marta_schedules
    where content_id=p_content_id and owner_id=uid and scheduled_for=p_when
      and status in ('PROGRAMMATO','MANUALE_ASSISTITO') order by platform;
end $$;

revoke all on function public.marta_schedule_content(uuid,timestamp with time zone) from public, anon;
grant execute on function public.marta_schedule_content(uuid,timestamp with time zone) to authenticated;

create or replace function public.marta_publish_now(p_content_id uuid)
returns setof public.marta_schedules
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare uid uuid := auth.uid(); publish_at timestamptz := now(); inserted_count int;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  if not exists(select 1 from public.marta_contents where id=p_content_id and owner_id=uid and status='APPROVATO') then
    raise exception 'Il contenuto deve essere APPROVATO';
  end if;
  perform pg_advisory_xact_lock(hashtext('marta_publish_now:'||uid::text||':'||p_content_id::text));
  insert into public.marta_schedules(owner_id,content_id,platform,scheduled_for,status,fallback_level)
  select uid,p_content_id,v.platform,publish_at,
    case when v.platform in ('facebook','instagram') and exists(
      select 1 from public.marta_integrations i
      where i.owner_id=uid and i.platform=v.platform and i.enabled=true and i.status='CONNESSO' and i.provider='buffer'
    ) then 'PROGRAMMATO' else 'MANUALE_ASSISTITO' end,
    case when v.platform in ('facebook','instagram') and exists(
      select 1 from public.marta_integrations i
      where i.owner_id=uid and i.platform=v.platform and i.enabled=true and i.status='CONNESSO' and i.provider='buffer'
    ) then 1 else 4 end
  from public.marta_social_variants v
  where v.content_id=p_content_id and v.owner_id=uid and v.status='APPROVATO' and v.approved_at is not null
    and not exists(
      select 1 from public.marta_schedules s
      where s.content_id=p_content_id and s.owner_id=uid and s.platform=v.platform
        and s.status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO','PUBBLICATO')
    )
  on conflict do nothing;
  get diagnostics inserted_count=row_count;
  if inserted_count=0 then raise exception 'Nessuna caption approvata disponibile o contenuto già programmato'; end if;
  update public.marta_contents set status='PROGRAMMATO',updated_at=now() where id=p_content_id and owner_id=uid;
  return query select * from public.marta_schedules
    where content_id=p_content_id and owner_id=uid and scheduled_for=publish_at
      and status in ('PROGRAMMATO','MANUALE_ASSISTITO') order by platform;
end $$;

revoke all on function public.marta_publish_now(uuid) from public, anon;
grant execute on function public.marta_publish_now(uuid) to authenticated;

create or replace function public.marta_cancel_schedule(p_schedule_id uuid)
returns void
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare uid uuid := auth.uid(); cid uuid;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  update public.marta_schedules set status='ANNULLATO',updated_at=now()
    where id=p_schedule_id and owner_id=uid and status in ('PROGRAMMATO','MANUALE_ASSISTITO','ERRORE')
    returning content_id into cid;
  if cid is null then raise exception 'Programmazione non annullabile'; end if;
  if not exists(
    select 1 from public.marta_schedules
    where owner_id=uid and content_id=cid and status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO')
  ) then
    update public.marta_contents set status='APPROVATO',updated_at=now()
      where id=cid and owner_id=uid and status='PROGRAMMATO';
  end if;
end $$;

revoke all on function public.marta_cancel_schedule(uuid) from public, anon;
grant execute on function public.marta_cancel_schedule(uuid) to authenticated;
