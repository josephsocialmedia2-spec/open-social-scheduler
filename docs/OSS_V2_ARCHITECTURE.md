# Open Social Scheduler 2.0 — Control Center architecture

## Obiettivo
Trasformare il repository da insieme di script/workflow in un Social Operating System multi-cliente con stato persistente, API centrale, publisher sostituibili e analytics misurabili.

## Principi
- PostgreSQL come fonte primaria dei dati in produzione.
- SQLite solo per sviluppo locale/smoke test.
- Google Drive resta archivio/import-export, non fonte di verità operativa.
- GitHub Actions resta CI/CD e automazione di supporto, non database.
- Postiz resta un adapter di pubblicazione, non il cuore del dominio.
- Ogni contenuto ha stato esplicito e audit dei tentativi di pubblicazione.

## Stato contenuti
DRAFT -> READY -> APPROVED -> SCHEDULED -> PUBLISHING -> PUBLISHED

Stati eccezione: FAILED, RETRY, BLOCKED, CANCELLED.

## Modello dati iniziale
- Client
- SocialAccount
- ContentItem
- PublishAttempt
- AnalyticsSnapshot

## Adapter publishing
Il campo `publisher_adapter` permette di mantenere Postiz oggi e introdurre successivamente adapter diretti Meta/LinkedIn/TikTok senza cambiare il modello dati o la dashboard.

## API iniziali
- GET /health
- GET /api/control-center
- GET/POST /api/clients
- GET/POST /api/social-accounts
- GET/POST /api/content
- PATCH /api/content/{id}/status

## Migrazione
Fase 1: backend e schema persistente senza modificare il publisher legacy.
Fase 2: import di `publisher/clients/*.json`, queue e content bank nel database.
Fase 3: adapter Postiz/Direct API leggono dal database e scrivono PublishAttempt.
Fase 4: dashboard unica usa `/api/control-center` e API dominio.
Fase 5: analytics confluiscono in AnalyticsSnapshot e alimentano scoring/apprendimento.

## Compatibilità
Durante la migrazione gli script esistenti continuano a funzionare. Nessun workflow di pubblicazione viene rimosso in questa prima fase.
