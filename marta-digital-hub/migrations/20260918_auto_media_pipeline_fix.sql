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

  update public.marta_processing_jobs j
  set status='IN_CODA',started_at=null,last_error='Ripresa automatica dopo timeout worker'
  where j.kind='PROCESS_MEDIA'
    and j.status='IN_CORSO'
    and j.started_at < now()-interval '120 minutes'
    and j.attempts < 3;

  with exhausted as (
    update public.marta_processing_jobs j
    set status='ERRORE',finished_at=now(),last_error=coalesce(j.last_error,'Numero massimo tentativi raggiunto')
    where j.kind='PROCESS_MEDIA'
      and j.status='IN_CORSO'
      and j.started_at < now()-interval '120 minutes'
      and j.attempts >= 3
    returning j.content_id,j.owner_id
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
