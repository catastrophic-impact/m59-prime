#!/usr/bin/env python3
"""EXIT AUDIT (offline, no server, minutes): for every baked room, what each baked door REALLY is and whether the planner can reach it from every arrival square.
  python3 claude_tools/exitaudit.py [ROO ..] [--workers 4] [--out docs/exit_audit]   (needs planlab built: claude_tools/planlab.sh in the box)
Kinds: DOOR (the game's own exit table lists this very square: docs/kod_exits.json), ZONE (a room zone from roomzones.json holds the square: any square of it exits), EDGE (a room-edge landing),
 TRANSIT (a travel-portal door), OTHER (none of those: the square is a guess). Reach: the planner's verdict (the half-square goal, door squares avoided like PathAvoidDoors) from every arrival square of the room
 (roomexits.json arrivals) to the door square; a door NO arrival reaches is DEAD, some arrivals NONE = PARTIAL."""
import json, os, re, subprocess, sys, concurrent.futures as cf
W = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work")); HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
a = sys.argv[1:]; opt = lambda k, d: a[a.index(k) + 1] if k in a else d
workers = int(opt("--workers", "4")); out = os.path.join(ROOT, opt("--out", "docs/exit_audit")); only = [x for x in a if not x.startswith("--") and not x.isdigit() and a[a.index(x) - 1] not in ("--workers", "--out")]
bake = json.load(open(W + "/navtmp/navbake.json")); kx = json.load(open(ROOT + "/docs/kod_exits.json")); zones = json.load(open(W + "/client_build/tree/tools/prime/roomzones.json"))["zones"]
rex = json.load(open(W + "/assets/roomexits.json")); PL = W + "/planlab/planlab"
def zone_hit(roo, to, row, col, rows, cols):
    for z in zones.get(roo + ".roo", []):
        if z["to"].lower().replace(".roo", "") != to: continue
        e = z["when"].replace("&&", " and ").replace("||", " or ").replace("===", "==").replace("!==", "!=").replace("!", " not ").replace("true", "True").replace("false", "False")
        try:
            if eval(e, {}, {"new_row": row, "new_col": col, "ROWS": rows, "COLS": cols}): return True
        except Exception: pass
    return False
def audit(r):
    roo = r["roo"]; path = W + f"/build/server2/rooms/{roo}.roo"
    if not os.path.exists(path): path = W + f"/assets/{roo}.roo"
    kd = {(d[0], d[1]) for d in kx.get(str(r["rid"]), {}).get("doors", [])}
    arr = rex.get(roo + ".roo", {}).get("arrivals", [])
    doors = r["doors"]; res = []
    avoid = [d for d in doors if not d["edge"]]
    for d in doors:
        row, col, to = d["row"], d["col"], d["to"]
        if d["edge"]: kind = "EDGE"
        elif (row, col) in kd: kind = "DOOR"
        elif zone_hit(roo, to, row, col, 999, 999): kind = "ZONE"
        elif d.get("kind") == 2 or d.get("purpose") == -1: kind = "TRANSIT"
        else: kind = "OTHER"
        res.append({"row": row, "col": col, "to": to, "kind": kind, "arrivals": {}})
    if not arr or not os.path.exists(PL): return roo, r["rid"], res, "no arrivals" if not arr else "no planlab"
    # every door square the GAME lists for this room, one by one (a doorway is often several adjacent squares with the same landing; the baker must pick one the planner reaches)
    sq = {}
    for e in kx.get(str(r["rid"]), {}).get("doors", []):
        lines = "".join(f"{ar} {ac} {e[0]} {e[1]}\n" for ar, ac in arr); args = [PL, path]
        for o in avoid:
            if (o["row"], o["col"]) != (e[0], e[1]): args += ["-a", f"{o['row']},{o['col']}"]
        p = subprocess.run(args, input=lines, capture_output=True, text=True, timeout=600)
        okc = sum(1 for ln in p.stdout.splitlines() if re.match(r"\(\d+,\d+\)->\(\d+,\d+\) WAY", ln))
        sq[f"{e[0]},{e[1]}"] = [okc, len(arr)]
    SQUARES[str(r["rid"])] = sq
    for d, x in zip(doors, res):
        lines = "".join(f"{ar} {ac} {d['row']} {d['col']}\n" for ar, ac in arr)
        args = [PL, path]
        for o in avoid:
            if (o["row"], o["col"]) != (d["row"], d["col"]): args += ["-a", f"{o['row']},{o['col']}"]
        p = subprocess.run(args, input=lines, capture_output=True, text=True, timeout=600)
        for ln in p.stdout.splitlines():
            m = re.match(r"\((\d+),(\d+)\)->\((\d+),(\d+)\) (WAY|NO WAY)", ln)
            if m: x["arrivals"][f"{m.group(1)},{m.group(2)}"] = m.group(5) == "WAY"
    return roo, r["rid"], res, ""
SQUARES = {}
rooms = [r for r in bake if not only or r["roo"] in only]
os.makedirs(out, exist_ok=True); allres = {}
with cf.ThreadPoolExecutor(workers) as ex:
    for roo, rid, res, note in ex.map(audit, rooms):
        allres[roo] = {"rid": rid, "doors": res, "note": note}
        res_all = res; res = [d for d in res if not d["to"].startswith("guildh") and not roo.startswith("guildh")]   # bots never use guild-hall doors (kept in audit.json, left out of this list)
        bad = [d for d in res if d["arrivals"] and not any(d["arrivals"].values())]
        part = [d for d in res if d["arrivals"] and any(d["arrivals"].values()) and not all(d["arrivals"].values())]
        if bad or part: print(f"{roo} ({rid}): " + "; ".join([f"DEAD {d['kind']} {d['row']},{d['col']}->{d['to']}" for d in bad] + [f"PARTIAL {d['kind']} {d['row']},{d['col']}->{d['to']} ({sum(d['arrivals'].values())}/{len(d['arrivals'])})" for d in part]), flush=True)
json.dump(allres, open(out + "/audit.json", "w"))
json.dump(SQUARES, open(out + "/squares.json", "w"))
kinds = {}
for v in allres.values():
    for d in v["doors"]: kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
print("doors by kind:", kinds, "| rooms", len(allres))
