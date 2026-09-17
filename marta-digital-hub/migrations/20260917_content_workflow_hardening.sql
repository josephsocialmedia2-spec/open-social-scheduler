-- Marta Ruffino Digital Hub - content workflow hardening
-- Keeps approval, scheduling and ownership rules enforceable at database level.

-- Child rows must belong to the same owner as their content.
alter table public.marta_transcripts drop constraint if exists marta_transcripts_content_owner_fkey;
alter table public.marta_transcripts add constraint marta_transcripts_content_owner_fkey foreign key(content_id,owner_id) references public.marta_contents(id,owner_id) on delete cascade;
alter table public.marta_social_variants drop constraint if exists marta_social_variants_content_owner_fkey;
alter table public.marta_social_variants add constraint marta_social_variants_content_owner_fkey foreign key(content_id,owner_id) references public.marta_contents(id,owner_id) on delete cascade;
alter table public.marta_schedules drop constraint if exists marta_schedules_content_owner_fkey;
alter table public.marta_schedules add constraint marta_schedules_content_owner_fkey foreign key(content_id,owner_id) references public.marta_contents(id,owner_id) on delete cascade;
alter table public.marta_media_versions drop constraint if exists marta_media_versions_content_owner_fkey;
alter table public.marta_media_versions add constraint marta_media_versions_content_owner_fkey foreign key(content_id,owner_id) references public.marta_contents(id,owner_id) on delete cascade;
alter table public.marta_performance_metrics drop constraint if exists marta_performance_metrics_content_owner_fkey;
alter table public.marta_performance_metrics add constraint marta_performance_metrics_content_owner_fkey foreign key(content_id,owner_id) references public.marta_contents(id,owner_id) on delete cascade;
alter table public.marta_processing_jobs drop constraint if exists marta_processing_jobs_content_owner_fkey;
alter table public.marta_processing_jobs add constraint marta_processing_jobs_content_owner_fkey foreign key(content_id,owner_id) references public.marta_contents(id,owner_id) on delete cascade;
alter table public.marta_tracking_links drop constraint if exists marta_tracking_links_content_owner_fkey;
alter table public.marta_tracking_links add constraint marta_tracking_links_content_owner_fkey foreign key(content_id,owner_id) references public.marta_contents(id,owner_id) on delete cascade;

-- Reasonable payload limits and approval consistency.
alter table public.marta_transcripts drop constraint if exists marta_transcripts_payload_check;
alter table public.marta_transcripts add constraint marta_transcripts_payload_check check (
  char_length(original_text) <= 200000 and
  char_length(corrected_text) <= 200000 and
  char_length(language) between 1 and 16 and
  (source_model is null or char_length(source_model) <= 120)
);

alter table public.marta_social_variants drop constraint if exists marta_variants_text_check;
alter table public.marta_social_variants drop constraint if exists marta_variants_json_check;
alter table public.marta_social_variants drop constraint if exists marta_variants_approval_check;
alter table public.marta_social_variants add constraint marta_variants_text_check check (
  (hook is null or char_length(hook) <= 500) and
  (cta is null or char_length(cta) <= 1000)
);
alter table public.marta_social_variants add constraint marta_variants_json_check check (
  case when jsonb_typeof(hashtags)='array' then jsonb_array_length(hashtags) <= 100 and pg_column_size(hashtags) <= 20000 else false end
  and case when jsonb_typeof(variants)='object' then pg_column_size(variants) <= 200000 else false end
);
alter table public.marta_social_variants add constraint marta_variants_approval_check check (
  (status='APPROVATO' and approved_at is not null and
    case when platform='youtube'
      then char_length(btrim(coalesce(variants->>'description',''))) > 0
      else char_length(btrim(coalesce(variants->>'medium',variants->>'short',''))) > 0
    end)
  or (status<>'APPROVATO' and approved_at is null)
);

