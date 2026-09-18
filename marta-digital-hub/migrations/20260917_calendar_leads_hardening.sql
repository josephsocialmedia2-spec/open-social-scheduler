-- Marta Ruffino Digital Hub - calendar/autopilot/leads hardening
-- Isolated to marta_* objects. Does not touch F1/CRM.

create unique index if not exists marta_schedules_content_platform_once_idx
on public.marta_schedules(owner_id,content_id,platform)
where status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO','PUBBLICATO');

alter table public.marta_autopilot_settings
  drop constraint if exists marta_autopilot_timezone_check;
alter table public.marta_autopilot_settings
  add constraint marta_autopilot_timezone_check check (timezone='Europe/Rome');

alter table public.marta_leads
  drop constraint if exists marta_leads_text_limits_check,
  drop constraint if exists marta_leads_platform_check,
  drop constraint if exists marta_leads_status_check,
  drop constraint if exists marta_leads_value_check;

alter table public.marta_leads
  add constraint marta_leads_text_limits_check check (
    char_length(coalesce(name,'')) <= 200
    and char_length(coalesce(contact,'')) <= 500
    and char_length(coalesce(source,'')) <= 200
    and char_length(coalesce(campaign,'')) <= 200
    and char_length(coalesce(request,'')) <= 4000
    and char_length(coalesce(notes,'')) <= 4000
  ),
  add constraint marta_leads_platform_check check (
    platform is null or platform in ('instagram','facebook','tiktok','youtube','linkedin','sito')
  ),
  add constraint marta_leads_status_check check (
    status in ('NUOVO','CONTATTATO','APPUNTAMENTO','CLIENTE','PERSO')
  ),
  add constraint marta_leads_value_check check (
    (value is null or value >= 0) and (margin_value is null or margin_value >= 0)
  );

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
  if not exists(select 1 from public.marta_contents where id=p_content_id and owner_id=uid and status='APPROVATO') then raise exception 'Il contenuto deve essere APPROVATO'; end if;

  perform pg_advisory_xact_lock(hashtext('marta_schedule:'||uid::text||':'||p_content_id::text));

  insert into public.marta_schedules(owner_id,content_id,platform,scheduled_for)
    select uid,p_content_id,v.platform,p_when
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

  update public.marta_contents set status='PROGRAMMATO' where id=p_content_id and owner_id=uid;
  return query select * from public.marta_schedules where content_id=p_content_id and owner_id=uid and status='PROGRAMMATO' order by platform;
end $$;

revoke all on function public.marta_schedule_content(uuid,timestamp with time zone) from public, anon;
grant execute on function public.marta_schedule_content(uuid,timestamp with time zone) to authenticated;

create or replace function public.marta_reschedule_item(p_schedule_id uuid,p_when timestamp with time zone)
returns public.marta_schedules
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare uid uuid := auth.uid(); outrow public.marta_schedules;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  if p_when is null or p_when <= now() then raise exception 'Scegli una data futura'; end if;
  update public.marta_schedules
    set scheduled_for=p_when,updated_at=now()
    where id=p_schedule_id and owner_id=uid and status='PROGRAMMATO'
    returning * into outrow;
  if outrow.id is null then raise exception 'Programmazione non modificabile'; end if;
  return outrow;
end $$;

revoke all on function public.marta_reschedule_item(uuid,timestamp with time zone) from public, anon;
grant execute on function public.marta_reschedule_item(uuid,timestamp with time zone) to authenticated;

create or replace function public.marta_cancel_schedule(p_schedule_id uuid)
returns void
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare uid uuid := auth.uid(); cid uuid;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  update public.marta_schedules
    set status='ANNULLATO',updated_at=now()
    where id=p_schedule_id and owner_id=uid and status in ('PROGRAMMATO','ERRORE')
    returning content_id into cid;
  if cid is null then raise exception 'Programmazione non annullabile'; end if;
  if not exists(
    select 1 from public.marta_schedules
    where owner_id=uid and content_id=cid and status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO')
  ) then
    update public.marta_contents set status='APPROVATO' where id=cid and owner_id=uid and status='PROGRAMMATO';
  end if;
end $$;

revoke all on function public.marta_cancel_schedule(uuid) from public, anon;
grant execute on function public.marta_cancel_schedule(uuid) to authenticated;

create or replace function public.marta_run_autopilot()
returns table(content_id uuid,scheduled_for timestamp with time zone,platform_count integer)
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  uid uuid := auth.uid(); s public.marta_autopilot_settings; d int; i int; local_date date; candidate timestamptz; picked uuid; n int;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  perform pg_advisory_xact_lock(hashtext('marta_autopilot:'||uid::text));
  select * into s from public.marta_autopilot_settings where owner_id=uid;
  if not found or not s.enabled then return; end if;
  if s.timezone <> 'Europe/Rome' then raise exception 'Timezone Autopilot non valida'; end if;

  for d in 0..(s.horizon_days-1) loop
    local_date := (now() at time zone s.timezone)::date + d;
    if not (extract(isodow from local_date)::smallint = any(s.weekdays)) then continue; end if;
    for i in 1..least(s.posts_per_day,cardinality(s.slots)) loop
      candidate := (local_date + s.slots[i]) at time zone s.timezone;
      if candidate <= now() + interval '10 minutes' then continue; end if;
      if exists(select 1 from public.marta_schedules where owner_id=uid and scheduled_for=candidate and status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO','PUBBLICATO')) then continue; end if;
      select c.id into picked from public.marta_contents c
      where c.owner_id=uid and c.status='APPROVATO'
        and not exists(select 1 from public.marta_schedules x where x.content_id=c.id and x.owner_id=uid and x.status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO','PUBBLICATO'))
        and exists(select 1 from public.marta_social_variants v where v.content_id=c.id and v.owner_id=uid and v.status='APPROVATO' and v.approved_at is not null and v.platform=any(s.platforms))
      order by c.created_at,c.id limit 1;
      if picked is null then return; end if;
      insert into public.marta_schedules(owner_id,content_id,platform,scheduled_for)
      select uid,picked,v.platform,candidate from public.marta_social_variants v
      where v.content_id=picked and v.owner_id=uid and v.status='APPROVATO' and v.approved_at is not null and v.platform=any(s.platforms)
      on conflict do nothing;
      get diagnostics n=row_count;
      if n>0 then
        update public.marta_contents set status='PROGRAMMATO' where id=picked and owner_id=uid;
        content_id:=picked;scheduled_for:=candidate;platform_count:=n;return next;
      end if;
      picked:=null;
    end loop;
  end loop;
end $$;

revoke all on function public.marta_run_autopilot() from public, anon;
grant execute on function public.marta_run_autopilot() to authenticated;
