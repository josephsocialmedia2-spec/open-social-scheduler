#!/usr/bin/env bash
set -euo pipefail

DISPLAY=:99
VNC_PORT=5901
NOVNC_PORT=6080
STATE_DIR=/tmp/f1-social-desktop
mkdir -p "$STATE_DIR"

start_if_missing() {
  local name="$1"; shift
  local pidfile="$STATE_DIR/$name.pid"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    return 0
  fi
  "$@" >"$STATE_DIR/$name.log" 2>&1 &
  echo $! >"$pidfile"
}

start_if_missing xvfb Xvfb "$DISPLAY" -screen 0 1440x1000x24 -nolisten tcp -ac
sleep 1
export DISPLAY
start_if_missing openbox openbox
start_if_missing x11vnc x11vnc -display "$DISPLAY" -localhost -nopw -forever -shared -rfbport "$VNC_PORT"
sleep 1

NOVNC_WEB=/usr/share/novnc
if [ ! -d "$NOVNC_WEB" ]; then
  echo "noVNC web root not found at $NOVNC_WEB"
  exit 3
fi
start_if_missing novnc websockify --web="$NOVNC_WEB" 127.0.0.1:6080 127.0.0.1:5901

cat <<'EOF'
F1 Social cloud login desktop is running locally on the VPS only.

Create an SSH tunnel FROM YOUR COMPUTER:
  ssh -L 6080:127.0.0.1:6080 <VPS_USER>@<VPS_IP>

Then open in your local browser:
  http://127.0.0.1:6080/vnc.html

On the VPS, in another shell:
  export DISPLAY=:99
  source /opt/f1-browser-venv/bin/activate
  cd <open-social-scheduler>
  export SUPABASE_SERVICE_ROLE_KEY='<protected backend value>'
  python scripts/f1_browser_session.py <client-slug> <platform>

The noVNC/VNC ports are bound to 127.0.0.1 and are not exposed publicly.
EOF
