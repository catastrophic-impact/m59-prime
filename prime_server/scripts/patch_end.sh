#!/bin/bash
# Write the edits made since patch_begin.sh as patches/NAME.patch (applies after the earlier patches).  Usage: scripts/patch_end.sh 0002-class-framework
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"; TREE="$WORK/build/tree"; SNAP="$WORK/patchwork"
OUT="$HERE/patches/$1.patch"; : > "$OUT"
while read -r f; do [ -n "$f" ] && diff -u --label "a/$f" --label "b/$f" "$SNAP/$f" "$TREE/$f" >> "$OUT"; done < "$SNAP/.files"
echo "wrote $OUT ($(grep -c '^@@' "$OUT") hunks)"
