-- Marta Ruffino Digital Hub - upload/storage hardening
-- Isolated to marta_* objects. Does not touch F1/CRM.

alter table public.marta_contents
  drop constraint if exists marta_contents_file_size_check;

alter table public.marta_contents
  add constraint marta_contents_file_size_check
    check (file_size is null or (file_size > 0 and file_size <= 52428800)),
  add constraint marta_contents_title_check
    check (char_length(btrim(title)) between 1 and 200),
  add constraint marta_contents_filename_check
    check (original_filename is null or char_length(original_filename) between 1 and 180),
  add constraint marta_contents_mime_check
    check (mime_type is null or mime_type in ('video/mp4','video/quicktime','video/webm')),
  add constraint marta_contents_storage_path_check
    check (storage_path is null or (char_length(storage_path) <= 1024 and storage_path like owner_id::text || '/%')),
  add constraint marta_contents_loaded_state_check
    check (status in ('IN_ELABORAZIONE','ERRORE') or storage_path is not null);

create or replace function public.marta_reserve_upload(
  p_title text,
  p_category text,
  p_notes text,
  p_filename text,
  p_mime text,
  p_file_size bigint
) returns setof public.marta_contents
language plpgsql
security invoker
set search_path = public, pg_temp
as $$
declare
  v_uid uuid := auth.uid();
  v_used bigint := 0;
  v_budget constant bigint := 800000000;
  v_derived_reserve constant bigint := 57671680;
begin
  if v_uid is null or not marta_private.is_allowed(v_uid) then
    raise exception 'Accesso non autorizzato';
  end if;
  if p_file_size is null or p_file_size <= 0 then raise exception 'Il file è vuoto'; end if;
  if p_file_size > 52428800 then raise exception 'Il file supera 50 MB'; end if;
  if p_mime not in ('video/mp4','video/quicktime','video/webm') then raise exception 'Formato video non consentito'; end if;
  if char_length(btrim(coalesce(p_title,''))) not between 1 and 200 then raise exception 'Titolo non valido'; end if;
  if char_length(coalesce(p_filename,'')) not between 1 and 180 then raise exception 'Nome file non valido'; end if;

  -- Serialize quota reservations for the same owner so two browser tabs cannot
  -- both pass the free-only budget check at the same time.
  perform pg_advisory_xact_lock(hashtext('marta_upload_quota:' || v_uid::text));

  select coalesce(sum(coalesce(c.file_size,0)+coalesce(c.audio_file_size,0)+coalesce(c.publish_file_size,0)),0)
    into v_used
    from public.marta_contents c
    where c.owner_id=v_uid;

  select v_used + coalesce(sum(coalesce(m.file_size,0)),0)
    into v_used
    from public.marta_media_versions m
    where m.owner_id=v_uid;

  if v_used + p_file_size + v_derived_reserve > v_budget then
    raise exception 'Quota gratuita prudenziale insufficiente';
  end if;

  return query
    insert into public.marta_contents(
      owner_id,title,category,notes,original_filename,mime_type,file_size,status
    ) values(
      v_uid,
      btrim(p_title),
      nullif(btrim(coalesce(p_category,'')),''),
      nullif(btrim(coalesce(p_notes,'')),''),
      p_filename,
      p_mime,
      p_file_size,
      'IN_ELABORAZIONE'
    ) returning *;
end $$;

revoke all on function public.marta_reserve_upload(text,text,text,text,text,bigint) from public, anon;
grant execute on function public.marta_reserve_upload(text,text,text,text,text,bigint) to authenticated;

-- The old one-time owner claim flow is obsolete after the allowlisted login hardening.
-- Keep the function for forensic/history purposes but make it unreachable from the Data API.
revoke execute on function public.marta_claim_owner(text) from public, anon, authenticated;
