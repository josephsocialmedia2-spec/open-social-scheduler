-- Final guard for direct Data API inserts into marta_contents.
-- Controlled lifecycle states must only be reached through verified transitions.

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
  if tg_op='INSERT' then
    if new.status not in ('IN_ELABORAZIONE','ERRORE') then
      raise exception 'Un nuovo contenuto deve iniziare in elaborazione';
    end if;
    return new;
  end if;

  if new.status is not distinct from old.status then return new; end if;

  if new.status='APPROVATO' then
    if old.status in ('IN_ELABORAZIONE','ERRORE') then raise exception 'Il contenuto non è pronto per l approvazione'; end if;
    if new.storage_path is null or not exists(
      select 1 from storage.objects o
      where o.bucket_id='marta-content-originals' and o.name=new.storage_path
    ) then raise exception 'Il video originale non è presente nello storage'; end if;
    select count(*),count(*) filter(where status='APPROVATO' and approved_at is not null)
      into total_count,approved_count
      from public.marta_social_variants
      where content_id=new.id and owner_id=new.owner_id and status<>'NON_PUBBLICARE';
    if total_count=0 or approved_count<>total_count then raise exception 'Approva prima tutte le caption da pubblicare'; end if;
  elsif new.status='PROGRAMMATO' then
    if not exists(
      select 1 from public.marta_schedules s
      where s.content_id=new.id and s.owner_id=new.owner_id
        and s.status in ('PROGRAMMATO','INVIATO','MANUALE_ASSISTITO')
    ) then raise exception 'Nessuna programmazione attiva per il contenuto'; end if;
  elsif new.status='PUBBLICATO' then
    if not exists(
      select 1 from public.marta_schedules s
      where s.content_id=new.id and s.owner_id=new.owner_id and s.status='PUBBLICATO'
    ) then raise exception 'Nessuna pubblicazione confermata dalla piattaforma'; end if;
  end if;
  return new;
end $$;

drop trigger if exists marta_contents_status_guard_insert on public.marta_contents;
drop trigger if exists marta_contents_status_guard on public.marta_contents;
create trigger marta_contents_status_guard_insert
before insert on public.marta_contents
for each row execute function public.marta_content_status_guard();
create trigger marta_contents_status_guard
before update of status on public.marta_contents
for each row execute function public.marta_content_status_guard();
