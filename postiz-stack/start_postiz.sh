#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="$ROOT/vendor/postiz-docker-compose/docker-compose.yaml"
ENV_FILE="$ROOT/postiz.env"
OVERRIDE="$ROOT/docker-compose.override.yml"
PRODUCTION="$ROOT/docker-compose.production.yml"

if [ ! -f "$COMPOSE" ]; then
  echo "Postiz upstream not cloned. Run: bash postiz-stack/bootstrap_postiz.sh" >&2
  exit 2
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy postiz.env.example and configure it first." >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

for required in POSTIZ_DOMAIN MAIN_URL FRONTEND_URL NEXT_PUBLIC_BACKEND_URL JWT_SECRET; do
  if [ -z "${!required:-}" ] || [[ "${!required}" == CHANGE_ME* ]]; then
    echo "Missing/unsafe required variable: $required" >&2
    exit 2
  fi
done

if [ "$MAIN_URL" != "https://$POSTIZ_DOMAIN" ] || [ "$FRONTEND_URL" != "https://$POSTIZ_DOMAIN" ]; then
  echo "MAIN_URL and FRONTEND_URL must both equal https://$POSTIZ_DOMAIN" >&2
  exit 2
fi
if [ "$NEXT_PUBLIC_BACKEND_URL" != "https://$POSTIZ_DOMAIN/api" ]; then
  echo "NEXT_PUBLIC_BACKEND_URL must equal https://$POSTIZ_DOMAIN/api" >&2
  exit 2
fi

export POSTIZ_STACK_DIR="$ROOT"

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE" \
  -f "$OVERRIDE" \
  -f "$PRODUCTION" \
  config >/dev/null

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE" \
  -f "$OVERRIDE" \
  -f "$PRODUCTION" \
  up -d

echo "Postiz started at $FRONTEND_URL"
echo "HTTPS certificate will be issued automatically by Caddy when DNS for $POSTIZ_DOMAIN points to this server and ports 80/443 are reachable."
