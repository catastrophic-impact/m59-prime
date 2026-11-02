#!/bin/bash
# Bot trace (debug mode for the playerbots). The trace lines (PBOT-TRACE) go to the server's debug log; they switch themselves off after 3000 lines or 15 minutes.
#   scripts/bot_trace.sh on <bot id | all>   start tracing one bot (or every bot)
#   scripts/bot_trace.sh show [N]            print the last N (default 80) trace lines
#   scripts/bot_trace.sh off                 stop tracing and clean the log (the debug log is emptied: the server appends, so this is safe while it runs)
# Env: PRIME_ADMIN_PORT (default 9999), PRIME_SERVER_DIR (default server).
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${PRIME_WORK:-$HOME/boxes/m59-box/src/prime_work}"
LOG="$W/build/${PRIME_SERVER_DIR:-server}/channel/debug.txt"
case "$1" in
  on) [ -n "$2" ] || { echo "usage: bot_trace.sh on <bot id|all>"; exit 1; }
      id=$2; [ "$id" = all ] && id=-1
      "$HERE/prime_set.sh" piPBotTraceEnd 0 >/dev/null; "$HERE/prime_set.sh" piPBotTrace "$id" >/dev/null; echo "tracing bot $2 (off after 3000 lines / 15 min)";;
  show) grep -a "PBOT-TRACE" "$LOG" | tail -n "${2:-80}" | cut -c1-230;;
  off) "$HERE/prime_set.sh" piPBotTrace 0 >/dev/null; "$HERE/prime_set.sh" piPBotTraceEnd 0 >/dev/null; : > "$LOG"; echo "trace off, debug log emptied";;
  *) sed -n 2,8p "$0";;
esac
