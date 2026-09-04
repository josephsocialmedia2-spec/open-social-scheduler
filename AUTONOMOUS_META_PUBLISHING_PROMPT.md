# PROMPT OPERATIVO — PUBBLICAZIONE AUTOMATICA FACEBOOK + INSTAGRAM

Agisci come agente autonomo senior specializzato in social publishing, Meta Graph API, GitHub Actions, Python e controllo qualità.

## Obiettivo

Configurare e mantenere un sistema gratuito che pubblichi automaticamente per F1 Immobiliare esattamente due contenuti al giorno su Facebook e Instagram, senza richiedere conferme, approvazioni o interventi manuali prima di ogni pubblicazione.

## Vincoli obbligatori

1. Non usare Post Studio, Postiz, Buffer, Hootsuite, Later, Zapier, Make o altri scheduler a pagamento.
2. Usare esclusivamente GitHub Actions come scheduler/runtime e le API ufficiali Meta come trasporto.
3. Pubblicare su entrambe le piattaforme:
   - Pagina Facebook F1 Immobiliare.
   - Account Instagram professionale collegato.
4. Frequenza esatta:
   - 10:30 Europe/Rome: post/carousel.
   - 18:30 Europe/Rome: Reel.
5. Gestire automaticamente ora solare e ora legale Europe/Rome.
6. Nessun gate umano: non devono esistere stati `awaiting_approval`, richieste `CONFERMO`, `APPROVO` o equivalenti per questi due slot.
7. Prima di pubblicare, il sistema deve creare/renderizzare il media necessario e poi pubblicarlo nello stesso workflow.
8. Rendere il processo idempotente: lo stesso slot non deve mai essere pubblicato due volte, anche in caso di retry o workflow duplicato.
9. In caso di pubblicazione parziale, ritentare solo la piattaforma mancante.
10. Non salvare access token nel repository. Usare esclusivamente GitHub Actions Secrets.
11. Credenziali attese:
    - `F1_FACEBOOK_PAGE_ACCESS_TOKEN`
    - `F1_INSTAGRAM_ACCESS_TOKEN`
    - `F1_INSTAGRAM_USER_ID`
12. Il Reel deve essere pubblicato come Reel nativo su Facebook e Instagram, non come semplice link o post video generico.
13. Il post mattutino deve essere nativo su entrambe le piattaforme; su Instagram usare carousel quando previsto dal renderer.
14. Usare le caption e le regole editoriali F1 già presenti nel repository e ruotare i contenuti evitando duplicazioni giornaliere.
15. Conservare nel file di stato solamente gli identificativi, gli esiti di pubblicazione e i dati necessari all'idempotenza.
16. Se un token o un ID Meta non è disponibile, il sistema deve fallire in modo esplicito nei log e non simulare una pubblicazione riuscita.
17. Nessun placeholder, nessun TODO e nessuna istruzione lasciata incompleta.

## Architettura richiesta

```text
publisher/content_bank/f1-immobiliare.json
        ↓
publisher/meta_twice_daily.py
        ↓
render_reels.py
        ↓
direct_api_publish.py
        ↓
Meta Graph API
        ↓
Facebook + Instagram
```

Workflow principale:

```text
.github/workflows/meta-twice-daily.yml
```

Il workflow deve effettuare quattro run UTC di copertura al giorno per gestire automaticamente il cambio CET/CEST. Il gate Python decide se lo slot locale è realmente dovuto. Una seconda run di copertura deve funzionare come retry e diventare un NOOP quando lo slot risulta già pubblicato.

## Controllo qualità obbligatorio

Prima di considerare conclusa qualsiasi modifica:

- compilare con `py_compile` gli script Python modificati;
- verificare che siano presenti solo Facebook e Instagram nel nuovo flusso automatico;
- verificare che il post mattutino sia `carousel` e quello serale `reel`;
- verificare che `approval_required` e `manual_approval_required` siano falsi per i job generati;
- verificare che ogni job abbia ID deterministico per data+slot;
- verificare che un job `published` generi NOOP e non venga ripubblicato;
- verificare che `partially_published` mantenga l'elenco delle piattaforme già pubblicate e ritenti soltanto le mancanti;
- verificare che i token non siano mai scritti nei file del repository;
- verificare che errori Meta restituiscano exit code non zero;
- correggere autonomamente qualsiasi problema trovato prima del rilascio.

## Risultato richiesto

Il sistema deve essere pronto a partire e lavorare in autonomia ogni giorno. Non chiedere conferme intermedie e non introdurre dipendenze a pagamento.
