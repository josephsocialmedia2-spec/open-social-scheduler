-- Marta Digital Hub - automatic media processing queue, max 16 per worker batch.
-- Isolated to marta_* objects. Does not touch F1/CRM.

create unique index if not exists marta_processing_jobs_active_content_kind_idx
  on public.marta_processing_jobs(content_id,kind)
  where status in ('IN_CODA','IN_CORSO');

create or replace function public.marta_enqueue_processing_job()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if new.status='CARICATO'
     and new.storage_path is not null
     and not exists(select 1 from public.marta_transcripts t where t.content_id=new.id)
     and not exists(
       select 1 from public.marta_processing_jobs j
       where j.content_id=new.id and j.kind='PROCESS_MEDIA' and j.status in ('IN_CODA','IN_CORSO')
     )
  then
    insert into public.marta_processing_jobs(owner_id,content_id,kind,status)
    values(new.owner_id,new.id,'PROCESS_MEDIA','IN_CODA');
  end if;
  return new;
end $$;

revoke all on function public.marta_enqueue_processing_job() from public, anon, authenticated;

drop trigger if exists marta_contents_enqueue_processing on public.marta_contents;
create trigger marta_contents_enqueue_processing
after insert or update of status,storage_path on public.marta_contents
for each row execute function public.marta_enqueue_processing_job();

