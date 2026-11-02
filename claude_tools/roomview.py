#!/usr/bin/env python3
"""ROOM VIEWER: one picture of a room with everything that decides whether a bot can walk there (pure python, no libraries).
Layers: floor height (dark blue = outside any sector, green..yellow = floor height low..high), walkable cells by the SERVER's own wall rules (cells with at least one open
link; a cell inside a sector but with no link is drawn dark red: blocked, usually inside a wall's margin), the region reachable from the start (cyan), the walls
(black = stops people, orange = stops people from one side only), solid objects (magenta), doors (blue), entrance squares where other rooms put you down (yellow, with the
source room printed), baked nodes (red), the planned path (white) and the start (white square) / goal (green square). Stdout gives the numbers.
Needs the grid dump of the server: touch dumpgrid.txt in the server folder, make the server build the room's grid (claude_tools/roomgrid.py ROOM does both), then:
  roomview.py ROOM [--start R,C] [--goal R,C] [--entrance N] [--nodes] [--trail botfollow.json] [--live snapshot.json] [--crop ROW,COL,HALF] [--scale PX] [--out file.png] [--server server2]
  --crop: only the window of HALF squares round ROW,COL (use with --scale 24..40 to look at one wall or neck)
  --live: a botinspect.py snapshot: things in the room (bots green, mobs orange, users white, other cyan-dark) with their number, the bot's route (yellow), the waypoint (pink) and the goal (green), the refused step (red X)
Without --start it uses the first entrance square (--entrance N picks another). Output default: docs/roomview/<rid>_<roo>.png"""
import heapq, json, math, os, struct, sys, zlib
W = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
HERE = os.path.dirname(os.path.abspath(__file__))

DIG = {"0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
       "6": "111100111101111", "7": "111001001001001", "8": "111101111101111", "9": "111101111001111"}
