-- Tighten annual email plan RLS to the selected client owner.
alter policy "f1_client_email_plans_owner_all"
on public.f1_client_email_plans
using (
  owner_id = (select auth.uid())
  and client_id in (
    select id from public.f1_content_clients
    where owner_id = (select auth.uid())
  )
)
with check (
  owner_id = (select auth.uid())
  and client_id in (
    select id from public.f1_content_clients
    where owner_id = (select auth.uid())
  )
);

alter policy "f1_client_email_plan_items_owner_all"
on public.f1_client_email_plan_items
using (
  owner_id = (select auth.uid())
  and client_id in (
    select id from public.f1_content_clients
    where owner_id = (select auth.uid())
  )
)
with check (
  owner_id = (select auth.uid())
  and client_id in (
    select id from public.f1_content_clients
    where owner_id = (select auth.uid())
  )
);