create or replace function public.marta_claim_processing_batch(p_limit integer default 16)
returns table(
  job_id uuid,
  owner_id uuid,
  content_id uuid,
  storage_path text,
  title text,
  category text,
  original_filename text,
  mime_type text,
  attempts integer
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  p_limit := least(greatest(coalesce(p_limit,16),1),16);

  update public.marta_processing_jobs
  set status='IN_CODA',started_at=null,last_error='Ripresa automatica dopo timeout worker'
  where kind='PROCESS_MEDIA'
    and status='IN_CORSO'
    and started_at < now()-interval '120 minutes'
    and attempts < 3;

  with exhausted as (
    update public.marta_processing_jobs
    set status='ERRORE',finished_at=now(),last_error=coalesce(last_error,'Numero massimo tentativi raggiunto')
    where kind='PROCESS_MEDIA'
      and status='IN_CORSO'
      and started_at < now()-interval '120 minutes'
      and attempts >= 3
    returning content_id,owner_id
  )
  update public.marta_contents c
  set status='ERRORE'
  from exhausted e
  where c.id=e.content_id and c.owner_id=e.owner_id;

  return query
  with picked as (
    select j.id
    from public.marta_processing_jobs j
    join public.marta_contents c on c.id=j.content_id and c.owner_id=j.owner_id
    where j.kind='PROCESS_MEDIA'
      and j.status='IN_CODA'
      and c.storage_path is not null
      and c.status in ('CARICATO','IN_ELABORAZIONE','ERRORE')
    order by j.created_at,j.id
    for update of j skip locked
    limit p_limit
  ),
  claimed as (
    update public.marta_processing_jobs j
    set status='IN_CORSO',
        attempts=j.attempts+1,
        started_at=now(),
        finished_at=null,
        last_error=null
    from picked p
    where j.id=p.id
    returning j.*
  )
  select cl.id,cl.owner_id,cl.content_id,c.storage_path,c.title,c.category,
         c.original_filename,c.mime_type,cl.attempts
  from claimed cl
  join public.marta_contents c on c.id=cl.content_id and c.owner_id=cl.owner_id
  order by cl.created_at,cl.id;
end $$;

revoke all on function public.marta_claim_processing_batch(integer) from public, anon, authenticated;
grant execute on function public.marta_claim_processing_batch(integer) to service_role;

create or replace function public.marta_finish_processing_job(
  p_job_id uuid,
  p_transcript text,
  p_audio_path text,
  p_audio_size bigint,
  p_model text,
  p_captions jsonb
) returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  j public.marta_processing_jobs;
  kv record;
  v_platform text;
  v_hook text;
  v_cta text;
  v_hashtags jsonb;
  v_variants jsonb;
begin
  select * into j
  from public.marta_processing_jobs
  where id=p_job_id and kind='PROCESS_MEDIA' and status='IN_CORSO'
  for update;

  if not found then raise exception 'Job non disponibile o non in corso'; end if;
  if char_length(btrim(coalesce(p_transcript,''))) not between 1 and 100000 then raise exception 'Trascrizione non valida'; end if;
  if p_audio_size is null or p_audio_size<=0 or p_audio_size>52428800 then raise exception 'Dimensione audio non valida'; end if;
  if p_audio_path is null or p_audio_path not like j.owner_id::text||'/%' then raise exception 'Percorso audio non valido'; end if;
  if char_length(coalesce(p_model,''))>100 then raise exception 'Modello non valido'; end if;
  if jsonb_typeof(p_captions)<>'object'
     or not (p_captions ?& array['instagram','facebook','tiktok','youtube','linkedin'])
     or (select count(*) from jsonb_object_keys(p_captions))<>5
  then raise exception 'Pacchetto caption incompleto'; end if;

  insert into public.marta_transcripts(owner_id,content_id,original_text,corrected_text,language,source_model)
  values(j.owner_id,j.content_id,btrim(p_transcript),btrim(p_transcript),'it',coalesce(nullif(p_model,''),'whisper'))
  on conflict(content_id) do update
    set original_text=excluded.original_text,
        corrected_text=excluded.corrected_text,
        language=excluded.language,
        source_model=excluded.source_model;

  for kv in select key,value from jsonb_each(p_captions)
  loop
    v_platform:=kv.key;
    if v_platform not in ('instagram','facebook','tiktok','youtube','linkedin') then
      raise exception 'Piattaforma caption non valida';
    end if;
    v_hook:=left(coalesce(kv.value->>'hook',''),500);
    v_cta:=left(coalesce(kv.value->>'cta',''),1000);
    v_hashtags:=coalesce(kv.value->'hashtags','[]'::jsonb);
    v_variants:=coalesce(kv.value->'variants','{}'::jsonb);
    if jsonb_typeof(v_hashtags)<>'array' or jsonb_array_length(v_hashtags)>50 then raise exception 'Hashtag non validi'; end if;
    if octet_length(v_hashtags::text)>5000 or octet_length(v_variants::text)>30000 then raise exception 'Payload caption troppo grande'; end if;

    insert into public.marta_social_variants(owner_id,content_id,platform,hook,cta,hashtags,variants,status,approved_at)
    values(j.owner_id,j.content_id,v_platform,v_hook,v_cta,v_hashtags,v_variants,'DA_APPROVARE',null)
    on conflict(content_id,platform) do update
      set hook=excluded.hook,
          cta=excluded.cta,
          hashtags=excluded.hashtags,
          variants=excluded.variants,
          status='DA_APPROVARE',
          approved_at=null;
  end loop;

  update public.marta_contents
  set audio_storage_path=p_audio_path,
      audio_file_size=p_audio_size,
      status='DA_APPROVARE'
  where id=j.content_id and owner_id=j.owner_id;

  update public.marta_processing_jobs
  set status='COMPLETATO',finished_at=now(),last_error=null
  where id=j.id;

  insert into public.marta_audit_logs(owner_id,module,action,entity_id,outcome,details)
  values(j.owner_id,'media','AUTO_PROCESS',j.content_id::text,'OK',
         jsonb_build_object('job_id',j.id,'model',p_model,'audio_bytes',p_audio_size));
end $$;

revoke all on function public.marta_finish_processing_job(uuid,text,text,bigint,text,jsonb) from public, anon, authenticated;
grant execute on function public.marta_finish_processing_job(uuid,text,text,bigint,text,jsonb) to service_role;

create or replace function public.marta_fail_processing_job(p_job_id uuid,p_error text)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare j public.marta_processing_jobs;
begin
  select * into j from public.marta_processing_jobs where id=p_job_id and kind='PROCESS_MEDIA' for update;
  if not found then return; end if;
  update public.marta_processing_jobs
  set status='ERRORE',finished_at=now(),last_error=left(coalesce(p_error,'Errore lavorazione'),2000)
  where id=j.id;
  update public.marta_contents set status='ERRORE' where id=j.content_id and owner_id=j.owner_id;
  insert into public.marta_audit_logs(owner_id,module,action,entity_id,outcome,error,details)
  values(j.owner_id,'media','AUTO_PROCESS',j.content_id::text,'ERRORE',left(coalesce(p_error,'Errore lavorazione'),2000),
         jsonb_build_object('job_id',j.id,'attempts',j.attempts));
end $$;

revoke all on function public.marta_fail_processing_job(uuid,text) from public, anon, authenticated;
grant execute on function public.marta_fail_processing_job(uuid,text) to service_role;

create or replace function public.marta_retry_processing(p_content_id uuid)
returns uuid
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare uid uuid:=auth.uid(); jid uuid;
begin
  if uid is null or not marta_private.is_allowed(uid) then raise exception 'Accesso non autorizzato'; end if;
  if not exists(select 1 from public.marta_contents where id=p_content_id and owner_id=uid and storage_path is not null) then
    raise exception 'Contenuto non disponibile';
  end if;
  update public.marta_contents set status='CARICATO' where id=p_content_id and owner_id=uid;
  select id into jid from public.marta_processing_jobs
  where content_id=p_content_id and owner_id=uid and kind='PROCESS_MEDIA' and status in ('IN_CODA','IN_CORSO')
  order by created_at desc limit 1;
  if jid is null then raise exception 'Impossibile creare la coda di lavorazione'; end if;
  return jid;
end $$;

revoke all on function public.marta_retry_processing(uuid) from public, anon;
grant execute on function public.marta_retry_processing(uuid) to authenticated;
