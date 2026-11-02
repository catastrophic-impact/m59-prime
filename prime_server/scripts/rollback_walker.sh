#!/bin/bash
# UNDO scripts/deploy_walker.sh: stop the server and put back the binary, the kod files, kodbase.txt, rsc0000.rsb, blakserv.cfg and the SAVEGAME folder from a backup.
#   scripts/rollback_walker.sh BACKUP_DIR [--target DIR] [--admin-port N] [--yes] [--no-start]
# NOTE: the savegame folder is put back as it was BEFORE the deploy: whatever the world saved since then (autosaves every 30 minutes) is gone. The server is NOT saved before it is
# stopped here (a world saved by the new code might not load in the old one).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
BK="${1:-}"; shift || true; TARGET="$W/build/server"; PORT=9999; YES=0; START=1
while [ $# -gt 0 ]; do case "$1" in --target) TARGET="$2"; shift 2;; --admin-port) PORT="$2"; shift 2;; --yes) YES=1; shift;; --no-start) START=0; shift;; *) sed -n 2,6p "$0"; exit 1;; esac; done
export PRIME_ADMIN_PORT="$PORT"; ADM="$HERE/admin_prime.py"
die() { printf '\nSTOP: %s\n' "$*" >&2; exit 1; }
[ -d "$BK" ] && [ -f "$BK/blakserv" ] && [ -d "$BK/savegame" ] && [ -d "$BK/memmap" ] || die "$BK is not a backup folder of deploy_walker.sh"
[ -d "$TARGET" ] || die "no server folder at $TARGET"
if [ $YES -ne 1 ]; then printf "Put back the backup %s into %s (the world goes back to the state before the deploy). Continue? [y/N] " "$BK" "$TARGET"; read -r A; [ "$A" = "y" ] || die "cancelled"; fi
PID=$(flatpak-spawn --host sh -c 'for p in $(pgrep -x blakserv); do [ "$(readlink /proc/$p/cwd)" = "'"$TARGET"'" ] && echo $p; done' 2>/dev/null)
if [ -n "$PID" ]; then flatpak-spawn --host kill "$PID"; for i in $(seq 1 20); do flatpak-spawn --host kill -0 "$PID" 2>/dev/null || break; sleep 1; done; echo "server stopped"; fi
cp "$BK/blakserv" "$TARGET/blakserv.old" && mv "$TARGET/blakserv.old" "$TARGET/blakserv"
rm -f "$TARGET"/loadkod/*.bof; cp -a "$BK"/loadkod/. "$TARGET/loadkod/" 2>/dev/null
cp "$BK/kodbase.txt" "$BK/rsc0000.rsb" "$BK/blakserv.cfg" "$TARGET/"
rm -rf "$TARGET/savegame"; cp -a "$BK/savegame" "$TARGET/savegame"
rm -rf "$TARGET/memmap"; cp -a "$BK/memmap" "$TARGET/memmap"     # the old running code
echo "restored from $BK"
[ $START -eq 1 ] || { echo "not started (--no-start)"; exit 0; }
(setsid nohup flatpak-spawn --host distrobox enter m59-box -- bash -c "cd $TARGET && exec ./blakserv </dev/null >console.out 2>&1" >/dev/null 2>&1 &)
for i in $(seq 1 60); do python3 "$ADM" "show accounts" >/dev/null 2>&1 && { echo "server is back (old code, old world)"; exit 0; }; sleep 3; done
echo "the server did not answer on the admin port $PORT in 3 minutes: look at $TARGET/console.out"; exit 2
