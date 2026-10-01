# Troubleshooting — Connection Doctor

- `NON_COLLEGATO`: run OAuth from Connect.
- `TOKEN_SCADUTO`: reconnect; do not reuse an expired token.
- `DA_RIAUTORIZZARE`: repeat provider consent.
- `PERMESSI_INSUFFICIENTI`: authorize the publishing scope required by that provider.
- `ACCOUNT_ERRATO`: choose the client's actual account/Page.
- `ACCOUNT_CONDIVISO`: the same provider ID is attached to multiple clients; select the intended account.
- `SERVER_CONFIG_MISSING`: provider app credentials/callback are not configured server-side.
- `LINKEDIN_PAGE_REQUIRED`: a member profile was authorized where an organization Page is required.

Never solve these errors by storing the client's password or by browser automation that bypasses the provider API.
