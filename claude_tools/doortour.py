#!/usr/bin/env python3
"""DOOR TOUR: walk the owner's logged-in character through the dead doors of docs/exit_audit_after one after the other WITHOUT waiting for anyone: it puts the character 3 squares from the door,
facing it, logs every move (room, square, fine position, facing) to docs/walktrace/tour_*.txt, and moves on by itself when the character leaves the room (log: where it went) or after --per seconds.
  PRIME_ADMIN_PORT=9999 $PRIME_WORK/admin-venv/bin/python claude_tools/doortour.py [--per 120] [--only ROO,ROO]   (read-only apart from placing the character)
The owner just walks to the door and uses it (Space for a door; walking in for a zone or an edge). Skipping a door: walk out of the room any way (or wait)."""
import asyncio, json, math, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
W = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
async def main():
    a = sys.argv[1:]; opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    per = float(opt("--per", "120")); only = (opt("--only") or "").split(",") if opt("--only") else []
    dist = float(opt("--dist", "3")); pick = [tuple(x.split(":")) for x in (opt("--doors") or "").split(";") if x]   # --doors "forest4:57,49;mardun03:35,27": exactly these door squares
    bake = {r["roo"]: r["rid"] for r in json.load(open(W + "/navtmp/navbake.json"))}
    audit = json.load(open(ROOT + "/docs/exit_audit_after/audit.json")); rex = json.load(open(W + "/assets/roomexits.json"))
    todo = []
    for roo, v in audit.items():
        if roo.startswith("guildh") or (only and roo not in only): continue
        for d in v["doors"]:
            if pick:
                if (roo, f"{d['row']},{d['col']}") in pick: todo.append((roo, v["rid"], d))
            elif d["arrivals"] and not any(d["arrivals"].values()) and not d["to"].startswith("guildh"): todo.append((roo, v["rid"], d))
    lab = await Lab.open(); objs = re.findall(r"OBJECT (\d+)", await lab.run("show instances user")); cand = []
    for o in objs:
        if re.search(r"poOwner\s*=\s*OBJECT \d+", await lab.run(f"show object {o}")): cand.append(o)
    if len(cand) != 1: sys.exit(f"{len(cand)} characters logged in {cand}")
    user = cand[0]; name = time.strftime("tour_%H%M"); out = open(f"{ROOT}/docs/walktrace/{name}.txt", "w")
    def log(s): print(s, flush=True); out.write(s + "\n"); out.flush()
    rooms = {}
    async def where():
        t = await lab.run(f"show object {user}"); g = lambda n: (re.search(n + r"\s*=\s*INT (-?\d+)", t) or [0, "?"])[1]
        ow = re.search(r"poOwner\s*=\s*OBJECT (\d+)", t)
        if not ow: return "none", g("piRow"), g("piCol"), g("piFine_row"), g("piFine_col"), "?"
        if ow.group(1) not in rooms:
            m = re.search(r"INT (\d+)", (await lab.run(f"send object {ow.group(1)} GetRoomNum")).split("return")[-1]); rooms[ow.group(1)] = int(m.group(1)) if m else -1
        ang = re.search(r"INT (-?\d+)", (await lab.run(f"send object {user} GetAngle")).split("return")[-1])
        return rooms[ow.group(1)], g("piRow"), g("piCol"), g("piFine_row"), g("piFine_col"), ang.group(1) if ang else "?"
    log(f"TOUR of {len(todo)} dead doors; the character is object {user}")
    for k, (roo, rid, d) in enumerate(todo, 1):
        r, c = d["row"], d["col"]; arrs = rex.get(roo + ".roo", {}).get("arrivals", [])
        best = min(arrs, key=lambda p: abs(math.hypot(p[0] - r, p[1] - c) - dist)) if arrs else [r, c]
        ang = int(round(math.atan2(r - best[0], c - best[1]) * 4096 / (2 * math.pi))) % 4096
        room = re.findall(r"OBJECT (\d+)", await lab.run(f"send object 0 FindRoomByNum num int {rid}"))[-1]
        await lab.run(f"send object 0 UtilGoNearSquare what object {user} where object {room} new_row int {best[0]} new_col int {best[1]} new_angle int {ang}")
        log(f"=== DOOR {k}/{len(todo)}: room {roo} ({rid}) kind {d['kind']} door square {r},{c} -> {d['to']}; you stand at {best[0]},{best[1]} facing it. Walk to it and use it.")
        t0 = time.time(); last = None
        while time.time() - t0 < per:
            w = await where(); cur = f"room {w[0]} square {w[1]},{w[2]} fine {w[3]},{w[4]} angle {w[5]}"
            if cur != last: log(f"  t+{time.time() - t0:5.1f}s {cur}"); last = cur
            if w[0] != rid:
                want = bake.get(d["to"].replace(".roo", "").lower()); await asyncio.sleep(1.5); w = await where()
                log(f"  --> LEFT the room: now in room {w[0]} at {w[1]},{w[2]}; expected room {want} ({d['to']}): " + ("CORRECT, this exit works" if w[0] == want else "WRONG ROOM, you took a different exit"))
                break
            await asyncio.sleep(0.2)
        else: log(f"  --> no exit within {per:.0f}s (door {r},{c} did not work or was not tried)")
    log("TOUR DONE"); await lab.close()
asyncio.run(main())
