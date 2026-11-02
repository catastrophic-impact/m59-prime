#!/bin/bash
# Clone (or update) the pinned client upstream into $PRIME_WORK/client_cache/upstream.  Usage: fetch_upstream.sh [alternative-url-or-local-path]
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
URL="${1:-$(awk '$1=="url"{print $2}' "$HERE/UPSTREAM.txt")}"
COMMIT="$(awk '$1=="commit"{print $2}' "$HERE/UPSTREAM.txt")"
DEST="$WORK/client_cache/upstream"; mkdir -p "$WORK/client_cache"
[ -d "$DEST/.git" ] || { git init -q "$DEST"; git -C "$DEST" remote add origin "$URL"; }
cd "$DEST"
# only the pinned commit is fetched (a shallow fetch); a full clone is the fallback
git cat-file -e "$COMMIT" 2>/dev/null || git fetch -q --depth 1 origin "$COMMIT" 2>/dev/null || git fetch -q origin
git checkout -q "$COMMIT"; echo "client upstream at $(git rev-parse --short HEAD)"
