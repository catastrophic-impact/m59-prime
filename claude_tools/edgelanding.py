#!/usr/bin/env python3
"""WHERE DOES THE FLOOR REACH THE EDGE?  For every edge exit of a room (walking off the N/S/E/W side leads to the neighbour room) find the REAL floor that touches that side and the landing square nearest to the
square the baker invented for the exit (the middle of the side). Offline, read-only, needs the grid dumps (roomgrid.py).
  python3 claude_tools/edgelanding.py [ROOM ..] [--all-dumped] [--server server2] [--json out.json] [--baker docs/edge_landings.json] [--touch 1.0]
FLOOR = grid cells with a valid floor height (inside the room's sectors). The server's lattice also calls the VOID around a room walkable, and it can be the biggest region (room 586): the main region here is
the region with the most FLOOR cells, not the most cells. (roomreach.py's edge test used the biggest region and passed any edge: its verdicts for edge exits are void.)
Per exit prints: side -> neighbour, the baked square, the landing (row,col) = the floor cell of the main floor region within --touch squares of the side that lies nearest to the baked square along the side,
the distance along the side from baked to landing, and NO-FLOOR when no floor of the main region touches that side at all (then nobody can leave that way: the exit must go from the map).
Result json: {rid: [{side, to, baked, landing|null, gap, floor_cells}]}."""
import json, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import roomreach as R

def floor_grid(server, roo):
    p = R.find_grid(server, roo)
    if not p: return None
    b = open(p, "rb").read(); ncols, nrows, cell = struct.unpack("<3i", b[4:16]); N = ncols * nrows
    return ncols, nrows, cell, b[16:16 + N], struct.unpack(f"<{N}f", b[16 + N:16 + 5 * N])

def main_floor_region(g):
    ncols, nrows, cell, links, hts = g
    comp, sizes = R.components(ncols, nrows, links); fl = [0] * len(sizes)
    for i, c in enumerate(comp):
        if c and hts[i] == hts[i]: fl[c] += 1
    main = max(range(1, len(sizes)), key=lambda i: fl[i]); return comp, main

def analyse(rid, bake, server, touch=1.0):
    r = bake[rid]; g = floor_grid(server, r["roo"])
    if not g: return None
    ncols, nrows, cell, links, hts = g; comp, main = main_floor_region(g)
    dump = json.load(open(os.path.join(R.W, "navtmp", "roomdump", r["roo"] + ".json"))); rows, cols = dump["rows"], dump["cols"]
    out = []; sides = {}
    for e in R.edges_of(r["roo"]).items(): sides[e[0]] = e[1]
    for d in r["doors"]:
        side = sides.get(d["to"])
        if side is None: continue
        row, col = d["row"], d["col"]; best = None; n = 0
        mid = {"W": (rows / 2, 1), "E": (rows / 2, cols), "N": (1, cols / 2), "S": (rows, cols / 2)}[side]      # reference: the middle of the side
        for i, c in enumerate(comp):
            if c != main or hts[i] != hts[i]: continue
            rr, cc = divmod(i, ncols); y = (rr + 0.5) * cell / 1024.0; x = (cc + 0.5) * cell / 1024.0
            dside = {"N": y, "W": x, "S": rows - y, "E": cols - x}[side]
            if dside <= touch:
                n += 1; along = abs((y + 0.5 - mid[0]) if side in "WE" else (x + 0.5 - mid[1]))
                if best is None or along < best[0]: best = (along, y + 0.5, x + 0.5)
        out.append({"side": side, "to": d["to"], "baked": [row, col], "landing": [round(best[1], 1), round(best[2], 1)] if best else None, "gap": round(abs((best[1] - row) if side in "WE" else (best[2] - col)), 1) if best else None, "floor_cells": n})
    return out

def main():
    a = sys.argv[1:]; arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    server = arg("--server", "server2"); touch = float(arg("--touch", "1.0")); outp = arg("--json", None)
    bake = {x["rid"]: x for x in json.load(open(os.path.join(R.W, "navtmp", "navbake.json")))}
    rooms = [int(x) for x in a if x.isdigit()]
    if "--all-dumped" in a: rooms = [rid for rid, r in bake.items() if R.find_grid(server, r["roo"])]
    res = {}; nofloor = far = 0
    for rid in rooms:
        x = analyse(rid, bake, server, touch)
        if x is None: print(rid, "no grid dump"); continue
        res[rid] = x
        for e in x:
            tag = "NO-FLOOR" if e["landing"] is None else ("gap %.1f" % e["gap"])
            if e["landing"] is None: nofloor += 1
            elif e["gap"] > 2: far += 1
            if "--quiet" not in a or e["landing"] is None or e["gap"] > 2:
                print(f"{rid:>5} {bake[rid]['name'][:28]:<28} {e['side']} -> {e['to']:<14} baked {tuple(e['baked'])} landing {tuple(e['landing']) if e['landing'] else None} {tag} ({e['floor_cells']} floor cells on that side)")
    print(f"\n{len(res)} rooms; {nofloor} edge exits with NO floor touching their side; {far} more whose landing is more than 2 squares from the baked square")
    if outp: json.dump(res, open(outp, "w"))
    if "--baker" in a:      # {rid: {'toRoo:side': [row, col]}}: the landing square on the server's own floor, read by navbake.ts (--edges)
        bk = {str(rid): {f"{e['to']}:{e['side']}": [max(1, round(e['landing'][0])), max(1, round(e['landing'][1]))] for e in x if e['landing']} for rid, x in res.items()}
        json.dump(bk, open(arg('--baker', ''), 'w')); print('baker landings ->', arg('--baker', ''))

if __name__ == "__main__": main()
