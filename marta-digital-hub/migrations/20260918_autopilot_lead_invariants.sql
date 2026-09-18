-- Additional invariants for Marta leads and Autopilot.
alter table public.marta_autopilot_settings
  drop constraint if exists marta_autopilot_posts_slots_check;
alter table public.marta_autopilot_settings
  add constraint marta_autopilot_posts_slots_check check (
    posts_per_day <= cardinality(slots)
  );

alter table public.marta_leads
  drop constraint if exists marta_leads_identity_check;
alter table public.marta_leads
  add constraint marta_leads_identity_check check (
    nullif(btrim(coalesce(name,'')),'') is not null
    or nullif(btrim(coalesce(contact,'')),'') is not null
  );