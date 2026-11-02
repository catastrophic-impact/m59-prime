#!/bin/bash
# Build the Prime Kod (and optionally the server/compiler) in the build tree, INSIDE the distrobox. Does NOT touch any running server.
# Run it detached from the sandbox (see claude_tools/README.md):
#   cp -a prime_server/overlay/. $W/build/tree/ ; (cd $W/build/tree/kod/object && find . -iname 'prime*.kod' -o -iname 'playerbot.kod' | xargs touch)
#   (setsid nohup flatpak-spawn --host distrobox enter m59-box -- bash -c "$PWD/claude_tools/kodbuild.sh [--c]" >/dev/null 2>&1 &)
# --c : also rebuild the compiler/utils first (needed when blakcomp/function.c changed) and the server binary after (when blakserv C changed).
# Done marker: $W/build/kodbuild.done (the box and the sandbox both see the build folder; the sandbox /tmp and the host $HOME are NOT the box's). Logs: $W/build/kod_pass_N.log, server_build.log.
W="${PRIME_WORK:-$HOME/src/prime_work}"   # inside the box $HOME is the box home (~/boxes/<name> on the host): the work folder is $HOME/src/prime_work
DONE="$W/build/kodbuild.done"; rm -f "$DONE"; cd "$W/build/tree" || exit 1
[ "$1" = "--c" ] && make -f makefile.linux Bcompiler Butil > "$W/build/compiler_build.log" 2>&1
for i in 1 2 3; do make -f makefile.linux Bkod RELEASE=1 > "$W/build/kod_pass_$i.log" 2>&1; grep -q "Need to recompile" "$W/build/kod_pass_$i.log" || break; done
[ "$1" = "--c" ] && make -f makefile.linux Bserver > "$W/build/server_build.log" 2>&1
echo done > "$DONE"
# afterwards: check grep -c "Need to recompile" on the last pass is 0; the only 'Error 1 (ignored)' lines (makedirs) and 'Unable to save rsc file' are normal.
# deploy to server2: kill it by pid, cp $W/build/tree/blakserv/debug/blakserv $W/build/server2/ (only if the C changed), then prime_server/scripts/test_redeploy.sh (WIPES server2's savegame).
