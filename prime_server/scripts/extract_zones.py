#!/usr/bin/env python3
"""Reads every room's SomethingMoved handler from the Kod and writes the ZONE exits (a step onto certain squares sends you to another room) to
prime_client/overlay/tools/prime/roomzones.json:  { "zones": { "marion.roo": [ { "to": "c4.roo", "when": "new_row < 32 && new_col > 66" } ] } }
`when` is a JS expression over new_row / new_col (Kod squares, 1-based) and ROWS / COLS (the room's size); fine_row / fine_col are taken as 32.
roomexits.json only holds a corner square of such a zone (marion: (31,67)), which can lie behind a hedge.   usage: extract_zones.py [kod object dir] [out json]"""
import json, os, re, sys
KOD = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/boxes/m59-box/src/prime_work/build/tree/kod/object")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../prime_client/overlay/tools/prime/roomzones.json")
txt = {}
for d, _, fs in os.walk(KOD):
    for f in fs:
        if f.endswith(".kod"): txt[os.path.join(d, f)] = re.sub(r"//[^\n]*", "", open(os.path.join(d, f), errors="replace").read())
rid2roo = {}
for t in txt.values():
    a = re.search(r"piRoom_num\s*=\s*(RID_\w+)", t, re.I); b = re.search(r"room_\w+\s*=\s*(\w+\.roo)", t, re.I)
    if a and b: rid2roo[a.group(1).upper()] = b.group(1).lower()
def block(t, at):
    i = t.index("{", at); depth = 0
    for j in range(i, len(t)):
        depth += (t[j] == "{") - (t[j] == "}")
        if depth == 0: return t[i + 1:j]
def js(cond):
    c = re.sub(r"\s+", " ", cond.lower())
    c = c.replace("send(self,@getroomrows)", "ROWS").replace("send(self,@getroomcols)", "COLS")
    c = re.sub(r"\bfine_(row|col)\b", "32", c)
    if re.search(r"[a-z_@]+\(", c.replace("(", " (").replace(" (", "(")) and re.search(r"\b[a-z_]+\(", re.sub(r"\(\s*(new|\d|rows|cols|\()", "( \\1", c)): pass
    for bad in ("what", "self", "isclass", "send"):
        if re.search(r"\b" + bad + r"\b", c): return None
    c = re.sub(r"\band\b", "&&", c); c = re.sub(r"\bor\b", "||", c); c = re.sub(r"\bnot\b", "!", c)
    c = c.replace("<>", "!=="); c = re.sub(r"(?<![<>!=])=(?!=)", "===", c)
    return c.replace("new_row", "new_row").strip()
zones, notes = {}, []
for f, t in txt.items():
    mroo = re.search(r"room_\w+\s*=\s*(\w+\.roo)", t, re.I); m = re.search(r"\n\s*SomethingMoved\s*\(", t)
    if not mroo or not m or "UtilGoNearSquare" not in t[m.start():]: continue
    src = mroo.group(1).lower(); b = block(t, m.start())
    for im in re.finditer(r"\bif\s*(.*?)\s*\{", b, re.I | re.S):
        cond = im.group(1).strip(); blk = block(b, im.end() - 1)
        if "UtilGoNearSquare" not in blk or re.search(r"\bif\b[^{]*\{", blk, re.I): continue   # innermost blocks only
        dm = re.search(r"#num\s*=\s*(RID_\w+)", blk, re.I)
        if not dm: notes.append(f"{src}: no RID destination in the block for: {cond[:70]!r}"); continue
        to = rid2roo.get(dm.group(1).upper()); w = js(cond)
        if not to: notes.append(f"{src}: unknown destination {dm.group(1)}"); continue
        if not w: notes.append(f"{src}: condition not understood: {cond[:70]!r}"); continue
        z = zones.setdefault(src, [])
        if not any(x["to"] == to and x["when"] == w for x in z): z.append({"to": to, "when": w})
json.dump({"_note": "made by prime_server/scripts/extract_zones.py from the Kod", "zones": zones, "notes": notes}, open(OUT, "w"), indent=1)
print(sum(len(v) for v in zones.values()), "zone exits in", len(zones), "rooms;", len(notes), "notes ->", os.path.relpath(OUT))
for n in notes: print("  ", n)
