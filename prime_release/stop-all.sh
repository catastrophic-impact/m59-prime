#!/usr/bin/env bash
# Stop the client and the server. The game is saved first.
HERE="$(cd "$(dirname "$0")" && pwd)"; export PRIME_ADMIN_PORT="${PRIME_ADMIN_PORT:-9999}"
if [ -f "$HERE/client.pids" ]; then while read -r p; do kill "$p" 2>/dev/null; done < "$HERE/client.pids"; rm -f "$HERE/client.pids"; echo "client stopped"; fi
if (echo > /dev/tcp/127.0.0.1/"$PRIME_ADMIN_PORT") 2>/dev/null; then python3 "$HERE/tools/admin_prime.py" "save game" >/dev/null 2>&1; echo "game saved"; fi
# blakserv runs as a parent and a child process: stop both
if [ -f "$HERE/server.pid" ]; then p="$(cat "$HERE/server.pid")"; pkill -P "$p" 2>/dev/null; kill "$p" 2>/dev/null; rm -f "$HERE/server.pid"; echo "server stopped"; fi
