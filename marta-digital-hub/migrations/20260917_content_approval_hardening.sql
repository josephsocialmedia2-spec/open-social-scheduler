-- Marta Ruffino Digital Hub - content/caption approval hardening
-- Isolated to marta_* objects. Does not touch F1/CRM.

alter table public.marta_social_variants
  drop constraint if exists marta_variants_text_limits_check,
  drop constraint if exists marta_variants_hashtags_shape_check,
  drop constraint if exists marta_variants_approval_integrity_check;

alter table public.marta_social_variants
  add constraint marta_variants_text_limits_check check (
    char_length(coalesce(hook,'')) <= 500
    and char_length(coalesce(cta,'')) <= 1000
    and char_length(case
      when platform='youtube' then coalesce(variants->>'description','')
      else coalesce(variants->>'medium',variants->>'short','')
    end) <= 12000
  ),
  add constraint marta_variants_hashtags_shape_check check (
    jsonb_typeof(hashtags)='array' and jsonb_array_length(hashtags) <= 50
  ),
  add constraint marta_variants_approval_integrity_check check (
    (
      status='APPROVATO'
      and approved_at is not null
      and char_length(btrim(case
        when platform='youtube' then coalesce(variants->>'description','')
        else coalesce(variants->>'medium',variants->>'short','')
      end)) between 1 and 12000
    )
    or (
      status<>'APPROVATO' and approved_at is null
    )
  );

alter table public.marta_transcripts
  drop constraint if exists marta_transcripts_text_check,
  drop constraint if exists marta_transcripts_language_check,
  drop constraint if exists marta_transcripts_source_model_check;

alter table public.marta_transcripts
  add constraint marta_transcripts_text_check check (
    char_length(btrim(original_text)) between 1 and 100000
    and char_length(btrim(corrected_text)) between 1 and 100000
  ),
  add constraint marta_transcripts_language_check check (
    char_length(btrim(language)) between 2 and 12
  ),
  add constraint marta_transcripts_source_model_check check (
    source_model is null or char_length(source_model) <= 100
  );

create or replace function public.marta_approve_content(p_content_id uuid)
returns void
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  uid uuid := auth.uid();
  v_total int;
  v_approved int;
  v_ignored int;
  v_invalid int;
begin
  if uid is null or not marta_private.is_allowed(uid) then
    raise exception 'Accesso non autorizzato';
  end if;

  if not exists (
    select 1 from public.marta_contents
    where id=p_content_id
      and owner_id=uid
      and storage_path is not null
      and status not in ('IN_ELABORAZIONE','ERRORE')
  ) then
    raise exception 'Il video deve essere caricato correttamente prima dell''approvazione';
  end if;

  select
    count(*),
    count(*) filter (where status='APPROVATO' and approved_at is not null),
    count(*) filter (where status='NON_PUBBLICARE'),
    count(*) filter (
      where status not in ('APPROVATO','NON_PUBBLICARE')
         or (status='APPROVATO' and (
              approved_at is null
              or char_length(btrim(case
                when platform='youtube' then coalesce(variants->>'description','')
                else coalesce(variants->>'medium',variants->>'short','')
              end))=0
            ))
    )
  into v_total,v_approved,v_ignored,v_invalid
  from public.marta_social_variants
  where content_id=p_content_id and owner_id=uid;

  if v_total <> 5 then
    raise exception 'Completa le 5 piattaforme: approva la caption oppure scegli Non pubblicare';
  end if;
  if v_invalid > 0 or v_approved + v_ignored <> 5 then
    raise exception 'Approva tutte le caption da pubblicare o segnale come Non pubblicare';
  end if;
  if v_approved = 0 then
    raise exception 'Approva almeno una caption da pubblicare';
  end if;

  update public.marta_contents
  set status='APPROVATO'
  where id=p_content_id and owner_id=uid;
end $$;

revoke all on function public.marta_approve_content(uuid) from public, anon;
grant execute on function public.marta_approve_content(uuid) to authenticated;

create or replace function public.marta_schedule_content(
  p_content_id uuid,
  p_when timestamp with time zone
) returns setof public.marta_schedules
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare uid uuid := auth.uid();
begin
  if uid is null or not marta_private.is_allowed(uid) then
    raise exception 'Accesso non autorizzato';
  end if;
  if p_when is null or p_when <= now() then
    raise exception 'Scegli una data futura';
  end if;
  if not exists(
    select 1 from public.marta_contents
    where id=p_content_id and owner_id=uid and status='APPROVATO'
  ) then
    raise exception 'Il contenuto deve essere APPROVATO';
  end if;

  insert into public.marta_schedules(owner_id,content_id,platform,scheduled_for)
    select uid,p_content_id,v.platform,p_when
    from public.marta_social_variants v
    where v.content_id=p_content_id
      and v.owner_id=uid
      and v.status='APPROVATO'
      and v.approved_at is not null
      and not exists(
        select 1 from public.marta_schedules s
        where s.content_id=p_content_id
          and s.owner_id=uid
          and s.platform=v.platform
          and s.status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO')
      );

  if not found then
    raise exception 'Nessuna caption approvata disponibile per la programmazione';
  end if;

  update public.marta_contents
  set status='PROGRAMMATO'
  where id=p_content_id and owner_id=uid;

  return query
    select * from public.marta_schedules
    where content_id=p_content_id and owner_id=uid and status='PROGRAMMATO'
    order by platform;
end $$;

revoke all on function public.marta_schedule_content(uuid,timestamp with time zone) from public, anon;
grant execute on function public.marta_schedule_content(uuid,timestamp with time zone) to authenticated;
