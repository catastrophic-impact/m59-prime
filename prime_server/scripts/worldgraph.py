#!/usr/bin/env python3
"""World graph + portal reachability audit (static, no server needed).
Reads rooms.json, roomexits.json, roomzones.json (the Kod's zone exits) and the baked bot graph (navbake.json from navrebake.sh), writes
docs/world_graph.json (rooms, links by type, the travel portals, flags) and prints which hunt rooms no bot can reach from ANY travel portal arrival
(bots use every main-network travel portal for free, 2026-10-29), minus the rooms the owner excluded.
  worldgraph.py [--hunt <bot_scenarios.log>]   (hunt rooms = the rooms named in that audit log; default prime_server/test_logs/bot_scenarios.log)"""
import json, math, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..", "..")
W = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
rooms = json.load(open(f"{W}/assets/rooms.json")); ex = json.load(open(f"{W}/assets/roomexits.json"))
zn = json.load(open(f"{ROOT}/prime_client/overlay/tools/prime/roomzones.json"))["zones"]
bake = {x["rid"]: x for x in json.load(open(os.environ.get("NAVJSON", f"{W}/navtmp/navbake.json")))}
name, roo2rid = {}, {}
for r in rooms:
    if r["name"] == "Death Realm": continue
    name.setdefault(r["rid"], r["name"]); roo2rid.setdefault(r["roo"], r["rid"])
# main-network travel portals (util/travelnet.kod): id, place, room, arrival row, arrival col
PORTALS = [(1, "Tos", 50, 29, 6), (2, "Marion", 200, 6, 5), (3, "Raza", 300, 23, 9), (4, "Jasper", 350, 57, 42), (5, "Barloque", 101, 4, 14),
           (6, "Cor Noth", 150, 44, 48), (7, "Ko'catan", 2000, 48, 11), (8, "Bergen", 2800, 52, 75), (9, "Brax", 578, 46, 47),
           (10, "Castle Victoria", 38, 7, 4), (90, "Proving Grounds", 4300, 12, 20)]
# owner decisions 2026-10-29 (docs/bot_unreachable_rooms.md section F) + the d6e6 trap stream (bots never go there)
EXCLUDED = {4: "never a bot destination", 6: "never", 28: "never", 32: "never", 35: "never", 47: "never", 749: "never on their own",
            546: "orphan room (nothing links to it)", 556: "orphan room", 550: "trap stream (NO_GO)", 551: "behind the trap stream"}
links = []
for f, v in ex.items():
    a = roo2rid.get(f)
    for d in v["doors"]:
        if d[2] and roo2rid.get(d[2]) and a: links.append({"from": a, "to": roo2rid[d[2]], "type": "door"})
    for e in v.get("edges") or []:
        if e.get("to") and roo2rid.get(e["to"]) and a: links.append({"from": a, "to": roo2rid[e["to"]], "type": "edge", "side": e["side"]})
for f, zs in zn.items():
    for z in zs:
        if z.get("to") and roo2rid.get(f) and roo2rid.get(z["to"]): links.append({"from": roo2rid[f], "to": roo2rid[z["to"]], "type": "zone"})
for p in PORTALS:
    for q in PORTALS:
        if p[0] != q[0]: links.append({"from": p[2], "to": q[2], "type": "travel portal"})
def near(rid, r, c):
    n = bake[rid]["nodes"]
    return min(range(len(n)), key=lambda i: math.hypot(n[i]["row"] - r, n[i]["col"] - c)) if n else None
def reach(start):
    seen, st = {start}, [start]
    while st:
        rid, n = st.pop()
        for e in bake[rid]["adj"][n]:
            t = (rid, e["to"])
            if t not in seen: seen.add(t); st.append(t)
        for d in bake[rid]["doors"]:
            if d["node"] == n and d["kind"] == 1 and d["destRid"] in bake:
                m = near(d["destRid"], d["arrRow"], d["arrCol"])
                if m is not None and (d["destRid"], m) not in seen: seen.add((d["destRid"], m)); st.append((d["destRid"], m))
    return {r for r, _ in seen}
