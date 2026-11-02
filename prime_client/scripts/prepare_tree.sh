#!/bin/bash
# Fresh client tree: pinned upstream + patches + overlay + our server config + links to the game assets.  Result: $PRIME_WORK/client_build/tree
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"; source "$HERE/scripts/env.sh"
SRC="$PRIME_WORK/client_cache/upstream"; TREE="$PRIME_WORK/client_build/tree"
[ -d "$SRC/.git" ] || "$HERE/scripts/fetch_upstream.sh"
mkdir -p "$PRIME_WORK/client_build"
[ -d "$TREE" ] && mv "$TREE" "$PRIME_WORK/client_build/tree.old.$(date +%s)"      # never rm: old trees are kept
mkdir -p "$TREE"; ( cd "$SRC" && git archive HEAD ) | tar -x -C "$TREE"; cd "$TREE"
for p in "$HERE"/patches/*.patch; do [ -e "$p" ] || continue; echo "patch $(basename "$p")"; patch -p1 -s < "$p"; done
[ -d "$HERE/overlay" ] && cp -a "$HERE/overlay/." "$TREE/"
"$HERE/scripts/rebrand.sh" "$TREE"
cp "$HERE/../prime_server/config/blakserv.cfg" server/config/blakserv.cfg          # the client reads the SecretKey from here
mkdir -p dist server/src/run/server/rsc
ln -sfn "$PRIME_WORK/assets" dist/assets                                           # the 104 game files (see prime_server / docs)
ln -sf "$PRIME_WORK/build/server/rsc0000.rsb" server/src/run/server/rsc/rsc0000.rsb  # for the headless test client
npm install --no-audit --no-fund >/dev/null 2>&1
echo "client tree ready: $TREE"
