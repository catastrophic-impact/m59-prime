#!/bin/bash
# Build the whole Prime server (64-bit) from build/tree into build/server.  Run from anywhere; uses the m59-box distrobox (Ubuntu 22.04).
# Usage: scripts/build.sh [--fresh|--quick]
#   --fresh  run prepare_tree.sh first (everything from scratch)
#   --quick  copy the overlay into the tree, keep the tree and compiler (for the edit-build-test loop); kod is rebuilt clean (about 4 minutes)
#   --incr   like --quick but only the changed kod files are compiled (about 1 minute). The class ids of kodbase.txt are checked afterwards;
#            if any existing class changed its id the script falls back to a clean --quick build by itself.
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
[ "$1" = "--fresh" ] && "$HERE/scripts/prepare_tree.sh"
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
if [ "$1" = "--quick" ] || [ "$1" = "--incr" ]; then cp -a "$HERE/overlay/." "$WORK/build/tree/"; fi
CLEAN=1    # class ids come from kodbase.txt: an incremental kod build corrupts them (invalid classes at save time), so kod is always rebuilt clean
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
TREE="$WORK/build/tree"; OUT="$WORK/build/server"
if [ "$1" = "--incr" ]; then CLEAN=""; cp "$TREE/kod/kodbase.txt" "$WORK/build/kodbase.before" 2>/dev/null || { echo "no kodbase yet: running --quick"; exec "$0" --quick; }; fi
RUN='cd "'$TREE'" && make -f makefile.linux Bcompiler Butil RELEASE=1 >/dev/null 2>&1; \
 if [ -n "'$CLEAN'" ]; then find kod -name "*.bof" -type f -delete; : > kod/kodbase.txt; fi; \
 for pass in 1 2; do make -f makefile.linux Bkod RELEASE=1 > "'$WORK'/build/kod_pass$pass.log" 2>&1; echo "kod pass $pass: $(grep -c " error" "'$WORK'/build/kod_pass$pass.log") errors"; done; \
 make -f makefile.linux Bserver RELEASE=1 > "'$WORK'/build/server.log" 2>&1; echo "server: $(grep -c " error" "'$WORK'/build/server.log") errors"; \
 cd run/server/rsc && ../../../bin/rscmerge -o ../rsc0000.rsb *.rsc'
if [ -n "$CONTAINER_ID" ]; then bash -c "$RUN"; else flatpak-spawn --host distrobox enter m59-box -- bash -c "$RUN"; fi
if [ "$1" = "--incr" ]; then
  # an existing class must keep its id (kodbase line "C Name id ..."); new classes may only be added
  python3 - "$WORK/build/kodbase.before" "$TREE/kod/kodbase.txt" <<'PY' || { echo "class ids changed: falling back to a clean build"; exec "$0" --quick; }
import sys
def classes(p):
    return {l.split()[1]: l.split()[2] for l in open(p, errors="replace") if l.startswith("C ")}
old, new = classes(sys.argv[1]), classes(sys.argv[2])
bad = [c for c, i in old.items() if new.get(c) != i]
sys.exit(1 if bad else 0)
PY
fi
# assemble the runnable server directory (new directory every time; the old one is deleted)
[ -d "$OUT" ] && rm -rf "$OUT"      # no more server.old.* backups (14 GB piled up); the build starts a new game anyway
mkdir -p "$OUT/channel" "$OUT/savegame"
R="$TREE/run/server"
cp -a "$R/loadkod" "$R/rsc" "$R/memmap" "$R/rsc0000.rsb" "$OUT/"
cp "$TREE/kod/kodbase.txt" "$TREE/kod/include/blakston.khd" "$TREE/kod/include/protocol.khd" "$OUT/"
cp "$TREE/blakserv/debug/blakserv" "$OUT/blakserv"
cp -a "$TREE/resource/rooms" "$OUT/rooms"
cp "$HERE/config/blakserv.cfg" "$OUT/"; printf '# packages\n' > "$OUT/packages.txt"
echo "server ready in $OUT"
