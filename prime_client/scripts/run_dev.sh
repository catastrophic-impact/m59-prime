#!/bin/bash
# Start the gateway (ws 8059 -> Prime server 5960) and the dev web server (http://127.0.0.1:5173) in the background.  Stop: stop_dev.sh
HERE="$(cd "$(dirname "$0")/.." && pwd)"; source "$HERE/scripts/env.sh"
TREE="$PRIME_WORK/client_build/tree"; LOG="$PRIME_WORK/client_build"
python3 "$HERE/../prime_server/scripts/sync_client_strings.py"
cd "$TREE"
(setsid nohup node tools/gateway/gateway.ts --server 127.0.0.1:5960 > "$LOG/gateway.log" 2>&1 &)
cd apps/client; (setsid nohup npx vite > "$LOG/vite.log" 2>&1 &)
sleep 8; curl -s -o /dev/null -w "client: http://127.0.0.1:5173 (%{http_code})\n" http://127.0.0.1:5173/
