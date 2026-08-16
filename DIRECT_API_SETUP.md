# Direct Social API — zero-subscription setup

This repository can publish without Postiz. GitHub Actions is the controller and official social APIs are the transport.

## Approval model

No scheduled workflow publishes content. `Open Social Engine Daily - Prepare Only` prepares the queue and opens a GitHub issue. The repository owner confirms from that issue:

- `/check JOB_ID` checks whether the required OAuth secrets are present, without publishing.
- `/publish JOB_ID` is the explicit publication confirmation.

The approval command dispatches `Publish Social - CONFIRM REQUIRED` automatically.

## Separate credentials per brand

F1 Immobiliare uses the `F1_` prefix. Real Media Pro uses the `RMP_` prefix.

For each brand configure these GitHub Secrets as needed:

- `<PREFIX>_FACEBOOK_PAGE_ACCESS_TOKEN`
- `<PREFIX>_INSTAGRAM_ACCESS_TOKEN`
- `<PREFIX>_INSTAGRAM_USER_ID`
- `<PREFIX>_TIKTOK_ACCESS_TOKEN`
- `<PREFIX>_LINKEDIN_ACCESS_TOKEN`
- `<PREFIX>_LINKEDIN_AUTHOR_URN`
- `<PREFIX>_YOUTUBE_CLIENT_ID`
- `<PREFIX>_YOUTUBE_CLIENT_SECRET`
- `<PREFIX>_YOUTUBE_REFRESH_TOKEN`
- `<PREFIX>_PINTEREST_ACCESS_TOKEN`
- `<PREFIX>_PINTEREST_BOARD_ID`

Recommended repository Variables:

- `META_GRAPH_VERSION=v23.0`
- `LINKEDIN_VERSION=202601`
- `TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE`
- `YOUTUBE_PRIVACY_STATUS=private` during first tests; switch to `public` only when the Google API project is eligible for public uploads.
- `PINTEREST_LINK=https://f1immobiliare.com/` for F1, or omit it until brand-specific link variables are added.

## Platform behavior

- Facebook: local MP4 is uploaded as a Page Reel using the Meta Graph API.
- Instagram: the approved MP4 is temporarily exposed as a GitHub Release asset, used to create the Reel container, then the temporary asset is removed.
- TikTok: local MP4 is transferred with Content Posting API `FILE_UPLOAD` after creator-info validation.
- LinkedIn: organic text post on the configured member or organization URN.
- YouTube: resumable upload using OAuth 2.0 refresh credentials.
- Pinterest: the first video frame becomes a JPEG Pin sent as base64 media.

## Facebook Groups

Facebook Groups are deliberately outside `direct_api_publish.py`. Meta removed the general Groups API and `publish_to_groups` capability. The group radar can find, deduplicate, classify, queue and track groups/content, while join requests and final group posting remain explicit Facebook UI actions.

## Security

Never commit access tokens, refresh tokens, client secrets or account passwords to the repository. Store them only as GitHub Actions Secrets.
