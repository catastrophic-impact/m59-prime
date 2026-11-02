#!/usr/bin/env python3
"""BOT FLIGHT RECORDER reader: the last 40 decisions of a bot (PlayerBot.Trace entries: stop moving, enter room, steps, route chosen, planner refusals, give-ups),
read over admin at once (the server's debug log is buffered for minutes).  The bot only records while the bot trace is on for it (this tool can switch it on).
  PRIME_ADMIN_PORT=9998 $PRIME_WORK/admin-venv/bin/python claude_tools/botevents.py BOT_ID [--on] [--off] [--watch SECS]
  --on     turn the trace on for this bot (rule piPBotTrace; it switches itself off after 3000 lines / 15 min)
  --off    turn the trace off
  --watch  keep printing new entries for SECS seconds (default: print the ring once)
Entries print as  [+secs] what a b c d e f  (+secs relative to the newest entry at the first read). Needs the Kod with PlayerBot.TraceRing (server2 build 2026-11-01)."""
import asyncio, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from botlab import Lab, debug_strings

async def ring(lab, body):
    out = await lab.run(f"send object {body} TraceRing")
    m = re.search(r"return from.*?: LIST (\d+)", out, re.S)
    if not m: return []
    r = await lab.list(int(m.group(1)))
    if len(r) < 2 or not isinstance(r[1], list): return []
    head, items = r[0], r[1]
    ordered = items[head:] + items[:head]       # oldest first
    return [e for e in ordered if isinstance(e, list) and len(e) >= 2]

DS = debug_strings()
def show(e):
    def v(x):
        if x is None: return ""
        if isinstance(x, tuple):
            m = re.fullmatch(r"(\d+)", str(x[1]).strip())
            if x[0] == "DEBUGSTR" and m: return DS.get(int(m.group(1)), "<str %s>" % m.group(1))
            return str(x[1]).strip('"')
        return str(x)
    return " ".join(x for x in (v(y) for y in e[1:]) if x)

async def main():
    a = sys.argv[1:]; bot = int(a[0]); lab = await Lab.open(); body = await lab.body(bot)
    if not body: sys.exit(f"bot {bot} has no body")
    if "--on" in a:
        await lab.run(f"set object {lab.prime} piPBotTraceEnd int 0"); await lab.run(f"set object {lab.prime} piPBotTrace int {bot}"); print(f"trace ON for bot {bot} (off after 3000 lines / 15 min)")
    if "--off" in a:
        await lab.run(f"set object {lab.prime} piPBotTrace int 0"); await lab.run(f"set object {lab.prime} piPBotTraceEnd int 0"); print("trace OFF"); await lab.close(); return
    secs = int(a[a.index("--watch") + 1]) if "--watch" in a else 0
    seen = set(); t_ref = None; t_end = time.time() + secs
    while True:
        es = await ring(lab, body)
        if not es and not secs: print("ring is empty: is the trace on for this bot? (--on)")
        for e in es:
            key = (e[0], show(e))
            if key in seen: continue
            seen.add(key); t_ref = t_ref if t_ref is not None else e[0]
            print(f"[{e[0] - t_ref:+5d}s] {show(e)}", flush=True)
        if time.time() >= t_end: break
        await asyncio.sleep(1.0)
    await lab.close()
if __name__ == "__main__": asyncio.run(main())
