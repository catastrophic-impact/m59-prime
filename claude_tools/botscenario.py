#!/usr/bin/env python3
"""botscenario: the SCENARIO LIBRARY. Any bot test in a few lines; failures come back as self-explaining BUNDLES. Import it, do not run it.
TEST SERVER ONLY (it places test bots with huge health): PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2.

    from botscenario import Scenario
    sc = await Scenario.open()                       # admin link + flight recorder on for every bot
    bot = (await sc.bots())[0]
    r = await sc.walk(bot, 2901, start=(10, 25), goal=(28, 3))      # the one walker: the bot plans its own way (server A*) and walks it
    print(r["outcome"], r["why"])                    # arrived | stuck | exited | gaveup | timeout   (None = harness problem: placement did not take)
    # a failed trip also has r["report"] (botinspect text), r["picture"] (png), r["events"] (decoded recorder), r["cause"] (bodies within 2 squares), r["trail"] (json)
    await sc.close()

Building blocks for other scenarios (room mechanics, PVP...): sc.clean(bot), sc.place(bot, rid, (row, col)) -> bool (confirmed in the room AND on the start square),
sc.sample(body) -> one position sample, sc.events(body) -> decoded flight-recorder lines, sc.inspect(bot) -> (report, snapshot, picture).
Bundles go to docs/scenarios/<name>.* (name = room_tag). Harness traps this fixes (all hit in session 18): the path prototype keeps its OLD goal alive unless piPathState/pbPathTest
are reset; a bot that walked out of the room needs seconds to be placed again; a placement can silently not take effect (start square checked from the first sample)."""
import asyncio, json, math, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab, ROOT, debug_strings
import botinspect

OUT = os.path.join(ROOT, "docs", "scenarios")
def _num(t, n):
    m = re.search(rf"\b{n}\s*=\s*(?:INT|OBJECT)\s+(-?\d+)", t); return int(m.group(1)) if m else 0
def pos(s): return (s[2] - 1) + s[4] / 64.0, (s[3] - 1) + s[5] / 64.0      # sample -> 0-based squares (row, col)

