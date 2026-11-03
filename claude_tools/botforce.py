#!/usr/bin/env python3
"""BOTFORCE: put every test bot into a chosen situation AT ONCE instead of waiting for natural behaviour (TEST SERVER ONLY). Combine with timescale.py and botwatch.py --stop-on.
  PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 $PRIME_WORK/admin-venv/bin/python claude_tools/botforce.py MODE [--bots 40] [--rooms 593,74] [--hp 0]
  hunt     each bot is set down at a door of a DIFFERENT hunt room (the catalogue rooms, or --rooms; rooms repeat when there are more bots) and begins to hunt at once (PBotTestHuntHere)
  travel   each bot is sent from its home town to a hunt room the real way (PBotTestHunt: portals, doors, walking)
  act N    every bot begins activity N at once (1 town, 2 inn, 3 hunt, 4 shop, 5 dead) (PBotTestAct)
--hp N sets the bot's health for the test (0 = its own). Then: botwatch.py --scale 10 --every 3 --stop-on STILL,STUCK,NOWAY,MISMATCH."""
import asyncio, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab

async def main():
    a = sys.argv[1:]; arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    if not a or a[0].startswith("--"): sys.exit(__doc__)
    mode = a[0]; nb = int(arg("--bots", "40")); hp = int(arg("--hp", "0")); lab = await Lab.open(); P = lab.prime
    t = await lab.run(f"show object {P}"); m = re.search(r"plPBotRooms\s*=\s*LIST (\d+)", t)
    rooms = [int(x) for x in arg("--rooms", "").split(",") if x] or [r[0] for r in await lab.list(int(m.group(1))) if isinstance(r, list) and r]
    ok = 0
    for i in range(1, nb + 1):
        if not await lab.body(i): continue
        if mode == "act": cmd = f"send object {P} PBotTestAct id int {i} act int {a[1]}"
        else: cmd = f"send object {P} {'PBotTestHuntHere' if mode == 'hunt' else 'PBotTestHunt'} id int {i} rid int {rooms[(i - 1) % len(rooms)]} hp int {hp}"
        out = await lab.run(cmd); ok += 1
    print(f"{mode}: {ok} bots forced" + (f" over {len(rooms)} rooms" if mode != "act" else ""))
    await lab.close()
asyncio.run(main())
