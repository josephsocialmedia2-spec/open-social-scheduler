# Deployment

## Frontend
The production frontend is the existing GitHub Pages deployment under `f1-content-hub/`. Merge to the default branch, then let the repository Pages workflow publish the static files.

## Database
Apply `supabase/migrations/20261001_later_personal_manager.sql` to the existing project.

## Edge Function
Deploy `supabase/functions/f1-social-oauth/index.ts` as `f1-social-oauth`. The function already uses custom authentication for admin/service routes and has public invitation routes protected by high-entropy expiring invite tokens.

## Smoke checks
1. Open Content Hub and authenticate.
2. Confirm only active clients appear in the dashboard.
3. Run Connection Doctor on a client.
4. Generate an invite and open it in a private window.
5. Verify the provider redirects to its official consent page.
6. Do not mark a channel connected unless provider verification succeeds.
