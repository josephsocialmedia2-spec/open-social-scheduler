-- Generate and protect the F1 OAuth encryption secret inside Supabase Vault.
-- This removes the need for a human-managed F1_OAUTH_ENCRYPTION_KEY.

do $$
begin
  if not exists (
    select 1
    from vault.secrets
    where name = 'f1_oauth_encryption_key'
  ) then
    perform vault.create_secret(
      encode(gen_random_bytes(32), 'hex'),
      'f1_oauth_encryption_key',
      'F1 Social Publisher OAuth AES/HMAC application secret'
    );
  end if;
end
$$;

create or replace function public.f1_get_oauth_encryption_secret()
returns text
language sql
security definer
set search_path = ''
as $$
  select decrypted_secret
  from vault.decrypted_secrets
  where name = 'f1_oauth_encryption_key'
  limit 1
$$;

revoke all on function public.f1_get_oauth_encryption_secret() from public;
revoke all on function public.f1_get_oauth_encryption_secret() from anon;
revoke all on function public.f1_get_oauth_encryption_secret() from authenticated;
grant execute on function public.f1_get_oauth_encryption_secret() to service_role;

comment on function public.f1_get_oauth_encryption_secret() is
  'Service-role-only accessor for the F1 OAuth encryption key stored in Supabase Vault.';
