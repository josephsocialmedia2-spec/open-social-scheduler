# F1 Social Autonomous Cloud

This layer runs without the user's PC for ordinary operations.

## Flow

WhatsApp Business webhook -> f1_content_inbox -> f1-content-autopilot -> f1_content_items / f1_content_calendar -> existing API publishers -> verified publication state -> one daily report.

The browser fallback remains disabled until a persistent cloud browser host is provisioned and each client session is individually verified.

## WhatsApp requirements

The webhook uses only the official WhatsApp Business Platform. Required Supabase Edge Function secrets:

- WHATSAPP_VERIFY_TOKEN
- WHATSAPP_APP_SECRET
- WHATSAPP_ACCESS_TOKEN
- WHATSAPP_PHONE_NUMBER_ID
- META_GRAPH_VERSION

Never commit their values.

Each authorized number must exist in f1_whatsapp_senders and should have a deterministic client_id. auto_process controls automatic intake. report_recipient selects the number that receives the end-of-day report. Operational receipt messages are suppressed.

## Autonomous decisions

The autopilot uses each client's publishing_preferences and only schedules a platform when a usable route exists:

- API: enabled + verified + COLLEGATO + no reauthorization.
- Browser: READY profile + CONNECTED platform session.

Temporary processing errors retry automatically. Permanent ambiguities become NEEDS_REVIEW without stopping other clients.

## Daily report

The report function is invoked by GitHub every five minutes but only produces the report at 23:00 Europe/Rome, unless manually forced. It stores the report in f1_social_daily_reports and sends it through WhatsApp when a report recipient and valid WhatsApp Business credentials are configured.

## Safety

No passwords, cookies or tokens are stored in GitHub or normal database tables. The WhatsApp webhook validates the Meta HMAC signature. Duplicate message IDs and duplicate content hashes are blocked.
