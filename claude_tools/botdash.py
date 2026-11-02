#!/usr/bin/env python3
"""BOT DASHBOARD: every bot with a body in one table (read-only), refreshed every few seconds; flags the ones that look wrong.
  PRIME_ADMIN_PORT=9998 $PRIME_WORK/admin-venv/bin/python claude_tools/botdash.py [--once] [--every 5] [--secs 60] [--max-bots 200]
Columns: bot id, body object, room id, square (row,col), doing, stuck count, health, in-world, planner state (if the path prototype is used), journey room.
FLAGS (printed under the table): STUCK (piStuck > 0), NOMOVE (same square and not parked for the last 3 refreshes while 'walking'/'hunt'), NOROOM (in-world body with no room),
PILE (3+ bots on the same square), PLANNER (planner state 3/4 while walking), The summary line counts bots per activity and per room.
Many bots = many admin calls (about 0.05 s each): use --every 10 for 100 bots. Use botinspect.py BOT on a flagged bot."""
import asyncio, collections, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab, DOING, PATH_STATE

def num(t, n):
    m = re.search(rf"\b{n}\s*=\s*(?:INT|OBJECT)\s+(-?\d+)", t); return int(m.group(1)) if m else 0

async def snapshot(lab, ids):
    rows = []
    for b in ids:
        body = await lab.body(b)
        if not body: continue
        t = await lab.run(f"show object {body}")
        rows.append({"bot": b, "body": body, "rid": num(t, "piNavRid"), "row": num(t, "piRow"), "col": num(t, "piCol"), "doing": num(t, "piDoing"), "stuck": num(t, "piStuck"),
                     "hp": num(t, "piHit_points") // 100, "inworld": bool(re.search(r"poOwner\s*=\s*OBJECT", t)), "plan": num(t, "piPathState"), "jrid": num(t, "piJourneyRid")})
    return rows

async def main():
    a = sys.argv[1:]; once = "--once" in a; every = float(a[a.index("--every") + 1]) if "--every" in a else 5; secs = float(a[a.index("--secs") + 1]) if "--secs" in a else 60
    mx = int(a[a.index("--max-bots") + 1]) if "--max-bots" in a else 200
    lab = await Lab.open(); m = re.search(r"piPBotNextId\s*=\s*INT\s*(\d+)", await lab.run(f"show object {lab.prime}")); ids = range(1, min(int(m.group(1)) if m else 50, mx + 1))
    hist = collections.defaultdict(list); t_end = time.time() + secs
    while True:
        rows = await snapshot(lab, ids); flags = []
        print(f"--- {time.strftime('%H:%M:%S')}  {len(rows)} bots with a body"); print(f"{'bot':>4} {'body':>6} {'room':>5} {'row,col':>8} {'doing':<8} {'stuck':>5} {'hp':>6} {'world':>5} {'plan':<12} {'jrid':>5}")
        cnt = collections.Counter(); rooms = collections.Counter(); at = collections.defaultdict(list)
        for r in rows:
            h = hist[r["bot"]]; h.append((r["rid"], r["row"], r["col"])); h[:] = h[-4:]
            cnt[DOING.get(r["doing"], r["doing"])] += 1; rooms[r["rid"]] += 1; at[(r["rid"], r["row"], r["col"])].append(r["bot"])
            print(f"{r['bot']:>4} {r['body']:>6} {r['rid']:>5} {str(r['row']) + ',' + str(r['col']):>8} {str(DOING.get(r['doing'], r['doing'])):<8} {r['stuck']:>5} {r['hp']:>6} {int(r['inworld']):>5} {PATH_STATE.get(r['plan'], r['plan']) if r['plan'] else '':<12} {r['jrid'] or '':>5}")
            if r["stuck"] > 0: flags.append(f"STUCK bot {r['bot']} (stuck {r['stuck']}) room {r['rid']} at {r['row']},{r['col']}")
            if r["plan"] in (3, 4) and len(h) >= 3 and len(set(h[-3:])) == 1 and r["doing"] in (3, 4, 6, 8, 11): flags.append(f"PLANNER bot {r['bot']} {PATH_STATE[r['plan']]} (and not moving for 3 refreshes) room {r['rid']} at {r['row']},{r['col']}")
            if r["inworld"] and not r["rid"]: flags.append(f"NOROOM bot {r['bot']} is in a room object but piNavRid is 0")
            if r["doing"] in (3, 4, 11) and len(h) >= 4 and len(set(h)) == 1: flags.append(f"NOMOVE bot {r['bot']} {DOING.get(r['doing'])} but on the same square for 4 refreshes: room {r['rid']} at {r['row']},{r['col']}")
        for k, v in at.items():
            if len(v) >= 3: flags.append(f"PILE bots {v} on the same square: room {k[0]} at {k[1]},{k[2]}")
        print("activities:", dict(cnt)); print("rooms:", dict(rooms.most_common(8)))
        print("FLAGS:" if flags else "no flags"); [print("  " + f) for f in flags]
        if once or time.time() >= t_end: break
        await asyncio.sleep(every)
    await lab.close()
if __name__ == "__main__": asyncio.run(main())
