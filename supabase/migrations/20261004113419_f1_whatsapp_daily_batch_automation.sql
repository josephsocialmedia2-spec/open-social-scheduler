alter table public.f1_whatsapp_senders
  add column if not exists daily_batch_enabled boolean not null default true,
  add column if not exists daily_batch_time time not null default '02:00',
  add column if not exists caption_delay_minutes integer not null default 60,
  add column if not exists auto_publish_after_caption boolean not null default true,
  add column if not exists last_batch_local_date date,
  add column if not exists last_batch_started_at timestamptz;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'f1_whatsapp_caption_delay_minutes_check'
      and conrelid = 'public.f1_whatsapp_senders'::regclass
  ) then
    alter table public.f1_whatsapp_senders
      add constraint f1_whatsapp_caption_delay_minutes_check
      check (caption_delay_minutes between 0 and 1440);
  end if;
end
$$;

comment on column public.f1_whatsapp_senders.daily_batch_enabled is
  'If true, WhatsApp inbox rows for this client are promoted once per local day by the autonomous batch.';
comment on column public.f1_whatsapp_senders.daily_batch_time is
  'Client-local daily processing time. Default 02:00.';
comment on column public.f1_whatsapp_senders.caption_delay_minutes is
  'Delay after video speech transcription before caption generation. Default 60 minutes.';
comment on column public.f1_whatsapp_senders.auto_publish_after_caption is
  'If true, WhatsApp-generated calendar rows may publish automatically through a verified social route.';
