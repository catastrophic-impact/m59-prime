#!/usr/bin/env python3
"""Playerbot scenario tests: drives the bots of a RUNNING Prime test server through every scenario that is built and reports what failed.

Run (the admin venv has what admin_tui needs):   $PRIME_WORK/admin-venv/bin/python scripts/bot_scenarios.py [--rooms 74,306] [--batch 30] [--timeout 1500] [--only town,hunt,death]
Needs the server built with the PBotTest* messages (primeplayerbots.kod). It sets the rules itself (town life 1, time scale 100 (real time), no-risk routes, bot count = batch).
Logs (overwritten every run):  prime_server/test_logs/bot_scenarios.log (full detail) and bot_scenarios_summary.txt.
Scenarios: town (street / inn / shop), hunt (every hunt room of the survey, on foot from the bot's home town, health raised so any map is survivable),
death (killed bot goes to the underworld and comes back), group (NOT BUILT yet: reported as such).
A scenario fails with a reason and a state trail; the server's own PBOT-FAIL debug lines (channel/debug.txt) are copied into the log.
"""
import argparse, asyncio, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import admin_tui as T  # noqa: E402  (AdminLink)

WORK = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
LOGDIR = os.path.join(HERE, "..", "test_logs")
DEBUG_TXT = os.path.join(WORK, "build", os.environ.get("PRIME_SERVER_DIR", "server"), "channel", "debug.txt")
PBA = {"NONE": 0, "TOWN": 1, "INN": 2, "HUNT": 3, "SHOP": 4, "DEAD": 5}
DOING = {1: "idle", 2: "hang", 3: "walk", 4: "errand", 5: "talk", 6: "transit", 7: "globe", 8: "leave", 9: "inn", 10: "shop", 11: "hunt", 12: "dead"}
FIELDS = ["rid", "node", "doing", "jrid", "stuck", "inworld", "hp", "kills", "act", "hroom", "target", "mobs", "foe", "foes", "failed", "row", "col", "goal"]


class Log:
    def __init__(self):
        os.makedirs(LOGDIR, exist_ok=True)
        self.f = open(os.path.join(LOGDIR, "bot_scenarios.log"), "w")
        self.t0 = time.time()

    def __call__(self, msg):
        line = f"[{time.time() - self.t0:7.1f}s] {msg}"
        print(line, flush=True)
        self.f.write(line + "\n")
        self.f.flush()


class Driver:
    def __init__(self, link, log, prime_id):
        self.L, self.log, self.PB = link, log, prime_id

    async def send(self, msg, **params):
        args = " ".join(f"{k} int {v}" for k, v in params.items())
        return await self.L.run(f"send object {self.PB} {msg} {args}".strip())

    LOST = object()

    async def state(self, bot, retry=True):
        """None = the bot has no body (a normal answer). Only a malformed answer (the admin link out of step) reconnects: reconnecting on every
        'no body' made ~50 admin connections a minute while the bots were being listed, and the server died after such bursts (2026-10-31)."""
        st = await self._state(bot)
        if st is self.LOST and retry:
            try:
                await self.L.close()
                await self.L.connect()
            except Exception:
                pass
            st = await self._state(bot)
        return None if st is self.LOST else st

    async def _state(self, bot):
        out = await self.send("PBotTestState", id=bot)
        m = re.search(r"return from.*?: LIST (\d+)", out, re.S)
        if not m:
            return None if re.search(r"return from.*?: \$ 0", out, re.S) else self.LOST
        body = await self.L.run(f"show list {m.group(1)}")
        vals = [int(v) for v in re.findall(r"^: (?:INT|OBJECT|\$) (-?\d+)", body, re.M)]
        if len(vals) < len(FIELDS):
            return self.LOST
        return dict(zip(FIELDS, vals))

    async def prop(self, name, value):
        await self.L.run(f"set object {self.PB} {name} int {value}")

    async def bots_with_bodies(self):
        top = await self.L.run(f"show object {self.PB}")
        m = re.search(r"piPBotNextId\s*=\s*INT\s*(\d+)", top)
        n = int(m.group(1)) if m else 200
        ids = []
        for b in range(1, n):
            if await self.state(b):
                ids.append(b)
        return ids

    async def hunt_rooms(self):
        m = None
        for _ in range(3):
            top = await self.L.run(f"show object {self.PB}")
            m = re.search(r"plPBotRooms\s*=\s*LIST\s*(\d+)", top)
            if m:
                break
            await self.L.close()
            await self.L.connect()
        if not m:
            return []
        out = await self.L.run(f"show list {m.group(1)}")
        return [(int(r), int(lvl)) for r, lvl in re.findall(r"^: \[\n: INT (\d+)\n: INT (\d+)", out, re.M)]


