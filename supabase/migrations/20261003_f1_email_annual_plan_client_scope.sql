-- Idempotent owner + client scope for annual email plans.
do $$
begin
  if exists (select 1 from pg_policies where schemaname='public' and tablename='f1_client_email_plans' and policyname='f1_client_email_plans_owner_all') then
    execute 'alter policy "f1_client_email_plans_owner_all" on public.f1_client_email_plans using ((select auth.uid()) = owner_id and client_id in (select id from public.f1_content_clients where owner_id = (select auth.uid()))) with check ((select auth.uid()) = owner_id and client_id in (select id from public.f1_content_clients where owner_id = (select auth.uid())))';
  end if;
  if exists (select 1 from pg_policies where schemaname='public' and tablename='f1_client_email_plans' and policyname='f1_client_email_plans_owner_client') then
    execute 'alter policy "f1_client_email_plans_owner_client" on public.f1_client_email_plans using ((select auth.uid()) = owner_id and client_id in (select id from public.f1_content_clients where owner_id = (select auth.uid()))) with check ((select auth.uid()) = owner_id and client_id in (select id from public.f1_content_clients where owner_id = (select auth.uid())))';
  end if;
  if exists (select 1 from pg_policies where schemaname='public' and tablename='f1_client_email_plan_items' and policyname='f1_client_email_plan_items_owner_all') then
    execute 'alter policy "f1_client_email_plan_items_owner_all" on public.f1_client_email_plan_items using ((select auth.uid()) = owner_id and client_id in (select id from public.f1_content_clients where owner_id = (select auth.uid()))) with check ((select auth.uid()) = owner_id and client_id in (select id from public.f1_content_clients where owner_id = (select auth.uid())))';
  end if;
  if exists (select 1 from pg_policies where schemaname='public' and tablename='f1_client_email_plan_items' and policyname='f1_client_email_plan_items_owner_client') then
    execute 'alter policy "f1_client_email_plan_items_owner_client" on public.f1_client_email_plan_items using ((select auth.uid()) = owner_id and client_id in (select id from public.f1_content_clients where owner_id = (select auth.uid()))) with check ((select auth.uid()) = owner_id and client_id in (select id from public.f1_content_clients where owner_id = (select auth.uid())))';
  end if;
end $$;