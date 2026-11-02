#!/bin/bash
# Start the freshly built Prime server (ports 5960/9999) in the background; waits until the admin console answers.
# Stop it with: scripts/stop_test_server.sh
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}/build/server"
cd ~; (setsid nohup flatpak-spawn --host distrobox enter m59-box -- bash -c "cd $OUT && exec ./blakserv </dev/null >console.out 2>&1" >/dev/null 2>&1 &)
ADM="$HERE/admin_prime.py"
for i in $(seq 1 120); do python3 "$ADM" "show accounts" >/dev/null 2>&1 && { "$HERE/ensure_admin.sh" >/dev/null 2>&1; [ $? -eq 10 ] && { echo "admin character created: restarting the server once"; "$HERE/stop_test_server.sh" >/dev/null 2>&1; sleep 4; exec "$HERE/run_test_server.sh"; }; echo "prime server ready"; exit 0; }; sleep 3; done
echo "server did not answer"; exit 1
