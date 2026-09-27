# DigitalOcean deployment runbook for F1 Social

This runbook provisions only the VPS substrate. It does not place passwords, OAuth tokens, cookies, CAPTCHA data or Supabase service-role values in GitHub.

## Target

- Ubuntu 24.04 LTS
- 2 vCPU minimum
- 4 GB RAM minimum
- 40 GB SSD minimum
- public inbound firewall: SSH/22 only
- persistent browser data: /srv/f1social/browser-profiles

## Provisioning

Use `deploy/digitalocean-cloud-init.yaml` as user-data when creating the Droplet.

After the Droplet is reachable:

```bash
ssh f1admin@<DROPLET_IP>
cd /opt/f1social/open-social-scheduler
sudo -E bash scripts/install_f1_social_browser_runner.sh
```

The installer intentionally stops if the one-time GitHub runner token has not been provided.

Generate the temporary runner token from:

`https://github.com/josephsocialmedia2-spec/open-social-scheduler/settings/actions/runners/new`

Then rerun:

```bash
export GITHUB_RUNNER_TOKEN='<temporary runner token>'
sudo -E bash scripts/install_f1_social_browser_runner.sh
```

Do not commit the token.

## Backend secret

The publication worker needs `SUPABASE_SERVICE_ROLE_KEY` at runtime. Keep it only in the protected runner/service environment or GitHub Actions secret. Never place it in cloud-init, repository files, browser JavaScript or documentation.

## One-time social login

```bash
cd /opt/f1social/open-social-scheduler
bash scripts/start_f1_browser_desktop.sh
```

Create the SSH tunnel printed by the script, then run:

```bash
export DISPLAY=:99
source /opt/f1-browser-venv/bin/activate
export SUPABASE_SERVICE_ROLE_KEY='<protected value>'
python scripts/f1_browser_session.py antica-cappella facebook
```

Repeat only for the client/platform combinations that need browser fallback.

## Enable automatic browser fallback

After the self-hosted runner is online and at least one browser social session has been verified, set repository variable:

`F1_BROWSER_FALLBACK_ENABLED=true`

Before enabling production clicks, run the workflow manually with `dry_run=true`.

## Host validation

```bash
cd /opt/f1social/open-social-scheduler
bash scripts/check_f1_browser_host.sh
```
