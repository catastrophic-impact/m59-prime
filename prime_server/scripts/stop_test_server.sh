#!/bin/bash
# Saves the game first (if the server answers), then stops only the Prime test server (the one running from $PRIME_WORK/build/server), never another blakserv.
python3 "$(dirname "$0")/admin_prime.py" "save game" 2>&1 | tail -1
flatpak-spawn --host distrobox enter m59-box -- bash -c 'for p in $(pgrep -f "^./blakserv"); do case "$(readlink /proc/$p/cwd)" in *prime_work*) kill $p; echo stopped $p;; esac; done'