alter table public.marta_leads drop constraint if exists marta_leads_payload_check;
alter table public.marta_leads drop constraint if exists marta_leads_platform_check;
alter table public.marta_leads drop constraint if exists marta_leads_status_check;
alter table public.marta_leads add constraint marta_leads_payload_check check (
  (name is null or char_length(name) <= 200) and
  (contact is null or char_length(contact) <= 500) and
  (source is null or char_length(source) <= 200) and
  (campaign is null or char_length(campaign) <= 200) and
  (request is null or char_length(request) <= 8000) and
  (notes is null or char_length(notes) <= 12000)
);
alter table public.marta_leads add constraint marta_leads_platform_check check (platform is null or platform in ('instagram','facebook','tiktok','youtube','linkedin','sito'));
alter table public.marta_leads add constraint marta_leads_status_check check (status in ('NUOVO','CONTATTATO','APPUNTAMENTO','CLIENTE','PERSO'));

alter table public.marta_integrations drop constraint if exists marta_integrations_enabled_identity_check;
alter table public.marta_integrations add constraint marta_integrations_enabled_identity_check check (not enabled or nullif(btrim(external_integration_id),'') is not null);

alter table public.marta_schedules drop constraint if exists marta_schedules_published_confirmation_check;
alter table public.marta_schedules add constraint marta_schedules_published_confirmation_check check (
  status<>'PUBBLICATO' or (confirmed_at is not null and (nullif(btrim(provider_post_id),'') is not null or nullif(btrim(published_url),'') is not null))
);
create unique index if not exists marta_schedules_active_unique on public.marta_schedules(owner_id,content_id,platform)
  where status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO');

-- Nullable content references (lead/log) must still match owner when present.
create or replace function public.marta_assert_optional_content_owner()
returns trigger
language plpgsql
security invoker
set search_path=public,pg_temp
as $$
begin
  if new.content_id is not null and not exists(
    select 1 from public.marta_contents c where c.id=new.content_id and c.owner_id=new.owner_id
  ) then
    raise exception 'Il contenuto non appartiene al proprietario del record';
  end if;
  return new;
end $$;

drop trigger if exists marta_leads_content_owner_guard on public.marta_leads;
create trigger marta_leads_content_owner_guard before insert or update of content_id,owner_id on public.marta_leads
for each row execute function public.marta_assert_optional_content_owner();
drop trigger if exists marta_publish_logs_content_owner_guard on public.marta_publish_logs;
create trigger marta_publish_logs_content_owner_guard before insert or update of content_id,owner_id on public.marta_publish_logs
for each row execute function public.marta_assert_optional_content_owner();

-- Direct table API writes cannot bypass schedule rules.
create or replace function public.marta_schedule_guard()
returns trigger
language plpgsql
security invoker
set search_path=public,pg_temp
as $$
begin
  if not exists(select 1 from public.marta_contents c where c.id=new.content_id and c.owner_id=new.owner_id) then
    raise exception 'Contenuto non valido per questo proprietario';
  end if;
  if new.status='PROGRAMMATO' then
    if new.scheduled_for <= now() + interval '1 minute' then raise exception 'La programmazione deve essere futura'; end if;
    if not exists(select 1 from public.marta_contents c where c.id=new.content_id and c.owner_id=new.owner_id and c.status in ('APPROVATO','PROGRAMMATO')) then
      raise exception 'Il contenuto deve essere APPROVATO';
    end if;
    if not exists(select 1 from public.marta_social_variants v where v.content_id=new.content_id and v.owner_id=new.owner_id and v.platform=new.platform and v.status='APPROVATO' and v.approved_at is not null) then
      raise exception 'La caption della piattaforma deve essere APPROVATA';
    end if;
  end if;
  if new.status='PUBBLICATO' and (new.confirmed_at is null or (nullif(btrim(new.provider_post_id),'') is null and nullif(btrim(new.published_url),'') is null)) then
    raise exception 'PUBBLICATO richiede conferma reale della piattaforma';
  end if;
  return new;
end $$;

drop trigger if exists marta_schedules_guard on public.marta_schedules;
create trigger marta_schedules_guard before insert or update on public.marta_schedules
for each row execute function public.marta_schedule_guard();

-- Content state itself cannot be forged with a direct PATCH.
create or replace function public.marta_content_status_guard()
returns trigger
language plpgsql
security invoker
set search_path=public,storage,pg_temp
as $$
declare
  total_count int;
  approved_count int;