by_portal = {}
for pid, pname, rid, row, col in PORTALS:
    if rid not in bake: print("portal room not baked:", pname, rid); continue
    by_portal[pname] = reach((rid, near(rid, row, col)))
ok = set().union(*by_portal.values())
logf = sys.argv[sys.argv.index("--hunt") + 1] if "--hunt" in sys.argv else f"{ROOT}/prime_server/test_logs/bot_scenarios.log"
hunt = sorted({int(m) for m in re.findall(r"hunt room,(\d+),", open(logf).read())})
# rooms with a hop in the raw exit data from a baked-reachable room (the baker lost it) vs no link at all
raw_in = collections.defaultdict(set)
for l in links: raw_in[l["to"]].add(l["from"])
rep = {"excluded": [], "reachable": [], "baker_lost": [], "no_link": []}
for r in hunt:
    if r in EXCLUDED: rep["excluded"].append(r)
    elif r in ok: rep["reachable"].append(r)
    elif raw_in[r] & ok or any(l["from"] in ok and l["to"] == r for l in links): rep["baker_lost"].append(r)
    else: rep["no_link"].append(r)
nodes = [{"rid": r, "name": name.get(r, ""), "excluded": EXCLUDED.get(r), "baked_from_portals": r in ok, "portal": next((p[1] for p in PORTALS if p[2] == r), None)} for r in sorted(name)]
json.dump({"_note": "made by prime_server/scripts/worldgraph.py", "nodes": nodes, "links": links}, open(f"{ROOT}/docs/world_graph.json", "w"), separators=(",", ":"))
print(f"rooms {len(nodes)}, links {len(links)}; baked graph reaches {len(ok & set(name))} rooms from the 11 portal arrivals")
for p, s in by_portal.items(): print(f"  from {p:16s}: {len(s)} rooms")
print(f"hunt rooms in the audit list: {len(hunt)} -> reachable from some portal {len(rep['reachable'])}, excluded {len(rep['excluded'])}, still lost by the baked graph {len(rep['baker_lost'])}, no link at all {len(rep['no_link'])}")
for k in ("baker_lost", "no_link"):
    print(f"{k}:", [(r, name.get(r, "")[:28]) for r in rep[k]])

# ---- boundary: raw links leaving the baked-reachable set, and why the baker lost them ----
if "--boundary" in sys.argv:
    def comps(x):
        n = len(x["nodes"]); c = [-1] * n; k = 0
        for s in range(n):
            if c[s] >= 0: continue
            st = [s]; c[s] = k
            while st:
                for e in x["adj"][st.pop()]:
                    if c[e["to"]] < 0: c[e["to"]] = k; st.append(c[e["to"]] and e["to"])
            k += 1
        return c
    seen_raw = set(r for r in ok)
    q = collections.deque(ok)
    adj = collections.defaultdict(set)
    for l in links:
        if l["type"] != "travel portal": adj[l["from"]].add(l["to"])
    while q:
        a = q.popleft()
        for b in adj[a]:
            if b not in seen_raw and b not in EXCLUDED: seen_raw.add(b); q.append(b)
    print("raw exits (no portals) reach", len(seen_raw), "rooms; hunt rooms still lost though raw-reachable:", [r for r in hunt if r in seen_raw and r not in ok])
    C = {}
    for a in sorted(ok):
        for b in sorted(adj[a]):
            if b in ok or b in EXCLUDED or b not in bake: continue
            ds = [d for d in bake[a]["doors"] if d["destRid"] == b and d["kind"] == 1]
            if not ds: why = "NO DOOR baked"
            else:
                C.setdefault(a, comps(bake[a])); why = f"door node in piece {C[a][ds[0]['node']]} of {max(C[a])+1} (unreached)"
            print(f"  {a:5d} {name.get(a,'')[:26]:26s} -> {b:5d} {name.get(b,'')[:26]:26s} {why}")
