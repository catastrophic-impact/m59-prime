#!/usr/bin/env python3
"""bottravel: TRAVEL TEST. Sends test bots from one home town to hunt rooms elsewhere and reports, per trip, how it ended and WHY.
TEST SERVER ONLY (it raises nothing but sets the time scale and starts hunts):  PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 $PRIME_WORK/admin-venv/bin/python claude_tools/bottravel.py
    --home 300        home town room of the bots to use (300 Raza, 50 Tos, 102 Barloque, 150 Cor Noth, 200 Marion, 350 Jasper, 2000 Ko'catan, 2800 Bergensdorf, 2903 Jixa)
    --dests 8         how many hunt rooms to try (spread over the whole map); --rooms 593,74 to name them
    --bots 4          how many test bots travel at the same time (each bot one trip at a time)
    --timeout 120     real seconds per trip; --scale 10 the bot time scale (10 = ten times as fast; walking too)
    --hp N            health the bot is given (0 = its own: its own health decides which routes are survivable)
Outcome per trip: ARRIVED (in the destination room) | TURNED (left its way and came back to a room it had already left, or reached another room for good) | DROPPED (its activity changed: it gave
the journey up) | STUCK (no move for 40 s) | TIMEOUT. Every failed trip prints the room trail, the last decisions of its flight recorder and any GIVE UP / no way / Rescue line, so the reason is in the output.
The same bot is used again for the next destination, set down at its home town door by PBotTestHunt (the real way a hunter starts)."""
import argparse, asyncio, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botscenario import Scenario

WHYS = re.compile(r"GIVE UP|give up|no way|NO WAY|rescue|Rescue|journey|route|stuck|fail|blocked|refus", re.I)

async def identity(sc, bot):
    out = await sc.L.run(f"send object {sc.prime} PBotIdentity id int {bot}")
    m = re.search(r"return from.*?: LIST (\d+)", out, re.S)
    return await sc.lab.list(int(m.group(1))) if m else None

async def hunt_rooms(sc):
    t = await sc.L.run(f"show object {sc.prime}")
    m = re.search(r"plPBotRooms\s*=\s*LIST (\d+)", t)
    if not m: return []
    rooms = await sc.lab.list(int(m.group(1)))
    return [r[0] for r in rooms if isinstance(r, list) and r and isinstance(r[0], int)]

async def reachable(sc, bot, home):
    """the rooms the REGISTRY would consider for this bot at its home door (PBotRouteEstimate with toRid 0: the survivable routes for its own health)"""
    body = await sc.body(bot)
    await sc.L.run(f"send object {sc.prime} PBotTestHunt id int {bot} rid int {home} hp int 0")      # sets it down at its home town door
    await asyncio.sleep(3)
    t = await sc.L.run(f"show object {body}")
    rid, node = int(re.search(r"piNavRid\s*=\s*INT (\d+)", t).group(1)), int(re.search(r"piNavNode\s*=\s*INT (\d+)", t).group(1))
    hp = re.search(r"INT (\d+)", (await sc.L.run(f"send object {body} GetHealth")).split("return")[-1])
    hp = int(hp.group(1)) if hp else 0
    out = await sc.L.run(f"send object {sc.prime} PBotRouteEstimate fromRid int {rid} fromNode int {node} toRid int 0 iHealth int {hp}")
    m = re.search(r"return from.*?: LIST (\d+)", out, re.S)
    lst = await sc.lab.list(int(m.group(1))) if m else []
    return [x for x in lst if isinstance(x, int)], hp

