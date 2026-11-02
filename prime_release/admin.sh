#!/usr/bin/env bash
# Run one admin command on the running server, e.g.  ./admin.sh "show users"   ./admin.sh "save game"   (the admin console port is only open on this machine)
HERE="$(cd "$(dirname "$0")" && pwd)"; export PRIME_ADMIN_PORT="${PRIME_ADMIN_PORT:-9999}"
exec python3 "$HERE/tools/admin_prime.py" "$@"