class Scenario:
    @classmethod
    async def open(cls, link=None, recorder=True):
        """link: reuse an admin link (several workers need one each); recorder: switch the bot trace on for every bot (flight recorder; limit raised for long runs)"""
        self = cls(); self.lab = await Lab.open() if link is None else Lab.on(link, await cls._prime(link)); self.L = self.lab.L; self.prime = self.lab.prime; self.DS = debug_strings()
        # placement tools need REAL time: at piBotTimeScale 10 a placed bot walks off before the question is asked (edgeprobe once reported every edge exit unreachable)
        await self.L.run(f"set object {self.prime} piBotTimeScale int 100")
        if recorder:
            for k, v in (("piPBotTraceMax", 1000000), ("piPBotTraceMins", 240), ("piPBotTraceEnd", 0), ("piPBotTrace", -1)): await self.L.run(f"set object {self.prime} {k} int {v}")
        return self
    @staticmethod
    async def _prime(L): return int(re.search(r"OBJECT\s+(\d+)", await L.run("show instances primeclasses")).group(1))
    async def close(self): await self.lab.close()

    async def bots(self):
        """ids of the bots that have a body (test bots 1..N)"""
        import bot_scenarios as B
        return await B.Driver(self.L, lambda m: None, self.prime).bots_with_bodies()
    async def body(self, bot): return await self.lab.body(bot)
    async def clean(self, body):
        """forget a finished walk (the walk's outcome stays in piPathState until the next walk starts)"""
        await self.L.run(f"set object {body} piPathState int 0")
    async def sample(self, body, t0=None):
        t = await self.L.run(f"show object {body}")
        if "piRow" not in t: return None
        return [round(time.time() - (t0 or time.time()), 2), _num(t, "piNavRid"), _num(t, "piRow"), _num(t, "piCol"), _num(t, "piFine_row"), _num(t, "piFine_col"),
                _num(t, "piDoing"), _num(t, "piStuck"), _num(t, "piGoalNode"), _num(t, "piPathState")]
    async def place(self, bot, body, rid, start, hp=99999, wait=8):
        """set the test bot down on a square and CONFIRM it (in the room, near the square). False = harness problem."""
        await self.clean(body)
        cmd = f"send object {self.prime} PBotTestPlace id int {bot} rid int {rid} row int {start[0]} col int {start[1]} hp int {hp}"
        await self.L.run(cmd)
        for k in range(wait):
            await asyncio.sleep(1.0)
            tt = await self.L.run(f"show object {body}")
            if _num(tt, "piNavRid") == rid and re.search(r"poOwner\s*=\s*OBJECT", tt):
                s = await self.sample(body)
                if s and math.hypot(pos(s)[0] - (start[0] - 0.5), pos(s)[1] - (start[1] - 0.5)) <= 2: return True
            if k % 3 == 2: await self.L.run(cmd)
        return False
    async def events(self, body, last=12):
        """the bot's flight recorder in words, oldest first"""
        out = await self.L.run(f"send object {body} TraceRing"); m = re.search(r"return from.*?: LIST (\d+)", out, re.S)
        if not m: return []
        r = await self.lab.list(int(m.group(1)))
        if len(r) < 2 or not isinstance(r[1], list): return []
        ev = r[1][r[0]:] + r[1][:r[0]]
        def v(x): return "" if x is None else (self.DS.get(int(x[1]), "?") if isinstance(x, tuple) and x[0] == "DEBUGSTR" else str(x[1]) if isinstance(x, tuple) else str(x))
        return [" ".join(t for t in (v(y) for y in e[1:]) if t) for e in ev if isinstance(e, list) and len(e) > 1][-last:]
    async def inspect(self, bot, name=None, near=6, pic=True):
        os.makedirs(OUT, exist_ok=True); return await botinspect.inspect(self.lab, bot, near, pic, out_dir=OUT, tag=name)

    async def walk(self, bot, rid, start, goal, timeout=90, stall=20, tag=0, bundle=True):
        """Place the bot at `start`, make it walk to `goal` (squares), judge it from its REAL position. Outcomes: arrived (within 1.5 squares) | exited (left the room: a door/edge exit square)
        | fled (could not beat a blocking creature: rescue) | stuck (no progress for `stall` s, or the planner's own stuck / no-way) | timeout. None = harness problem."""
        body = await self.body(bot)
        if not body or not await self.place(bot, body, rid, start): return None
        try:
            return await self._walk(bot, body, rid, start, goal, timeout, stall, tag, bundle)
        finally:      # whatever happened (a dropped trip too): stop the walker and park the bot, or its leftover walk spoils the next trip
            await self.place_quiet(bot, body, rid, start)

    async def _walk(self, bot, body, rid, start, goal, timeout, stall, tag, bundle):
        await self.L.run(f"send object {self.prime} PBotTestPath id int {bot} rid int {rid} row int {start[0]} col int {start[1]} trow int {goal[0]} tcol int {goal[1]}")
        gp = (goal[0] - 0.5, goal[1] - 0.5); t0 = time.time(); samples = []; best = 1e9; best_t = t0; out = None; why = ""; fought = False
        while time.time() - t0 < timeout:
            await asyncio.sleep(0.5)
            s = await self.sample(body, t0)
            if s is None: return None
            samples.append(s); d = math.hypot(pos(s)[0] - gp[0], pos(s)[1] - gp[1])
            if len(samples) == 1 and math.hypot(pos(s)[0] - (start[0] - 0.5), pos(s)[1] - (start[1] - 0.5)) > 2.5:
                return None      # the walk command put the bot somewhere else (PBotTestPath places it again; a start in a pocket gets moved): harness problem, not a bot failure
            if d < best - 0.25: best = d; best_t = time.time()
            if d <= 1.5: out = "arrived"; break
            if s[1] != rid: out = "exited"; why = "walked out of the room (door/edge exit square)"; break
            if s[9] == 6: fought = True
            if s[9] == 7: out = "fled"; why = "planner: could not beat the creature that blocked the way -> rescue"; break
            if s[9] in (3, 4): out = "stuck"; why = "planner: " + ("no way" if s[9] == 3 else "stuck"); break
            if time.time() - best_t > stall: out = "stuck"; why = f"no progress {stall}s"; break
        out = out or "timeout"; end = pos(samples[-1]) if samples else (0, 0)
        r = {"room": rid, "tag": tag, "start": list(start), "goal": list(goal), "outcome": out, "why": why, "secs": round(time.time() - t0, 1),
             "left": round(math.hypot(end[0] - gp[0], end[1] - gp[1]), 1), "bot": bot, "fought": fought}
        if out != "arrived" and bundle:
            name = f"{rid}_{tag}"; os.makedirs(OUT, exist_ok=True)
            ex = await self.lab.explain_stuck(body); r["cause"] = ex; r["events"] = await self.events(body)
            if ex["near"]: n0 = ex["near"][0]; r["why"] = (r["why"] + f"; {n0['class']} ({n0['kind']}) {n0['dist']} squares away").strip("; ")
            r["report"], snap, pic = await self.inspect(bot, name)
            if pic: r["picture"] = os.path.relpath(pic, ROOT)
            f = os.path.join(OUT, name + ".trail.json"); json.dump({"bot": bot, "trip": r, "samples": samples}, open(f, "w")); r["trail"] = os.path.relpath(f, ROOT)
        return r
    async def place_quiet(self, bot, body, rid, start):
        """park: stop whatever the bot is doing so it cannot walk into the next scenario"""
        await self.clean(body); await self.L.run(f"send object {self.prime} PBotTestPlace id int {bot} rid int {rid} row int {start[0]} col int {start[1]} hp int 99999")
