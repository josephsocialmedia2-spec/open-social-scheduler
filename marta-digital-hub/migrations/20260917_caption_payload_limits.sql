-- Bound caption payload sizes so direct API writes cannot bypass frontend limits.
alter table public.marta_social_variants
  drop constraint if exists marta_variants_payload_budget_check;

alter table public.marta_social_variants
  add constraint marta_variants_payload_budget_check check (
    octet_length(hashtags::text) <= 5000
    and octet_length(variants::text) <= 30000
  );
