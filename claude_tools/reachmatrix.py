#!/usr/bin/env python3
"""REACH MATRIX BY THE PLANNER'S OWN RULES: for every room, from EVERY arrival square (every square the GAME's door and edge exit tables put a player on: docs/kod_exits.json from kodexits.py) the server's planner is asked for a way to EVERY door / edge landing
of that room. (The grid lattice of roomreach.py says 'reachable' where the planner says 'no way' in about a third of the cases; bots live by the planner.) TEST SERVER ONLY (it sets test bots down):
  PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 python claude_tools/reachmatrix.py [ROOM ..] [--all-open] [--out docs/reach_matrix] [--write-trap] [--workers 4]
Method: a test bot is put down EXACTLY on the arrival square (PBotTestPlace; PBotTestPath would move a bot out of a pocket) and told to walk to the door (PlayerBot.TestPathTo): the first plan is made at once and PathState says 3 = no way.
To stay short each arrival tries doors until one has a way, then only the doors no earlier arrival reached. An arrival the bot cannot be put on exactly is listed as 'unplaceable' (not judged).
Output: docs/reach_matrix/matrix.json and report.md: per room the arrivals with NO way to any door (SEALED ARRIVAL: a bot put down there can never leave), the doors NO arrival can reach (DEAD DOOR),
and the single failing pairs (partial). 'Doors' include edge exits (their landing square) and portals; arrivals that are also door squares count as doors reached by themselves.
--write-trap writes the sealed landings and the POCKETS (reach under a third of the room's doors) as [destRid, row, col] to docs/trap_landings.json, which navbake.ts (via navrebake.sh) keeps bots from using. Use it after ANY change to the walker, the planner or the nav data; feed the sealed arrivals/dead doors into docs/world_map_exclusions.json (worldmap.py) after the owner has seen them."""
import asyncio, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botscenario import Scenario, ROOT
import botlab
W = os.path.expanduser("~/boxes/m59-box/src/prime_work")

_KOD = None
def kod_arrivals(rid):
    """{(row, col): {'SRCROOM@door square' | 'SRCROOM:side'}} = every square the GAME puts a player on when entering this room (docs/kod_exits.json, made by kodexits.py)"""
    global _KOD
    if _KOD is None: _KOD = json.load(open(os.path.join(ROOT, "docs", "kod_exits.json")))
    out = {}
    for src, r in _KOD.items():
        for d in r["doors"]:
            if d[2] == rid: out.setdefault((d[3], d[4]), set()).add(f"{r['name']}@{d[0]},{d[1]}")
        for e in r["edges"]:
            if e[1] == rid: out.setdefault((e[2], e[3]), set()).add(f"{r['name']}:{e[0]}")
    return out

def room_pairs(bake, rid):
    """arrivals = the game's exact landings (kodexits.py), doors = the baked doors of the room (edge exits at their landing on the real floor, portals, shops)"""
    r = bake[rid]; arr = kod_arrivals(rid); doors = {}
    for d in r["doors"]: doors.setdefault((d["row"], d["col"]), set()).add(d["to"] or "?")
    return arr, doors

async def state_of(sc, body):
    t = await sc.L.run(f"send object {body} PathState")
    m = re.search(r"return from.*?: LIST (\d+)", t, re.S)
    return await sc.lab.list(int(m.group(1))) if m else None      # [state, steps, plans, ?, row, col]; state 3 = no way

async def place_exact(sc, bot, body, rid, a, tries=60):
    """PBotTestPlace and wait until the body stands on the very square (the live registry puts bots down exactly like this). False = it never did (an occupied square, a start the placement moves)."""
    await sc.clean(body)
    await sc.L.run(f"send object {sc.prime} PBotTestPlace id int {bot} rid int {rid} row int {a[0]} col int {a[1]} hp int 99999")
    for k in range(tries):
        await asyncio.sleep(0.1)
        s = await sc.sample(body)
        if s and s[1] == rid and (s[2], s[3]) == tuple(a): return True
        if k % 20 == 19: await sc.L.run(f"send object {sc.prime} PBotTestPlace id int {bot} rid int {rid} row int {a[0]} col int {a[1]} hp int 99999")
    return False