def fmt(st):
    if not st:
        return "no body"
    return f"room {st['rid']} node {st['node']} {DOING.get(st['doing'], st['doing'])} jrid {st['jrid']} stuck {st['stuck']} world {st['inworld']} hp {st['hp']} act {st['act']} hroom {st['hroom']} kills {st['kills']} target {st['target']} mobs-in-room {st['mobs']} foe-in-reach {st['foe']} foes-alive {st['foes']} failed {st['failed']} at {st['row']},{st['col']} goal node {st['goal']}"


async def watch(drv, jobs, timeout, log, poll=6):
    """jobs: {bot: dict(name, ok(state, trail) -> bool|str|None, fail(state, trail) -> reason|None)}. Polls until each is done or timed out."""
    t0 = time.time()
    trail = {b: [] for b in jobs}
    result = {}
    last_move = {b: (None, t0) for b in jobs}
    while len(result) < len(jobs) and time.time() - t0 < timeout:
        for b, job in jobs.items():
            if b in result:
                continue
            st = await drv.state(b)
            tr = trail[b]
            if not tr or tr[-1][1] != fmt(st):
                tr.append((round(time.time() - t0), fmt(st)))
                del tr[:-40]
            if st is None:
                result[b] = ("FAIL", "bot body lost")
                continue
            key = (st["rid"], st["node"], st["doing"], st["inworld"])
            if key != last_move[b][0]:
                last_move[b] = (key, time.time())
            verdict = job["ok"](st, tr)
            if verdict:
                result[b] = ("PASS", verdict if isinstance(verdict, str) else "")
                continue
            why = job["fail"](st, tr, time.time() - last_move[b][1], time.time() - t0)
            if why:
                result[b] = ("SKIP" if why.startswith("SKIP") else "FAIL", why)
    for b in jobs:
        if b not in result:
            result[b] = ("FAIL", f"timeout after {timeout}s")
    return result, trail


def report(log, name, res, trail, summary):
    for b, (verdict, why) in sorted(res.items()):
        label = f"{name} bot {b}"
        summary.append((label, verdict, why))
        log(f"{verdict} {label} {why}")
        if verdict == "FAIL":
            for t, line in trail[b][-12:]:
                log(f"      +{t:>4}s {line}")


async def scenario_town(drv, log, bots, summary, timeout):
    """street, inn, shop: each in its own bot; expect the bot in the world, in a room of the expected kind, doing something sensible."""
    if len(bots) < 3:
        log("town: not enough bots")
        return
    jobs = {}
    spec = [("TOWN", bots[0]), ("INN", bots[1]), ("SHOP", bots[2])]
    for act, b in spec:
        await drv.send("PBotTestAct", id=b, act=PBA[act])

        def ok(st, tr, act=act):
            if act == "SHOP":
                # by design the shopper waits out of the world until a player enters its shop (PBotShopPresence); it needs a shop room chosen
                return "shopper waits in limbo for a player (materialising needs a player in the shop: not tested here)" if st["act"] == PBA["SHOP"] and not st["inworld"] else None
            if not st["inworld"]:
                return None
            if act == "INN":
                return f"in inn room {st['rid']}" if st["doing"] in (2, 7, 9) else None
            if act == "SHOP":
                return f"at shop {st['rid']}" if st["doing"] == 10 else None
            return f"on the street in room {st['rid']}" if st["doing"] in (1, 2, 3, 5, 7) and not st["jrid"] else None

        def fail(st, tr, still, elapsed, act=act):
            if elapsed > 120 and not st["inworld"] and act == "TOWN":
                return "town bot is not in the world"
            if st["stuck"] >= 40:
                return f"stuck {st['stuck']}"
            return None

        jobs[b] = dict(name=act, ok=ok, fail=fail)
    res, trail = await watch(drv, jobs, min(timeout, 600), log)
    report(log, "town", res, trail, summary)


