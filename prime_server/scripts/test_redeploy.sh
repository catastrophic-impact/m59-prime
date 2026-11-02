#!/bin/bash
# Deploy the freshly compiled kod (build/tree) to the SECOND test server (build/server2, ports 5961/9998) and restart only it. Never touches the owner's server.
# Compile first: cp -a overlay/. $WORK/build/tree/ && (in the box) cd $WORK/build/tree && make -f makefile.linux Bkod RELEASE=1
W="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"; B="$W/build/server2"
PID=$(flatpak-spawn --host sh -c 'for p in $(pgrep -x blakserv); do [ "$(readlink /proc/$p/cwd)" = "'"$B"'" ] && echo $p; done')
[ -n "$PID" ] && { flatpak-spawn --host kill $PID; sleep 4; }
rm -f "$B"/savegame/*; rm -r "$B/memmap"; mkdir "$B/memmap"
cp "$W"/build/tree/run/server/loadkod/*.bof "$B/loadkod/" && cp "$W/build/tree/kod/kodbase.txt" "$W/build/tree/run/server/rsc0000.rsb" "$B/"; cp "$W"/build/tree/run/server/rsc/*.rsc "$B/rsc/"   # the server itself reads rsc/*.rsc (rsc0000.rsb is the clients' merge of them): a stale rsc/ means "SetResourceName can't find resource id" for every new resource
(setsid nohup flatpak-spawn --host distrobox enter m59-box -- bash -c "cd $B && exec ./blakserv </dev/null >console.out 2>&1" >/dev/null 2>&1 &)
for i in $(seq 1 40); do (timeout 1 bash -c "echo > /dev/tcp/127.0.0.1/9998" 2>/dev/null) && break; sleep 3; done
export PRIME_ADMIN_PORT=9998; "$(dirname "$0")/prime_set.sh" piTownLife 1 >/dev/null; "$(dirname "$0")/prime_set.sh" piPlayerBotCount 20 >/dev/null; echo "server2 ready (bots need ~60 s for bodies)"
