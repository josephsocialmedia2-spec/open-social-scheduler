-- Marta Digital Hub - RLS performance hardening + backup run ownership
-- Only marta_* objects are changed.

alter policy marta_allowlist_gate on public.marta_audit_logs
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_audit_owner on public.marta_audit_logs
  using (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_autopilot_settings
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_autopilot_owner on public.marta_autopilot_settings
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_backup_runs
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
drop policy if exists marta_backup_runs_owner on public.marta_backup_runs;
create policy marta_backup_runs_owner on public.marta_backup_runs
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_contents
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_contents_owner on public.marta_contents
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_editorial_profiles
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_editorial_owner on public.marta_editorial_profiles
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_integrations
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_integrations_owner on public.marta_integrations
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_investment_entries
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_investments_owner on public.marta_investment_entries
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_leads
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_leads_owner on public.marta_leads
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_media_versions
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_versions_owner on public.marta_media_versions
  using (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_performance_metrics
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_metrics_owner on public.marta_performance_metrics
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_processing_jobs
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_jobs_owner on public.marta_processing_jobs
  using (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_profiles
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_profiles_owner on public.marta_profiles
  using (id = (select auth.uid()))
  with check (id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_publish_logs
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_publish_logs_owner on public.marta_publish_logs
  using (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_schedules
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_schedules_owner on public.marta_schedules
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_service_costs
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_costs_owner on public.marta_service_costs
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_social_variants
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_variants_owner on public.marta_social_variants
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_tracking_links
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_tracking_owner on public.marta_tracking_links
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

alter policy marta_allowlist_gate on public.marta_transcripts
  using (marta_private.is_allowed((select auth.uid())))
  with check (marta_private.is_allowed((select auth.uid())));
alter policy marta_transcripts_owner on public.marta_transcripts
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

drop function if exists public.marta_claim_owner(text);