begin
  if new.status is not distinct from old.status then return new; end if;
  if new.status='APPROVATO' then
    if old.status in ('IN_ELABORAZIONE','ERRORE') then raise exception 'Il contenuto non è pronto per l approvazione'; end if;
    if new.storage_path is null or not exists(select 1 from storage.objects o where o.bucket_id='marta-content-originals' and o.name=new.storage_path) then
      raise exception 'Il video originale non è presente nello storage';
    end if;
    select count(*),count(*) filter(where status='APPROVATO' and approved_at is not null)
      into total_count,approved_count
      from public.marta_social_variants
      where content_id=new.id and owner_id=new.owner_id and status<>'NON_PUBBLICARE';
    if total_count=0 or approved_count<>total_count then raise exception 'Approva prima tutte le caption da pubblicare'; end if;
  elsif new.status='PROGRAMMATO' then
    if not exists(select 1 from public.marta_schedules s where s.content_id=new.id and s.owner_id=new.owner_id and s.status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO')) then
      raise exception 'Nessuna programmazione attiva per il contenuto';
    end if;
  elsif new.status='PUBBLICATO' then
    if not exists(select 1 from public.marta_schedules s where s.content_id=new.id and s.owner_id=new.owner_id and s.status='PUBBLICATO') then
      raise exception 'Nessuna pubblicazione confermata dalla piattaforma';
    end if;
  end if;
  return new;
end $$;

drop trigger if exists marta_contents_status_guard on public.marta_contents;
create trigger marta_contents_status_guard before update of status on public.marta_contents
for each row execute function public.marta_content_status_guard();

-- Any caption edit invalidates content approval and cancels pending publication.
create or replace function public.marta_variant_invalidates_content()
returns trigger
language plpgsql
security invoker
set search_path=public,pg_temp
as $$
begin
  update public.marta_schedules set status='ANNULLATO'
    where content_id=new.content_id and owner_id=new.owner_id and status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO','ERRORE');
  update public.marta_contents set status='DA_APPROVARE'
    where id=new.content_id and owner_id=new.owner_id and status not in ('IN_ELABORAZIONE','ERRORE');
  return new;
end $$;

drop trigger if exists marta_variants_invalidate_content on public.marta_social_variants;
create trigger marta_variants_invalidate_content after insert or update of hook,cta,hashtags,variants,status,approved_at on public.marta_social_variants
for each row execute function public.marta_variant_invalidates_content();

-- Transcript changes invalidate generated/approved copy as well.
create or replace function public.marta_transcript_invalidates_copy()
returns trigger
language plpgsql
security invoker
set search_path=public,pg_temp
as $$
begin
  if tg_op='INSERT' or new.original_text is distinct from old.original_text or new.corrected_text is distinct from old.corrected_text then
    update public.marta_social_variants set status='DA_RIVEDERE',approved_at=null
      where content_id=new.content_id and owner_id=new.owner_id and status not in ('NON_PUBBLICARE','DA_RIVEDERE');
    update public.marta_schedules set status='ANNULLATO'
      where content_id=new.content_id and owner_id=new.owner_id and status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO','ERRORE');
    update public.marta_contents set status='DA_APPROVARE'
      where id=new.content_id and owner_id=new.owner_id and status not in ('IN_ELABORAZIONE','ERRORE');
  end if;
  return new;
end $$;

drop trigger if exists marta_transcripts_invalidate_copy on public.marta_transcripts;
create trigger marta_transcripts_invalidate_copy after insert or update of original_text,corrected_text on public.marta_transcripts
for each row execute function public.marta_transcript_invalidates_copy();

-- Friendly RPCs keep the same API, but now enforce future scheduling and real media.
create or replace function public.marta_approve_content(p_content_id uuid)
returns void
language plpgsql
security invoker
set search_path=public,storage,pg_temp
as $$
declare
  uid uuid := auth.uid();
  c public.marta_contents;
  total_count int;
  approved_count int;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  select * into c from public.marta_contents where id=p_content_id and owner_id=uid;
  if not found then raise exception 'Contenuto non trovato'; end if;
  if c.status in ('IN_ELABORAZIONE','ERRORE') then raise exception 'Il contenuto non è pronto per l approvazione'; end if;
  if c.storage_path is null or not exists(select 1 from storage.objects o where o.bucket_id='marta-content-originals' and o.name=c.storage_path) then raise exception 'Il video originale non è presente nello storage'; end if;
  select count(*),count(*) filter(where status='APPROVATO' and approved_at is not null)
    into total_count,approved_count
    from public.marta_social_variants
    where content_id=p_content_id and owner_id=uid and status<>'NON_PUBBLICARE';
  if total_count=0 or approved_count<>total_count then raise exception 'Approva prima tutte le caption da pubblicare'; end if;
  update public.marta_contents set status='APPROVATO' where id=p_content_id and owner_id=uid;
end $$;

create or replace function public.marta_schedule_content(p_content_id uuid,p_when timestamptz)
returns setof public.marta_schedules
language plpgsql
security invoker
set search_path=public,pg_temp
as $$
declare
  uid uuid := auth.uid();
  n int;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  if p_when is null or p_when <= now()+interval '1 minute' then raise exception 'Scegli una data futura'; end if;
  if not exists(select 1 from public.marta_contents where id=p_content_id and owner_id=uid and status='APPROVATO') then raise exception 'Il contenuto deve essere APPROVATO'; end if;
  insert into public.marta_schedules(owner_id,content_id,platform,scheduled_for)
    select uid,p_content_id,v.platform,p_when from public.marta_social_variants v
    where v.content_id=p_content_id and v.owner_id=uid and v.status='APPROVATO' and v.approved_at is not null
      and not exists(select 1 from public.marta_schedules s where s.content_id=p_content_id and s.owner_id=uid and s.platform=v.platform and s.status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO'));
  get diagnostics n=row_count;
  if n=0 then raise exception 'Nessuna caption approvata disponibile da programmare'; end if;
  update public.marta_contents set status='PROGRAMMATO' where id=p_content_id and owner_id=uid;
  return query select * from public.marta_schedules where content_id=p_content_id and owner_id=uid and scheduled_for=p_when and status='PROGRAMMATO' order by platform;
end $$;

create or replace function public.marta_run_autopilot()
returns table(content_id uuid,scheduled_for timestamptz,platform_count integer)
language plpgsql
security invoker
set search_path=public,pg_temp
as $$
declare
  uid uuid := auth.uid();
  s public.marta_autopilot_settings;
  d int; i int; local_date date; candidate timestamptz; picked uuid; n int;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  perform pg_advisory_xact_lock(hashtext('marta_autopilot:'||uid::text));
  select * into s from public.marta_autopilot_settings where owner_id=uid;
  if not found or not s.enabled then return; end if;
  for d in 0..(s.horizon_days-1) loop
    local_date := (now() at time zone s.timezone)::date + d;
    if not (extract(isodow from local_date)::smallint = any(s.weekdays)) then continue; end if;
    for i in 1..least(s.posts_per_day,cardinality(s.slots)) loop
      candidate := (local_date + s.slots[i]) at time zone s.timezone;
      if candidate <= now()+interval '10 minutes' then continue; end if;
      if exists(select 1 from public.marta_schedules where owner_id=uid and scheduled_for=candidate and status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO','PUBBLICATO')) then continue; end if;
      select c.id into picked from public.marta_contents c
      where c.owner_id=uid and c.status='APPROVATO'
        and not exists(select 1 from public.marta_schedules x where x.content_id=c.id and x.owner_id=uid and x.status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO'))
        and exists(select 1 from public.marta_social_variants v where v.content_id=c.id and v.owner_id=uid and v.status='APPROVATO' and v.approved_at is not null and v.platform=any(s.platforms))
      order by c.created_at,c.id limit 1;
      if picked is null then return; end if;
      insert into public.marta_schedules(owner_id,content_id,platform,scheduled_for)
        select uid,picked,v.platform,candidate from public.marta_social_variants v
        where v.content_id=picked and v.owner_id=uid and v.status='APPROVATO' and v.approved_at is not null and v.platform=any(s.platforms);
      get diagnostics n=row_count;
      if n>0 then
        update public.marta_contents set status='PROGRAMMATO' where id=picked and owner_id=uid;
        content_id:=picked;scheduled_for:=candidate;platform_count:=n;return next;
      end if;
      picked:=null;
    end loop;
  end loop;
end $$;
