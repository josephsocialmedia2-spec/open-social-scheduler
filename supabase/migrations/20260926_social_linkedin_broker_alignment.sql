update public.f1_client_social_channels
set provider='oauth_broker', updated_at=now()
where platform='linkedin-page'
  and enabled=false
  and verified=false
  and provider='direct';
