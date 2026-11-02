# Building Meridian 59 Prime

## The easy way: one script (needs distrobox)

```bash
git clone https://github.com/catastrophic-impact/m59-prime && cd m59-prime
./m59primesetup.sh            # about 20-40 minutes the first time; ./m59primesetup.sh --help lists the options
```

It creates the distrobox `m59-box` (Ubuntu 22.04, own home `~/boxes/m59-box`), installs the build tools in it, builds the server and the web client, downloads the pinned game files and
writes the portable folder `release/` (server, web client, Node runtime, `start-server.sh`, `start-client.sh`, `stop-all.sh`, `admin.sh`). Copy `release/` anywhere and run it.
Everything big lives inside the box home (`~/boxes/m59-box/src/prime_work`, called `$PRIME_WORK` below); the project folder stays small.

## What the script does, step by step (the manual way, Ubuntu 22.04 or similar)

Packages: `build-essential bison flex git curl unzip xz-utils binutils patch python3 python3-venv ca-certificates`.

```bash
export PRIME_WORK=$HOME/src/prime_work          # any folder with a few GB of space

# 1  server: pinned upstream (prime_server/UPSTREAM.txt) + patches/ + overlay/ + Linux fix-ups, then compile (about 5-10 min)
prime_server/scripts/build.sh --fresh           # result: $PRIME_WORK/build/server  (blakserv, loadkod, rsc0000.rsb, rooms, blakserv.cfg)

# 2  Node 24 (any Linux x64 build from nodejs.org) unpacked into $PRIME_WORK/node/node-v24...-linux-x64

# 3  client: pinned upstream (prime_client/UPSTREAM.txt) + patches/ + overlay/, then npm install
ELECTRON_SKIP_BINARY_DOWNLOAD=1 prime_client/scripts/prepare_tree.sh    # result: $PRIME_WORK/client_build/tree

# 4  the game files (not in this repository): the release named in prime_client/ASSETS.txt, its resources/assets folder, unpacked to $PRIME_WORK/assets
#    (or any folder with a manifest.json that you already have); then give the client OUR server's string table:
python3 prime_server/scripts/sync_client_strings.py

# 5  build the client
source prime_client/scripts/env.sh && (cd $PRIME_WORK/client_build/tree && npm run build)    # apps/client/dist
```

To run without the portable folder: start the server (`cd $PRIME_WORK/build/server && ./blakserv`), then `prime_client/scripts/run_dev.sh` (client at http://127.0.0.1:5173).

## Updating upstream

Nothing upstream is edited by hand. Change the commit in `prime_server/UPSTREAM.txt` or `prime_client/UPSTREAM.txt`, run the matching `prepare_tree.sh`: a patch that no longer applies shows which hook must be
re-pointed. The game files are pinned separately (`prime_client/ASSETS.txt`: release tag and SHA-256): move that pin only together with a test run, the files change between releases.

## Developer notes

* After changing a parent Blakod class, touch the subclasses' `.kod` files before building; an incremental Kod build corrupts class ids, so `build.sh` always builds Kod clean.
* `prime_server/scripts/` has the test and deploy scripts, `claude_tools/` the bot and map debugging tools (`claude_tools/README.md`), `wiki/changes.txt` the numbered change log.
