#!/usr/bin/env bash
set -euo pipefail

POSTIZ_VERSION="${POSTIZ_VERSION:-v2.22.1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$ROOT/vendor"
APP_DIR="$VENDOR/postiz-app"
COMPOSE_DIR="$VENDOR/postiz-docker-compose"

mkdir -p "$VENDOR"

clone_or_update() {
  local repo="$1"
  local dir="$2"
  local ref="$3"
  if [ -d "$dir/.git" ]; then
    git -C "$dir" fetch --depth 1 origin "$ref"
    git -C "$dir" checkout --detach FETCH_HEAD
  else
    git clone --depth 1 --branch "$ref" "$repo" "$dir"
  fi
}

# Runtime/deployment repository maintained by Postiz.
if [ -d "$COMPOSE_DIR/.git" ]; then
  git -C "$COMPOSE_DIR" pull --ff-only
else
  git clone --depth 1 https://github.com/gitroomhq/postiz-docker-compose.git "$COMPOSE_DIR"
fi

# Source clone kept separate for audit/development and AGPL compliance.
clone_or_update "https://github.com/gitroomhq/postiz-app.git" "$APP_DIR" "$POSTIZ_VERSION"

printf 'Postiz source: %s\n' "$(git -C "$APP_DIR" rev-parse --short HEAD)"
printf 'Postiz compose: %s\n' "$(git -C "$COMPOSE_DIR" rev-parse --short HEAD)"
printf 'Pinned version: %s\n' "$POSTIZ_VERSION"

cat <<'EOF'
Clone complete.
Next:
  1. copy postiz.env.example to postiz.env
  2. fill domain/JWT/provider OAuth credentials
  3. run ./start_postiz.sh
EOF
