-- F1 Social isolated tenant + publication state compatibility.
-- Idempotent: preserves all historical statuses and adds the official F1 Social states.

alter table public.f1_content_items
  drop constraint if exists f1_content_items_status_check;

alter table public.f1_content_items
  add constraint f1_content_items_status_check check (
    status = any(array[
      'BOZZA','PRONTO','IN PUBBLICAZIONE','PUBBLICATO','PARZIALMENTE PUBBLICATO','ERRORE',
      'IN ARRIVO','DA CLASSIFICARE','DA LAVORARE','IN LAVORAZIONE','DA APPROVARE','APPROVATO',
      'PROGRAMMATO','ARCHIVIATO','ERRORE_MEDIA','ERRORE_QUEUE','ERRORE_PUBBLICAZIONE',
      'CANALE_DA_COLLEGARE','CREDENZIALI_MANCANTI','AUTH_REQUIRED','DA_RIAUTORIZZARE',
      'TIKTOK_REVIEW_REQUIRED','BOZZA_TIKTOK_INVIATA'
    ])
  );

insert into public.f1_content_clients
  (owner_id,name,slug,category,facebook,instagram,tiktok,youtube,status,timezone,auto_publish,approval_required,automation_status,profile_metadata)
select
  r.owner_id,
  'F1 Social',
  'f1-social',
  'Social media management',
  'https://www.facebook.com/josephrealmedia',
  'https://www.instagram.com/realmediaproageency/',
  'https://www.tiktok.com/@realmediapro_agency',
  'https://www.youtube.com/channel/UC4G1Oq0z-_b0UTwRmYBxbCA',
  'ATTIVO',
  'Europe/Rome',
  false,
  false,
  'MANUALE',
  jsonb_build_object(
    'operator','Real Media Pro',
    'exclusive_account_whitelist',true,
    'allow_client_accounts',false
  )
from public.f1_content_clients r
where r.slug='real-media-pro'
  and not exists (select 1 from public.f1_content_clients where slug='f1-social')
limit 1;

update public.f1_client_social_channels s
set profile_url = case s.platform
  when 'facebook' then 'https://www.facebook.com/josephrealmedia'
  when 'instagram' then 'https://www.instagram.com/realmediaproageency/'
  when 'tiktok' then 'https://www.tiktok.com/@realmediapro_agency'
  when 'youtube' then 'https://www.youtube.com/channel/UC4G1Oq0z-_b0UTwRmYBxbCA'
  else s.profile_url
end,
updated_at=now()
from public.f1_content_clients c
where c.slug='f1-social'
  and s.client_id=c.id
  and s.owner_id=c.owner_id;
