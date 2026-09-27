
-- Restrict cloud-browser seed trigger function from public API execution.
revoke all on function public.f1_seed_cloud_browser_for_client() from public;
revoke all on function public.f1_seed_cloud_browser_for_client() from anon;
revoke all on function public.f1_seed_cloud_browser_for_client() from authenticated;
grant execute on function public.f1_seed_cloud_browser_for_client() to service_role;
