#!/bin/bash
# Open the client in Electron (Chromium) instead of a browser, on the desktop, pointed at the dev server (run_dev.sh must be running).
# The Electron binary and the desktop shell are built once (first run); later runs just start it. Stop: close the window.
HERE="$(cd "$(dirname "$0")/.." && pwd)"; source "$HERE/scripts/env.sh"
TREE="$PRIME_WORK/client_build/tree"
[ -x "$TREE/node_modules/electron/dist/electron" ] || (cd "$TREE/node_modules/electron" && node install.js)
[ -f "$TREE/apps/desktop/out/main.cjs" ] || (cd "$TREE/apps/desktop" && npm run build)
curl -s -o /dev/null http://127.0.0.1:5173/ || "$HERE/scripts/run_dev.sh"
LOG="$PRIME_WORK/client_build/electron.log"
(setsid nohup flatpak-spawn --host env SHARDS_DEV_URL=http://127.0.0.1:5173 "$TREE/node_modules/electron/dist/electron" "$TREE/apps/desktop" --no-sandbox --disable-gpu-sandbox > "$LOG" 2>&1 &)
sleep 6; tail -5 "$LOG"; echo "electron started (log: $LOG)"
