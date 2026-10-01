-- Add explicit free-tier status bands required by the operational guard.

alter table public.f1_free_quota_usage
  add column if not exists status text
  generated always as (
    case
      when hard_limit is null or hard_limit <= 0 then 'BLOCCO'
      when ((used_value / hard_limit) * 100) >= 95 then 'BLOCCO'
      when ((used_value / hard_limit) * 100) >= 85 then 'AVVISO'
      when ((used_value / hard_limit) * 100) >= 70 then 'INFORMAZIONE'
      else 'OK'
    end
  ) stored;

alter table public.f1_free_quota_usage
  add column if not exists available_percent numeric
  generated always as (
    case
      when hard_limit is null or hard_limit <= 0 then 0
      else greatest(0, round(100 - ((used_value / hard_limit) * 100), 2))
    end
  ) stored;

comment on column public.f1_free_quota_usage.status is
  'Free-tier operational band: OK <70, INFORMAZIONE >=70, AVVISO >=85, BLOCCO >=95.';
comment on column public.f1_free_quota_usage.available_percent is
  'Percentage of the configured free quota still available.';
