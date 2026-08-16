#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="$ROOT/vendor/postiz-docker-compose/docker-compose.yaml"
ENV_FILE="$ROOT/postiz.env"
OVERRIDE="$ROOT/docker-compose.override.yml"

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

for required in MAIN_URL FRONTEND_URL NEXT_PUBLIC_BACKEND_URL JWT_SECRET; do
  if [ -z "${!required:-}" ] || [[ "${!required}" == CHANGE_ME* ]]; then
    echo "Missing/unsafe required variable: $required" >&2
    exit 2
  fi
done

docker compose --env-file "$ENV_FILE" -f "$COMPOSE" -f "$OVERRIDE" config >/dev/null
docker compose --env-file "$ENV_FILE" -f "$COMPOSE" -f "$OVERRIDE" up -d

echo "Postiz started at $FRONTEND_URL"