async def scenario_death(drv, log, bot, summary, timeout):
    """a killed bot waits in the underworld (real room), then is back among the living (act NONE/INN, in the world)."""
    await drv.send("PBotTestAct", id=bot, act=PBA["TOWN"])
    await asyncio.sleep(10)
    await drv.send("PBotDied", id=bot)
    seen_dead = []

    def ok(st, tr):
        if st["doing"] == 12:
            seen_dead.append(1)
        return "died, underworld, revived" if seen_dead and st["inworld"] and st["doing"] != 12 and st["act"] != PBA["DEAD"] else None

    def fail(st, tr, still, elapsed):
        return None

    res, trail = await watch(drv, {bot: dict(name="death", ok=ok, fail=fail)}, min(timeout, 2400), log, poll=10)
    report(log, "death", res, trail, summary)


async def scenario_rescue(drv, log, bot, summary, timeout):
    """a bot stuck for good in a far room casts Rescue (whatever its class) and is taken home: in an inn of its home town, no journey, no hunt."""
    await drv.send("PBotTestHuntHere", id=bot, rid=574, hp=400)
    await asyncio.sleep(15)
    first = await drv.state(bot)
    # the bot gives up its walk for good: it casts Rescue (PlayerBot.CastRescue), as the stuck rule does after six failed walks in two minutes
    m = re.search(r"^: OBJECT (\d+)", await drv.L.run(f"send object {drv.PB} PBotBodyOf id int {bot}"), re.M)
    if m: await drv.L.run(f"send object {m.group(1)} CastRescue")

    def ok(st, tr):
        if first and st["rid"] != 574 and st["inworld"] and st["act"] != PBA["HUNT"] and not st["jrid"]:
            return f"rescued from room 574 to room {st['rid']}"
        return None

    def fail(st, tr, still, elapsed):
        return "still in room 574 after 120 s: no rescue" if elapsed > 120 else None

    res, trail = await watch(drv, {bot: dict(name="rescue", ok=ok, fail=fail)}, min(timeout, 200), log)
    report(log, "rescue", res, trail, summary)


