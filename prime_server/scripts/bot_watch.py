#!/usr/bin/env python3
"""Watch ONE bot: set it down in a hunt room (or walk it there) and print its state every few seconds, so its movement can be read as a trail.
Usage: PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 admin-venv/bin/python scripts/bot_watch.py ROOM [--secs 180] [--hp 2000] [--walk] [--step 3]"""
import argparse, asyncio, re, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_scenarios as B
T = B.T

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("room", type=int)
    ap.add_argument("--secs", type=int, default=180)
    ap.add_argument("--hp", type=int, default=2000)
    ap.add_argument("--walk", action="store_true")
    ap.add_argument("--step", type=int, default=3)
    ap.add_argument("--trace", action="store_true", help="turn the bot trace on for this bot (scripts/bot_trace.sh show / off)")
    a = ap.parse_args()
    L = T.AdminLink(); await L.connect()
    out = await L.run("show instances primeclasses")
    prime = int(re.search(r"OBJECT\s+(\d+)", out).group(1))
    drv = B.Driver(L, lambda m: print(m, flush=True), prime)
    await drv.prop("piTownLife", 1); await drv.prop("piBotTimeScale", 100); await drv.prop("piPBotNoRisk", 1)
    bots = await drv.bots_with_bodies()
    bot = bots[-1]
    if a.trace:
        await drv.prop("piPBotTraceEnd", 0); await drv.prop("piPBotTrace", bot)
    await drv.send("PBotTestHunt" if a.walk else "PBotTestHuntHere", id=bot, rid=a.room, hp=a.hp)
    t0 = time.time(); last = None
    while time.time() - t0 < a.secs:
        st = await drv.state(bot)
        line = B.fmt(st)
        if line != last:
            print(f"[{int(time.time()-t0):4d}s] {line}", flush=True)
            last = line
        await asyncio.sleep(a.step)
    await L.close()
asyncio.run(main())
