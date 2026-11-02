#!/bin/bash
# Build a fresh source tree: pinned upstream + our patches + our overlay + Linux fix-ups.  Result: $PRIME_WORK/build/tree
# Usage: scripts/prepare_tree.sh      (re-run after changing patches/ or overlay/; it recreates the tree from scratch)
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
SRC="$WORK/cache/upstream"; TREE="$WORK/build/tree"
[ -d "$SRC/.git" ] || "$HERE/scripts/fetch_upstream.sh"
mkdir -p "$WORK/build"
[ -d "$TREE" ] && mv "$TREE" "$WORK/build/tree.old.$(date +%s)"      # never rm: old trees are kept (delete them by hand)
mkdir -p "$TREE"
( cd "$SRC" && git archive HEAD ) | tar -x -C "$TREE"
cd "$TREE"
for p in "$HERE"/patches/*.patch; do [ -e "$p" ] || continue; echo "patch $(basename "$p")"; patch -p1 -s < "$p"; done
[ -d "$HERE/overlay" ] && cp -a "$HERE/overlay/." "$TREE/"
python3 "$HERE/scripts/linux_fixups.py" "$TREE/kod"
mkdir -p run/server/{loadkod,rsc,memmap,channel,savegame,rooms}
echo "tree ready: $TREE"
