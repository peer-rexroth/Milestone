#!/bin/bash
# Launches Milestone on a local server (needed for PWA install/offline
# support, which browsers refuse to enable for file:// pages) and opens it
# in Chrome or Edge — Safari doesn't support installing this kind of PWA on
# macOS.
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT=8937
PID_FILE="$DIR/.milestone-server.pid"
LOG_FILE="$DIR/.milestone-server.log"
URL="http://127.0.0.1:$PORT/milestone.html"

is_up() {
  curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$PORT/manifest.json"
}

if ! is_up; then
  # Clear a stale pid file from a server that's no longer running.
  if [ -f "$PID_FILE" ] && ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    rm -f "$PID_FILE"
  fi
  if [ -f "$PID_FILE" ]; then
    echo "Port $PORT looks busy with something other than Milestone. Edit PORT in this script to change it."
  else
    nohup python3 -m http.server "$PORT" --bind 127.0.0.1 > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Started Milestone server on $URL (pid $(cat "$PID_FILE"))"
    sleep 0.6
  fi
fi

if [ -d "/Applications/Google Chrome.app" ]; then
  open -a "Google Chrome" "$URL"
elif [ -d "/Applications/Microsoft Edge.app" ]; then
  open -a "Microsoft Edge" "$URL"
else
  echo "Neither Chrome nor Edge found in /Applications — opening your default browser instead."
  echo "Install/offline support needs Chrome or Edge; Safari doesn't support it for this kind of app."
  open "$URL"
fi
