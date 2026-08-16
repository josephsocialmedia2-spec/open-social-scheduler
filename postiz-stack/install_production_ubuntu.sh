#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID}" -ne 0 ]; then
  echo "Run as root: sudo bash postiz-stack/install_production_ubuntu.sh" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOMAIN="${POSTIZ_DOMAIN:-social.realmediapro.it}"
ENV_FILE="$ROOT/postiz.env"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git curl ca-certificates docker.io openssl python3
if apt-cache show docker-compose-v2 >/dev/null 2>&1; then
  apt-get install -y docker-compose-v2
elif apt-cache show docker-compose-plugin >/dev/null 2>&1; then
  apt-get install -y docker-compose-plugin
else
  echo "Docker Compose v2 package not found in configured apt repositories." >&2
  exit 2
fi
systemctl enable --now docker

docker compose version

bash "$ROOT/bootstrap_postiz.sh"

if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT/postiz.env.example" "$ENV_FILE"
fi

JWT_SECRET="$(openssl rand -hex 48)"
python3 - "$ENV_FILE" "$DOMAIN" "$JWT_SECRET" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
domain = sys.argv[2]
jwt = sys.argv[3]
lines = path.read_text(encoding='utf-8').splitlines()
updates = {
    'POSTIZ_DOMAIN': domain,
    'MAIN_URL': f'https://{domain}',
    'FRONTEND_URL': f'https://{domain}',
    'NEXT_PUBLIC_BACKEND_URL': f'https://{domain}/api',
}
existing_jwt = ''
for line in lines:
    if line.startswith('JWT_SECRET='):
        existing_jwt = line.split('=', 1)[1].strip()
if not existing_jwt or existing_jwt.startswith('CHANGE_ME'):
    updates['JWT_SECRET'] = jwt

out = []
seen = set()
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key = line.split('=', 1)[0]
        if key in updates:
            out.append(f'{key}={updates[key]}')
            seen.add(key)
            continue
    out.append(line)
for key, value in updates.items():
    if key not in seen and not any(x.startswith(key + '=') for x in out):
        out.append(f'{key}={value}')
path.write_text('\n'.join(out) + '\n', encoding='utf-8')
PY

chmod 600 "$ENV_FILE"

SERVER_IP="$(curl -4fsS --max-time 10 https://api.ipify.org || true)"
DNS_IP="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1 {print $1}')"

echo
if [ -n "$SERVER_IP" ]; then
  echo "Server public IPv4: $SERVER_IP"
fi
if [ -n "$DNS_IP" ]; then
  echo "$DOMAIN currently resolves to: $DNS_IP"
else
  echo "$DOMAIN does not currently resolve to an IPv4 address."
fi

if [ -n "$SERVER_IP" ] && [ "$DNS_IP" != "$SERVER_IP" ]; then
  cat <<EOF

DNS ACTION REQUIRED BEFORE HTTPS CAN WORK:
Create/update an A record:
  host: social
  value: $SERVER_IP

If your DNS provider uses another hostname, set POSTIZ_DOMAIN before rerunning this installer.
The stack can be prepared now, but Caddy cannot issue a certificate until DNS points here.
EOF
fi

bash "$ROOT/start_postiz.sh"

cat <<EOF

Production stack launched.
Open: https://$DOMAIN
Environment file: $ENV_FILE

Next manual security/OAuth steps:
1. Open Postiz and create/login to the administrator account.
2. Keep registration disabled after the administrator exists.
3. Configure provider App IDs/Secrets in $ENV_FILE and restart with start_postiz.sh.
4. Connect F1 Immobiliare channels through the provider OAuth screens.
5. Create a Postiz Public API key and store it in GitHub as POSTIZ_API_KEY.
EOF
