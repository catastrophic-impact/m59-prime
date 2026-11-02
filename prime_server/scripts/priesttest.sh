#!/bin/bash
# Test helper: a Priest logs in (headless), gets Holy Touch / Mana Focus / Zap at 80%, is teleported into the Mausoleum and fights with Holy Touch.
# Usage: priesttest.sh account charname [extra headless args]
HERE="$(cd "$(dirname "$0")" && pwd)"; A="python3 $HERE/admin_prime.py"
source "$HERE/../../prime_client/scripts/env.sh"; cd "$PRIME_WORK/client_build/tree"
U=$1; N=$2; shift 2
node tools/headless/client.ts --user $U --pass x --char $N --class 2 --stay 70 --cast 21:self --castat 30 --castevery 12 --attack "$@" > /tmp/claude-1000/priest.log 2>&1 &
sleep 9
P=$($A "show users" | grep -i "$N" | awk '{print $2}')
for sp in 21 67 23 27; do $A "send object $P AddSpell num int $sp iability int 80" >/dev/null; done
$A "send object $P TeleportTo RID int 306" >/dev/null; sleep 3
$A "send object $P GainHealth amount int 500" >/dev/null
echo "player $P"; $A "show object $P" | grep "piPlayerClass\|piMight \|piMysticism \|piMax_Mana\|piMana "
$A "show object $P" | grep -A0 "plUsing"
wait
grep "MSG\|cast" /tmp/claude-1000/priest.log | grep -v "safety\|Welcome\|mail\|peace" | cut -c1-200 | head -40
