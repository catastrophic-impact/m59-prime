#!/bin/bash
# Clone (or update) the pinned upstream into $PRIME_WORK/cache/upstream (~420 MB, outside the project).
# Usage: scripts/fetch_upstream.sh [alternative-url-or-local-path]
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
URL="${1:-$(awk '$1=="url"{print $2}' "$HERE/UPSTREAM.txt")}"
COMMIT="$(awk '$1=="commit"{print $2}' "$HERE/UPSTREAM.txt")"
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"   # big files live OUTSIDE the project (keeps the git repo small)
DEST="$WORK/cache/upstream"
mkdir -p "$WORK/cache"
if [ ! -d "$DEST/.git" ]; then git init -q "$DEST"; git -C "$DEST" remote add origin "$URL"; fi
cd "$DEST"
# only the pinned commit is fetched (a shallow fetch: a few MB instead of the whole history); a full clone is the fallback
git cat-file -e "$COMMIT" 2>/dev/null || git fetch -q --depth 1 origin "$COMMIT" 2>/dev/null || git fetch -q origin
git checkout -q "$COMMIT"
echo "upstream at $(git rev-parse --short HEAD)"
