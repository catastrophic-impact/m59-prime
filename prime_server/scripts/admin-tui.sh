#!/bin/bash
# Terminal admin for the Prime server: start / stop (saves first) / restart / save, the Prime rules, accounts, logs, console.
# Creates a private Python venv with 'textual' on the first run (in $PRIME_WORK/admin-venv, outside the project).
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
VENV="$WORK/admin-venv"
if [ ! -x "$VENV/bin/python" ]; then
  echo "First run: creating $VENV ..." >&2
  python3 -m venv "$VENV" && "$VENV/bin/pip" install -q textual || exit 1
fi
exec "$VENV/bin/python" "$HERE/../tools/admin_tui.py" "$@"
