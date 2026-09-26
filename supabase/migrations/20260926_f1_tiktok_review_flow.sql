-- TikTok Direct Post review/compliance support.
-- Additive: stores user-approved TikTok settings on content items and
-- platform-specific publication state on calendar rows.

alter table public.f1_content_items
  add column if not exists tiktok_settings jsonb not null default '{}'::jsonb;

alter table public.f1_content_calendar
  add column if not exists platform_metadata jsonb not null default '{}'::jsonb;

alter table public.f1_content_items
  drop constraint if exists f1_content_items_status_check;

alter table public.f1_content_items
  add constraint f1_content_items_status_check check (
    status = any(array[
      'IN ARRIVO','DA CLASSIFICARE','DA LAVORARE','IN LAVORAZIONE','PRONTO',
      'DA APPROVARE','APPROVATO','PROGRAMMATO','IN PUBBLICAZIONE','PUBBLICATO','ARCHIVIATO',
      'ERRORE_MEDIA','ERRORE_QUEUE','ERRORE_PUBBLICAZIONE','CANALE_DA_COLLEGARE',
      'CREDENZIALI_MANCANTI','AUTH_REQUIRED','DA_RIAUTORIZZARE','TIKTOK_REVIEW_REQUIRED'
    ]::text[])
  );

comment on column public.f1_content_items.tiktok_settings is
  'Per-content TikTok user choices and explicit consent; never stores OAuth tokens.';

comment on column public.f1_content_calendar.platform_metadata is
  'Provider-specific publication state such as TikTok publish_id and processing status.';
