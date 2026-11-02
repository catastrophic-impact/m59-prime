#!/usr/bin/env python3
"""Static reachability of the baked bot graph (navbake.json): from each of the 9 towns' inns, which rooms can a bot walk to?
Walks node routes inside a room, doors (kind 1) between rooms; arrival = the room's node nearest the arrival square.
  navreach.py navbake.json [other.json]   prints rooms reachable from NO town / from only some, and (with two files) what changed."""
import json, sys, math
HOMES = {50: "Tos", 102: "Barloque", 150: "CorNoth", 200: "Marion", 300: "Raza", 350: "Jasper", 2000: "Kocatan", 2800: "Berg", 2903: "Jixa"}

def load(p):
    g = {x["rid"]: x for x in json.load(open(p))}
    return g

def reach(g, start_rid):
    def near(rid, r, c):
        n = g[rid]["nodes"]
        return min(range(len(n)), key=lambda i: math.hypot(n[i]["row"] - r, n[i]["col"] - c)) if n else None
    seen, stack = set(), []
    # start: the inn node by its way out: the first inn of the home town (kind inn, region == home)
    inns = [x for x in g.values() if x["kind"] == "inn" and x["region"] == start_rid]
    if not inns: return set(), set()
    dn = [d["node"] for d in inns[0]["doors"] if d["kind"] == 1]
    s = (inns[0]["rid"], dn[0] if dn else 0)
    seen.add(s); stack.append(s)
    while stack:
        rid, n = stack.pop()
        for e in g[rid]["adj"][n]:
            t = (rid, e["to"])
            if t not in seen: seen.add(t); stack.append(t)
        for d in g[rid]["doors"]:
            if d["node"] != n or d["kind"] != 1 or d["destRid"] not in g: continue
            m = near(d["destRid"], d["arrRow"], d["arrCol"])
            if m is None: continue
            t = (d["destRid"], m)
            if t not in seen: seen.add(t); stack.append(t)
    return seen, {r for r, _ in seen}

def summary(g):
    allrooms = {r for r, x in g.items() if x["kind"] == "room"}
    per = {}
    for h in HOMES:
        per[h] = reach(g, h)[1] & allrooms
    union = set().union(*per.values())
    return allrooms, per, union

a = load(sys.argv[1]); ra, pa, ua = summary(a)
print(f"{sys.argv[1]}: {len(ra)} wild/dungeon rooms; reachable from at least one town {len(ua)}; from none {len(ra - ua)}")
print("  pairs (town,room) reachable:", sum(len(v) for v in pa.values()), "of", len(ra) * len(HOMES))
for h, v in pa.items(): print(f"  {HOMES[h]:9s} {len(v)}")
if len(sys.argv) > 2:
    b = load(sys.argv[2]); rb, pb, ub = summary(b)
    print(f"{sys.argv[2]}: reachable from at least one town {len(ub)}; from none {len(rb - ub)}; pairs", sum(len(v) for v in pb.values()), "of", len(rb) * len(HOMES))
    print("  newly reachable (some town):", sorted(ub - ua)[:80])
    print("  lost:", sorted(ua - ub))
    print("  still from none:", sorted(rb - ub))
