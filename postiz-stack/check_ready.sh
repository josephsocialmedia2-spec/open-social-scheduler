#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT/postiz.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

DOMAIN="${POSTIZ_DOMAIN:?POSTIZ_DOMAIN is required}"
BASE="https://$DOMAIN"

echo "Checking DNS..."
getent ahostsv4 "$DOMAIN" | head -n 3 || true

echo
echo "Checking HTTPS..."
curl -fsSIL --max-time 20 "$BASE" | head -n 12

echo
echo "Checking API route..."
API_STATUS="$(curl -sS -o /tmp/postiz-api-check.txt -w '%{http_code}' --max-time 20 "$BASE/api" || true)"
echo "GET $BASE/api -> HTTP $API_STATUS"

if [ -n "${POSTIZ_API_KEY:-}" ]; then
  echo
echo "Checking Public API integrations..."
  curl -fsS --max-time 30 \
    -H "Authorization: $POSTIZ_API_KEY" \
    "$BASE/public/v1/integrations" | python3 -m json.tool | head -n 80
else
  echo
echo "POSTIZ_API_KEY not present in postiz.env; authenticated Public API check skipped."
fi

echo
echo "Checking containers..."
export POSTIZ_STACK_DIR="$ROOT"
docker compose \
  --env-file "$ENV_FILE" \
  -f "$ROOT/vendor/postiz-docker-compose/docker-compose.yaml" \
  -f "$ROOT/docker-compose.override.yml" \
  -f "$ROOT/docker-compose.production.yml" \
  ps
