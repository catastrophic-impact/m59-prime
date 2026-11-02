#!/bin/bash
# Test helper: like slamtest.sh but the slam goes through the real wire path (UC_SHARDS_OBJECT "skill 407" from the headless client).
HERE="$(cd "$(dirname "$0")" && pwd)"; A="python3 $HERE/admin_prime.py"
source "$HERE/../../prime_client/scripts/env.sh"; cd "$PRIME_WORK/client_build/tree"
node tools/headless/client.ts --user ${1:-sw1} --pass x --char ${2:-Wireslam} --class 1 --stay 90 --skill 407:nearest --castat 40 --castevery 6 > /tmp/claude-1000/slamwire.log 2>&1 &
sleep 9
P=$($A "show users" | grep -i "${2:-Wireslam}" | awk '{print $2}')
$A "send object $P TeleportTo RID int 306" >/dev/null; sleep 3
$A "send object $P GainHealth amount int 500" >/dev/null
$A "send object $P AddSkill num int 407 iability int 80" >/dev/null
SH=$($A "create object MetalShield" | grep -o "[0-9]*\.$" | tr -d .)
$A "send object $P NewHold what object $SH" >/dev/null; $A "send object $P TryUseItem what object $SH" >/dev/null
M=$($A "create object Mummy" | grep -o "[0-9]*\.$" | tr -d .)
R=$($A "show object $P" | grep poOwner | grep -o "OBJECT [0-9]*" | cut -d" " -f2)
ROW=$($A "show object $P" | grep "piRow " | grep -o "[0-9]*$"); COL=$($A "show object $P" | grep "piCol " | grep -o "[0-9]*$")
$A "send object $R NewHold what object $M new_row int $ROW new_col int $((COL+1))" >/dev/null
echo "player $P mummy $M"
wait
grep "skill\|MSG" /tmp/claude-1000/slamwire.log | grep -i "skill\|stun\|slam" | cut -c1-200
