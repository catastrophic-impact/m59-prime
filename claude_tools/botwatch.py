#!/usr/bin/env python3
"""BOT WATCH: observe ALL bots for a long time and explain every failure while it happens (read-only; --trace switches the flight recorder on for all bots: test server only).
  PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 $PRIME_WORK/admin-venv/bin/python claude_tools/botwatch.py [--mins 30] [--every 5] [--trace] [--out DIR]
Every --every seconds each bot with a body is sampled (room, square, activity, stuck, planner state, journey). An EPISODE starts when a bot is
  NOWAY   the planner says 'no way' for 20 s          STILL   walking/transit/hunt/errand on the same square for 45 s while the planner says 'walking'
  STUCK   stuck count > 0 for 30 s                    DEAD    dead for 240 s (waiting for its resurrection longer than expected)
  HOME    the same activity in the same room for 15 min (transit/walk/hunt only: a trip that never ends)
At that moment the tool captures the EVIDENCE: botinspect's report (position, goal, first refused step and REASON, bodies nearby) and, with --trace, the flight recorder's last decisions
decoded into words. When the episode ends its length is recorded. Nothing is guessed: each episode carries its own evidence.
Output (docs/botwatch/<time>/): report.md (coverage: what activities/rooms/journeys the run actually saw; episodes grouped by cause, worst first; every episode with its evidence),
episodes.json, timeline.csv (every sample). Read report.md first; then botinspect.py / botevents.py on a bot that is still failing."""
import asyncio, collections, csv, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab, DOING, PATH_STATE, ROOT
import botinspect, botevents, botdash

THRESH = {"NOWAY": 20, "STILL": 45, "STUCK": 30, "DEAD": 240, "HOME": 900}
MOVING = ("transit", "walk", "hunt", "errand")

async def evidence(lab, bot, trace):
    text, snap, _ = await botinspect.inspect(lab, bot, near=6, pic=False, tag="botwatch_tmp")
    ev = {"inspect": text}
    if trace:
        body = await lab.body(bot)
        if body:
            try: ev["events"] = [f"[{e[0]}] {botevents.show(e)}" for e in (await botevents.ring(lab, body))[-14:]]
            except Exception as x: ev["events"] = [f"(recorder unreadable: {x})"]
    return ev

def cause_key(kind, ev, row):
    t = ev.get("inspect", ""); why = re.search(r"REASON: (a WALL|a BODY|an EXIT)", t)
    m = re.search(r"goal square (\d+),(\d+)", t); st = re.search(r"WALK \(planner\): state (\d+) = ([^;]+);", t)
    return (kind, row["rid"], DOING.get(row["doing"], row["doing"]), f"goal {m.group(1)},{m.group(2)}" if m else "no walk goal", why.group(1) if why else "")

