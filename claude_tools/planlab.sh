#!/bin/bash
# PLANLAB: build the server's own planner (blakserv/roofile.c, unchanged) as a standalone program, 2 s, no server needed. Run in the box:
#   flatpak-spawn --host distrobox enter m59-box -- bash claude_tools/planlab.sh   ; then:  $PRIME_WORK/planlab/planlab ROOM.roo [-v] [-a row,col ...] < "srow scol grow gcol" lines (game squares)
W="${PRIME_WORK:-$HOME/src/prime_work}"; mkdir -p "$W/planlab"; cp "$(dirname "$0")/planlab.cpp" "$W/planlab/harness.cpp"; cp "$(dirname "$0")/planlab_clientmove.inc" "$W/planlab/clientmove.inc"; cd "$W/planlab" || exit 1
cp "$W/build/tree/blakserv/roofile.c" . 2>/dev/null
g++ -O2 -fpermissive -w -x c++ -D__forceinline=inline -DBLAK_PLATFORM_LINUX -Wno-write-strings -I"$W/build/tree/include" -I"$W/build/tree/blakserv" -c harness.cpp -o harness.o && g++ harness.o -o planlab && echo built
