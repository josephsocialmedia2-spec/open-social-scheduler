-- Distinguish a TikTok draft delivered to the creator inbox from a public post.
alter table public.f1_content_items
  drop constraint if exists f1_content_items_status_check;

alter table public.f1_content_items
  add constraint f1_content_items_status_check check (
    status = any(array[
      'IN ARRIVO','DA CLASSIFICARE','DA LAVORARE','IN LAVORAZIONE','PRONTO',
      'DA APPROVARE','APPROVATO','PROGRAMMATO','IN PUBBLICAZIONE','PUBBLICATO','ARCHIVIATO',
      'ERRORE_MEDIA','ERRORE_QUEUE','ERRORE_PUBBLICAZIONE','CANALE_DA_COLLEGARE',
      'CREDENZIALI_MANCANTI','AUTH_REQUIRED','DA_RIAUTORIZZARE','TIKTOK_REVIEW_REQUIRED',
      'BOZZA_TIKTOK_INVIATA'
    ]::text[])
  );