async def check_room(sc, bot, bake, rid):
    """arrivals x doors, cheaply: each arrival tries doors until one has a way (then only the doors no earlier arrival has reached); a bot is put down EXACTLY on the arrival before every try"""
    arr, doors = room_pairs(bake, rid)
    if not arr or not doors: return {"rid": rid, "name": bake[rid]["name"], "skipped": "no arrivals" if not arr else "no doors"}
    body = await sc.body(bot); res = {}; unplaceable = []; reached = set()
    for a in sorted(arr):
        ok_any = False; tested = 0
        for d in sorted(doors):
            if a == d: res[(a, d)] = "same"; reached.add(d); ok_any = True; continue
            if ((a[0] - d[0]) ** 2 + (a[1] - d[1]) ** 2) ** 0.5 <= 1.5: res[(a, d)] = "near"; reached.add(d); continue   # a door walk ends within 1.5 squares of the door: the bot is there already (the planner answers 'no way' for a goal it stands at)
            if ok_any and d in reached: continue
            if not await place_exact(sc, bot, body, rid, a):
                unplaceable.append(list(a)); break
            await sc.L.run(f"send object {body} TestPathTo iRow int {d[0]} iCol int {d[1]}")
            st = await state_of(sc, body); tested += 1
            if not st or len(st) < 6: res[(a, d)] = "unreadable"; continue
            res[(a, d)] = "noway" if st[0] == 3 else "ok"
            if st[0] != 3: reached.add(d); ok_any = True
    # POCKETS: a landing that had a no-way try but also a way is tried against up to 6 other doors spread over the room: reaching less than a third of the room's doors = a pocket (West Jasper (52,35): one door beside it, nothing else)
    pockets = []
    for a in sorted(arr):
        mine = {d: v for (a2, d), v in res.items() if a2 == a}
        if "noway" not in mine.values() or "ok" not in mine.values(): continue
        rest = [d for d in sorted(doors) if d != a and d not in mine and ((a[0] - d[0]) ** 2 + (a[1] - d[1]) ** 2) ** 0.5 > 1.5]
        for d in rest[::max(1, len(rest) // 6)][:6]:      # at most 6 doors, spread over the room: enough to tell a pocket from a landing that reaches the room
            if not await place_exact(sc, bot, body, rid, a): break
            await sc.L.run(f"send object {body} TestPathTo iRow int {d[0]} iCol int {d[1]}")
            st = await state_of(sc, body); mine[d] = "noway" if (st and st[0] == 3) else "ok"; res[(a, d)] = mine[d]
        others = [v for d, v in mine.items() if d != a]
        if others and sum(1 for v in others if v == "ok") * 3 < len(others): pockets.append(list(a))
    first = sorted(arr)[0]; await place_exact(sc, bot, body, rid, first)
    out = {"rid": rid, "name": bake[rid]["name"], "arrivals": {f"{a[0]},{a[1]}": sorted(arr[a]) for a in arr}, "doors": {f"{d[0]},{d[1]}": sorted(doors[d]) for d in doors}, "pairs": {f"{a[0]},{a[1]}>{d[0]},{d[1]}": v for (a, d), v in res.items()}, "unplaceable": unplaceable}
    tested_arr = {a for (a, d) in res}
    sealed = [a for a in tested_arr if not any(res[(a2, d)] == "ok" for (a2, d) in res if a2 == a) and any(res[(a2, d)] == "noway" for (a2, d) in res if a2 == a)]   # a door that IS the arrival square is no way out
    out["pockets"] = pockets; out["sealed_arrivals"] = [list(a) for a in sealed]; out["dead_doors"] = [list(d) for d in doors if d not in reached and not unplaceable]
    out["noway_pairs"] = [f"{a[0]},{a[1]}>{d[0]},{d[1]}" for (a, d), v in res.items() if v == "noway"]
    return out

async def main():
    a = sys.argv[1:]; arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    outd = arg("--out", os.path.join(ROOT, "docs", "reach_matrix")); os.makedirs(outd, exist_ok=True)
    bake = {x["rid"]: x for x in json.load(open(os.path.join(W, "navtmp", "navbake.json")))}
    rooms = [int(x) for x in a if x.isdigit()]
    if "--all-open" in a:
        wm = json.load(open(os.path.join(ROOT, "docs", "world_map.json"))); wm = wm["rooms"] if isinstance(wm, dict) and "rooms" in wm else wm
        items = wm.items() if isinstance(wm, dict) else enumerate(wm)
        rooms = sorted(int(k) if isinstance(wm, dict) else r["rid"] for k, r in items if r.get("status") == "OPEN" and (int(k) if isinstance(wm, dict) else r["rid"]) in bake)
    nw = int(arg("--workers", "4")); t0 = time.time(); results = {}
    scs = [await Scenario.open(recorder=False) for _ in range(nw)]; pool = await scs[0].bots()
    print(f"{len(rooms)} rooms, {len(pool)} test bots, {nw} workers; output {outd}", flush=True)
    queue = list(rooms)
    async def worker(wi):
        sc = scs[wi]; mine = pool[wi::nw]; bi = 0
        while queue:
            rid = queue.pop(0); r = None
            for tries in range(3):
                if not mine: break
                r = await check_room(sc, mine[bi % len(mine)], bake, rid)
                if r.get("skipped") == "placement did not take": bi += 1; continue
                break
            r = r or {"rid": rid, "skipped": "no test bot could be placed"}; results[rid] = r
            flag = "" if r.get("skipped") or not (r.get("sealed_arrivals") or r.get("dead_doors") or r.get("pockets")) else f"  SEALED {r['sealed_arrivals']} POCKETS {r['pockets']} DEAD DOORS {r['dead_doors']}"
            print(f"[{int(time.time() - t0):>5}s] {len(results)}/{len(rooms)} room {rid} {r.get('name', '')[:28]}: " + (r.get("skipped") or f"{len(r['pairs'])} tries, {len(r['noway_pairs'])} no way" + (f", unplaceable {r['unplaceable']}" if r['unplaceable'] else "")) + flag, flush=True)
    await asyncio.gather(*[worker(w) for w in range(nw)])
    for sc in scs: await sc.close()
    results = [results[k] for k in sorted(results)]; json.dump(results, open(os.path.join(outd, "matrix.json"), "w"))
    L = [f"# Reach matrix by the planner ({time.strftime('%Y-%m-%d %H:%M')}), {len(results)} rooms", "",
         "SEALED ARRIVAL = a bot put down there has no way to any door of the room. DEAD DOOR = no arrival square of the room has a way to it.", ""]
    for r in results:
        if r.get("skipped"): L.append(f"- room {r['rid']} {r.get('name', '')}: skipped ({r['skipped']})"); continue
        if r["sealed_arrivals"] or r["dead_doors"]: L.append(f"- **room {r['rid']} {r['name']}**: sealed arrivals {r['sealed_arrivals']} (from {[r['arrivals'][f'{a[0]},{a[1]}'] for a in r['sealed_arrivals']]}); dead doors {[(d, r['doors'][f'{d[0]},{d[1]}']) for d in r['dead_doors']]}")
    L.append(""); L.append("Rooms with only single failing pairs: " + ", ".join(f"{r['rid']} ({len(r['noway_pairs'])})" for r in results if not r.get("skipped") and r["noway_pairs"] and not r["sealed_arrivals"] and not r["dead_doors"]))
    if "--write-trap" in a:
        trap = sorted([r["rid"], x[0], x[1]] for r in results if not r.get("skipped") for x in r["sealed_arrivals"] + r.get("pockets", []))
        json.dump(trap, open(os.path.join(ROOT, "docs", "trap_landings.json"), "w")); print(f"{len(trap)} trap landings -> docs/trap_landings.json (the baker reads it: navrebake.sh)")
    open(os.path.join(outd, "report.md"), "w").write("\n".join(L) + "\n"); print("report", os.path.join(outd, "report.md"))

if __name__ == "__main__": asyncio.run(main())
