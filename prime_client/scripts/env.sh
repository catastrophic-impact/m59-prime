# source this: puts the portable Node 24 (downloaded into $PRIME_WORK/node) on PATH
export PRIME_WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
# whichever Node 24 build is in $PRIME_WORK/node (m59primesetup.sh puts it there)
NODE_BIN="$(ls -d "$PRIME_WORK"/node/node-v*-linux-x64/bin 2>/dev/null | tail -1)"
[ -n "$NODE_BIN" ] && export PATH="$NODE_BIN:$PATH"