async def trip(sc, bot, dest, timeout, hp):
    body = await sc.body(bot)
    await sc.clean(body)
    t0 = time.time()
    await sc.L.run(f"send object {sc.prime} PBotTestHunt id int {bot} rid int {dest} hp int {hp}")
    trail, last_move, last_pos, why, n = [], t0, None, "", 0
    while time.time() - t0 < timeout:
        await asyncio.sleep(1.5)
        s = await sc.sample(body, t0)
        if not s: continue
        rid, doing = s[1], s[6]
        if rid and (not trail or trail[-1] != rid): trail.append(rid)
        p = (rid, s[2], s[3])
        if p != last_pos: last_pos, last_move = p, time.time()
        if rid == dest: return "ARRIVED", trail, time.time() - t0, ""
        n += 1
        if n % 3 == 0 and time.time() - t0 > 6:                         # its REGISTRY activity (PBA_HUNT = 3, PBA_INN = 2, PBA_NONE = 0 ...): changed = the journey was given up
            ident = await identity(sc, bot)
            if ident and len(ident) > 9 and (ident[7] != 3 or ident[9] != dest):
                return "DROPPED", trail, time.time() - t0, f"registry activity now {ident[7]} (PBA 0 none 1 town 2 inn 3 hunt 4 shop 5 dead), goal room {ident[9]}"
        if time.time() - last_move > 40: return "STUCK", trail, time.time() - t0, f"no move in room {rid} at {s[2]},{s[3]}"
        if len(trail) >= 3 and trail[-1] in trail[:-2] and trail[-1] != dest: return "TURNED", trail, time.time() - t0, "came back to a room it had left"
    return "TIMEOUT", trail, time.time() - t0, ""

async def worker(sc, bot, jobs, results, a):
    while jobs:
        dest = jobs.pop(0)
        out, trail, secs, extra = await trip(sc, bot, dest, a.timeout, a.hp)
        lines = []
        if out != "ARRIVED":
            ev = await sc.events(await sc.body(bot), last=60)
            lines = [e for e in ev if WHYS.search(e)][-6:] or ev[-4:]
        results.append((bot, dest, out, trail, secs, extra, lines))
        print(f"bot {bot:>3} -> {dest:>5}  {out:8} {secs:5.0f}s  rooms {' > '.join(map(str, trail)) or '-'}  {extra}", flush=True)
        for l in lines: print(f"        | {l[:150]}", flush=True)

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", type=int, default=300); ap.add_argument("--dests", type=int, default=8); ap.add_argument("--rooms", default="")
    ap.add_argument("--bots", type=int, default=4); ap.add_argument("--timeout", type=int, default=120); ap.add_argument("--scale", type=int, default=10)
    ap.add_argument("--hp", type=int, default=0); ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    sc = await Scenario.open()
    await sc.L.run(f"set object {sc.prime} piTownLife int 1")
    mine = []
    for b in await sc.bots():
        ident = await identity(sc, b)
        if ident and len(ident) > 6 and ident[6] == a.home: mine.append(b)
    mine = mine[:a.bots]
    if not mine: print(f"no test bot has home {a.home}"); await sc.close(); return
    if a.rooms: dests = [int(x) for x in a.rooms.split(",")]
    else:
        reach, hp0 = await reachable(sc, mine[0], a.home)
        allr = [r for r in await hunt_rooms(sc) if r != a.home and (a.all or r in reach)]
        print(f"bot {mine[0]} has health {hp0}; {len(reach)} rooms reachable by its survivable routes, {len(allr)} of them hunt rooms" + ("" if a.all else " (--all tries every hunt room, reachable or not)"), flush=True)
        step = max(1, len(allr) // a.dests); dests = allr[::step][:a.dests]
    print(f"bots {mine} (home {a.home}) -> rooms {dests}, scale {a.scale}", flush=True)
    # one admin link per travelling bot (opened first: Scenario.open sets the time scale back to 100)
    import botlab as BL
    scs = [sc]
    for _ in mine[1:]:
        link = BL.B.T.AdminLink(); await link.connect(); scs.append(await Scenario.open(link=link, recorder=False))
    await sc.L.run(f"set object {sc.prime} piBotTimeScale int {a.scale}")
    jobs, results = list(dests), []
    await asyncio.gather(*(worker(w, b, jobs, results, a) for w, b in zip(scs, mine)))
    await sc.L.run(f"set object {sc.prime} piBotTimeScale int 100")
    n = {}
    for r in results: n[r[2]] = n.get(r[2], 0) + 1
    print("\nSUMMARY", n); await sc.close()

asyncio.run(main())
