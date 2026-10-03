-- F1 Social EMAIL: all campaign/account data is server-side only.
-- The browser talks to f1-client-email; service_role is never exposed.
revoke all on table
  public.f1_client_email_accounts,
  public.f1_client_email_oauth_tokens,
  public.f1_client_email_brand_kits,
  public.f1_client_email_graphics,
  public.f1_client_email_templates,
  public.f1_client_email_suppressions,
  public.f1_client_email_attachments,
  public.email_campaigns,
  public.email_campaign_recipients,
  public.email_campaign_events
from anon, authenticated, public;

grant select, insert, update, delete on table
  public.f1_client_email_accounts,
  public.f1_client_email_oauth_tokens,
  public.f1_client_email_brand_kits,
  public.f1_client_email_graphics,
  public.f1_client_email_templates,
  public.f1_client_email_suppressions,
  public.f1_client_email_attachments,
  public.email_campaigns,
  public.email_campaign_recipients,
  public.email_campaign_events
to service_role;
