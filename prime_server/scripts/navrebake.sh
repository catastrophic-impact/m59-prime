#!/bin/bash
# Rebake the bot navmeshes (primenavdata.kod) with the server-refused points of navblocked.json closed.  Then: scripts/hotreload.sh, scripts/navcheck.py.
HERE="$(cd "$(dirname "$0")/.." && pwd)"
W="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
OV="$HERE/../prime_client/overlay/tools/prime"
mkdir -p "$W/client_build/tree/tools/prime" "$W/navtmp"
cp "$OV/navbake.ts" "$OV/roomzones.json" "$W/client_build/tree/tools/prime/"
mkdir -p "$W/navtmp/navprobe"; cp "$OV"/navprobe/*_x2.json "$W/navtmp/navprobe/" 2>/dev/null
if [ -n "$NAV_NO_BLOCKED" ]; then echo '{}' > "$W/navtmp/navhard.json"; echo '{}' > "$W/navtmp/navprune.json"; else cp "$OV/navhard.json" "$OV/navprune.json" "$W/navtmp/" 2>/dev/null; fi
if [ -n "$NAV_NO_BLOCKED" ]; then echo '{}' > "$W/navtmp/navblocked.json"; else cp "$OV/navblocked.json" "$W/navtmp/navblocked.json" 2>/dev/null || echo '{}' > "$W/navtmp/navblocked.json"; fi
cp "$OV/navobjects.json" "$W/navtmp/navobjects.json" 2>/dev/null || echo '{}' > "$W/navtmp/navobjects.json"
# the game's own exit tables (claude_tools/kodexits.py) and the landings the planner cannot leave (claude_tools/reachmatrix.py -> docs/trap_landings.json, [] when none)
cp "$HERE/../docs/kod_exits.json" "$W/navtmp/kod_exits.json"; cp "$HERE/../docs/edge_landings.json" "$W/navtmp/edge_landings.json" 2>/dev/null || echo '{}' > "$W/navtmp/edge_landings.json"; cp "$HERE/../docs/trap_landings.json" "$W/navtmp/trap_landings.json" 2>/dev/null || echo '[]' > "$W/navtmp/trap_landings.json"
flatpak-spawn --host distrobox enter m59-box -- bash -c "cd $W/client_build/tree && $W/node/node-v24.22.0-linux-x64/bin/node tools/prime/navbake.ts --assets $W/assets --kod $W/build/tree/kod --out $W/navtmp/primenavdata.kod --json $W/navtmp/navbake.json --blocked $W/navtmp/navblocked.json --objects $W/navtmp/navobjects.json --relax --probe $W/navtmp/navprobe --landings $W/navtmp/kod_exits.json --trap $W/navtmp/trap_landings.json --edges $W/navtmp/edge_landings.json" > "$W/navtmp/bake.log" 2>&1 || { tail -5 "$W/navtmp/bake.log"; exit 1; }
cp "$W/navtmp/primenavdata.kod" "$HERE/overlay/kod/object/prime/primenavdata.kod"
tail -2 "$W/navtmp/bake.log"
