alter table public.marta_investment_entries
  drop constraint if exists marta_investment_entries_input_check;
alter table public.marta_investment_entries
  add constraint marta_investment_entries_input_check check (
    char_length(btrim(service)) between 1 and 200
    and amount >= 0
    and (note is null or char_length(note) <= 1000)
  );