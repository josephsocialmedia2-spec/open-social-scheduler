update public.f1_content_clients
set
  approval_required = false,
  publishing_preferences =
    jsonb_set(
      coalesce(publishing_preferences,'{}'::jsonb),
      '{review_before_schedule}',
      'false'::jsonb,
      true
    ),
  updated_at = now()
where status = 'ATTIVO'
  and (
    coalesce(approval_required,false) = true
    or coalesce((publishing_preferences->>'review_before_schedule')::boolean,false) = true
  );

create unique index if not exists f1_whatsapp_one_report_recipient_per_owner
  on public.f1_whatsapp_senders(owner_id)
  where active = true and report_recipient = true;
