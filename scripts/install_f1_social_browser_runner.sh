#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Run as root: sudo -E bash scripts/install_f1_social_browser_runner.sh"
  exit 2
fi

: "${GITHUB_REPOSITORY_URL:=https://github.com/josephsocialmedia2-spec/open-social-scheduler}"
: "${F1_RUNNER_LABELS:=f1-social-browser,linux}"
: "${F1_BROWSER_ROOT:=/srv/f1social/browser-profiles}"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y   ca-certificates curl jq git python3 python3-venv python3-pip nodejs npm xvfb   libnss3 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2t64 fonts-liberation

id -u f1social >/dev/null 2>&1 || useradd --create-home --shell /bin/bash f1social
mkdir -p "$F1_BROWSER_ROOT" /opt/f1-actions-runner
chown -R f1social:f1social /srv/f1social /opt/f1-actions-runner

python3 -m venv /opt/f1-browser-venv
/opt/f1-browser-venv/bin/pip install --upgrade pip
/opt/f1-browser-venv/bin/pip install 'requests==2.32.5' 'playwright>=1.55,<2'
/opt/f1-browser-venv/bin/python -m playwright install --with-deps chromium

if [ ! -x /opt/f1-actions-runner/run.sh ]; then
  RUNNER_VERSION=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r '.tag_name' | sed 's/^v//')
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64) RUNNER_ARCH=x64 ;;
    aarch64|arm64) RUNNER_ARCH=arm64 ;;
    *) echo "Unsupported architecture: $ARCH"; exit 3 ;;
  esac
  curl -fsSL -o /tmp/actions-runner.tgz     "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
  tar -xzf /tmp/actions-runner.tgz -C /opt/f1-actions-runner
  chown -R f1social:f1social /opt/f1-actions-runner
fi

if [ ! -f /opt/f1-actions-runner/.runner ]; then
  if [ -z "${GITHUB_RUNNER_TOKEN:-}" ]; then
    cat <<EOF
Dependencies are installed. Runner registration still needs a one-time token.
Open:
${GITHUB_REPOSITORY_URL}/settings/actions/runners/new
Then rerun this script with:
GITHUB_RUNNER_TOKEN=<temporary-token> sudo -E bash scripts/install_f1_social_browser_runner.sh
EOF
    exit 10
  fi
  sudo -u f1social bash -lc     "cd /opt/f1-actions-runner && ./config.sh --unattended --url '$GITHUB_REPOSITORY_URL' --token '$GITHUB_RUNNER_TOKEN' --name 'f1-social-browser-$(hostname)' --labels '$F1_RUNNER_LABELS' --work '_work'"
fi

cd /opt/f1-actions-runner
./svc.sh install f1social || true
./svc.sh start
./svc.sh status || true

cat >/etc/profile.d/f1-social-browser.sh <<EOF
export F1_BROWSER_ROOT="$F1_BROWSER_ROOT"
export PATH="/opt/f1-browser-venv/bin:\$PATH"
EOF
chmod 0644 /etc/profile.d/f1-social-browser.sh

echo "F1 Social browser runner installed. Browser root: $F1_BROWSER_ROOT"
