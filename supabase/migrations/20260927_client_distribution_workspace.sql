-- Client content distribution workspace.
-- Adds per-client publication preferences and per-content editable multi-platform plans.

alter table public.f1_content_clients
  add column if not exists publishing_preferences jsonb not null default '{}'::jsonb;

alter table public.f1_content_items
  add column if not exists distribution_plan jsonb not null default '{}'::jsonb;

update public.f1_content_clients
set auto_publish=true,
    publishing_preferences = coalesce(publishing_preferences,'{}'::jsonb) || jsonb_build_object(
      'facebook',jsonb_build_object('time','11:00','enabled',true),
      'instagram',jsonb_build_object('time','13:30','enabled',true),
      'tiktok',jsonb_build_object('time','18:30','enabled',true),
      'youtube',jsonb_build_object('time','21:00','enabled',true),
      'linkedin-page',jsonb_build_object('time','09:30','enabled',true),
      'review_before_schedule',true,
      'timezone','Europe/Rome'
    ),
    updated_at=now()
where slug='antica-cappella';
