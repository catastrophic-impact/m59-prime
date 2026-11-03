#!/usr/bin/env python3
"""WALKTRACE: record where a logged-in character goes, every 0.2 s while it changes (room, square, fine position, facing), to docs/walktrace/NAME.txt. Read-only.
  PRIME_ADMIN_PORT=9999 $PRIME_WORK/admin-venv/bin/python claude_tools/walktrace.py NAME [--user OBJ] [--secs 600] [--place ROOM ROW COL ANGLE]
--place first puts the character on that square (the game's own UtilGoNearSquare) and starts recording at once. Without --user it takes the only character logged in."""
import asyncio, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab
async def main():
    a = sys.argv[1:]; name = a[0]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    secs = float(opt("--secs", "600")); lab = await Lab.open(); user = opt("--user")
    if user is None:
        objs = re.findall(r"OBJECT (\d+)", await lab.run("show instances user")); cand = []
        for o in objs:
            if re.search(r"poOwner\s*=\s*OBJECT \d+", await lab.run(f"show object {o}")): cand.append(o)
        if len(cand) != 1: sys.exit(f"{len(cand)} characters logged in {cand}: give --user")
        user = cand[0]
    if "--place" in a:
        i = a.index("--place"); rid, row, col, ang = a[i + 1:i + 5]
        room = re.findall(r"OBJECT (\d+)", await lab.run(f"send object 0 FindRoomByNum num int {rid}"))[-1]
        await lab.run(f"send object 0 UtilGoNearSquare what object {user} where object {room} new_row int {row} new_col int {col} new_angle int {ang}")
    out = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "walktrace", name + ".txt"), "w")
    t0 = time.time(); last = None; rooms = {}
    while time.time() - t0 < secs:
        t = await lab.run(f"show object {user}")
        g = lambda n: (re.search(n + r"\s*=\s*INT (-?\d+)", t) or [0, "?"])[1]
        ow = re.search(r"poOwner\s*=\s*OBJECT (\d+)", t)
        if ow:
            if ow.group(1) not in rooms:
                m = re.search(r"INT (\d+)", (await lab.run(f"send object {ow.group(1)} GetRoomNum")).split("return")[-1]); rooms[ow.group(1)] = m.group(1) if m else "?"
            room = rooms[ow.group(1)]
        else: room = "none"
        ang = re.search(r"INT (-?\d+)", (await lab.run(f"send object {user} GetAngle")).split("return")[-1])
        cur = f"room {room} square {g('piRow')},{g('piCol')} fine {g('piFine_row')},{g('piFine_col')} angle {ang.group(1) if ang else '?'}"
        if cur != last:
            line = f"t+{time.time() - t0:6.1f}s {cur}"; print(line, flush=True); out.write(line + "\n"); out.flush(); last = cur
        await asyncio.sleep(0.2)
    await lab.close()
asyncio.run(main())
