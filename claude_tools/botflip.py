#!/usr/bin/env python3
"""TARGET FLIP-FLOP DETECTOR (read-only): finds a fighting/hunting bot that cannot decide on a target ('spazzing': turning back and forth) and prints what it was choosing between.
  PRIME_ADMIN_PORT=9999 PRIME_SERVER_DIR=server python claude_tools/botflip.py [--secs 180] [--every 0.5] [--flips 3] [--window 8]
Every --every seconds the bots that are hunting or fighting (activity hunt, or a target set) are sampled: target object, behaviour state, position, health. A FLIP is a switch from one live target straight to another (after a kill the target is none for a moment: that is not a flip); --flips of them inside
--window seconds are reported with the targets involved (class, distance, health), how far apart they are, the bot's own health, the hunt foe the registry loop would pick (HuntFoe) and the last positions
(heading changes show as zig-zag). Needs only the admin port."""
import asyncio, collections, math, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab, DOING

def g(t, n):
    m = re.search(rf"\b{n}\s*=\s*(?:INT|OBJECT)\s+(-?\d+)", t); return int(m.group(1)) if m else 0

async def main():
    a = sys.argv[1:]; arg = lambda k, d: float(a[a.index(k) + 1]) if k in a else d
    secs, every, flips, window = arg("--secs", 180), arg("--every", 0.5), int(arg("--flips", 3)), arg("--window", 8)
    lab = await Lab.open(); top = g(await lab.run(f"show object {lab.prime}"), "piPBotNextId") or 60
    hist = collections.defaultdict(lambda: collections.deque(maxlen=80)); last_rep = {}; t_end = time.time() + secs; reported = 0
    print(f"watching hunters/fighters for {secs:g} s (flip = target change, {flips} in {window:g} s reports)", flush=True)
    bodies = {}
    while time.time() < t_end:
        t = time.time()
        for b in range(1, top):
            if b not in bodies or t % 60 < every: bodies[b] = await lab.body(b)
            body = bodies[b]
            if not body: continue
            tx = await lab.run(f"show object {body}")
            tgt = re.search(r"poTarget\s*=\s*OBJECT\s+(\d+)", tx); tgt = int(tgt.group(1)) if tgt else None
            if g(tx, "piDoing") != 11 and tgt is None: continue
            row, col = g(tx, "piRow") + g(tx, "piFine_row") / 64.0, g(tx, "piCol") + g(tx, "piFine_col") / 64.0
            h = hist[b]; h.append((t, tgt, round(row, 2), round(col, 2), g(tx, "piState"), g(tx, "piHit_points") // 100))
            ch = [(x[0], x[1]) for i, x in enumerate(h) if i and x[1] and h[i - 1][1] and x[1] != h[i - 1][1] and t - x[0] <= window]      # a switch from one LIVE target to another (no target -> target is a kill and the next foe: normal)
            if len(ch) >= flips and t - last_rep.get(b, 0) > 30:
                last_rep[b] = t; reported += 1
                tg = sorted({x[1] for x in h if x[1] and t - x[0] <= window})
                print(f"\n[{time.strftime('%H:%M:%S')}] FLIP bot {b} (body {body}) room {g(tx, 'piNavRid')} at {row:.1f},{col:.1f}: {len(ch)} target changes in {window:g} s, targets {tg}, bot health {g(tx, 'piHit_points') // 100}, behaviour state {g(tx, 'piState')}, doing {DOING.get(g(tx, 'piDoing'))}", flush=True)
                for o in tg:
                    p = await lab.props(o);
                    if p.get("_class", "?") == "?": print(f"   target {o}: gone"); continue
                    print(f"   target {o} {p['_class']}: at {g(await lab.run(f'show object {o}'), 'piRow')},{g(await lab.run(f'show object {o}'), 'piCol')} health {g(await lab.run(f'show object {o}'), 'piHit_points') // 100}")
                print("   last samples (t-ago, target, row, col, state): " + " ".join(f"({t - x[0]:.1f}s,{x[1]},{x[2]},{x[3]},{x[4]})" for x in list(h)[-8:]), flush=True)
        await asyncio.sleep(max(0.05, every - (time.time() - t)))
    print(f"\ndone: {reported} flip reports"); await lab.close()

if __name__ == "__main__": asyncio.run(main())
