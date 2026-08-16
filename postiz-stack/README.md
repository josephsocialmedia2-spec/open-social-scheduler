# Postiz runtime for Open Social Scheduler

This directory integrates Postiz as a **separate network service**. Open Social Scheduler remains the multi-client controller; Postiz handles OAuth, scheduling and provider APIs.

## Why it is isolated

Postiz is licensed under AGPL-3.0. The source and official compose repositories are cloned at deployment time into `postiz-stack/vendor/` and are not vendored into this repository. Preserve all upstream notices and comply with the Postiz AGPL terms when modifying or exposing a modified Postiz instance over a network.

Upstream:
- https://github.com/gitroomhq/postiz-app
- https://github.com/gitroomhq/postiz-docker-compose

Pinned application release: `v2.22.1`.

## Install on an always-on Linux host

```bash
bash postiz-stack/bootstrap_postiz.sh
cp postiz-stack/postiz.env.example postiz-stack/postiz.env
# edit postiz.env
bash postiz-stack/start_postiz.sh
```

The official stack includes Postiz, PostgreSQL, Redis and Temporal. Put an HTTPS reverse proxy in front of Postiz before configuring production OAuth providers.

## Social provider credentials

Configure provider applications in `postiz.env`. The credentials belong to the Postiz server and must never be committed.

For the initial OSS target:
- Meta: `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` (Facebook + FB-linked Instagram)
- LinkedIn: `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`
- YouTube: `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`
- TikTok: `TIKTOK_CLIENT_ID`, `TIKTOK_CLIENT_SECRET`
- Pinterest: `PINTEREST_CLIENT_ID`, `PINTEREST_CLIENT_SECRET`

After restart, connect each client channel through OAuth in Postiz. Then copy the exact integration IDs into `publisher/clients/<client>.json` or run the integration discovery helper.

## Open Social Scheduler connection

GitHub Actions needs only:
- secret `POSTIZ_API_KEY`
- variable `POSTIZ_API_URL`, e.g. `https://social.example.com/public/v1`

The social-provider App Secrets stay on the Postiz host, not in GitHub Actions.

## Security rule

Open Social Scheduler never chooses a social account merely because it is the first Facebook or Instagram integration it sees. Production jobs require an explicit integration ID per client/platform. This is deliberate tenant isolation.
