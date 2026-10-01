# Test Report — Later Personal Manager

## Automated coverage
- active vs archived client filtering
- green state
- one-disconnected orange state
- two-disconnected red state
- expired-token red state
- no-scheduled-post red state
- no-new-content red state
- Edge Function TypeScript check
- invite security contract (session storage only for temporary raw invite; DB stores token hash)
- LinkedIn organization publishing scope contract

CI workflow: `.github/workflows/later-personal-manager-qa.yml`.

This report is finalized only after the branch workflow passes and deployment smoke checks complete.
