#!/usr/bin/env bash
# m59primesetup.sh - one-script setup of Meridian 59 Prime on Linux with distrobox.
#
#   ./m59primesetup.sh [--name m59-box] [--release DIR] [--assets-from DIR] [--assemble-only] [--force-rebuild]
#
# What it does (first run: 20-40 minutes, 4 GB of disk; later runs reuse what is already built):
#   1  creates a distrobox (Ubuntu 22.04) called m59-box with its own home folder ~/boxes/m59-box (your real home is not touched),
#      and installs the build tools inside it (apt, inside the box only);
#   2  builds the game server: the pinned Server 104 source + our patches + our own files, compiled in the box;
#   3  downloads a portable Node.js into the box, builds the web client (pinned Meridian Shards client + our patches + our own files);
#   4  downloads the game files (art, sounds, rooms) from the pinned Meridian Shards release (prime_client/ASSETS.txt; checked by SHA-256).
#      They are not part of this repository; --assets-from DIR uses game files you already have instead;
#   5  puts everything into one portable folder, release/ (default: next to this script): server, web client, a Node runtime, start and stop scripts.
#      Copy release/ anywhere and run ./start-server.sh and ./start-client.sh in it (see release/README.txt). Nothing is written outside that folder at run time.
#
# Requirements on your computer: Linux, distrobox + podman (or docker), curl. Everything else is installed inside the box.
# Without distrobox you can follow the same steps by hand on Ubuntu 22.04: docs/BUILDING.md.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NAME="${M59_BOX_NAME:-m59-box}"; RELEASE=""; ASSETS_FROM=""; ASSEMBLE_ONLY=0; FORCE=0; INSIDE=0
while [ $# -gt 0 ]; do case "$1" in
  --name) NAME="$2"; shift 2;; --release) RELEASE="$2"; shift 2;; --assets-from) ASSETS_FROM="$2"; shift 2;;
  --assemble-only) ASSEMBLE_ONLY=1; shift;; --force-rebuild) FORCE=1; shift;; --inside) INSIDE=1; shift;;
  -h|--help) sed -n 2,19p "$0"; exit 0;; *) echo "unknown option: $1 (see --help)"; exit 1;; esac; done
