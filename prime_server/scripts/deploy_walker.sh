#!/bin/bash
# DEPLOY THE NEW PLAYERBOT WALKER (patches 0073-0075 + the Kod that uses them) to a server folder, with a backup and a rollback.
#   scripts/deploy_walker.sh [--target DIR] [--admin-port N] [--yes] [--no-start]
#     --target      the server folder (default: the owner's $PRIME_WORK/build/server, admin port 9999)
#     --admin-port  its maintenance port (default 9999; the rehearsal copy uses 9997)
#     --yes         do not ask before stopping/starting
#     --no-start    install only; do not start the server
# NOTE: the server turns loadkod/*.bof into memmap/ when it starts and empties loadkod/, so a server folder's CODE is memmap/ (plus kodbase.txt and rsc0000.rsb).
# WHAT IT DOES: 1 checks that the compiled build matches the overlay (refuses otherwise); 2 if the server in TARGET runs: admin "save game", then stops it (by pid, checked by cwd);
#   3 BACKS UP binary, loadkod, memmap (the running code), kodbase.txt, rsc0000.rsb, blakserv.cfg and the savegame folder to $PRIME_WORK/build/backup_before_walker_<time>; 4 installs the new binary and kod files
#   (the binary and the Kod MUST go together: the new Kod calls C functions the old binary does not have); 5 starts the server and checks the layout, the bot bodies and the error log;
#   6 prints the command that undoes it all:  scripts/rollback_walker.sh <backup folder> [--target DIR] [--admin-port N]
# The saved world is kept (the rules, the bots, the characters): only the code is replaced. Rules that are saved in the world (piTownLife, piPlayerBotCount, ...) stay as they are.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
TARGET="$W/build/server"; PORT=9999; YES=0; START=1
while [ $# -gt 0 ]; do case "$1" in --target) TARGET="$2"; shift 2;; --admin-port) PORT="$2"; shift 2;; --yes) YES=1; shift;; --no-start) START=0; shift;; *) sed -n 2,14p "$0"; exit 1;; esac; done
TREE="$W/build/tree"; OVERLAY="$HERE/../overlay/kod"; ADM="$HERE/admin_prime.py"; export PRIME_ADMIN_PORT="$PORT"
say() { printf '\n== %s\n' "$*"; }
die() { printf '\nSTOP: %s\n' "$*" >&2; exit 1; }
[ -d "$TARGET" ] && [ -x "$TARGET/blakserv" ] || die "no server folder at $TARGET"
NEWBIN="$TREE/blakserv/debug/blakserv"; [ -x "$NEWBIN" ] || NEWBIN="$TREE/run/server/blakserv"
[ -x "$NEWBIN" ] || die "no compiled server binary in the build tree"
KODDIR="$TREE/run/server/loadkod"; [ -f "$KODDIR/playerbot.bof" ] || die "no compiled kod in the build tree"

say "1. checks"
# every overlay kod file must be older than the compiled playerbot.bof / primeplayerbots.bof (else the build is stale)
NEWEST=$(find "$OVERLAY" -name '*.kod' -printf '%T@ %p\n' | sort -n | tail -1)
OLDEST_BOF=$(stat -c %Y "$KODDIR/playerbot.bof" "$KODDIR/primeplayerbots.bof" | sort -n | head -1)
[ "${NEWEST%%.*}" -le "$OLDEST_BOF" ] || die "the overlay kod (${NEWEST#* }) is newer than the compiled bof files: build first (claude_tools/kodbuild.sh --c) and test on server2"
for c in EXPLAINMOVEBSP SETBODYRADIUSBSP AVOIDSQUAREBSP CLEARAVOIDBSP; do grep -q "$c" "$TREE/include/bkod.h" || die "the build tree has no patches 0073-0075 ($c missing in include/bkod.h)"; done
grep -qa "ExplainMoveBSP" "$NEWBIN" || die "the compiled binary does not contain ExplainMoveBSP (patch 0073): build the server (claude_tools/kodbuild.sh --c)"
grep -qa "AvoidSquareBSP" "$NEWBIN" && grep -qa "SetBodyRadiusBSP" "$NEWBIN" || die "the compiled binary does not contain AvoidSquareBSP (patch 0075)"
echo "build is current: binary $NEWBIN, kod $(ls $KODDIR/*.bof | wc -l) files, newest overlay file older than the bof files"

PID=$(flatpak-spawn --host sh -c 'for p in $(pgrep -x blakserv); do [ "$(readlink /proc/$p/cwd)" = "'"$TARGET"'" ] && echo $p; done' 2>/dev/null)
if [ -n "$PID" ]; then echo "the server in $TARGET is RUNNING (pid $PID)"; else echo "the server in $TARGET is not running"; fi
if [ $YES -ne 1 ]; then printf "\nThis stops/starts the server in %s. Players on it are disconnected. Continue? [y/N] " "$TARGET"; read -r A; [ "$A" = "y" ] || die "cancelled"; fi

if [ -n "$PID" ]; then
  say "2. save the world and stop the server"
  python3 "$ADM" "save game" 2>&1 | tail -2 || die "the admin 'save game' failed: not stopping the server"
  sleep 5
  flatpak-spawn --host kill "$PID"; for i in $(seq 1 20); do flatpak-spawn --host kill -0 "$PID" 2>/dev/null || break; sleep 1; done
  flatpak-spawn --host kill -0 "$PID" 2>/dev/null && die "the server did not stop"
  echo "stopped"
else say "2. (nothing to stop)"; fi

say "3. backup"
BK="$W/build/backup_before_walker_$(date +%Y%m%d_%H%M%S)"; mkdir -p "$BK"
# memmap/ is the server's RUNNING CODE (it moves the .bof files from loadkod/ into memmap/ when it starts): the backup must have it or a rollback has no old code
cp -a "$TARGET/blakserv" "$TARGET/loadkod" "$TARGET/memmap" "$TARGET/rsc" "$TARGET/kodbase.txt" "$TARGET/rsc0000.rsb" "$TARGET/blakserv.cfg" "$TARGET/savegame" "$BK/" || die "the backup failed (nothing was changed)"
echo "backup: $BK ($(du -sh "$BK" | cut -f1))"

say "4. install (binary and kod together)"
cp "$NEWBIN" "$TARGET/blakserv.new" && mv "$TARGET/blakserv.new" "$TARGET/blakserv"
rm -f "$TARGET"/loadkod/*.bof; cp "$KODDIR"/*.bof "$TARGET/loadkod/"
cp "$TREE/kod/kodbase.txt" "$TREE/run/server/rsc0000.rsb" "$TARGET/"
cp "$TREE"/run/server/rsc/*.rsc "$TARGET/rsc/"     # the server reads rsc/*.rsc (rsc0000.rsb is the clients' merge): without this new resources are unknown to it
rm -rf "$TARGET/memmap"; mkdir "$TARGET/memmap"
echo "installed: $(ls "$TARGET"/loadkod/*.bof | wc -l) kod files"
[ $START -eq 1 ] || { echo "not started (--no-start). Undo: scripts/rollback_walker.sh $BK --target $TARGET --admin-port $PORT"; exit 0; }

say "5. start and verify"
ERR0=$(grep -a -c "" "$TARGET/channel/error.txt" 2>/dev/null || echo 0)     # lines already in the log (it is part of the saved folder): only what comes after counts
(setsid nohup flatpak-spawn --host distrobox enter m59-box -- bash -c "cd $TARGET && exec ./blakserv </dev/null >console.out 2>&1" >/dev/null 2>&1 &)
UP=0; for i in $(seq 1 60); do python3 "$ADM" "show accounts" >/dev/null 2>&1 && { UP=1; break; }; sleep 3; done
[ $UP -eq 1 ] || { echo "the server did not answer on the admin port $PORT in 3 minutes"; echo "UNDO:  $HERE/rollback_walker.sh $BK --target $TARGET --admin-port $PORT"; exit 2; }
PRIME=$(python3 "$ADM" "show instances primeclasses" | grep -o "OBJECT [0-9]*" | head -1 | cut -d' ' -f2)
echo "PrimeClasses object $PRIME"
LAYOUT=$(python3 "$ADM" "show object $PRIME" | grep -E "piPBotTicks|piPBotNoRisk|piTownLife|piPlayerBotCount")
echo "$LAYOUT"
BAD=0
echo "$LAYOUT" | grep -q "piPBotTicks *= INT" || BAD=1
echo "$LAYOUT" | grep -q "piPBotNoRisk *= INT" || BAD=1
echo "$LAYOUT" | grep -q "piPlayerBotCount *= INT" || BAD=1
[ $BAD -eq 0 ] && echo "layout check: PrimeClasses properties are integers (not shifted)" || echo "LAYOUT CHECK FAILED: PrimeClasses looks shifted (saved world and new code disagree)"
echo "waiting 100 s for the bots to get their bodies ..."; sleep 100
NB=0; for b in $(seq 1 60); do R=$(python3 "$ADM" "send object $PRIME PBotBodyOf id int $b" 2>/dev/null | grep -cE "^: OBJECT"); NB=$((NB+R)); done
echo "bot bodies found among the first 60 bot ids: $NB"
ERR="$TARGET/channel/error.txt"
if [ -f "$ERR" ]; then
  PAT="can't find a handler for MESSAGE \(Path\|WalkTo\|PBot\|GoTo\|Explain\|CountGiveUp\|Trace\)\|Nth past end of list\|primeplayerbots.bof.*can't take\|playerbot.bof.*can't"
  N=$(tail -n +$((ERR0+1)) "$ERR" | grep -a -c "$PAT")
  echo "error.txt (new lines only): $N that point at the bot code"; tail -n +$((ERR0+1)) "$ERR" | grep -a "$PAT" | sed 's/^[A-Za-z]* *[0-9]* [0-9]* [0-9:]* | //' | cut -c1-160 | sort | uniq -c | sort -rn | head -5
  echo "(known and harmless: 'can't find property plNavPath' while an OLD save loads, 'unable to get class 11650', startup room messages, 'too many instructions' in a 30-bot start)"
fi
echo
if [ $BAD -eq 0 ]; then echo "DONE. If anything looks wrong:  $HERE/rollback_walker.sh $BK --target $TARGET --admin-port $PORT"
else echo "PROBLEM: undo with  $HERE/rollback_walker.sh $BK --target $TARGET --admin-port $PORT"; exit 3; fi
