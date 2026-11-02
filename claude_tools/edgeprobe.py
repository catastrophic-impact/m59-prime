#!/usr/bin/env python3
"""VERIFY EVERY EDGE-EXIT LANDING WITH THE PLANNER and pick one the bots can really walk to. TEST SERVER ONLY (it sets test bots down):
  PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 python claude_tools/edgeprobe.py [ROOM ..] [--workers 4] [--baker docs/edge_landings.json]
The grid lattice (edgelanding.py) finds floor that touches a side of a room, but the server's planner is stricter than the lattice (about a third of the cases): a landing it picks can be
unreachable (West Jasper west exit (47,1): no way from anywhere). For each baked edge exit this tool puts a test bot EXACTLY on a landing the game puts players on in that room (a non-trap
landing of docs/kod_exits.json), and asks the planner (TestPathTo) for a way to the exit's current square; if there is none it tries other floor squares along that side, nearest the middle first
(up to 10), and keeps the first one the planner reaches. Output: the verified landings in --baker format ({rid: {'toRoo:side': [row, col]}}, read by navbake.ts --edges) and a report of what changed
and which edge exits no tried square could reach: those are MISSING from the file, and navbake.ts drops an edge exit that is missing from the file of a room that was probed (docs/edge_unreachable.json lists them for the manual audit)."""
import asyncio, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botscenario import Scenario, ROOT
import roomreach as R, edgelanding as E, reachmatrix as M

def side_cells(rid, bake, server, side, rows, cols, touch=1.0, limit=10):
    g = E.floor_grid(server, bake[rid]["roo"])
    if not g: return []
    ncols, nrows, cell, links, hts = g; comp, main = E.main_floor_region(g)
    mid = {"W": rows / 2, "E": rows / 2, "N": cols / 2, "S": cols / 2}[side]; seen = {}
    for i, c in enumerate(comp):
        if c != main or hts[i] != hts[i]: continue
        rr, cc = divmod(i, ncols); y = (rr + 0.5) * cell / 1024.0; x = (cc + 0.5) * cell / 1024.0
        d = {"N": y, "W": x, "S": rows - y, "E": cols - x}[side]
        if d > touch: continue
        sq = (int(y) + 1, int(x) + 1); along = abs((y if side in "WE" else x) - mid)
        if sq not in seen or along < seen[sq]: seen[sq] = along
    out = sorted(seen, key=lambda q: seen[q])
    # spread: the nearest few and then every k-th, so a pocket next to the middle does not use up every try
    return (out[:4] + out[4::max(1, len(out) // 6)])[:limit]

async def probe_room(sc, bot, bake, rid, trap, server):
    r = bake[rid]; body = await sc.body(bot)
    dump = json.load(open(os.path.join(R.W, "navtmp", "roomdump", r["roo"] + ".json"))); rows, cols = dump["rows"], dump["cols"]
    anchors = [a for a in sorted(M.kod_arrivals(rid)) if [rid, a[0], a[1]] not in trap][:3]
    sides = {e[0]: e[1] for e in R.edges_of(r["roo"]).items()}
    res = {}; changed = []; unreachable = []
    exits = [d for d in r["doors"] if d.get("edge") == 1 and sides.get(d["to"])]
    if not anchors or not exits: return res, changed, unreachable, "no anchor" if exits else ""
    async def reach(goal):
        for a in anchors:
            if not await M.place_exact(sc, bot, body, rid, a): continue
            if abs(a[0] - goal[0]) + abs(a[1] - goal[1]) <= 1: return True
            await sc.L.run(f"send object {body} TestPathTo iRow int {goal[0]} iCol int {goal[1]}")
            st = await M.state_of(sc, body)
            if st and st[0] != 3: return True
        return False
    done = {}
    for d in exits:
        side = sides[d["to"]]; key = (side, d["row"], d["col"])
        if key not in done:
            pick = None
            if await reach((d["row"], d["col"])): pick = (d["row"], d["col"])
            else:
                for q in side_cells(rid, bake, server, side, rows, cols):
                    if q != (d["row"], d["col"]) and await reach(q): pick = q; break
            done[key] = pick
        pick = done[key]
        if pick is None: unreachable.append(f"{d['to']}:{side}"); continue
        res[f"{d['to']}:{side}"] = list(pick)
        if pick != (d["row"], d["col"]): changed.append(f"{d['to']}:{side} {d['row']},{d['col']} -> {pick[0]},{pick[1]}")
    return res, changed, unreachable, ""

async def main():
    a = sys.argv[1:]; arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    nw = int(arg("--workers", "4")); server = os.environ.get("PRIME_SERVER_DIR", "server2"); outp = arg("--baker", os.path.join(ROOT, "docs", "edge_landings.json"))
    bake = {x["rid"]: x for x in json.load(open(os.path.join(R.W, "navtmp", "navbake.json")))}
    trap = json.load(open(os.path.join(ROOT, "docs", "trap_landings.json"))) if os.path.exists(os.path.join(ROOT, "docs", "trap_landings.json")) else []
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and not (i and a[i - 1].startswith("--"))]      # positional args only (not the values of options)
    rooms = [int(x) for x in pos if x.isdigit()] or sorted(rid for rid, r in bake.items() if any(d.get("edge") == 1 for d in r["doors"]) and R.find_grid(server, r["roo"]))
    scs = [await Scenario.open(recorder=False) for _ in range(nw)]; pool = await scs[0].bots(); queue = list(rooms); t0 = time.time()
    result = {}; changes = []; unreach = []
    print(f"{len(rooms)} rooms with edge exits, {nw} workers", flush=True)
    async def worker(wi):
        mine = pool[wi::nw]
        while queue and mine:
            rid = queue.pop(0); res, ch, un, note = await probe_room(scs[wi], mine[0], bake, rid, trap, server)
            if res: result[str(rid)] = res
            for c in ch: changes.append(f"room {rid} {bake[rid]['name']}: {c}")
            for u in un: unreach.append(f"room {rid} {bake[rid]['name']}: {u}")
            print(f"[{int(time.time() - t0):>4}s] room {rid} {bake[rid]['name'][:26]}: {len(res)} exits ok, {len(ch)} moved, {len(un)} unreachable {note}", flush=True)
    await asyncio.gather(*[worker(w) for w in range(nw)])
    for sc in scs: await sc.close()
    json.dump(result, open(outp, "w")); json.dump(sorted(unreach), open(os.path.join(ROOT, "docs", "edge_unreachable.json"), "w"), indent=0)
    print(f"{len(changes)} landings moved, {len(unreach)} edge exits no square could reach -> {outp}, docs/edge_unreachable.json")
    for c in changes[:40]: print("  moved:", c)
    for u in sorted(unreach)[:40]: print("  UNREACHABLE:", u)

if __name__ == "__main__": asyncio.run(main())
