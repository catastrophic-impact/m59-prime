#!/bin/bash
# Fast edit loop (about 10 s instead of a 4 minute rebuild): sync the overlay into the build tree, compile ONLY what changed (incremental kod build),
# copy the new .bof files + kodbase to the running server and run the admin command `reload system` (saves, reloads the code, players stay on).
# Safe for changes to the BODY of messages, constants and resource strings. It refuses (use build.sh --fresh instead) when a class or file was added/removed,
# or the `properties:` / `classvars:` section of a changed class differs (the saved objects would not match), or a .khd include changed.
# Upstream files patched via patch_begin/patch_end: edit them in the build tree first, then run this with --tree (no overlay sync).
# The TUI must be closed (the server's admin port takes one connection).  Usage: scripts/hotreload.sh [--tree]
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"; TREE="$WORK/build/tree"; OUT="$WORK/build/server"
STAMP="$WORK/build/.hotreload_stamp"; [ -f "$STAMP" ] || touch -d "10 minutes ago" "$STAMP"
if [ "$1" != "--tree" ]; then
  # refuse structural changes
  ( cd "$HERE/overlay/kod" && find . -type f -name "*.kod" | sort ) > /tmp/hr_over.txt
  ( cd "$TREE/kod" && for f in $(cat /tmp/hr_over.txt); do [ -f "$f" ] || echo "NEW FILE $f"; done ) | grep . && { echo "A new .kod file: use scripts/build.sh --fresh"; exit 1; }
  struct() { sed -n '/^classvars:/,/^messages:/p' "$1" | grep -v '^ *//' | tr -s ' \n' | md5sum; }
  for f in $(cat /tmp/hr_over.txt); do
    if ! cmp -s "$HERE/overlay/kod/$f" "$TREE/kod/$f"; then
      [ "$(struct "$HERE/overlay/kod/$f")" = "$(struct "$TREE/kod/$f")" ] || { echo "$f: classvars/properties changed: use scripts/build.sh --fresh"; exit 1; }
    fi
  done
  if ! diff -q -r "$HERE/overlay/kod/include" "$TREE/kod/include" >/dev/null 2>&1; then
    for f in $(cd "$HERE/overlay/kod/include" && ls); do cmp -s "$HERE/overlay/kod/include/$f" "$TREE/kod/include/$f" || { echo "include/$f changed: use scripts/build.sh --fresh"; exit 1; }; done
  fi
  cp -a "$HERE/overlay/." "$TREE/"
fi
RUN='cd "'$TREE'" && make -f makefile.linux Bkod RELEASE=1 > "'$WORK'/build/kod_hot.log" 2>&1; echo "kod: $(grep -c " error" "'$WORK'/build/kod_hot.log") errors"'
if [ -n "$CONTAINER_ID" ]; then bash -c "$RUN"; else flatpak-spawn --host distrobox enter m59-box -- bash -c "$RUN"; fi
grep -q "error" "$WORK/build/kod_hot.log" && { grep " error" "$WORK/build/kod_hot.log" | head; exit 1; }
N=0; for b in $(find "$TREE/run/server/loadkod" -name "*.bof" -newer "$STAMP"); do cp "$b" "$OUT/loadkod/"; N=$((N+1)); done
cp "$TREE/kod/kodbase.txt" "$OUT/kodbase.txt"
cp "$TREE/run/server/rsc0000.rsb" "$OUT/" 2>/dev/null || true
touch "$STAMP"; echo "$N changed .bof copied"
[ "$N" = 0 ] && { echo "nothing changed"; exit 0; }
python3 "$HERE/scripts/admin_prime.py" "reload system" | tail -1
