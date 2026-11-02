#!/usr/bin/env python3
"""Follow ONE playerbot live and record its real trail (exact square + fine position, room, doing, stuck, goal node) every poll.
Reads only (admin 'show object' on the bot's body), so nothing in the game changes. Test server by default.
  PRIME_ADMIN_PORT=9998 $PRIME_WORK/admin-venv/bin/python claude_tools/botfollow.py BOT_ID [--secs 120] [--poll 0.4] [--room RID]
Writes docs/botfollow/bot<ID>_<unix time>.json = {"bot":ID, "samples":[[t, rid, row, col, fine_row, fine_col, doing, stuck, goal, phase], ...]}
Positions: row/col are 1-based squares, fine is 0..63 inside the square (FINENESS 64): x = (col-1) + fine_col/64 squares.
Draw it:  python3 claude_tools/roomview.py ROOM --trail docs/botfollow/<file>.json
Stops at --secs, or when --room is given and the bot has been in that room and left it. Prints a line when the room or doing changes or stuck rises."""
import argparse, asyncio, json, os, re, sys, time
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "prime_server", "scripts"))
import bot_scenarios as B
T = B.T

def num(txt, name):
    m = re.search(rf"\b{name}\s*=\s*(?:INT|OBJECT)\s+(-?\d+)", txt)
    return int(m.group(1)) if m else 0

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bot", type=int); ap.add_argument("--secs", type=int, default=120)
    ap.add_argument("--poll", type=float, default=0.4); ap.add_argument("--room", type=int)
    a = ap.parse_args()
    L = T.AdminLink(); await L.connect()
    out = await L.run("show instances primeclasses")
    prime = int(re.search(r"OBJECT\s+(\d+)", out).group(1))
    body = None; samples = []; t0 = time.time(); last = None; seen_room = False
    while time.time() - t0 < a.secs:
        if body is None:
            r = await L.run(f"send object {prime} PBotBodyOf id int {a.bot}")
            m = re.search(r": OBJECT (\d+)", r)
            if not m: await asyncio.sleep(2); continue
            body = int(m.group(1))
        t = await L.run(f"show object {body}")
        if "piRow" not in t: body = None; continue      # body gone (bot logged out / recreated)
        s = [round(time.time() - t0, 2), num(t, "piNavRid"), num(t, "piRow"), num(t, "piCol"), num(t, "piFine_row"), num(t, "piFine_col"),
             num(t, "piDoing"), num(t, "piStuck"), num(t, "piGoalNode"), num(t, "piPhase")]
        samples.append(s)
        key = (s[1], s[6], s[7] > 0)
        if key != last:
            print(f"[{s[0]:6.1f}s] room {s[1]} at {s[2]},{s[3]} {B.DOING.get(s[6], s[6])} stuck {s[7]} goal node {s[8]}", flush=True); last = key
        if a.room:
            if s[1] == a.room: seen_room = True
            elif seen_room: break
        await asyncio.sleep(a.poll)
    await L.close()
    d = os.path.join(ROOT, "docs", "botfollow"); os.makedirs(d, exist_ok=True)
    f = os.path.join(d, f"bot{a.bot}_{int(time.time())}.json")
    json.dump({"bot": a.bot, "samples": samples}, open(f, "w"))
    print(f"{len(samples)} samples -> {f}")
if __name__ == "__main__": asyncio.run(main())
