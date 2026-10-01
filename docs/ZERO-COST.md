# Zero Cost Guard

The implementation introduces no paid API or automatic upgrade.

## Current free resources
The design reuses the repository's GitHub Pages/Actions and the existing Supabase project. Free tiers have hard limits; they are not treated as infinite capacity.

The `f1_free_quota_usage` registry is the source for operational blocking:
- below 70%: normal
- 70–84.99%: information
- 85–94.99%: warning
- 95% or more: block non-essential new usage before a paid transition can occur

## Rules
- Never enable pay-as-you-go automatically.
- Never activate a paid trial as a fallback.
- If storage/database/egress/function quota is near the blocking threshold, stop new non-essential uploads/jobs and keep existing data intact.
- Provider app review/verification is an external permission process, not a paid fallback.
