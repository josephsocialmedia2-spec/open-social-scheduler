delete from public.f1_free_quota_usage
where service_key='supabase_storage_media';

comment on table public.f1_free_quota_usage is
  'Zero-cost quota registry. Supabase Storage is tracked project-wide via service_key supabase_storage_project; uploads block at projected 95% of the configured free ceiling.';
