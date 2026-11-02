#!/usr/bin/env python3
"""botperf: PERFORMANCE OF THE BOTS. Steps the bot count through a few sizes on the TEST server and measures, for each size, what the server pays for them:
  CPU of the blakserv process over a window (percent of one core), the answer time of an admin command (how late the game loop is), the longest top-level message the server saw (show status),
  the bodies that exist, the list nodes in use (show memory) and the process memory. Then fits cost per bot and says what 100 or more would cost.
TEST SERVER ONLY (it changes piPlayerBotCount):  PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2 python3 claude_tools/botperf.py [--sizes 10,30,60,100] [--settle 90] [--window 60]
Run it in the background (it takes about (settle + window) x sizes seconds); output goes to stdout."""
import argparse, os, re, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADM = os.path.join(ROOT, "prime_server", "scripts", "admin_prime.py")
W = os.path.expanduser("~/boxes/m59-box/src/prime_work")
SERVER = os.environ.get("PRIME_SERVER_DIR", "server2")

def adm(c, t=90):
    t0 = time.time(); out = subprocess.run([sys.executable, ADM, c], capture_output=True, text=True, timeout=t).stdout; return out, time.time() - t0

def pid():
    out = subprocess.run(["flatpak-spawn", "--host", "sh", "-c", 'for p in $(pgrep -x blakserv); do [ "$(readlink /proc/$p/cwd)" = "%s" ] && echo $p; done' % os.path.join(W, "build", SERVER)], capture_output=True, text=True).stdout.split()
    return int(out[0])

def cpu_ticks(p):
    s = subprocess.run(["flatpak-spawn", "--host", "cat", f"/proc/{p}/stat"], capture_output=True, text=True).stdout.rsplit(")", 1)[1].split()
    return int(s[11]) + int(s[12]), int(s[21]) * 4096      # utime + stime (ticks), rss bytes

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--sizes", default="10,30,60,100"); ap.add_argument("--settle", type=int, default=90); ap.add_argument("--window", type=int, default=60)
    a = ap.parse_args(); p = pid(); hz = os.sysconf("SC_CLK_TCK")
    out, _ = adm("show instances primeclasses"); prime = re.search(r"OBJECT (\d+)", out).group(1)
    rows = []
    print(f"server pid {p}; sizes {a.sizes}; settle {a.settle}s, window {a.window}s", flush=True)
    for n in [int(x) for x in a.sizes.split(",")]:
        adm(f"set object {prime} piPlayerBotCount int {n}")
        time.sleep(a.settle)
        # bodies that exist
        bodies = len(re.findall(r"OBJECT \d+", adm("show instances playerbot")[0]))
        c0, _ = cpu_ticks(p); t0 = time.time(); lat = []
        while time.time() - t0 < a.window:
            lat.append(adm("show status")[1]); time.sleep(5)
        c1, rss = cpu_ticks(p); dt = time.time() - t0
        cpu = (c1 - c0) / hz / dt * 100
        st = adm("show status")[0]; m = re.search(r"Longest time on one top level message is (\d+) milliseconds", st); longest = int(m.group(1)) if m else -1
        mem = adm("show memory")[0]; ln = re.search(r"List\D+(\d+)", mem); lists = int(ln.group(1)) if ln else -1
        rows.append((n, bodies, cpu, sum(lat) / len(lat), max(lat), longest, lists, rss / 1048576))
        print(f"bots {n:>4}  bodies {bodies:>4}  cpu {cpu:5.1f}% of a core  admin answer avg {rows[-1][3]:.2f}s max {rows[-1][4]:.2f}s  longest message {longest} ms  list nodes {lists}  rss {rows[-1][7]:.0f} MB", flush=True)
    base = rows[0]
    if len(rows) > 1:
        per = [(r[2] - base[2]) / max(1, r[1] - base[1]) for r in rows[1:]]
        print(f"\ncost per added bot: {sum(per) / len(per):.3f}% of a core (from the sizes above); at 100 bodies ~{base[2] + (100 - base[1]) * sum(per) / len(per):.1f}% of a core, at 200 ~{base[2] + (200 - base[1]) * sum(per) / len(per):.1f}%")

main()
