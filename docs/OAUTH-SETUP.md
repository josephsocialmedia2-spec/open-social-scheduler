# OAuth Setup

Broker base:
`https://nqnmlsmeiynxbdojeyjt.supabase.co/functions/v1/f1-social-oauth`

Callbacks:
- Facebook: `/callback/facebook`
- Instagram: `/callback/instagram`
- TikTok: `/callback/tiktok`
- YouTube: `/callback/youtube`
- LinkedIn: `/callback/linkedin`

Secrets stay in Supabase Edge Function secrets, never GitHub Pages.

Required publishing scopes are validated at runtime:
- Facebook: `pages_manage_posts`
- Instagram: `instagram_content_publish`
- TikTok: `video.publish`
- YouTube: `https://www.googleapis.com/auth/youtube.upload`
- LinkedIn Page: `w_organization_social`

Meta/TikTok/Google/LinkedIn can require provider-side app review, testing users, business verification or product access before production use. The app must report those as external requirements instead of simulating success.
