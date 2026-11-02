#!/usr/bin/env python3
"""WALK REGRESSION on the TEST server: random start/goal pairs (baked nodes of a room, at least 6 squares apart, fixed seed) are walked by test bots with THE walker (the planner of
PlayerBot.WalkTo). The trip logic and the failure bundles live in claude_tools/botscenario.py (Scenario.walk): this script only picks the pairs, runs them on several bots
(one worker owns a whole room: bots block each other) and writes the summary. History: the old baked-route walker was replaced by the planner on 2026-11-02; the last A/B
(old 34/40, planner 39/40 on 80 identical trips) is in docs/walker_ab/.
Outcomes: arrived | exited (walked out through a door/edge square) | fled (a blocking creature too strong: rescue) | stuck | timeout. Failed trips save a bundle in docs/scenarios/.
TEST ONLY (places test bots with huge health on server2):
  PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 python claude_tools/walkcheck.py ROOM [ROOM..] [--pairs 8] [--timeout 90] [--stall 20] [--workers 3] [--seed 11]
Summary -> docs/walkcheck/results.json/.md (overwritten each run). A bot that cannot be placed twice in a row is dropped from the pool and its trip requeued; the run ends when the queue or the pool is empty."""
import asyncio, json, math, os, random, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botscenario import Scenario, ROOT
import botlab
W = os.path.expanduser("~/boxes/m59-box/src/prime_work")
OUT = os.path.join(ROOT, "docs", "walkcheck")

class Run:
    def __init__(self, a): self.a = a; self.res = []; self.harness = 0; self.trips = 0; self.t0 = time.time(); self.stop = False; self.owner = {}; self.tries = {}

async def worker(run, q, pool, wi, first):
    """one worker = one bot at a time from the shared pool; a bot that fails to be placed twice in a row (a natural bot that went to a shop and has no body, say) is dropped and the next one is taken"""
    sc = await Scenario.open(recorder=first)
    bot = None; fails = 0
    while q and not run.stop:
        if bot is None:
            if not pool: break
            bot = pool.pop(0); fails = 0
        rid, start, goal, tag = q.pop(0)
        if run.owner.setdefault(rid, wi) != wi: q.append((rid, start, goal, tag)); await asyncio.sleep(1); continue
        r = await sc.walk(bot, rid, start, goal, run.a.timeout, run.a.stall, tag)
        run.trips += 1
        if r is None:
            fails += 1; run.harness += 1; print(f"  harness: bot {bot} could not be placed at {start} in {rid} (trip dropped, requeued)", flush=True)
            run.tries[(rid, tuple(start))] = run.tries.get((rid, tuple(start)), 0) + 1
            if run.tries[(rid, tuple(start))] < 2: q.append((rid, start, goal, tag))     # a second bot could not be placed there either: that start square is unplaceable (a pocket): dropped for good
            if fails >= 2: print(f"  bot {bot} dropped from the pool (no body / cannot be placed)", flush=True); bot = None
            await asyncio.sleep(2)
            continue
        fails = 0; run.res.append(r)
        print(f"[{int(time.time()-run.t0):4d}s] room {rid} #{tag} {tuple(start)}->{tuple(goal)}: {r['outcome']} {r['why']} ({r['secs']}s, {r['left']} sq left)", flush=True)
    for k in [k for k, v in run.owner.items() if v == wi]: del run.owner[k]     # a worker that is done releases its rooms, or the others wait for it for ever
    await sc.close()

async def main():
    argv = sys.argv[1:]
    class A: pairs = 8; timeout = 90; stall = 20; workers = 3; seed = 11
    a = A()
    for k in ("pairs", "timeout", "stall", "workers", "seed"):
        if f"--{k}" in argv: i = argv.index(f"--{k}"); setattr(a, k, int(argv[i + 1])); del argv[i:i + 2]
    rooms = [int(x) for x in argv]
    bake = {x["rid"]: x for x in json.load(open(os.path.join(W, "navtmp/navbake.json")))}
    random.seed(a.seed); q = []
    for rid in rooms:
        n = bake[rid]["nodes"]; k = 0; tries = 0
        while k < a.pairs and tries < 200:
            tries += 1; p, g = random.sample(range(len(n)), 2)
            if math.hypot(n[p]["row"] - n[g]["row"], n[p]["col"] - n[g]["col"]) < 6: continue
            q.append((rid, (n[p]["row"], n[p]["col"]), (n[g]["row"], n[g]["col"]), k)); k += 1
    sc0 = await Scenario.open(); bots = await sc0.bots(); await sc0.close()
    a.workers = min(a.workers, len(bots)); print(f"{len(q)} pairs, {a.workers} workers, bot pool {bots}", flush=True)
    run = Run(a); pool = list(bots)
    await asyncio.gather(*[worker(run, q, pool, i, i == 0) for i in range(a.workers)])
    os.makedirs(OUT, exist_ok=True); json.dump(run.res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    md = ["# Walk regression (the planner walker)", "", "| room | trips | arrived | stuck | exited | fled | timeout |", "|---|---|---|---|---|---|---|"]
    for rid in rooms:
        rr = [r for r in run.res if r["room"] == rid]
        md.append(f"| {rid} | {len(rr)} | " + " | ".join(str(sum(1 for r in rr if r["outcome"] == o)) for o in ("arrived", "stuck", "exited", "fled", "timeout")) + " |")
    md.append(f"| all | {len(run.res)} | " + " | ".join(str(sum(1 for r in run.res if r["outcome"] == o)) for o in ("arrived", "stuck", "exited", "fled", "timeout")) + " |")
    md += ["", f"harness problems: {run.harness} of {run.trips} trips", "", "Failed trips (bundles in docs/scenarios/: .png picture with the cause drawn, .json report, .trail.json for roomview --trail):"]
    for r in run.res:
        if r["outcome"] != "arrived":
            md.append(f"- room {r['room']} {r['start']}->{r['goal']}: {r['outcome']} {r['why']} ({r['left']} sq left) {r.get('picture', '')}")
            md += [f"    - {e}" for e in r.get("events", [])[-4:]]
    open(os.path.join(OUT, "results.md"), "w").write("\n".join(md) + "\n"); print("\n".join(md))
if __name__ == "__main__": asyncio.run(main())