async def main():
    a = sys.argv[1:]; arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    mins = float(arg("--mins", "30")); every = float(arg("--every", "5")); trace = "--trace" in a
    out = arg("--out", os.path.join(ROOT, "docs", "botwatch", time.strftime("%Y%m%d_%H%M%S"))); os.makedirs(out, exist_ok=True)
    lab = await Lab.open(); m = re.search(r"piPBotNextId\s*=\s*INT\s*(\d+)", await lab.run(f"show object {lab.prime}")); ids = range(1, int(m.group(1)) if m else 50)
    if trace:
        for k, v in (("piPBotTraceMax", 1000000), ("piPBotTraceMins", 600), ("piPBotTraceEnd", 0), ("piPBotTrace", -1)): await lab.run(f"set object {lab.prime} {k} int {v}")
    t0 = time.time(); t_end = t0 + mins * 60
    state = {}            # bot -> {"pos": (rid,row,col), "since": t, "doing_since": (doing, rid, t), "kinds": {kind: t_started_condition}}
    open_ep = {}          # (bot, kind) -> episode
    out_since = {}; out_time = collections.Counter(); out_longest = collections.defaultdict(int); out_n = collections.Counter()
    death_log = []; eps = []; cov_act = collections.Counter(); cov_room = collections.Counter(); bots_seen = set(); deaths = 0; room_changes = 0
    tl = csv.writer(open(os.path.join(out, "timeline.csv"), "w")); tl.writerow(["t", "bot", "rid", "row", "col", "doing", "stuck", "hp", "plan", "jrid", "inworld"])
    print(f"watching for {mins:g} min, every {every:g} s, trace {'ON' if trace else 'off'}; output {out}", flush=True)
    last_print = 0
    while time.time() < t_end:
        t = time.time()
        try: rows = await botdash.snapshot(lab, ids)
        except Exception as x: rows = []; print(f"[{int((t - t0) // 60):>3}:{int((t - t0) % 60):02d}] admin link failed ({x!r})", flush=True)
        if not rows and state:      # the admin link dropped (a sample with no bot at all after bots were seen): reconnect and sample again
            try: await lab.close()
            except Exception: pass
            await asyncio.sleep(2); lab = await Lab.open(); print(f"[{int((t - t0) // 60):>3}:{int((t - t0) % 60):02d}] admin link reopened", flush=True)
            try: rows = await botdash.snapshot(lab, ids)
            except Exception: rows = []
        now = t - t0
        for r in rows:
            b = r["bot"]; bots_seen.add(b); d = DOING.get(r["doing"], str(r["doing"])); pos = (r["rid"], r["row"], r["col"])
            tl.writerow([round(now), b, r["rid"], r["row"], r["col"], d, r["stuck"], r["hp"], PATH_STATE.get(r["plan"], "") if r["plan"] else "", r["jrid"], int(r["inworld"])])
            cov_act[d] += every; cov_room[r["rid"]] += every
            s = state.setdefault(b, {"pos": pos, "since": now, "doing": (d, r["rid"], now), "kinds": {}, "last_doing": d, "last_rid": r["rid"]})
            if s["pos"] != pos: s["pos"] = pos; s["since"] = now
            if s["doing"][:2] != (d, r["rid"]): s["doing"] = (d, r["rid"], now)
            if d == "dead" and s["last_doing"] != "dead":
                deaths += 1
                ev = {"events": []}
                if trace:      # the flight recorder still holds what the bot decided in its last seconds
                    try: ev["events"] = [f"[{e[0]}] {botevents.show(e)}" for e in (await botevents.ring(lab, r["body"]))[-22:]]
                    except Exception as x: ev["events"] = [f"(recorder unreadable: {x})"]
                death_log.append({"bot": b, "t": round(now), "room": s["last_rid"], "doing_before": s["last_doing"], "hp_before": s.get("hp", 0), "events": ev["events"]})
                print(f"[{int(now // 60):>3}:{int(now % 60):02d}] DEATH  bot {b} was {s['last_doing']} in room {s['last_rid']} (health {s.get('hp', 0)}%)", flush=True)
            s["hp"] = r["hp"]
            if r["rid"] != s["last_rid"] and r["rid"]: room_changes += 1
            s["last_doing"] = d; s["last_rid"] = r["rid"]
            conds = set()
            if not r["inworld"]:
                out_since.setdefault(b, (now, d)); out_time[d] += every
            elif b in out_since:
                t_out, d_out = out_since.pop(b); out_n[d_out] += 1; out_longest[d_out] = max(out_longest[d_out], round(now - t_out))
            if not r["inworld"]: s["kinds"].clear(); continue      # a bot out of the world (hunting away, in a shop) has no position to judge
            if r["plan"] == 3 and d in MOVING: conds.add("NOWAY")      # (a bot at rest keeps the planner state of its LAST walk, often from another room: not a failure)
            if r["stuck"] > 0: conds.add("STUCK")
            if d == "dead": conds.add("DEAD")
            if d in MOVING and r["plan"] == 1 and now - s["since"] >= 1: conds.add("STILL")
            if d in MOVING[:3] and now - s["doing"][2] >= 1: conds.add("HOME")
            for kind in list(s["kinds"]):
                if kind not in conds: s["kinds"].pop(kind); ep = open_ep.pop((b, kind), None); (ep and ep.update(end=round(now), length=round(now - ep["start_cond"])))
            for kind in conds:
                s["kinds"].setdefault(kind, now)
                held = now - (s["since"] if kind == "STILL" else s["doing"][2] if kind == "HOME" else s["kinds"][kind])
                if held >= THRESH[kind] and (b, kind) not in open_ep:
                    ev = await evidence(lab, b, trace)
                    ep = {"bot": b, "kind": kind, "at": round(now), "start_cond": round(now - held), "rid": r["rid"], "row": r["row"], "col": r["col"], "doing": d, "jrid": r["jrid"], "evidence": ev, "key": cause_key(kind, ev, r)}
                    open_ep[(b, kind)] = ep; eps.append(ep)
                    print(f"[{int(now // 60):>3}:{int(now % 60):02d}] {kind:<6} bot {b} {d} room {r['rid']} at {r['row']},{r['col']}  ({ep['key'][3]} {ep['key'][4]})", flush=True)
        if now - last_print >= 300: last_print = now; print(f"[{int(now // 60):>3}:{int(now % 60):02d}] {len(rows)} bots, {len(eps)} episodes so far ({len(open_ep)} open), deaths {deaths}, room changes {room_changes}", flush=True)
        await asyncio.sleep(max(0.5, every - (time.time() - t)))
    for ep in open_ep.values(): ep["end"] = None; ep["length"] = round(time.time() - t0 - ep["start_cond"])
    if trace: await lab.run(f"set object {lab.prime} piPBotTrace int 0")
    await lab.close()
    # report
    L = [f"# Bot watch {time.strftime('%Y-%m-%d %H:%M')} ({mins:g} min, {len(bots_seen)} bots, sampled every {every:g} s)", "", "## Coverage (what this run actually saw)", ""]
    tot = sum(cov_act.values()) or 1
    L.append("activity time share: " + ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in cov_act.most_common()))
    L.append(f"deaths {deaths}; room changes {room_changes}; rooms visited {len([r for r in cov_room if r])}: " + ", ".join(str(r) for r, _ in cov_room.most_common(25)))
    L += ["", "## Time out of the world (a bot between rooms, in a shop, hunting away): by the activity it had when it left", ""]
    L.append("; ".join(f"{k}: {out_n[k]} trips, longest {out_longest[k]} s, total {int(out_time[k])} s" for k in sorted(out_time)) or "no bot left the world")
    L += ["still out at the end: " + (", ".join(f"bot {b} ({d_}, since t+{int(t_)} s)" for b, (t_, d_) in out_since.items()) or "none")]
    L += ["", f"## Deaths ({len(death_log)}): where, doing what, health before, and the bot's last decisions (needs --trace)", ""]
    for dl in death_log:
        L += [f"### DEATH bot {dl['bot']} t+{dl['t']} s in room {dl['room']}, was {dl['doing_before']}, health {dl['hp_before']}% one sample before", "```"] + (dl["events"] or ["(no recorder: run with --trace)"]) + ["```", ""]
    L += ["", "## Episodes grouped by cause (kind, room, activity, goal, reason of the first refused step)", ""]
    groups = collections.defaultdict(list)
    for e in eps: groups[e["key"]].append(e)
    if not eps: L.append("none: no bot failed in this run")
    for k, g in sorted(groups.items(), key=lambda kv: -sum(x["length"] or 0 for x in kv[1])):
        bots = sorted({x["bot"] for x in g}); L.append(f"- **{k[0]}** room {k[1]} {k[2]}, {k[3]} {k[4]}: {len(g)} episode(s), bots {bots}, longest {max(x['length'] or 0 for x in g)} s" + ("  [STILL OPEN at the end]" if any(x['end'] is None for x in g) else ""))
    L += ["", "## Evidence per episode", ""]
    for e in eps:
        L += [f"### {e['kind']} bot {e['bot']} room {e['rid']} at {e['row']},{e['col']}, {e['doing']}, from t+{e['start_cond']} s, length {e['length']} s" + (" (open)" if e["end"] is None else ""), "```", e["evidence"]["inspect"]]
        if e["evidence"].get("events"): L += ["-- last decisions (flight recorder):"] + e["evidence"]["events"]
        L += ["```", ""]
    open(os.path.join(out, "report.md"), "w").write("\n".join(L)); json.dump(eps, open(os.path.join(out, "episodes.json"), "w"), default=list)
    print(f"done: {len(eps)} episodes in {len(groups)} groups; report {os.path.join(out, 'report.md')}")

if __name__ == "__main__": asyncio.run(main())
