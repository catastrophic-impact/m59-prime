#!/usr/bin/env python3
"""WHY DID THE PLANNER SAY 'NO WAY'?  Classifies every 'BSPFindPathStep GRID-NOWAY' line of a server's channel/error.txt against the room's grid dump (offline, read-only).
  PRIME_ADMIN_PORT=9999 python3 claude_tools/nowayclass.py [--log PATH] [--since "Nov  01 2026 08:"] [--grids server2] [--top 15]
The server logs room, start and goal (roo units, x = col, y = row, 1024 per square) and how many cells the search explored. For each event this tool looks both ends up in the grid:
  START-IN-WALL     start cell is not walkable (nearest walkable cell farther than `near`)
  START-POCKET      start is walkable but its region is NOT the room's main region (a sealed pocket / porch)
  GOAL-IN-WALL      goal cell not walkable (nothing walkable within `near` squares of it): the goal itself is off the floor
  GOAL-OTHER-REGION goal is walkable but in another region than the start (a wall or a closed area between)
  GOAL-NEAR         goal is not reachable, but the START'S REGION comes within 1.5 squares of it (what a door/edge walk needs: 'ends within a square and a half')
  SAME-REGION       both ends are in one region by the lattice rule (the planner's link rule is stricter than the lattice: a margin or a one-way edge)
Output: counts per class, then the top (room, start, goal) groups with their class and how often they repeated (repeats = a bot retrying the same impossible walk).
The room numbers in the log are roomdata ids of the RUNNING server: the tool asks that server over admin (PRIME_ADMIN_PORT, read-only) to translate them, so run it against the server the log belongs to.
Needs the grid dump of the room (claude_tools/roomgrid.py ROOM on server2); rooms without a dump are counted as NO-DUMP and listed."""
import asyncio, collections, json, math, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import roomreach as R
from botlab import Lab

def room_names():
    bake = json.load(open(os.path.join(R.W, "navtmp", "navbake.json")))
    return {x["rid"]: x["roo"] for x in bake}, {x["roo"]: x["rid"] for x in bake}

def nearest(ncols, nrows, cell, links, r0, c0, radius):
    best = None
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            rr, cc = r0 + dr, c0 + dc
            if 0 <= rr < nrows and 0 <= cc < ncols and links[rr * ncols + cc]:
                d = dr * dr + dc * dc
                if best is None or d < best[0]: best = (d, rr, cc)
    return best

def classify(g, comp, sizes, main, fx, fy, tx, ty, near_sq=1.5):
    ncols, nrows, cell, links = g
    cell_of = lambda x, y: (int(y / cell), int(x / cell))
    rs, cs = cell_of(fx, fy); rg, cg = cell_of(tx, ty)
    inside = lambda r, c: 0 <= r < nrows and 0 <= c < ncols
    def comp_at(r, c): return comp[r * ncols + c] if inside(r, c) and links[r * ncols + c] else 0
    cs_comp = comp_at(rs, cs); cg_comp = comp_at(rg, cg)
    if not cs_comp:
        b = nearest(ncols, nrows, cell, links, rs, cs, 6)
        if not b: return "START-IN-WALL", {}
        cs_comp = comp[b[1] * ncols + b[2]]
    if cs_comp != main: return "START-POCKET", {"start_region": sizes[cs_comp]}
    if not cg_comp:
        b = nearest(ncols, nrows, cell, links, rg, cg, int(near_sq * 1024 / cell))
        if not b: return "GOAL-IN-WALL", {}
        cg_comp = comp[b[1] * ncols + b[2]]
        if cg_comp == cs_comp: return "SAME-REGION", {"goal_cell_walkable": False}
    if cg_comp != cs_comp:
        # does the start's region come within near_sq squares of the goal?
        rad = int(near_sq * 1024 / cell)
        for dr in range(-rad, rad + 1):
            for dc in range(-rad, rad + 1):
                if inside(rg + dr, cg + dc) and comp[(rg + dr) * ncols + cg + dc] == cs_comp and dr * dr + dc * dc <= rad * rad:
                    return "GOAL-NEAR", {"goal_region": sizes[cg_comp]}
        return "GOAL-OTHER-REGION", {"goal_region": sizes[cg_comp]}
    return "SAME-REGION", {}

async def main():
    a = sys.argv[1:]; arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    log = arg("--log", os.path.join(R.W, "build", "server", "channel", "error.txt")); since = arg("--since", ""); gs = arg("--grids", "server2"); top = int(arg("--top", "15"))
    name_of, rid_of = room_names()
    lab = await Lab.open(); rmap = await lab.room_map(); await lab.close()      # roomdata id -> nav rid (this server's run)
    roo_of = lambda rd: name_of.get(rmap.get(rd))
    events = []
    for l in open(log, errors="replace"):
        if "GRID-NOWAY" not in l or since not in l: continue
        m = re.search(r"room (\d+) from \((\d+),(\d+)\) to \((\d+),(\d+)\), cells explored (\d+) of (\d+)", l)
        if m: events.append(tuple(map(int, m.groups())))
    cache = {}; res = collections.Counter(); groups = collections.defaultdict(lambda: [0, None, None]); nodump = collections.Counter()
    for rm, fx, fy, tx, ty, ex, tot in events:
        roo = roo_of(rm)
        if rm not in cache:
            pass
        if rm not in cache:
            g = R.load(gs, roo) if roo else None
            if g:
                comp, sizes = R.components(g[0], g[1], g[3]); main = max(range(1, len(sizes)), key=lambda i: sizes[i])
                cache[rm] = (g, comp, sizes, main)
            else: cache[rm] = None
        c = cache[rm]
        if not c: nodump[rmap.get(rm, -rm)] += 1; res["NO-DUMP"] += 1; continue
        cls, info = classify(c[0], c[1], c[2], c[3], fx, fy, tx, ty)
        res[cls] += 1; k = (rmap.get(rm, -rm), round(fy / 1024 + .5), round(fx / 1024 + .5), round(ty / 1024 + .5), round(tx / 1024 + .5)); gr = groups[k]; gr[0] += 1; gr[1] = cls; gr[2] = (ex, tot, info)
    print(f"{len(events)} GRID-NOWAY events in {log}" + (f" (lines containing {since!r})" if since else ""))
    for k, v in res.most_common(): print(f"  {k:<18} {v:>5}  {100 * v // max(1, len(events))}%")
    print(f"\ntop {top} repeated walks (room, start row,col -> goal row,col):")
    for k, (n, cls, d) in sorted(groups.items(), key=lambda kv: -kv[1][0])[:top]:
        print(f"  x{n:<4} room {k[0]:<5} ({k[1]},{k[2]}) -> ({k[3]},{k[4]})  {cls:<18} explored {d[0]} of {d[1]} {d[2] if d[2] else ''}")
    if nodump: print("\nrooms without a grid dump (run roomgrid.py):", dict(nodump))

if __name__ == "__main__": asyncio.run(main())