RELEASE="${RELEASE:-$HERE/release}"
step() { printf '\n== %s\n' "$*"; }
die() { printf '\nSTOP: %s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------------------------------------------------------------------ on the host: make the box, then run this script inside it
if [ "$INSIDE" -eq 0 ]; then
  command -v distrobox >/dev/null || die "distrobox is not installed (https://distrobox.it). It needs podman or docker too."
  command -v podman >/dev/null || command -v docker >/dev/null || die "distrobox needs podman or docker."
  BOXHOME="$HOME/boxes/$NAME"
  if ! distrobox list 2>/dev/null | awk -F'|' 'NR>1{gsub(/ /,"",$2); print $2}' | grep -qx "$NAME"; then
    step "creating the distrobox '$NAME' (Ubuntu 22.04) with its own home folder $BOXHOME"
    mkdir -p "$BOXHOME"
    distrobox create --name "$NAME" --image ubuntu:22.04 --home "$BOXHOME" --yes
  else
    echo "using the existing distrobox '$NAME'"
  fi
  args=(--inside --release "$RELEASE"); [ -n "$ASSETS_FROM" ] && args+=(--assets-from "$ASSETS_FROM"); [ "$ASSEMBLE_ONLY" -eq 1 ] && args+=(--assemble-only); [ "$FORCE" -eq 1 ] && args+=(--force-rebuild)
  exec distrobox enter "$NAME" -- bash "$HERE/m59primesetup.sh" "${args[@]}"
fi

# ------------------------------------------------------------------------------------------------------------------ inside the box
export PRIME_WORK="$HOME/src/prime_work"          # big files live here (inside the box home), never in the project
export ELECTRON_SKIP_BINARY_DOWNLOAD=1 PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm_config_audit=false npm_config_fund=false
TREE="$PRIME_WORK/client_build/tree"; SRV="$PRIME_WORK/build/server"
mkdir -p "$PRIME_WORK"
# The login SecretKey must be the same in the server's blakserv.cfg and in the built client. The repository carries a placeholder; every setup makes its own random key
# (kept in $PRIME_WORK/secretkey) and puts it into the client build and the release's server config.
set_key() {   # $1 = a blakserv.cfg
  [ -s "$PRIME_WORK/secretkey" ] || head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24 > "$PRIME_WORK/secretkey"
  sed -i "s/^SecretKey .*/SecretKey            $(cat "$PRIME_WORK/secretkey")/" "$1"
}

if [ "$ASSEMBLE_ONLY" -eq 0 ]; then
  step "1/6 build tools (apt, inside the box)"
  need=(build-essential bison flex git curl unzip xz-utils binutils patch python3 python3-venv ca-certificates); missing=()
  for p in "${need[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p"); done
  if [ ${#missing[@]} -gt 0 ]; then sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}"; else echo "all installed"; fi

  step "2/6 game server (pinned Server 104 source + patches + our files; about 5-10 minutes)"
  if [ -d "$SRV/savegame" ] && [ -n "$(ls -A "$SRV/savegame" 2>/dev/null)" ] && [ "$FORCE" -eq 0 ]; then
    die "$SRV already holds a saved game and the build would replace that folder. Nothing was changed. Use --force-rebuild if you really want to, or --assemble-only to just make the release folder from what is built."
  fi
  "$HERE/prime_server/scripts/build.sh" --fresh
  [ -x "$SRV/blakserv" ] || die "the server did not build: see $PRIME_WORK/build/*.log"

  step "3/6 portable Node.js"
  if ! ls "$PRIME_WORK"/node/node-v*-linux-x64/bin/node >/dev/null 2>&1; then
    mkdir -p "$PRIME_WORK/node"; base="https://nodejs.org/dist/latest-v24.x"
    sums="$(curl -fsSL "$base/SHASUMS256.txt")"; file="$(echo "$sums" | awk '/linux-x64\.tar\.xz$/{print $2}')"; want="$(echo "$sums" | awk '/linux-x64\.tar\.xz$/{print $1}')"
    [ -n "$file" ] || die "could not find a Node 24 download"
    curl -fL -o "$PRIME_WORK/node/$file" "$base/$file"
    [ "$(sha256sum "$PRIME_WORK/node/$file" | cut -d' ' -f1)" = "$want" ] || die "the Node download is damaged (checksum)"
    tar -xJf "$PRIME_WORK/node/$file" -C "$PRIME_WORK/node" && rm -f "$PRIME_WORK/node/$file"
  fi
  source "$HERE/prime_client/scripts/env.sh"; echo "node $(node -v)"

  step "4/6 web client (pinned Meridian Shards client + patches + our files; npm install takes a few minutes)"
  "$HERE/prime_client/scripts/prepare_tree.sh"
  [ -x "$TREE/node_modules/.bin/vite" ] || die "npm install did not finish: run  cd $TREE && npm install  to see why"
  set_key "$TREE/server/config/blakserv.cfg"      # the client build reads the key from here

  step "5/6 game files (art, sounds, rooms: not in this repository)"
  if [ -f "$PRIME_WORK/assets/manifest.json" ]; then echo "already there: $PRIME_WORK/assets"
  elif [ -n "$ASSETS_FROM" ]; then
    [ -f "$ASSETS_FROM/manifest.json" ] || die "--assets-from: no manifest.json in $ASSETS_FROM (give the folder that holds the game files)"
    mkdir -p "$PRIME_WORK/assets" && cp -a "$ASSETS_FROM/." "$PRIME_WORK/assets/"
  else
    get() { awk -v k="$1" '$1==k{ $1=""; sub(/^ +/,""); print }' "$HERE/prime_client/ASSETS.txt"; }
    repo="$(get repo)"; tag="$(get tag)"; file="$(get file)"; sha="$(get sha256)"; path="$(get path)"
    mkdir -p "$PRIME_WORK/cache"; deb="$PRIME_WORK/cache/$file"
    echo "downloading $file from github.com/$repo (release $tag, about 490 MB) ..."
    curl -fL -C - -o "$deb" "https://github.com/$repo/releases/download/$tag/$file"
    [ "$(sha256sum "$deb" | cut -d' ' -f1)" = "$sha" ] || die "the downloaded file does not match the pinned checksum in prime_client/ASSETS.txt (deleted: run again, or use --assets-from)"
    tmp="$PRIME_WORK/cache/assets_unpack"; rm -rf "$tmp"; mkdir -p "$tmp"
    ar p "$deb" data.tar.xz | tar -xJ -C "$tmp" "$path"
    mv "$tmp/$path" "$PRIME_WORK/assets" && rm -rf "$tmp" "$deb"
  fi
  [ -f "$PRIME_WORK/assets/manifest.json" ] || die "the game files are missing"
  python3 "$HERE/prime_server/scripts/sync_client_strings.py"      # the client needs OUR server's string table

  step "6/6 build the web client"
  (cd "$TREE" && npm run build)
  [ -f "$TREE/apps/client/dist/index.html" ] || die "the client build produced nothing: see the messages above"
fi

# ------------------------------------------------------------------------------------------------------------------ the portable release folder
step "assembling the portable folder: $RELEASE"
source "$HERE/prime_client/scripts/env.sh"
[ -x "$SRV/blakserv" ] && [ -f "$TREE/apps/client/dist/index.html" ] && [ -f "$PRIME_WORK/assets/manifest.json" ] || die "nothing built yet: run without --assemble-only first"
[ -e "$RELEASE" ] && { mv "$RELEASE" "$RELEASE.old.$(date +%s)"; echo "the previous $RELEASE was kept as $RELEASE.old.*"; }
mkdir -p "$RELEASE/server" "$RELEASE/client/web" "$RELEASE/runtime" "$RELEASE/tools"
# server: the program, its compiled code, the string table and the room files; a new game starts empty
for f in blakserv blakserv.cfg blakston.khd protocol.khd kodbase.txt rsc0000.rsb packages.txt loadkod memmap rsc rooms; do cp -a "$SRV/$f" "$RELEASE/server/"; done
mkdir -p "$RELEASE/server/channel" "$RELEASE/server/savegame"
set_key "$RELEASE/server/blakserv.cfg"
# client: the built web client, the game files, the gateway (one bundled file), a small web server, and Node itself
cp -a "$TREE/apps/client/dist/." "$RELEASE/client/web/"
cp -a "$PRIME_WORK/assets" "$RELEASE/client/web/assets"
node "$TREE/node_modules/.bin/rolldown" "$TREE/tools/gateway/gateway.ts" --format esm --platform node --silent -o "$RELEASE/client/gateway.mjs"
[ -s "$RELEASE/client/gateway.mjs" ] || die "the gateway bundle was not made"
cp "$HERE/prime_release/serve.mjs" "$RELEASE/client/serve.mjs"
cp "$(command -v node)" "$RELEASE/runtime/node"
# admin tools and the start / stop scripts
for f in admin_prime.py ensure_admin.sh prime_set.sh; do cp "$HERE/prime_server/scripts/$f" "$RELEASE/tools/"; done
for f in start-server.sh start-client.sh stop-all.sh admin.sh README.txt; do cp "$HERE/prime_release/$f" "$RELEASE/"; done
cp "$HERE/LICENSE" "$HERE/NOTICE.md" "$RELEASE/"
chmod +x "$RELEASE"/*.sh "$RELEASE/tools/"*.sh
printf 'Meridian 59 Prime, built %s\n' "$(date +%Y-%m-%d)" > "$RELEASE/VERSION.txt"

step "done"
du -sh "$RELEASE" | cut -f1 | sed 's/^/size of the portable folder: /'
cat <<E

Your portable folder: $RELEASE
Copy it anywhere, then in it:
  ./start-server.sh      (first start prints the admin password once)
  ./start-client.sh      then open the printed address in a browser
  ./stop-all.sh          saves the game and stops everything
More: $RELEASE/README.txt
E
