#!/usr/bin/env bash
set -euo pipefail

fail=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "OK   $label"
  else
    echo "FAIL $label"
    fail=1
  fi
}

check "git" command -v git
check "python3" command -v python3
check "Chromium Playwright env" test -x /opt/f1-browser-venv/bin/python
check "GitHub runner" test -x /opt/f1-actions-runner/run.sh
check "Browser profile root" test -d /srv/f1social/browser-profiles
check "noVNC helper" test -f scripts/start_f1_browser_desktop.sh
check "Cloud publisher module" test -f publisher/cloud_publisher/main.py

if systemctl list-units --type=service --all | grep -q 'actions.runner'; then
  echo "OK   GitHub Actions runner service detected"
else
  echo "WARN GitHub Actions runner service not detected"
fi

if ss -lnt | grep -Eq '0\.0\.0\.0:(5901|6080)|\[::\]:(5901|6080)'; then
  echo "FAIL VNC/noVNC exposed publicly"
  fail=1
else
  echo "OK   VNC/noVNC not publicly exposed"
fi

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "F1 Social cloud browser host checks passed."