def png(path, w, h, px):
    raw = b"".join(b"\0" + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    def ch(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
def find_grid(server, roo):
    d = os.path.join(W, "build", server)
    for f in os.listdir(d):
        if f.lower() in (f"pathgrid_{roo}.bin".lower(), f"pathgrid_{roo}.roo.bin".lower()): return os.path.join(d, f)
    return os.path.join(d, f"pathgrid_{roo}.roo.bin")
DC = [1, 1, 0, -1, -1, -1, 0, 1]; DR = [0, 1, 1, 1, 0, -1, -1, -1]
def main():
    a = sys.argv[1:]
    def opt(name, default=None):
        if name in a: i = a.index(name); v = a[i + 1]; del a[i:i + 2]; return v
        return default
    server = opt("--server", "server2"); start = opt("--start"); goal = opt("--goal"); ent_i = int(opt("--entrance", "0")); out = opt("--out")
    trail = opt("--trail"); live = opt("--live"); crop = opt("--crop"); scale = opt("--scale")
    nodes_on = "--nodes" in a
    if nodes_on: a.remove("--nodes")
    rid = int(a[0])
    bake = {x["rid"]: x for x in json.load(open(os.path.join(W, "navtmp/navbake.json")))}
    r = bake[rid]; roo = r["roo"]
    dump = json.load(open(os.path.join(W, "navtmp/roomdump", roo + ".json")))
    gpath = find_grid(server, roo)
    if not os.path.exists(gpath): sys.exit(f"no grid dump {gpath}: run claude_tools/roomgrid.py {rid} first")
    b = open(gpath, "rb").read(); assert b[:4] == b"PGR1"
    ncols, nrows, cell = struct.unpack("<3i", b[4:16]); N = ncols * nrows
    links = b[16:16 + N]; hts = struct.unpack(f"<{N}f", b[16 + N:16 + N + 4 * N])
    objs = json.load(open(os.path.join(HERE, "..", "prime_client/overlay/tools/prime/navobjects.json"))).get(str(rid), [])
    ents = {}
    for o in bake.values():
        for d in o["doors"]:
            if d["destRid"] == rid: ents.setdefault((d["arrRow"], d["arrCol"]), []).append(o["roo"])
    entl = sorted(ents)
    S = int(scale) if scale else max(4, min(12, 1400 // max(r2["cols"] if False else dump["cols"], dump["rows"])))   # pixels per square
    PX = S / 1024.0
    Wd, Hd = int(dump["cols"] * S) + 1, int(dump["rows"] * S) + 1
    px = bytearray(Wd * Hd * 3)
    def put(x, y, c):
        if 0 <= x < Wd and 0 <= y < Hd: i = (y * Wd + x) * 3; px[i:i + 3] = bytes(c)
    def rect(x0, y0, x1, y1, c):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1): put(x, y, c)
    def line(x0, y0, x1, y1, c):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1); dx, dy = abs(x1 - x0), -abs(y1 - y0); sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1; e = dx + dy
        while True:
            put(x0, y0, c)
            if x0 == x1 and y0 == y1: break
            e2 = 2 * e
            if e2 >= dy: e += dy; x0 += sx
            if e2 <= dx: e += dx; y0 += sy
    valid = [h for h in hts if h == h]
    hmin, hmax = (min(valid), max(valid)) if valid else (0, 1)
    def hcol(h):
        t = 0 if hmax == hmin else (h - hmin) / (hmax - hmin)
        return (int(60 + 150 * t), int(120 + 80 * t), 70)
    # start / goal
    def sq_to_cell(row, col):   # square (1-based, centre) -> cell
        return min(nrows - 1, int((row - 0.5) * 1024 / cell)), min(ncols - 1, int((col - 0.5) * 1024 / cell))
    if start: sr, sc = map(int, start.split(","))
    elif entl: sr, sc = entl[min(ent_i, len(entl) - 1)]
    else: sr = sc = None
    reach = set()
    if sr is not None:
        r0, c0 = sq_to_cell(sr, sc); s0 = r0 * ncols + c0
        # start cell: itself or the nearest cell with a link within 2 cells
        best = None
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                rr, cc = r0 + dr, c0 + dc
                if 0 <= rr < nrows and 0 <= cc < ncols and links[rr * ncols + cc]:
                    d = dr * dr + dc * dc
                    if best is None or d < best[0]: best = (d, rr * ncols + cc)
        if best:
            stack = [best[1]]; reach.add(best[1])
            while stack:
                c = stack.pop(); m = links[c]; cr, cc = divmod(c, ncols)
                for d in range(8):
                    if m & (1 << d):
                        n = (cr + DR[d]) * ncols + cc + DC[d]
                        if n not in reach: reach.add(n); stack.append(n)
    # floor layer
    walk = sum(1 for m in links if m); inside = sum(1 for h in hts if h == h)
    for i in range(N):
        rr, cc = divmod(i, ncols); x0 = cc * cell * PX; y0 = rr * cell * PX; x1 = x0 + cell * PX; y1 = y0 + cell * PX
        if hts[i] != hts[i]: col = (14, 14, 40)
        elif not links[i]: col = (90, 30, 30)
        elif i in reach: col = (60, 200, 220)
        else: col = hcol(hts[i])
        rect(x0, y0, max(x0, x1 - 1), max(y0, y1 - 1), col)
    for w in dump["walls"]:
        c = (0, 0, 0) if (w[7] and w[8]) else (255, 150, 0)
        line(w[0] * S, w[1] * S, w[2] * S, w[3] * S, c)
    for x, y in objs: rect(x * PX - 2, y * PX - 2, x * PX + 2, y * PX + 2, (255, 0, 255))
    for d in r["doors"]: rect((d["col"] - 1) * S, (d["row"] - 1) * S, d["col"] * S - 1, d["row"] * S - 1, (60, 80, 255))
    for (er, ec) in entl: rect((ec - 1) * S, (er - 1) * S, ec * S - 1, er * S - 1, (255, 230, 0))
    if nodes_on:
        for n in r["nodes"]: rect((n["col"] - 0.5) * S - 2, (n["row"] - 0.5) * S - 2, (n["col"] - 0.5) * S + 2, (n["row"] - 0.5) * S + 2, (255, 40, 40))
    path_len = None
    if sr is not None and goal and reach:
        gr_, gc_ = map(int, goal.split(",")); gr0, gc0 = sq_to_cell(gr_, gc_)
        # A* over the links
        src = best[1]; gcell = gr0 * ncols + gc0
        gsc = (gr0 + 0.0, gc0 + 0.0)
        pq = [(0, src)]; g = {src: 0}; par = {src: None}; done = None
        while pq:
            f, c = heapq.heappop(pq)
            cr, cc = divmod(c, ncols)
            if abs(cr - gr0) <= 12 and abs(cc - gc0) <= 12: done = c; break
            m = links[c]
            for d in range(8):
                if m & (1 << d):
                    n = (cr + DR[d]) * ncols + cc + DC[d]; ng = g[c] + (1.414 if d & 1 else 1.0)
                    if ng < g.get(n, 1e30):
                        g[n] = ng; par[n] = c; heapq.heappush(pq, (ng + math.hypot(cr + DR[d] - gr0, cc + DC[d] - gc0), n))
        if done is not None:
            p = []; c = done
            while c is not None: p.append(c); c = par[c]
            p.reverse(); path_len = len(p)
            for i in range(len(p) - 1):
                (ar, ac), (br, bc) = divmod(p[i], ncols), divmod(p[i + 1], ncols)
                line((ac + 0.5) * cell * PX, (ar + 0.5) * cell * PX, (bc + 0.5) * cell * PX, (br + 0.5) * cell * PX, (255, 255, 255))
        rect((gc_ - 1) * S + 1, (gr_ - 1) * S + 1, gc_ * S - 2, gr_ * S - 2, (0, 255, 0))
    if trail:   # a botfollow.py recording: blue->green->yellow with time, stuck samples red, other rooms skipped, start white, end magenta
        smp = [x for x in json.load(open(trail))["samples"] if x[1] == rid]
        pts = [(((x[3] - 1) + x[5] / 64.0) * S, ((x[2] - 1) + x[4] / 64.0) * S, x[7]) for x in smp]
        for i in range(len(pts) - 1):
            f = i / max(1, len(pts) - 2); col = (int(255 * f), int(200 - 60 * f), int(255 * (1 - f)))
            if math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) < 6 * S: line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], col)
        for x, y, st in pts:
            if st: rect(x - 2, y - 2, x + 2, y + 2, (255, 0, 0))
        if pts:
            rect(pts[0][0] - 3, pts[0][1] - 3, pts[0][0] + 3, pts[0][1] + 3, (255, 255, 255)); rect(pts[-1][0] - 3, pts[-1][1] - 3, pts[-1][0] + 3, pts[-1][1] + 3, (255, 0, 255))
        print(f"  trail: {len(pts)} samples in this room, {sum(1 for p in pts if p[2])} while stuck")
    if live:   # botinspect snapshot
        sn = json.load(open(live)); P = lambda r, c, fr=32, fc=32: (((c - 1) + fc / 64.0) * S, ((r - 1) + fr / 64.0) * S)
        def label(x, y, txt, col):
            for ci, chh in enumerate(str(txt)):
                bits = DIG.get(chh)
                if bits:
                    for k, b in enumerate(bits):
                        if b == "1": rect(x + ci * 4 + (k % 3), y + (k // 3), x + ci * 4 + (k % 3), y + (k // 3), col)
        rt = sn.get("route") or []
        for i in range(len(rt) - 1):
            a1, b1 = P(*rt[i][:2], *(rt[i][2:4] if len(rt[i]) > 3 else (32, 32))), P(*rt[i + 1][:2], *(rt[i + 1][2:4] if len(rt[i + 1]) > 3 else (32, 32)))
            line(a1[0], a1[1], b1[0], b1[1], (255, 255, 0))
        for q in rt:
            x, y = P(*q[:2], *(q[2:4] if len(q) > 3 else (32, 32))); rect(x - 2, y - 2, x + 2, y + 2, (255, 255, 0))
        if sn.get("goal"): x, y = P(*sn["goal"]); rect(x - 4, y - 4, x + 4, y + 4, (0, 255, 0))
        if sn.get("wp"): x, y = P(*sn["wp"]); rect(x - 3, y - 3, x + 3, y + 3, (255, 120, 200))
        for t in sn.get("things", []):
            col = {"bot": (0, 255, 0), "mob": (255, 120, 0), "user": (255, 255, 255), "focus": (255, 0, 255)}.get(t["k"], (0, 120, 140))
            x, y = P(t["row"], t["col"], t.get("fr", 32), t.get("fc", 32)); r_ = 4 if t["k"] != "other" else 2
            rect(x - r_, y - r_, x + r_, y + r_, col); rect(x - r_ + 1, y - r_ + 1, x + r_ - 1, y + r_ - 1, (0, 0, 0) if t["k"] != "other" else col)
            if t.get("n") is not None: label(x + r_ + 1, y - 2, t["n"], col)
        if sn.get("wall"):   # the wall line that refused the step (roo units / 1024 = squares, x = col, y = row, 0-based)
            w = sn["wall"]; line(w[0] / 1024.0 * S, w[1] / 1024.0 * S, w[2] / 1024.0 * S, w[3] / 1024.0 * S, (255, 0, 0)); line(w[0] / 1024.0 * S + 1, w[1] / 1024.0 * S, w[2] / 1024.0 * S + 1, w[3] / 1024.0 * S, (255, 0, 0))
        if sn.get("refused"):
            x, y = P(*sn["refused"][:2], *(sn["refused"][2:4] if len(sn["refused"]) > 3 else (32, 32)))
            for k in range(-5, 6): put(int(x + k), int(y + k), (255, 0, 0)); put(int(x + k), int(y - k), (255, 0, 0))
    if sr is not None: rect((sc - 1) * S + 1, (sr - 1) * S + 1, sc * S - 2, sr * S - 2, (255, 255, 255))
    os.makedirs(os.path.join(HERE, "..", "docs", "roomview"), exist_ok=True)
    out = out or os.path.join(HERE, "..", "docs", "roomview", f"{rid}_{roo}.png")
    if crop:
        cr, cc, ch = map(int, crop.split(",")); x0 = max(0, int((cc - 1 - ch) * S)); x1 = min(Wd, int((cc + ch) * S)); y0 = max(0, int((cr - 1 - ch) * S)); y1 = min(Hd, int((cr + ch) * S))
        px = bytearray(b"".join(px[(y * Wd + x0) * 3:(y * Wd + x1) * 3] for y in range(y0, y1))); Wd, Hd = x1 - x0, y1 - y0
    png(out, Wd, Hd, px)
    print(f"room {rid} {r['name']} ({roo}): {dump['rows']} rows x {dump['cols']} cols, grid {ncols}x{nrows} cells of 1/{1024 // cell} square, {S} px per square")
    print(f"  cells inside the room's sectors: {inside}; walkable by the server's rules: {walk}; blocked inside the room: {inside - walk}; floor height {hmin:.0f}..{hmax:.0f}")
    print(f"  solid objects: {len(objs)}; doors: {len(r['doors'])}; entrances: " + ", ".join(f"{k} from {'/'.join(sorted(set(v)))}" for k, v in sorted(ents.items())[:10]))
    if sr is not None: print(f"  start {sr},{sc}: {len(reach)} cells reachable from it ({100.0 * len(reach) / max(1, walk):.1f}% of the walkable cells)" if reach else f"  start {sr},{sc}: NOT on a walkable cell (no link within 2 cells)")
    if goal: print(f"  goal {goal}: " + (f"path of {path_len} cells" if path_len else "no path"))
    print("  picture:", out)
if __name__ == "__main__": main()
