#!/usr/bin/env python3
"""THE GAME'S OWN EXIT TABLES, exactly: every room's door exits and edge exits with the square a player LANDS on, read from the room Kod files (offline, read-only).
  python3 claude_tools/kodexits.py [--kod DIR] [--out docs/kod_exits.json] [ROOM_ID ..]
A room's Kod lists  plExits = Cons([ row, col, RID_DEST, arrRow, arrCol, ROTATE ], plExits)  (stepping on square row,col puts you at arrRow,arrCol of DEST) and
plEdge_Exits = Cons([ LEAVE_NORTH|SOUTH|EAST|WEST, RID_DEST, arrRow, arrCol, ROTATE ], ...) (walking off that side). Each door square has ITS OWN landing: a player never lands on 'the room's arrival square'.
(The baker used to guess one arrival per room pair and gave every door of Jasper the landing (52,35), a platform with no way out; the door at (44,32) lands on (51,35), which is fine.)
Output {rid: {"name", "doors": [[row, col, toRid, arrRow, arrCol]], "edges": [[side, toRid, arrRow, arrCol, [cond type, n] or []]] in the game's order (first match wins)}}; locked doors, scripted doors (no RID_ target) are skipped.
Without --out prints a summary; with ROOM_ID prints that room's tables."""
import json, os, re, sys
W = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
HERE = os.path.dirname(os.path.abspath(__file__))
SIDE = {"LEAVE_NORTH": "N", "LEAVE_SOUTH": "S", "LEAVE_EAST": "E", "LEAVE_WEST": "W"}

COND = {"ROW_IS_GREATER_THAN": 1, "ROW_IS_LESS_THAN": 2, "COL_IS_GREATER_THAN": 3, "COL_IS_LESS_THAN": 4, "NO_OTHER_CONDITIONS": 5}

def rid_constants(kod):
    c = {}
    for m in re.finditer(r"^\s*(RID_[A-Z0-9_]+)\s*=\s*(\d+)", open(os.path.join(kod, "include", "blakston.khd"), errors="replace").read(), re.M): c[m.group(1)] = int(m.group(2))
    return c

def parse(kod):
    rid = rid_constants(kod); out = {}
    for root, _, files in os.walk(os.path.join(kod, "object", "active", "holder", "room")):
        for f in files:
            if not f.endswith(".kod"): continue
            t = re.sub(r"//[^\n]*", "", open(os.path.join(root, f), errors="replace").read())     # commented-out exits are not exits
            m = re.search(r"piRoom_num\s*=\s*(RID_[A-Z0-9_]+)", t)
            if not m or m.group(1) not in rid: continue
            me = rid[m.group(1)]; doors = []; edges = []
            for e in re.finditer(r"plExits\s*=\s*Cons\(\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(RID_[A-Z0-9_]+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,", t):
                if e.group(3) in rid: doors.append([int(e.group(1)), int(e.group(2)), rid[e.group(3)], int(e.group(4)), int(e.group(5))])
            # an edge exit may carry a condition on the square the player walks off from (room.kod StandardLeaveDir): ROW_IS_GREATER_THAN n, ROW_IS_LESS_THAN n, COL_IS_GREATER_THAN n,
            # COL_IS_LESS_THAN n (1..4), or NO_OTHER_CONDITIONS (5: the exit taken when no other one of that side matches). No condition = [].
            for e in re.finditer(r"plEdge_[Ee]xits\s*=\s*Cons\(\[\s*(LEAVE_[A-Z]+)\s*,\s*(RID_[A-Z0-9_]+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*[A-Z0-9_]+\s*(?:,\s*([A-Z_]+)\s*(?:,\s*(\d+))?\s*)?\]", t):
                if e.group(1) in SIDE and e.group(2) in rid:
                    cond = [COND[e.group(5)], int(e.group(6) or 0)] if e.group(5) in COND else []
                    edges.append([SIDE[e.group(1)], rid[e.group(2)], int(e.group(3)), int(e.group(4)), cond])
            edges.reverse()     # the game's list order (every Cons puts the entry in front): the first exit of a side that matches wins
            out[me] = {"name": m.group(1)[4:], "doors": doors, "edges": edges}
    return out

def edge_taken(edges, side, row, col):
    """The room a player lands in when walking off `side` of the room at square (row, col), by the game's own rule (room.kod StandardLeaveDir): `edges` is a room's list from this
    module (the game's list order, first match wins; an exit with no condition always matches; NO_OTHER_CONDITIONS is used only when none matches). None when no exit applies."""
    fallback = None
    for e in edges:
        if e[0] != side: continue
        c = e[4] if len(e) > 4 else []
        if not c: return e[1]
        t, n = c
        if (t == 1 and row > n) or (t == 2 and row < n) or (t == 3 and col > n) or (t == 4 and col < n): return e[1]
        if t == 5: fallback = e[1]
    return fallback

def main():
    a = sys.argv[1:]; arg = lambda k, d: a[a.index(k) + 1] if k in a else d
    kod = arg("--kod", os.path.join(W, "build", "tree", "kod")); res = parse(kod); outp = arg("--out", None)
    if outp: json.dump(res, open(outp, "w"), indent=0); print(f"{len(res)} rooms, {sum(len(r['doors']) for r in res.values())} door exits, {sum(len(r['edges']) for r in res.values())} edge exits -> {outp}")
    ids = [int(x) for x in a if x.isdigit()]
    for i in ids:
        r = res.get(i)
        if not r: print(i, "not found"); continue
        print(i, r["name"]); [print("  door", d[:2], "->", d[2], "lands", d[3:]) for d in r["doors"]]; [print("  edge", e[0], "->", e[1], "lands", e[2:]) for e in r["edges"]]
    if not outp and not ids: print(f"{len(res)} rooms, {sum(len(r['doors']) for r in res.values())} door exits, {sum(len(r['edges']) for r in res.values())} edge exits")

if __name__ == "__main__": main()
