#!/bin/bash
# Change a Prime rule on the running test server (see overlay/kod/object/prime/primerules.kod).  Usage: prime_set.sh piReagentMode 1 | prime_set.sh show
HERE="$(cd "$(dirname "$0")" && pwd)"; A="python3 $HERE/admin_prime.py"
$A "send class system GetPrime" >/dev/null
ID=$($A "show instances primeclasses" | grep -o "OBJECT [0-9]*" | head -1 | cut -d" " -f2)
if [ "$1" = show ]; then $A "show object $ID" | grep "piDeath\|piReagent\|piNoReagent\|pbUnlimited\|pbBow\|piBow\|piDagger\|piBrax\|pbFaction\|piTown\|piPlayer\|piBotTime\|piBotHunt\|piBotFight\|piBotFlee\|pbMurder\|pbBotMove\|pbClass\|piSpirit\|pbSpirit\|Bot"; exit; fi
$A "set object $ID $1 int $2" | tail -2
