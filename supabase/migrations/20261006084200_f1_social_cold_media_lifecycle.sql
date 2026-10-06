-- F1 Social cold-media lifecycle.
-- Keeps large media outside Supabase Storage until publication is imminent,
-- while preserving metadata, deletion safety and publication history.

alter table public.f1_content_media
  add column if not exists archive_provider text,
  add column if not exists archive_public_id text,
  add column if not exists archive_asset_id text,
  add column if not exists archive_resource_type text,
  add column if not exists archive_url text,
  add column if not exists archived_at timestamptz,
  add column if not exists storage_state text not null default 'HOT',
  add column if not exists hot_deleted_at timestamptz;

alter table public.f1_content_items
  add column if not exists deletion_requested_at timestamptz;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conrelid='public.f1_content_media'::regclass
      and conname='f1_content_media_storage_state_check'
  ) then
    alter table public.f1_content_media
      add constraint f1_content_media_storage_state_check
      check (storage_state in ('HOT','COLD','DELETE_PENDING','DELETED'));
  end if;
end $$;

create index if not exists f1_content_media_storage_state_idx
  on public.f1_content_media(storage_state, created_at);

create index if not exists f1_content_items_deletion_requested_idx
  on public.f1_content_items(deletion_requested_at)
  where deletion_requested_at is not null;
