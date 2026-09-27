alter table public.f1_whatsapp_senders
  add column if not exists managed_from_client boolean not null default false;

create or replace function public.f1_normalize_whatsapp_wa_id(p_value text)
returns text
language plpgsql
immutable
as $$
declare
  v text;
begin
  v := regexp_replace(coalesce(p_value, ''), '[^0-9]', '', 'g');
  if left(v, 2) = '00' then
    v := substring(v from 3);
  end if;
  if length(v) < 8 or length(v) > 15 then
    return null;
  end if;
  return v;
end;
$$;

create or replace function public.f1_sync_whatsapp_sender_from_client()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_old text;
  v_new text;
  v_source text;
begin
  if tg_op = 'UPDATE' then
    v_old := public.f1_normalize_whatsapp_wa_id(
      case
        when nullif(trim(coalesce(old.whatsapp, '')), '') is not null
          then old.whatsapp
        when coalesce(old.profile_metadata->>'whatsapp_same_as_phone', 'false') = 'true'
          then old.phone
        else null
      end
    );
  end if;

  v_source := case
    when nullif(trim(coalesce(new.whatsapp, '')), '') is not null
      then new.whatsapp
    when coalesce(new.profile_metadata->>'whatsapp_same_as_phone', 'false') = 'true'
      then new.phone
    else null
  end;
  v_new := public.f1_normalize_whatsapp_wa_id(v_source);

  if tg_op = 'UPDATE' and v_old is not null and v_old is distinct from v_new then
    update public.f1_whatsapp_senders
       set active = false,
           updated_at = now()
     where owner_id = new.owner_id
       and client_id = new.id
       and wa_id = v_old
       and managed_from_client = true;
  end if;

  if new.status = 'ATTIVO' and v_new is not null then
    insert into public.f1_whatsapp_senders (
      owner_id,
      wa_id,
      label,
      active,
      client_id,
      auto_process,
      report_recipient,
      suppress_operational_notifications,
      managed_from_client,
      updated_at
    ) values (
      new.owner_id,
      v_new,
      new.name,
      true,
      new.id,
      true,
      false,
      true,
      true,
      now()
    )
    on conflict (wa_id) do update
      set label = excluded.label,
          active = excluded.active,
          client_id = excluded.client_id,
          auto_process = excluded.auto_process,
          suppress_operational_notifications = excluded.suppress_operational_notifications,
          managed_from_client = true,
          updated_at = now()
      where public.f1_whatsapp_senders.owner_id = excluded.owner_id;
  end if;

  return new;
end;
$$;

drop trigger if exists trg_f1_sync_whatsapp_sender_from_client
  on public.f1_content_clients;

create trigger trg_f1_sync_whatsapp_sender_from_client
after insert or update of whatsapp, phone, profile_metadata, status, name
on public.f1_content_clients
for each row
execute function public.f1_sync_whatsapp_sender_from_client();

do $$
declare
  r record;
begin
  for r in
    select *
    from public.f1_content_clients
    where status = 'ATTIVO'
  loop
    perform public.f1_sync_whatsapp_sender_from_client();
  end loop;
exception
  when feature_not_supported then
    null;
end
$$;
