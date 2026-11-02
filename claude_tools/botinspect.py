#!/usr/bin/env python3
"""BOT INSPECTOR: one report and one picture of what a bot is doing RIGHT NOW (read-only).
  PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 $PRIME_WORK/admin-venv/bin/python claude_tools/botinspect.py BOT_ID [--near 10] [--no-picture]
Report: room, square + fine position, doing/phase, stuck, goal node, the route it holds (plNavPath, with the distance of each leg), the path prototype's state
(planner steps / refusals / plans and the first refused step), strict mode, and the nearest things in the room (bots, mobs, players, objects) with distance.
Picture (docs/botinspect/bot<ID>.png, needs the room's grid dump: claude_tools/roomgrid.py ROOM): the room with every body numbered (bot green, mobs orange,
players white, the inspected bot magenta), its route (yellow), its goal (green square), its waypoint (pink), the refused step (red X). Snapshot data -> bot<ID>.json."""
import asyncio, json, math, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab, ROOT, DOING, PATH_STATE

def sq(p, r="piRow", c="piCol", fr="piFine_row", fc="piFine_col"):
    g = lambda n: int(re.search(r"-?\d+", p.get(n, "0")).group(0)); return (g(r) - 1) + g(fr) / 64.0, (g(c) - 1) + g(fc) / 64.0

async def inspect(lab, bot, near=10, pic=True, out_dir=None, tag=None):
    """-> (report text, snapshot dict, picture path or None). Library entry point: the CLI below and claude_tools/botscenario.py use it."""
    lines = []; say = lambda *x: lines.append(" ".join(str(y) for y in x))
    body = await lab.body(bot)
    if not body: return f"bot {bot} has no body", None, None
    p = await lab.props(body); g = lambda n: int(re.search(r"-?\d+", p.get(n, "0")).group(0))
    room = int(re.search(r"OBJECT (\d+)", p.get("poOwner", "")).group(1)) if re.search(r"OBJECT (\d+)", p.get("poOwner", "")) else None
    rid = g("piNavRid"); me = sq(p)
    say(f"BOT {bot} body {body} class {p['_class']}: room {rid} (object {room}) at row {g('piRow')} col {g('piCol')} fine {g('piFine_row')},{g('piFine_col')}")
    say(f"  doing {DOING.get(g('piDoing'), g('piDoing'))} (arg {g('piDoingArg')}), phase {g('piPhase')}, stuck {g('piStuck')}, nav node {g('piNavNode')}, goal node {g('piGoalNode')}, journey room {g('piJourneyRid')}")
    route = []
    if re.search(r"LIST (\d+)", p.get("plNavDoor", "")): say("  heading for a door (plNavDoor set: the walk ends within a square and a half of it)")
    goal = wp = refused = wall = None
    if g("piPathState"):
        st = g("piPathState"); say(f"  WALK (planner): state {st} = {PATH_STATE.get(st, st)}; steps {g('piPathSteps')}, refused {g('piPathRefused')}, wall slides/nudges {g('piPathSlides')}, plans {g('piPathPlans')}")
        goal = (g("piPathRow"), g("piPathCol"), g("piPathFr"), g("piPathFc")); say(f"    goal square {goal[0]},{goal[1]} fine {goal[2]},{goal[3]}");
        if g("piPathWpR"): wp = (g("piPathWpR"), g("piPathWpC"), g("piPathWpFr"), g("piPathWpFc")); say(f"    waypoint {wp[0]},{wp[1]} fine {wp[2]},{wp[3]}")
        m = re.search(r"LIST (\d+)", p.get("plPathDbg", ""))
        if m:
            d = await lab.list(int(m.group(1)))
            if len(d) >= 6:
                f_, t_, w_ = d[0:2], d[2:4], d[4:6]   # [from_r, from_c, to_r, to_c, wp_r, wp_c, bsp] in Kod fine units (row*64+fine)
                u = lambda v: (v // 64, v % 64)
                say(f"    FIRST REFUSED STEP: from (sq {u(d[0])[0]},{u(d[1])[0]} fine {u(d[0])[1]},{u(d[1])[1]}) to (sq {u(d[2])[0]},{u(d[3])[0]} fine {u(d[2])[1]},{u(d[3])[1]}), the check said {d[6] if len(d) > 6 else '?'}")
                refused = (u(d[2])[0], u(d[3])[0], u(d[2])[1], u(d[3])[1])
                if len(d) >= 12:   # patch 0073: the server's reason
                    code, o = d[7], d[8:12]
                    if code == 1: say(f"    REASON: a WALL stops it: line ({o[0]/1024:.2f},{o[1]/1024:.2f}) -> ({o[2]/1024:.2f},{o[3]/1024:.2f}) in squares (x=col, y=row, 0-based)"); wall = o
                    elif code == 2: say(f"    REASON: a BODY stops it: object {o[0]} at ({o[1]/1024:.2f},{o[2]/1024:.2f}) squares (x=col, y=row, 0-based)")
                    elif code == 4: say(f"    REASON: an EXIT square stops it: the door at row {o[0]}, col {o[1]} (exit awareness: a bot walking inside a room must not step on a door)")
                    elif code == 0: say("    REASON: the check allows this step now (something moved since)")
                    else: say(f"    REASON: code {code} (no room data)")
    things = []
    if room:
        for t in await lab.room_things(room):
            d = math.hypot((t["row"] - 1) + t["fr"] / 64.0 - me[0], (t["col"] - 1) + t["fc"] / 64.0 - me[1]); t["dist"] = round(d, 1); things.append(t)
        things.sort(key=lambda t: t["dist"])
        say(f"  IN THE ROOM: {len(things)} bodies; nearest {near}:")
        for t in things[:near]: say(f"    #{t['obj']} {t['class']} ({t['kind']}) at {t['row']},{t['col']} fine {t['fr']},{t['fc']}  {t['dist']} squares away  hp {t['hp']}" + ("  <- THIS BOT" if t["obj"] == body else ""))
        for t in things: t["k"] = "focus" if t["obj"] == body else t["kind"]; t["n"] = t["obj"] % 1000
    snap = {"bot": bot, "body": body, "room": rid, "route": route, "goal": goal[:2] + goal[2:4] if goal else None, "wp": wp, "refused": refused, "wall": wall, "things": things}
    od = out_dir or os.path.join(ROOT, "docs", "botinspect"); os.makedirs(od, exist_ok=True); sf = os.path.join(od, f"{tag or 'bot' + str(bot)}.json"); json.dump(snap, open(sf, "w"))
    out = None
    if pic and rid:
        out = os.path.join(od, f"{tag or 'bot' + str(bot)}.png")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "claude_tools", "roomview.py"), str(rid), "--live", sf, "--out", out], capture_output=True, text=True)
        if r.returncode != 0: say("  picture NOT MADE: " + (r.stdout + r.stderr).strip().splitlines()[-1]); out = None
    return "\n".join(lines), snap, out

async def main():
    a = sys.argv[1:]; near = 10; pic = True
    if "--near" in a: i = a.index("--near"); near = int(a[i + 1]); del a[i:i + 2]
    if "--no-picture" in a: a.remove("--no-picture"); pic = False
    lab = await Lab.open(); text, snap, out = await inspect(lab, int(a[0]), near, pic); await lab.close()
    print(text)
    if out: print("  picture:", out)
if __name__ == "__main__": asyncio.run(main())
