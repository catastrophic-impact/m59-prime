#!/usr/bin/env python3
"""REACHABILITY FROM THE GRID, NO TRIPS: for each room the walkable cells (by the server's own wall rules) are split into connected regions; every entrance square (where another room's
door puts you down) and every door/exit square of the room is looked up in them. A door or entrance is 'main' when it lies in the room's largest region. A room is CONNECTED when all its
entrances and doors are in the main region; otherwise the ones outside are listed (a sealed porch, a closed yard, a door in a wall the margin closes).
Needs the grid dumps (claude_tools/roomgrid.py ROOM.. on the test server).  Usage: roomreach.py [ROOM ..] [--all-dumped] [--out docs/room_reachability_grid.md] [--server server2]"""
import json, os, struct, sys
W = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
HERE = os.path.dirname(os.path.abspath(__file__))
DC = [1, 1, 0, -1, -1, -1, 0, 1]; DR = [0, 1, 1, 1, 0, -1, -1, -1]
def find_grid(server, roo):
    d = os.path.join(W, "build", server)
    for f in os.listdir(d):
        if f.lower() in (f"pathgrid_{roo}.bin".lower(), f"pathgrid_{roo}.roo.bin".lower()): return os.path.join(d, f)
    return None
def load(server, roo):
    p = find_grid(server, roo)
    if not p: return None
    b = open(p, "rb").read()
    ncols, nrows, cell = struct.unpack("<3i", b[4:16]); N = ncols * nrows
    return ncols, nrows, cell, b[16:16 + N]
def components(ncols, nrows, links):
    comp = [0] * len(links); sizes = [0]; cid = 0
    for s in range(len(links)):
        if links[s] and not comp[s]:
            cid += 1; comp[s] = cid; stack = [s]; n = 0
            while stack:
                c = stack.pop(); n += 1; m = links[c]; cr, cc = divmod(c, ncols)
                for d in range(8):
                    if m & (1 << d):
                        k = (cr + DR[d]) * ncols + cc + DC[d]
                        if not comp[k]: comp[k] = cid; stack.append(k)
            sizes.append(n)
    return comp, sizes
def cell_comp(row, col, ncols, nrows, cell, links, comp, radius=12):
    r0 = int((row - 0.5) * 1024 / cell); c0 = int((col - 0.5) * 1024 / cell); best = None
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            rr, cc = r0 + dr, c0 + dc
            if 0 <= rr < nrows and 0 <= cc < ncols and links[rr * ncols + cc]:
                d = dr * dr + dc * dc
                if best is None or d < best[0]: best = (d, comp[rr * ncols + cc])
    return best[1] if best else 0
def touches(row, col, ncols, nrows, cell, links, comp, main, radius=12):
    r0 = int((row - 0.5) * 1024 / cell); c0 = int((col - 0.5) * 1024 / cell)
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            rr, cc = r0 + dr, c0 + dc
            if 0 <= rr < nrows and 0 <= cc < ncols and comp[rr * ncols + cc] == main: return True
    return False
_EXITS = None
def edges_of(roo):
    global _EXITS
    if _EXITS is None: _EXITS = json.load(open(os.path.join(W, "assets", "roomexits.json")))
    return {e["to"].replace(".roo", ""): e["side"] for e in _EXITS.get(roo + ".roo", {}).get("edges", []) if e.get("to")}
def edge_reached(side, ncols, nrows, cell, comp, main, rows_sq, cols_sq, margin=1536):
    """an exit in a room's EDGE: walking off that side leaves the room, so the main region only has to come within 1.5 squares of the side"""
    H = rows_sq * 1024; Wd = cols_sq * 1024
    for i in range(len(comp)):
        if comp[i] == main:
            r, c = divmod(i, ncols); y = (r + 0.5) * cell; x = (c + 0.5) * cell
            if (side == "N" and y < margin) or (side == "S" and y > H - margin) or (side == "W" and x < margin) or (side == "E" and x > Wd - margin): return True
    return False
