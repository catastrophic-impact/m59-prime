#!/usr/bin/env bash
# Start the Meridian 59 Prime game server in the background (game port 5960, admin port 9999 on this machine only). Stop it with ./stop-all.sh
# First start: an admin account is made and its password is printed ONCE (write it down; or set M59_ADMIN_PASSWORD / M59_ADMIN_ACCOUNT before the first start).
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/server" || exit 1
export PRIME_ADMIN_PORT="${PRIME_ADMIN_PORT:-9999}"
up() { (echo > /dev/tcp/127.0.0.1/"$PRIME_ADMIN_PORT") 2>/dev/null; }
if up; then echo "a server already answers on port $PRIME_ADMIN_PORT"; exit 0; fi
if ldd ./blakserv 2>&1 | grep -q "not found"; then
  echo "This computer's C library is older than the server needs (glibc 2.35+). Run the server inside the build box instead:"
  echo "  distrobox enter ${M59_BOX_NAME:-m59-box} -- \"$HERE/start-server.sh\""; exit 1
fi
mkdir -p channel savegame
launch() { nohup ./blakserv </dev/null >console.out 2>&1 & echo $! > "$HERE/server.pid"; }
wait_up() { for _ in $(seq 1 120); do up && return 0; sleep 1; done; return 1; }
launch; wait_up || { echo "the server did not come up: see server/console.out and server/channel/"; exit 1; }
"$HERE/tools/ensure_admin.sh"; rc=$?
if [ $rc -eq 10 ]; then      # a new admin character only works after a restart
  echo "restarting the server once for the new admin character ..."
  p="$(cat "$HERE/server.pid")"; pkill -P "$p" 2>/dev/null; kill "$p" 2>/dev/null; sleep 4; launch; wait_up || { echo "the server did not come back"; exit 1; }
fi
echo "server running (pid $(cat "$HERE/server.pid")): game port $(awk '$1=="Port"{print $2}' blakserv.cfg), admin console: ./admin.sh"
