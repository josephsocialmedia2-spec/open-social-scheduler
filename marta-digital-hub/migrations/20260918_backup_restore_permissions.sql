-- Allow the authenticated Marta owner to restore her own media-version metadata.
drop policy if exists marta_versions_owner on public.marta_media_versions;
create policy marta_versions_owner on public.marta_media_versions
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));
