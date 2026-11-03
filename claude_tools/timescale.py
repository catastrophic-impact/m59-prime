#!/usr/bin/env python3
"""TIME SCALE (TEST SERVER ONLY, server patch 0081): make the whole server's clock run N times faster (timers, regeneration, respawns, bot ticks, hunts, rests: everything uses the one clock).
  PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 $PRIME_WORK/admin-venv/bin/python claude_tools/timescale.py 30      (30x; 1 or 'off' = real time; no argument = just measure)
Writes <server dir>/timescale.txt (the server re-reads it once per real second and rebases its clock, so time never jumps) and MEASURES the factor: server clock seconds per real second over 6 s.
Keep piBotTimeScale at 100 when this is on (it would multiply). Refuses the live server folder. A savegame made while accelerated holds future times: test_redeploy.sh wipes server2 anyway.
Hunting, dying and health tests are valid under this (regeneration speeds up with everything else). Clients cannot keep up above ~5x: use it for bot tests, not for playing."""
import asyncio, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab

def clock_seconds(text):
    m = re.search(r"(\d\d):(\d\d):(\d\d)", text)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None

async def main():
    W = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work")); d = os.environ.get("PRIME_SERVER_DIR", "server2")
    if d == "server": sys.exit("refusing: that is the owner's live server folder")
    path = os.path.join(W, "build", d, "timescale.txt")
    if sys.argv[1:]:
        v = sys.argv[1]; n = 1.0 if v in ("off", "1") else float(v)
        if not 1 <= n <= 1000: sys.exit("factor 1..1000")
        open(path, "w").write(f"{n:g}\n"); print(f"timescale.txt = {n:g} ({path})")
        await asyncio.sleep(2.5)       # the server notices within one real second
    lab = await Lab.open()
    a = clock_seconds(await lab.run("show memory")); t0 = time.time(); await asyncio.sleep(6); b = clock_seconds(await lab.run("show memory")); t1 = time.time()
    await lab.close()
    if a is None or b is None: sys.exit("could not read the server clock")
    print(f"server clock advanced {(b - a) % 86400} s in {t1 - t0:.1f} real s = about {((b - a) % 86400) / (t1 - t0):.1f}x")
asyncio.run(main())
