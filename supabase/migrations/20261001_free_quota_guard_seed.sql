-- Ensure the free quota guard exists before the first media upload.

insert into public.f1_free_quota_usage(
  owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details,checked_at,updated_at
)
select distinct owner_id,
       'supabase_storage_media',
       'free',
       0,
       1073741824,
       'bytes',
       false,
       jsonb_build_object('source','owner_seed','threshold_percent',95),
       now(),now()
from public.f1_content_clients
where owner_id is not null
on conflict(owner_id,service_key) do nothing;

create or replace function public.f1_seed_media_quota_for_owner()
returns trigger
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  insert into public.f1_free_quota_usage(
    owner_id,service_key,plan_name,used_value,hard_limit,unit,blocked,details,checked_at,updated_at
  )
  values(
    new.owner_id,'supabase_storage_media','free',0,1073741824,'bytes',false,
    jsonb_build_object('source','client_seed','threshold_percent',95),now(),now()
  )
  on conflict(owner_id,service_key) do nothing;
  return new;
end;
$$;

revoke all on function public.f1_seed_media_quota_for_owner() from public, anon, authenticated;

drop trigger if exists f1_content_clients_seed_media_quota on public.f1_content_clients;
create trigger f1_content_clients_seed_media_quota
after insert on public.f1_content_clients
for each row execute function public.f1_seed_media_quota_for_owner();
