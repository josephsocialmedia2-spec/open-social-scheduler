-- Indici di supporto per le foreign key del modulo EMAIL F1 Social.
create index if not exists idx_f1_client_email_accounts_client_id on public.f1_client_email_accounts(client_id);
create index if not exists idx_f1_client_email_tokens_client_id on public.f1_client_email_oauth_tokens(client_id);
create index if not exists idx_f1_client_email_brand_client_id on public.f1_client_email_brand_kits(client_id);
create index if not exists idx_f1_client_email_graphics_client_id on public.f1_client_email_graphics(client_id);
create index if not exists idx_f1_client_email_templates_client_id on public.f1_client_email_templates(client_id);
create index if not exists idx_f1_client_email_suppressions_client_id on public.f1_client_email_suppressions(client_id);
create index if not exists idx_f1_client_email_attachments_client_id on public.f1_client_email_attachments(client_id);
create index if not exists idx_f1_client_email_attachments_campaign_id on public.f1_client_email_attachments(campaign_id);
create index if not exists idx_email_campaigns_client_id on public.email_campaigns(client_id);
create index if not exists idx_email_campaigns_email_account_id on public.email_campaigns(email_account_id);
create index if not exists idx_email_campaigns_template_id on public.email_campaigns(template_id);
create index if not exists idx_email_campaigns_graphic_id on public.email_campaigns(graphic_id);
create index if not exists idx_email_campaigns_compliance_by on public.email_campaigns(compliance_confirmed_by);
create index if not exists idx_email_campaign_recipients_client_id on public.email_campaign_recipients(client_id);
create index if not exists idx_email_campaign_events_client_id on public.email_campaign_events(client_id);