def analyse(rid, bake, server):
    r = bake[rid]; g = load(server, r["roo"])
    if not g: return None
    ncols, nrows, cell, links = g
    comp, sizes = components(ncols, nrows, links)
    walk = sum(1 for m in links if m); biggest = max(range(1, len(sizes)), key=lambda i: sizes[i]) if len(sizes) > 1 else 0
    main = biggest
    ents = {}
    for o in bake.values():
        for d in o["doors"]:
            if d["destRid"] == rid: ents.setdefault((d["arrRow"], d["arrCol"]), set()).add(o["roo"])
    # the reference region: where most of the room's entrances lie (a room whose entrances are all in one region is fine even if a bigger, unused region exists)
    votes = {}
    for (er, ec) in ents:
        c = cell_comp(er, ec, ncols, nrows, cell, links, comp)
        if c: votes[c] = votes.get(c, 0) + 1
    if votes: main = max(votes, key=lambda c: (votes[c], sizes[c]))
    out = {"rid": rid, "name": r["name"], "roo": r["roo"], "walk": walk, "regions": len(sizes) - 1, "main": sizes[main] if main else 0, "biggest": sizes[biggest] if biggest else 0, "ent": [], "door": []}
    for (er, ec), src in sorted(ents.items()):
        c = cell_comp(er, ec, ncols, nrows, cell, links, comp)
        # a body standing on the arrival square can step to an open cell next to it: the main region within half a square (4 cells) counts
        near = touches(er, ec, ncols, nrows, cell, links, comp, main, radius=4)
        out["ent"].append({"sq": [er, ec], "from": sorted(src), "in_main": bool(near or (c and c == main)), "region_cells": sizes[c] if c else 0})
    eds = edges_of(r["roo"]); side_ok = {}
    dump = json.load(open(os.path.join(W, "navtmp/roomdump", r["roo"] + ".json")))
    for d in r["doors"]:
        side = eds.get(d["to"])
        if side:   # an edge exit: the whole side counts
            if side not in side_ok: side_ok[side] = edge_reached(side, ncols, nrows, cell, comp, main, dump["rows"], dump["cols"])
            out["door"].append({"sq": [d["row"], d["col"]], "to": d["to"], "in_main": side_ok[side], "region_cells": 0, "edge": side})
            continue
        c = cell_comp(d["row"], d["col"], ncols, nrows, cell, links, comp)
        near = touches(d["row"], d["col"], ncols, nrows, cell, links, comp, main)   # a door lies in a wall: the main region within 1.5 squares of it is enough
        out["door"].append({"sq": [d["row"], d["col"]], "to": d["to"], "in_main": bool(near or (c and c == main)), "region_cells": sizes[c] if c else 0})
    return out
def main():
    a = sys.argv[1:]; server = "server2"
    if not a or "--help" in a or "-h" in a: print(__doc__); return
    if "--server" in a: i = a.index("--server"); server = a[i + 1]; del a[i:i + 2]
    out = os.path.join(HERE, "..", "docs", "room_reachability_grid.md")
    if "--out" in a: i = a.index("--out"); out = a[i + 1]; del a[i:i + 2]
    bake = {x["rid"]: x for x in json.load(open(os.path.join(W, "navtmp/navbake.json")))}
    rooms = [int(x) for x in a if x.isdigit()]
    if "--all-dumped" in a: rooms = [rid for rid, r in bake.items() if find_grid(server, r["roo"])]
    res = []
    for rid in rooms:
        x = analyse(rid, bake, server)
        if x: res.append(x)
    lines = ["# Room reachability from the server's walkable grid (no trips)", "",
             "main = the room's largest walkable region. An entrance or door counts when its square (or the nearest walkable cell within 1.5 squares) is in it.", "",
             "| room | name | walkable cells | regions | main region | entrances in main | doors in main | sealed entrances | sealed doors |", "|---|---|---|---|---|---|---|---|---|"]
    conn = 0
    for x in res:
        se = [e for e in x["ent"] if not e["in_main"]]; sd = [d for d in x["door"] if not d["in_main"]]
        if not se and not sd: conn += 1
        lines.append(f"| {x['rid']} | {x['name']} | {x['walk']} | {x['regions']} | {x['main']} | {len(x['ent']) - len(se)}/{len(x['ent'])} | {len(x['door']) - len(sd)}/{len(x['door'])} | "
                     + "; ".join(f"{e['sq']} from {'/'.join(e['from'])} ({e['region_cells']} cells)" for e in se) + " | " + "; ".join(f"{d['sq']}->{d['to']} ({d['region_cells']} cells)" for d in sd) + " |")
    open(out, "w").write("\n".join(lines) + "\n")
    json.dump(res, open(out.replace(".md", ".json"), "w"))
    print(f"{len(res)} rooms analysed, {conn} fully connected (every entrance and door in the main region); table: {out}")
if __name__ == "__main__": main()
