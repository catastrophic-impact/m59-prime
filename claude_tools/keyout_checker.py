#!/usr/bin/env python3
"""Make a fake-transparent JPEG (a checkerboard painted into the picture) really transparent. Pure Python (ffmpeg decodes the JPEG, zlib/struct write the PNG): no image library needed.
  python3 claude_tools/keyout_checker.py IN.jpg OUT.png [--feather 70] [--original ORIG.jpg]
METHOD: the checkerboard is a regular pattern, so it is MODELLED, not guessed: the two tones and the cell size/phase are measured in the top-left corner (which is all background); then the colour the checkerboard
would have at every pixel is predicted. The prediction is only used to un-mix glows. A pixel is background when it is neutral grey in the range of the two tones AND the window around it alternates (high local variance: a real checkerboard, not the flat grey of a plaque), grown through connected grey pixels: that
removes the checkerboard everywhere, also between the figures, inside enclosed areas and along the cell borders. Pixels next to removed background get a soft alpha (colour-to-alpha against
the predicted background colour, --feather = the colour distance counted as fully opaque) and their colour is un-mixed from the background, so no grey halo is left.
TRIANGULATION (--original): where a graphic was blended onto the checkerboard (the casters' spell glows, the globe's glass) the true colour and transparency are solved from TWO known backgrounds: the same picture
with its real background (ORIG.jpg, same size). With checker colour E, original background Bg (estimated per region), blended pixel Cb and original pixel Co:  Cb = F*a + E*(1-a),  Co = F*a + Bg*(1-a)
  => 1-a = (Cb-Co).(E-Bg)/|E-Bg|^2 and F = (Co-(1-a)*Bg)/a.  Region: the GLOW boxes (all pixels). The GLASS circle (the globe): the original tells the dark glass fill (transparent) from the bright gold bars (kept in their true colour from the original).
Needs the top-left 100x100 pixels, row 8 and column 8 to be pure checkerboard."""
import struct, subprocess, sys, zlib

