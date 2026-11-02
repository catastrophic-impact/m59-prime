#!/usr/bin/env python3
"""Draw a map of a room from what the client nav grid and the bake know, as a PNG (pure python, no libraries):
dark = no floor, coloured = floor (green = the largest connected area, other colours = other areas a bot cannot walk to from it), black lines = walls,
red squares = baked nodes, yellow lines = baked routes, blue squares = doors.   Usage: roommap.py RID [RID ...] | --all     Output: docs/roommaps/<rid>_<roo>.png
Needs: $PRIME_WORK/navtmp/roomdump/<roo>.json (node tools/prime/navdump.ts) and navtmp/navbake.json."""
import json, os, struct, sys, zlib
W = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "roommaps")
S = 10
PAL = {".": (28, 28, 32), "1": (96, 150, 96), "2": (150, 120, 70), "3": (110, 110, 170), "4": (160, 90, 140), "5": (90, 150, 160), "6": (170, 160, 80), "7": (150, 90, 90), "8": (120, 170, 120), "9": (130, 130, 130), "+": (120, 120, 120)}
def png(path, w, h, px):
    raw = b"".join(b"\0" + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    def ch(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))
def render(g, dump):
    rows, cols = dump["rows"], dump["cols"]; w, h = cols * S, rows * S
    px = bytearray(w * h * 3)
    def put(x, y, c):
        if 0 <= x < w and 0 <= y < h: i = (y * w + x) * 3; px[i:i + 3] = bytes(c)
    def line(x0, y0, x1, y1, c, th=0):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), -abs(y1 - y0); sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1; e = dx + dy
        while True:
            for a in range(-th, th + 1):
                for b in range(-th, th + 1): put(x0 + a, y0 + b, c)
            if x0 == x1 and y0 == y1: break
            e2 = 2 * e
            if e2 >= dy: e += dy; x0 += sx
            if e2 <= dx: e += dx; y0 += sy
    for r, rowtxt in enumerate(dump["areas"]):
        for c, ch in enumerate(rowtxt):
            col = PAL.get(ch, (120, 120, 120))
            for y in range(r * S, r * S + S):
                for x in range(c * S, c * S + S): put(x, y, col)
    for x0, y0, x1, y1 in dump["walls"]: line(x0 * S, y0 * S, x1 * S, y1 * S, (0, 0, 0))
    ctr = lambda row, col: ((col - 0.5) * S, (row - 0.5) * S)
    if g:
        for i, a in enumerate(g["adj"]):
            for e in a:
                if e["to"] < i: continue
                pts = [ctr(g["nodes"][i]["row"], g["nodes"][i]["col"])] + [ctr(v["row"] + (v.get("fr", 32) - 32) / 64, v["col"] + (v.get("fc", 32) - 32) / 64) for v in e["via"]] + [ctr(g["nodes"][e["to"]]["row"], g["nodes"][e["to"]]["col"])]
                for p, q in zip(pts, pts[1:]): line(p[0], p[1], q[0], q[1], (240, 220, 60))
        for d in g["doors"]:
            x, y = ctr(d["row"], d["col"])
            for a in range(-3, 4):
                for b in range(-3, 4): put(int(x) + a, int(y) + b, (60, 120, 255))
        for n in g["nodes"]:
            x, y = ctr(n["row"], n["col"])
            for a in range(-2, 3):
                for b in range(-2, 3): put(int(x) + a, int(y) + b, (255, 40, 40))
    return w, h, px
def main():
    bake = {x["rid"]: x for x in json.load(open(os.path.join(W, "navtmp", "navbake.json")))}
    rids = sys.argv[1:]
    if rids == ["--all"]: rids = sorted(bake)
    os.makedirs(OUT, exist_ok=True)
    for rid in map(int, rids):
        g = bake.get(rid)
        if not g: print("no bake for", rid); continue
        f = os.path.join(W, "navtmp", "roomdump", g["roo"] + ".json")
        if not os.path.exists(f): print("no dump for", g["roo"]); continue
        w, h, px = render(g, json.load(open(f)))
        png(os.path.join(OUT, f"{rid}_{g['roo']}.png"), w, h, px)
        print(f"{rid} {g['roo']}: {w}x{h}", flush=True)
main()
