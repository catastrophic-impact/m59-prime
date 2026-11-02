#!/usr/bin/env python3
"""Chroma key: remove a flat green (or any flat colour) background from a logo and write a PNG with real transparency. Pure Python (ffmpeg decodes, zlib/struct write): no image library needed.
  python3 claude_tools/keyout_green.py IN.jpg OUT.png [--tol 40] [--glow X,Y,R ...] [--band 3]
METHOD
  1 the key colour G = the median of the picture's four corners;
  2 BACKGROUND = pixels within --tol of G (largest channel difference) that are connected to the picture's edge, plus ENCLOSED pockets of key colour (a gap between a ring and its wings) that are flat
    (low variance: the casters' green robe is shaded, so it is never taken for background);
  3 EDGE BAND (--band pixels next to the background): FOREGROUND MATTING. Each edge pixel takes the colour F of the nearest solid pixel and its transparency from how far the pixel lies from F towards the key
    colour (alpha = 1 - t, t = (C-F).(G-F)/|G-F|^2). The colour never comes from un-mixing against the key, so a dark edge cannot grow a coloured fringe, and no green is left.
  4 GLOWS (--glow X,Y,R circles: spell graphics blended onto the key colour): pixels brighter than the key get COLOUR-TO-ALPHA (the smallest opacity at which the pixel is a real colour mixed with G), so
    the glow keeps its colour and fades out softly.
Preview on a dark colour: ffmpeg -f lavfi -i color=c=0x7a3b1e:s=WxH -i OUT.png -filter_complex overlay -frames:v 1 preview.png"""
import struct, subprocess, sys, zlib

