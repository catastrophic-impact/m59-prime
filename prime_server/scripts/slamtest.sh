#!/bin/bash
# Test helper: a classed Warrior logs in (headless), gets Shield Slam + a shield + a mummy next to him, then slams twice. Prints the game messages.
HERE="$(cd "$(dirname "$0")" && pwd)"
A="python3 $HERE/admin_prime.py"
source "$HERE/../../prime_client/scripts/env.sh"
cd "$PRIME_WORK/client_build/tree"
node tools/headless/client.ts --user ${1:-slam1} --pass x --char ${2:-Slammer} --class 1 --stay 75 > /tmp/claude-1000/slam.log 2>&1 &
sleep 9
P=$($A "show users" | grep -i "${2:-Slammer}" | awk '{print $2}')
$A "send object $P TeleportTo RID int 306" >/dev/null; sleep 3
$A "send object $P GainHealth amount int 500" >/dev/null
R=$($A "show object $P" | grep poOwner | grep -o "OBJECT [0-9]*" | cut -d' ' -f2)
$A "send object $P AddSkill num int 407 iability int 80" >/dev/null
SH=$($A "create object MetalShield" | grep -o "[0-9]*\.$" | tr -d .)
$A "send object $P NewHold what object $SH" >/dev/null; $A "send object $P TryUseItem what object $SH" >/dev/null
M=$($A "create object Mummy" | grep -o "[0-9]*\.$" | tr -d .)
ROW=$($A "show object $P" | grep "piRow " | grep -o "[0-9]*$"); COL=$($A "show object $P" | grep "piCol " | grep -o "[0-9]*$")
$A "send object $R NewHold what object $M new_row int $ROW new_col int $((COL+1))" >/dev/null
SK=$($A "show instances ShieldSlam" | grep -o "OBJECT [0-9]*" | head -1 | cut -d' ' -f2)
echo "player $P room $R shield $SH mummy $M skill $SK"
$A "send object $SK DoSkill who object $P oTarget object $M" >/dev/null; sleep 1
echo "mummy enchantments:"; $A "show object $M" | grep -i plEnch
$A "send object $SK DoSkill who object $P oTarget object $M" >/dev/null; sleep 2
PR=$($A "send object 0 GetPrime" | grep -o "OBJECT [0-9]*" | tail -1 | cut -d" " -f2)
echo "prime immunity list:"; $A "show object $PR" | grep -i plCCImmune; LST=$($A "show object $PR" | grep plCCImmune | grep -o "LIST [0-9]*" | cut -d" " -f2); [ -n "$LST" ] && $A "show list $LST" | head -12
wait
grep "MSG\|SAID" /tmp/claude-1000/slam.log | cut -c1-200
