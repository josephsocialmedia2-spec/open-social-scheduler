-- Remove the temporary bootstrap workaround used during the first login setup.
-- The allowlisted authenticated flow now uses marta_initialize_user instead.

drop function if exists public.marta_admin_initialize_owner(uuid,text);
drop table if exists public.marta_bootstrap_tokens;