def main():
    a = sys.argv[1:]; src, dst = a[0], a[1]; arg = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    tol, band = arg("--tol", 40), arg("--band", 3)
    glows = [tuple(map(int, a[i + 1].split(","))) for i, x in enumerate(a) if x == "--glow"]
    w, h = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", src], capture_output=True, text=True).stdout.strip().split("x"))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout; assert len(raw) == w * h * 3
    corner = [tuple(raw[3 * (y * w + x):3 * (y * w + x) + 3]) for y in range(0, 40) for x in (*range(0, 40), *range(w - 40, w)) for _ in (0,)] + [tuple(raw[3 * (y * w + x):3 * (y * w + x) + 3]) for y in range(h - 40, h) for x in (*range(0, 40), *range(w - 40, w))]
    G = tuple(sorted(c[k] for c in corner)[len(corner) // 2] for k in range(3))
    print(f"{w}x{h}: key colour {G}")
    def d_of(i): return max(abs(raw[3 * i] - G[0]), abs(raw[3 * i + 1] - G[1]), abs(raw[3 * i + 2] - G[2]))
    near = bytearray(1 if d_of(i) <= tol else 0 for i in range(w * h)); bg = bytearray(w * h); stack = []
    for x in range(w):
        for y in (0, h - 1): stack.append(y * w + x)
    for y in range(h):
        for x in (0, w - 1): stack.append(y * w + x)
    while stack:
        i = stack.pop()
        if bg[i] or not near[i]: continue
        bg[i] = 1; x, y = i % w, i // w
        if x: stack.append(i - 1)
        if x < w - 1: stack.append(i + 1)
        if y: stack.append(i - w)
        if y < h - 1: stack.append(i + w)
    # enclosed POCKETS of key colour (gaps between a ring and its wings, between vines): seeds = strictly key-coloured connected areas that are not background yet; then the background grows 2 pixels through
    # near-key pixels (the pockets' anti-aliased rims)
    seen = bytearray(w * h)
    for s0 in range(w * h):
        if bg[s0] or seen[s0] or d_of(s0) > 14: continue
        comp = [s0]; seen[s0] = 1; k = 0
        while k < len(comp):
            i = comp[k]; k += 1; x, y = i % w, i // w
            for j, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, y > 0), (i + w, y < h - 1)):
                if ok and not bg[j] and not seen[j] and d_of(j) <= 14: seen[j] = 1; comp.append(j)
        if len(comp) >= 20:
            for i in comp: bg[i] = 1
    for _ in range(2):
        grow = [i for i in range(w * h) if not bg[i] and near[i] and any(0 <= i % w + dx < w and 0 <= i // w + dy < h and bg[i + dy * w + dx] for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
        for i in grow: bg[i] = 1
    in_glow = lambda x, y: any((x - cx) ** 2 + (y - cy) ** 2 <= r * r for cx, cy, r in glows)
    near_bg = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if bg[i]: continue
            for dy in range(-band, band + 1):
                yy = y + dy
                if 0 <= yy < h and any(0 <= x + dx < w and bg[yy * w + x + dx] for dx in range(-band, band + 1)): near_bg[i] = 1; break
    def colour_to_alpha(r, g, b):
        al = 0.0
        for c, k in zip((r, g, b), G):
            al = max(al, (c - k) / (255 - k) if c > k else (k - c) / k if k else 0.0)
        al = min(1.0, al)
        if al < 0.2: return (0, 0, 0, 0)      # below this the faint halo is mostly JPEG noise
        if al >= 0.97: return (r, g, b, 255)
        return tuple(max(0, min(255, round(k + (c - k) / al))) for c, k in zip((r, g, b), G)) + (round(al * 255),)
    solid = lambda i: not bg[i] and not near_bg[i]
    def matte(x, y):
        i = y * w + x; r, g, b = raw[3 * i], raw[3 * i + 1], raw[3 * i + 2]
        for rad in range(1, band + 5):      # the nearest solid pixel
            best = None
            for dy in range(-rad, rad + 1):
                for dx in range(-rad, rad + 1):
                    if max(abs(dx), abs(dy)) != rad: continue
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < w and 0 <= yy < h and solid(yy * w + xx):
                        d2 = dx * dx + dy * dy
                        if best is None or d2 < best[0]: best = (d2, yy * w + xx)
            if best: break
        if not best: return (r, g, b, 255)
        fi = best[1]; f = (raw[3 * fi], raw[3 * fi + 1], raw[3 * fi + 2]); v = [G[k] - f[k] for k in range(3)]; den = sum(c * c for c in v)
        if den < 900: return (f[0], f[1], f[2], 255)      # the solid colour is itself close to the key (a green robe): nothing to separate
        t = min(1.0, max(0.0, sum((c - f[k]) * v[k] for k, c in enumerate((r, g, b))) / den))
        if t < 0.12: return (r, g, b, 255)
        if t > 0.97: return (0, 0, 0, 0)
        return (f[0], f[1], f[2], round((1 - t) * 255))
    out = bytearray(); n_bg = n_soft = 0
    for y in range(h):
        out.append(0)
        for x in range(w):
            i = y * w + x; r, g, b = raw[3 * i], raw[3 * i + 1], raw[3 * i + 2]
            if in_glow(x, y) and not bg[i]:
                if r > b + 10 or (r + g + b) > sum(G) + 20:      # warm or bright: the glow itself
                    px = colour_to_alpha(r, g, b)
                    if px[3] < 255: n_soft += 1
                    out += bytes(px); continue
                if g >= r and g >= b and d_of(i) <= 70: out += b"\x00\x00\x00\x00"; n_bg += 1; continue      # the greenish rest of the halo
            if bg[i]: out += b"\x00\x00\x00\x00"; n_bg += 1; continue
            r, g, b = raw[3 * i], raw[3 * i + 1], raw[3 * i + 2]
            if near_bg[i]:
                px = matte(x, y)
                if px[3] < 255: n_soft += 1
                out += bytes(px); continue
            out += bytes((r, g, b, 255))
    def chunk(t, d): c = struct.pack(">I", len(d)) + t + d; return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(dst, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(out), 9)) + chunk(b"IEND", b""))
    print(f"{n_bg} background pixels ({100 * n_bg // (w * h)}%), {n_soft} soft pixels -> {dst}")

if __name__ == "__main__": main()
