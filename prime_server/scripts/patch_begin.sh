#!/bin/bash
# Start editing upstream files in the build tree: snapshots them so patch_end.sh can write the difference as a patch.
# Usage: scripts/patch_begin.sh path/in/tree [more paths ...]      (then edit the files in $PRIME_WORK/build/tree)
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"; TREE="$WORK/build/tree"; SNAP="$WORK/patchwork"
[ -d "$SNAP" ] && mv "$SNAP" "$SNAP.old.$(date +%s)"; mkdir -p "$SNAP"
for f in "$@"; do mkdir -p "$SNAP/$(dirname "$f")"; cp -a "$TREE/$f" "$SNAP/$f"; echo "snapshot $f"; done
printf '%s\n' "$@" > "$SNAP/.files"