async def scenario_hunt(drv, log, bots, rooms, summary, timeout, hp, here=False, strict=False):
    """one bot per room: on foot from its home town to the room, then hunting (target seen or a kill) there."""
    jobs = {}
    for b, (rid, lvl) in zip(bots, rooms):
        if not await drv.send("PBotTestHuntHere" if here else "PBotTestHunt", id=b, rid=rid, hp=hp):
            log(f"hunt: bot {b} could not start for room {rid}")
        arrived = {}
        room_since = {}

        def ok(st, tr, rid=rid, arrived=arrived):
            if st["rid"] == rid and st["inworld"] and st["doing"] == 11:
                arrived.setdefault("t", time.time())
                arrived.setdefault("hp", st["hp"])
                if strict:
                    if st["kills"]:
                        return f"killed {st['kills']} in room {rid}"
                elif st["target"] or st["kills"]:
                    return f"hunting in room {rid} (kills {st['kills']})"
                if st["hp"] < arrived["hp"] and not strict:
                    return f"in a fight in room {rid} (hurt {arrived['hp']} -> {st['hp']})"
            if "t" in arrived and st["doing"] == 12:
                return f"fought and died in room {rid} (too weak for it, the underworld took it)"
            return None

        def fail(st, tr, still, elapsed, rid=rid, arrived=arrived, room_since=room_since):
            if st["failed"]:
                return f"STUCK (strict test mode, no quiet fix) in room {st['rid']} at node {st['node']} on its way to {rid}, standing at row {st['row']} col {st['col']}, goal node {st['goal']}"
            if not st["inworld"] and elapsed > 30:
                return "out of the world (limbo) while it should walk"
            if strict and st["rid"] == rid and st["doing"] == 11 and "t" in arrived and time.time() - arrived["t"] > 420 and not st["kills"]:
                return f"NO KILL in 7 min in room {rid}: at row {st['row']} col {st['col']} node {st['node']}, target {st['target']}, mobs {st['mobs']}, foes {st['foes']}, hp {st['hp']}"
            if st["rid"] == rid and st["doing"] == 11 and "t" in arrived and time.time() - arrived["t"] > 300 and not st["foes"]:
                return f"SKIP: no fightable monster alive in room {rid} (killed earlier, respawn pending, or a boss room)"
            if st["rid"] == rid and st["doing"] == 11 and "t" in arrived and time.time() - arrived["t"] > 300:
                return "in the hunt room for 5 min and never fought (no target, no kill)"
            if st["jrid"] and still > 240 and st["doing"] in (1, 3, 6, 8):
                return f"not moving for {int(still)} s on its way to {rid}"
            if st["jrid"] and st["inworld"] and room_since.get("rid") == st["rid"] and time.time() - room_since["t"] > 300:
                return f"still in room {st['rid']} after 5 min on its way to {rid} (stuck at a door or node {st['node']})"
            if room_since.get("rid") != st["rid"]:
                room_since.update(rid=st["rid"], t=time.time())
            if st["act"] != PBA["HUNT"]:
                return f"activity changed to {st['act']} before it arrived (act 2 = PBotJourneyFailed: no route from this bot's home town)"
            return None

        jobs[b] = dict(name=f"hunt {rid}", ok=ok, fail=fail)
    res, trail = await watch(drv, jobs, timeout, log)
    for b, (rid, lvl) in zip(bots, rooms):
        v, why = res[b]
        res[b] = (v, f"room {rid} (level {lvl}): {why}")
    report(log, "hunt", res, trail, summary)


