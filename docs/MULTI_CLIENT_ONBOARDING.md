# Onboarding di un nuovo cliente Social Engine

## 1. Crea il tenant

Copia `publisher/clients/_template.json` in:

`publisher/clients/<slug-cliente>.json`

Imposta almeno:
- `id`
- `name`
- `timezone`
- brand/layout
- campagna/CTA
- orari
- piattaforme desiderate

## 2. Crea la banca contenuti

Crea:

`publisher/content_bank/<slug-cliente>.json`

La struttura standard usa quattro categorie:
- `attract`
- `nurture`
- `hyperlocal`
- `convert`

Ogni voce può contenere `slug`, `title`, `slides`, `caption`. Sono supportati i token `{territory}`, `{cta}`, `{client}`.

## 3. Collega gli account in Postiz

Nel workspace/customer Postiz del cliente completa OAuth per i provider desiderati. Non salvare token o password in Open Social Scheduler.

## 4. Associa gli integration ID

Esegui in discovery:

```bash
POSTIZ_API_KEY=... POSTIZ_API_URL=https://.../public/v1 \
python publisher/discover_integrations.py
```

Se il `postiz_customer_name` coincide esattamente e c'è un solo account per provider, puoi scrivere automaticamente gli ID:

```bash
python publisher/discover_integrations.py --write
```

Se ci sono più account dello stesso provider, inserisci manualmente l'ID corretto nel JSON del tenant. Il motore non sceglie mai in modo ambiguo.

## 5. Attiva

Imposta `active: true`. Il workflow giornaliero creerà quattro job, renderizzerà i Reel e invierà a Postiz soltanto i provider con ID configurato. Se un provider marcato `required` non è configurato, l'intero job resta bloccato.

## 6. Stato job

- `draft` — creato ma non ancora riconciliato
- `awaiting_media` — video non ancora renderizzato
- `awaiting_integrations` — mancano ID social obbligatori
- `ready` — media + tenant + integrazioni validi
- `scheduled` — consegnato a Postiz
- `error` — errore di upload/API/provider

## 7. Analytics

Il workflow `Social Analytics Snapshot` usa gli integration ID configurati e salva uno snapshot per cliente in `publisher/analytics/<cliente>.json` quando la chiave Postiz è disponibile.