def main():
    a = sys.argv[1:]; src, dst = a[0], a[1]; arg = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    feather = arg("--feather", 70); orig_path = a[a.index("--original") + 1] if "--original" in a else None
    w, h = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", src], capture_output=True, text=True).stdout.strip().split("x"))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout; assert len(raw) == w * h * 3
    lum = lambda x, y: (raw[3 * (y * w + x)] + raw[3 * (y * w + x) + 1] + raw[3 * (y * w + x) + 2]) // 3
    # the two tones of the corner and the cell size / phase
    vals = sorted(lum(x, y) for y in range(100) for x in range(100)); mid = (vals[len(vals) // 10] + vals[-len(vals) // 10]) // 2
    dark = [(x, y) for y in range(100) for x in range(100) if lum(x, y) < mid]; light = [(x, y) for y in range(100) for x in range(100) if lum(x, y) >= mid]
    def tone(pts):
        ch = [[], [], []]
        for x, y in pts:
            i = 3 * (y * w + x); [ch[k].append(raw[i + k]) for k in range(3)]
        return tuple(sorted(c)[len(c) // 2] for c in ch)
    T = (tone(dark), tone(light))
    def edges(line):      # positions where the tone class changes along a line
        cls = [1 if v >= mid else 0 for v in line]; return [i for i in range(1, len(cls)) if cls[i] != cls[i - 1]]
    # the cell size is not a whole number (the picture was scaled): fit it on the whole of a row and a column that are background (row 8, column 8)
    ex = edges([lum(x, 8) for x in range(w)]); ey = edges([lum(8, y) for y in range(h)])
    fit = lambda e: ((e[-1] - e[0]) / (len(e) - 1), e[0])
    (cx, fx), (cy, fy) = fit(ex), fit(ey); cell = (cx + cy) / 2; ox, oy = fx % cell, fy % cell
    par0 = 1 if lum(2, 2) >= mid else 0      # tone class of the pixel (2, 2)
    k0 = (int((2 - ox) // cell) + int((2 - oy) // cell)) & 1
    def expected(x, y):
        k = (int((x - ox) // cell) + int((y - oy) // cell)) & 1; return T[par0 ^ k0 ^ k]
    print(f"{w}x{h}: tones {T}, cell {cell:.3f}px, phase ({ox:.2f},{oy:.2f})")
    # CLOSE = neutral grey inside the range of the two tones (the checkerboard, its anti-aliased cell borders, JPEG noise). The prediction above is NOT used here: across the picture it drifts by a pixel or two.
    lo_t, hi_t = min(T[0][0], T[1][0]) - 14, max(T[0][0], T[1][0]) + 14
    close = bytearray(w * h)
    for i in range(w * h):
        r, g, b = raw[3 * i], raw[3 * i + 1], raw[3 * i + 2]
        if max(r, g, b) - min(r, g, b) <= 16 and lo_t <= (r + g + b) // 3 <= hi_t: close[i] = 1
    # CORE = a window of about two cells is nearly all CLOSE and its brightness VARIES (a real checkerboard alternates two tones; the flat grey of a plaque or a stone does not vary)
    rad = int(cell * 0.9); W1 = w + 1
    ic = [0] * (W1 * (h + 1)); il = [0] * (W1 * (h + 1)); iq = [0] * (W1 * (h + 1))
    for y in range(h):
        rc = rl = rq = 0
        for x in range(w):
            i = y * w + x; v = (raw[3 * i] + raw[3 * i + 1] + raw[3 * i + 2]) // 3 if close[i] else 0
            rc += close[i]; rl += v; rq += v * v; k = (y + 1) * W1 + x + 1
            ic[k] = ic[k - W1] + rc; il[k] = il[k - W1] + rl; iq[k] = iq[k - W1] + rq
    def box(t, x0, y0, x1, y1): return t[y1 * W1 + x1] - t[y0 * W1 + x1] - t[y1 * W1 + x0] + t[y0 * W1 + x0]
    bg = bytearray(w * h); stack = []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            i = y * w + x
            if not close[i]: continue
            x0, x1, y0, y1 = max(0, x - rad), min(w, x + rad + 1), max(0, y - rad), min(h, y + rad + 1); area = (x1 - x0) * (y1 - y0)
            n = box(ic, x0, y0, x1, y1)
            if n / area < 0.80 or n < 60: continue
            m = box(il, x0, y0, x1, y1) / n; var = box(iq, x0, y0, x1, y1) / n - m * m
            if var >= 150: bg[i] = 1; stack.append(i)      # standard deviation of about 12 or more: two tones alternate
    while stack:
        i = stack.pop(); x, y = i % w, i // w
        for j, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, y > 0), (i + w, y < h - 1), (i - w - 1, x > 0 and y > 0), (i - w + 1, x < w - 1 and y > 0), (i + w - 1, x > 0 and y < h - 1), (i + w + 1, x < w - 1 and y < h - 1)):
            if ok and close[j] and not bg[j]: bg[j] = 1; stack.append(j)
    GLOW = [(270, 105, 46), (808, 75, 50)]      # the two casters' spell graphics (cx, cy, radius): the checkerboard shows through them
    GLASS = (512, 268, 120)                                # the globe's glass (cx, cy, radius)
    in_glow = lambda x, y: any((x - cx) ** 2 + (y - cy) ** 2 <= r * r for cx, cy, r in GLOW)
    in_arch = lambda x, y: 195 <= y <= 352 and abs(x - 512) <= 48 + min(max(y - 195, 0), 55) * 0.35 + 2      # the stone arch in the middle of the globe keeps its own pixels
    in_glass = lambda x, y: (x - GLASS[0]) ** 2 + (y - GLASS[1]) ** 2 <= GLASS[2] ** 2
    # POCKETS: small enclosed areas of checkerboard (the gaps between a ring and its wings) are too small for the window test above: a connected area of CLOSE pixels that is not background yet and whose
    # brightness alternates between two tones (a high variance) is background; the flat grey of a plaque or a stone has a low variance and stays.
    seen = bytearray(w * h)
    for start in range(w * h):
        if not close[start] or bg[start] or seen[start]: continue
        comp = [start]; seen[start] = 1; k = 0; sl = sq = 0
        while k < len(comp):
            i = comp[k]; k += 1; v = (raw[3 * i] + raw[3 * i + 1] + raw[3 * i + 2]) // 3; sl += v; sq += v * v; x, y = i % w, i // w
            for j, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, y > 0), (i + w, y < h - 1)):
                if ok and close[j] and not bg[j] and not seen[j]: seen[j] = 1; comp.append(j)
        n = len(comp)
        if n >= 60 and sq / n - (sl / n) ** 2 >= 400:
            for i in comp: bg[i] = 1
    # soft edge: pixels within 2 px of a removed pixel are un-mixed from the predicted background colour
    near = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if bg[y * w + x]: continue
            for dy in (-2, -1, 0, 1, 2):
                yy = y + dy
                if 0 <= yy < h and any(0 <= x + dx < w and bg[yy * w + x + dx] for dx in (-2, -1, 0, 1, 2)): near[y * w + x] = 1; break
    orig = bytearray(subprocess.run(["ffmpeg", "-v", "error", "-i", orig_path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout) if orig_path else None
    if orig: assert len(orig) == len(raw), "the original must have the same size"
    def region_bg(test):      # the original's background colour in a region: the median of its darker pixels
        pts = [(orig[3 * (y * w + x)], orig[3 * (y * w + x) + 1], orig[3 * (y * w + x) + 2]) for y in range(0, h, 3) for x in range(0, w, 3) if test(x, y)]
        pts = sorted([p for p in pts if sum(p) < 330], key=sum); pts = pts[:max(1, len(pts) // 2)]
        return tuple(sorted(c[k] for c in pts)[len(pts) // 2] for k in range(3))
    BG_GLOW = region_bg(in_glow) if orig else None
    def triangulate(x, y, bgc):
        i = 3 * (y * w + x); e = expected(x, y); cb = (raw[i], raw[i + 1], raw[i + 2]); co = (orig[i], orig[i + 1], orig[i + 2])
        d = [e[k] - bgc[k] for k in range(3)]; den = sum(v * v for v in d) or 1
        t = min(1.0, max(0.0, sum((cb[k] - co[k]) * d[k] for k in range(3)) / den)); al = 1.0 - t
        al = (al - 0.40) / 0.60      # the faint low-confidence haze (the original's background is only estimated) is cut, the solid glow rescaled
        if al < 0.04: return (0, 0, 0, 0)
        if al > 0.96: return (co[0], co[1], co[2], 255)
        return tuple(max(0, min(255, round((co[k] - t * bgc[k]) / al))) for k in range(3)) + (round(al * 255),)
    out = bytearray(); n_bg = n_soft = 0
    for y in range(h):
        out.append(0)
        for x in range(w):
            i = y * w + x
            if orig and in_glow(x, y): out += bytes(triangulate(x, y, BG_GLOW)); continue
            if orig and in_glass(x, y) and not in_arch(x, y):
                # the glass fill is dark in the ORIGINAL (the gold bars are bright): dark = transparent, bright = the bar in its true colour (the _b file has the checkerboard tinted into them)
                co = orig[3 * i:3 * i + 3]; lo_o = (co[0] + co[1] + co[2]) // 3; al = min(1.0, max(0.0, (lo_o - 60) / 70.0))
                out += bytes((co[0], co[1], co[2], round(al * 255))) if al > 0.04 else b"\x00\x00\x00\x00"; continue
            if bg[i]: out += b"\x00\x00\x00\x00"; n_bg += 1; continue
            r, g, b = raw[3 * i], raw[3 * i + 1], raw[3 * i + 2]
            if near[i]:
                e = expected(x, y); al = min(1.0, max(0.0, max(abs(r - e[0]), abs(g - e[1]), abs(b - e[2])) / feather))
                if al < 1.0:
                    al = max(al, 0.12); n_soft += 1
                    r, g, b = (max(0, min(255, round((c - (1 - al) * ev) / al))) for c, ev in zip((r, g, b), e)); out += bytes((r, g, b, round(al * 255))); continue
            out += bytes((r, g, b, 255))
    def chunk(t, d): c = struct.pack(">I", len(d)) + t + d; return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(dst, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(out), 9)) + chunk(b"IEND", b""))
    print(f"{n_bg} background pixels ({100 * n_bg // (w * h)}%) transparent, {n_soft} soft edge pixels -> {dst}")

if __name__ == "__main__": main()