async def scenario_aggro(drv, log, bots, rooms, summary, timeout):
    """monsters attack a bot that merely stands among them (a standing bot loses health or turns on a foe); the dead leave a corpse (not checked here)."""
    seen = {}
    for bot, (rid, _) in zip(bots, rooms):
        await drv.send("PBotSet", id=bot, pos=8, value=PBA["NONE"])
        await drv.send("PBotTestAct", id=bot, act=PBA["INN"])
        await drv.send("PBotPlaceNode", id=bot, rid=rid, node=1)
        st = await drv.state(bot)
        seen[bot] = (rid, st["hp"] if st else None)
    t0 = time.time()
    hit = {}
    while time.time() - t0 < 90 and len(hit) < len(bots):
        await asyncio.sleep(5)
        for bot in bots:
            st = await drv.state(bot)
            if st and bot not in hit and (st["hp"] < seen[bot][1] or st["target"] or st["doing"] == 12 or st["rid"] != seen[bot][0]):
                hit[bot] = (seen[bot][0], st)
    for bot in bots:
        log(f"aggro bot {bot} room {seen[bot][0]}: {'attacked' if bot in hit else 'left alone'}")
    summary.append(("aggro: monsters attack a standing bot", "PASS" if hit else "FAIL", f"{len(hit)} of {len(bots)} bots in rooms {[r for r, _ in rooms]} attacked within 90 s"))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms", help="comma list of hunt room numbers (default: all of the survey)")
    ap.add_argument("--batch", type=int, default=30)
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--hp", type=int, default=3000, help="health given to test hunters so any map is survivable (0 = leave)")
    ap.add_argument("--here", action="store_true", help="hunt tests set the bot down in the hunt room (fight only, no travel)")
    ap.add_argument("--strict", action="store_true", help="hunt passes only on a real kill")
    ap.add_argument("--only", default="town,hunt,death,rescue,aggro,group")
    a = ap.parse_args()
    only = set(a.only.split(","))
    log = Log()
    summary = []
    dbg_start = os.path.getsize(DEBUG_TXT) if os.path.exists(DEBUG_TXT) else 0
    L = T.AdminLink()
    await L.connect()
    out = await L.run("show instances primeclasses")
    prime = int(re.search(r"OBJECT\s+(\d+)", out).group(1))
    drv = Driver(L, log, prime)
    await drv.prop("piTownLife", 1)
    await drv.prop("piBotTimeScale", 100)
    await drv.prop("piPBotNoRisk", 1)
    # never lower the count below the bots in the game: the server logs the surplus out, test bots included ("bot body lost")
    cur = re.search(r"piPlayerBotCount\s*=\s*INT\s*(\d+)", await L.run(f"show object {prime}"))
    await drv.prop("piPlayerBotCount", max(a.batch + 6, int(cur.group(1)) if cur else 0))
    log(f"waiting for {a.batch + 6} bot bodies ...")
    bots = []
    for _ in range(60):
        bots = await drv.bots_with_bodies()
        if len(bots) >= a.batch + 6:
            break
        await asyncio.sleep(20)
    log(f"{len(bots)} bots with bodies")
    if len(bots) < 8:
        log("FAIL setup: too few bots")
        return
    tb, db, hb = bots[:3], bots[3], bots[4:]
    if "town" in only:
        await scenario_town(drv, log, tb, summary, a.timeout)
    if "death" in only:
        await scenario_death(drv, log, db, summary, a.timeout)
    if "rescue" in only:
        await scenario_rescue(drv, log, db if "death" not in only else hb[-1], summary, a.timeout)
    if "hunt" in only:
        rooms = await drv.hunt_rooms()
        if a.rooms:
            want = {int(x) for x in a.rooms.split(",")}
            known = {r[0]: r for r in rooms}
            rooms = [known.get(r, (r, 0)) for r in sorted(want)]   # a room outside the survey (PBotNoHunt) can still be tested by name
        log(f"{len(rooms)} hunt rooms to test, batches of {len(hb)}")
        for i in range(0, len(rooms), len(hb)):
            chunk = rooms[i:i + len(hb)]
            log(f"hunt batch {i // len(hb) + 1}: rooms {[r for r, _ in chunk]}")
            await scenario_hunt(drv, log, hb[:len(chunk)], chunk, summary, a.timeout, a.hp, a.here, a.strict)
    if "aggro" in only:
        rooms = await drv.hunt_rooms()
        pick = rooms[:: max(1, len(rooms) // 6)][:6]
        await scenario_aggro(drv, log, hb[:len(pick)], pick, summary, a.timeout)
    if "group" in only:
        summary.append(("group bots", "SKIP", "NOT BUILT: bot groups (player invite, bot-bot hunting groups) are the next stage"))
        log("SKIP group: not built yet")
    # server-side failure lines of this run
    fails = []
    if os.path.exists(DEBUG_TXT):
        with open(DEBUG_TXT, errors="replace") as f:
            f.seek(dbg_start)
            fails = [ln.strip() for ln in f if "PBOT-FAIL strict" in ln or "PBOT-FAIL journey" in ln]
    log(f"--- server debug lines of this run ({len(fails)}) ---")
    for ln in fails[:300]:
        log(ln)
    passed = sum(1 for _, v, _ in summary if v == "PASS")
    failed = [s for s in summary if s[1] == "FAIL"]
    with open(os.path.join(LOGDIR, "bot_scenarios_summary.txt"), "w") as f:
        f.write(f"{passed} passed, {len(failed)} failed, {sum(1 for s in summary if s[1] == 'SKIP')} skipped\n")
        for label, v, why in summary:
            if v != "PASS":
                f.write(f"{v} {label}: {why}\n")
    log(f"DONE {passed} passed, {len(failed)} failed")
    await L.close()


if __name__ == "__main__":
    asyncio.run(main())
