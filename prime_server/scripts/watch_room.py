#!/usr/bin/env python3
"""Place a bot at a square of a room (as if it had just zoned in; TEST ONLY, huge health) and let it hunt; print where it goes and what it visits.
Usage: PRIME_ADMIN_PORT=9999 watch_room.py ROOM ROW COL [--secs 240] [--trace]"""
import asyncio, re, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_scenarios as B
async def main():
    a = sys.argv[1:]; secs = 240; trace = "--trace" in a
    if "--secs" in a:
        i = a.index("--secs"); secs = int(a[i + 1]); del a[i:i + 2]
    a = [x for x in a if x != "--trace"]
    rid, row, col = map(int, a[:3])
    L = B.T.AdminLink(); await L.connect()
    prime = int(re.search(r"OBJECT\s+(\d+)", await L.run("show instances primeclasses")).group(1))
    drv = B.Driver(L, print, prime)
    bot = (await drv.bots_with_bodies())[-1]
    if trace:
        await drv.prop("piPBotTraceEnd", 0); await drv.prop("piPBotTrace", bot)
    await drv.send("PBotTestHuntAt", id=bot, rid=rid, row=row, col=col, hp=99999)
    t0 = time.time(); squares = set(); nodes = set(); last = None; kills = 0
    while time.time() - t0 < secs:
        st = await drv.state(bot)
        if st is None: print("no body"); break
        squares.add((st["row"], st["col"])); nodes.add(st["node"]); kills = st["kills"]
        cur = (st["rid"], st["row"], st["col"])
        if time.time() - t0 > 0 and int(time.time() - t0) % 15 < 2 and cur != last:
            print(f"[{int(time.time()-t0):3d}s] room {st['rid']} at {st['row']},{st['col']} node {st['node']} kills {kills} stuck {st['stuck']} failed {st['failed']} foes {st['foes']}", flush=True); last = cur
        await asyncio.sleep(2)
    print(f"visited {len(squares)} squares, {len(nodes)} different nodes {sorted(nodes)}, kills {kills}")
    await L.close()
asyncio.run(main())
