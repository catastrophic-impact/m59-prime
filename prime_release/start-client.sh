#!/usr/bin/env bash
# Start the web client for this machine: the gateway (browser <-> game server) and a small web server. Then open the printed address in a browser.
# Stop it with ./stop-all.sh.   Other computers on your network:  M59_WEB_HOST=0.0.0.0 ./start-client.sh  (then use this computer's address)
HERE="$(cd "$(dirname "$0")" && pwd)"; NODE="$HERE/runtime/node"
WEB_PORT="${M59_WEB_PORT:-8080}"; WEB_HOST="${M59_WEB_HOST:-127.0.0.1}"; GW_PORT="${M59_GATEWAY_PORT:-8059}"; GAME_PORT="${M59_GAME_PORT:-5960}"   # (change them only when another program uses these ports)
[ -x "$NODE" ] || { echo "runtime/node is missing"; exit 1; }
if [ -f "$HERE/client.pids" ] && kill -0 "$(head -1 "$HERE/client.pids")" 2>/dev/null; then echo "the client is already running: http://$WEB_HOST:$WEB_PORT"; exit 0; fi
cd "$HERE/client" || exit 1
# game files, the arena season file and everything the gateway writes stay inside this folder
GATEWAY_TRUST_PROXY=1 ARENA_ASSETS="$HERE/client/web/assets" ARENA_STATE="$HERE/client/arena-state.json" \
  nohup "$NODE" gateway.mjs --port "$GW_PORT" --server 127.0.0.1:$GAME_PORT >gateway.log 2>&1 & GW=$!
nohup "$NODE" serve.mjs --port "$WEB_PORT" --host "$WEB_HOST" --dir "$HERE/client/web" --gateway 127.0.0.1:$GW_PORT >web.log 2>&1 & WEB=$!
printf '%s\n%s\n' "$GW" "$WEB" > "$HERE/client.pids"
sleep 2
kill -0 "$GW" 2>/dev/null && kill -0 "$WEB" 2>/dev/null || { echo "the client did not start: see client/gateway.log and client/web.log"; exit 1; }
echo "client running: open  http://$WEB_HOST:$WEB_PORT  in a browser (any account name and password you type on first login is created)"
