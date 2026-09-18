-- Marta Digital Hub - library metadata and tracking link hardening
alter table public.marta_contents
  add column if not exists duration_seconds numeric,
  add column if not exists duplicate_of uuid references public.marta_contents(id) on delete set null;

alter table public.marta_contents
  drop constraint if exists marta_contents_duration_check;
alter table public.marta_contents
  add constraint marta_contents_duration_check check (
    duration_seconds is null or (duration_seconds > 0 and duration_seconds <= 86400)
  );

alter table public.marta_tracking_links
  drop constraint if exists marta_tracking_links_platform_check,
  drop constraint if exists marta_tracking_links_lengths_check,
  drop constraint if exists marta_tracking_links_url_check;

alter table public.marta_tracking_links
  add constraint marta_tracking_links_platform_check check (
    platform in ('instagram','facebook','tiktok','youtube','linkedin')
  ),
  add constraint marta_tracking_links_lengths_check check (
    char_length(coalesce(destination_url,'')) <= 2000
    and char_length(coalesce(tracked_url,'')) <= 3000
    and char_length(coalesce(utm_source,'')) <= 100
    and char_length(coalesce(utm_medium,'')) <= 100
    and char_length(coalesce(utm_campaign,'')) <= 200
    and char_length(coalesce(utm_content,'')) <= 200
  ),
  add constraint marta_tracking_links_url_check check (
    (destination_url is null or destination_url ~ '^https?://')
    and (tracked_url is null or tracked_url ~ '^https?://')
  );

create index if not exists marta_contents_duplicate_of_idx
  on public.marta_contents(duplicate_of)
  where duplicate_of is not null;
