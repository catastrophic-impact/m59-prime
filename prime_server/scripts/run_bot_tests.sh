#!/bin/bash
# Run the playerbot scenario tests against the running test server (see bot_scenarios.py for options); output is also in prime_server/test_logs/.
WORK="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
exec "$WORK/admin-venv/bin/python" -u "$(dirname "$0")/bot_scenarios.py" "$@"
