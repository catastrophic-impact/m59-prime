#!/usr/bin/env python3
"""botlab: the shared library of the bot debug tools (admin access + decoding). Import it, do not run it.
Everything reads through the admin port ('show object', 'show list', 'send object'), so nothing here changes the game unless a tool says so.
  lab = await Lab.open()                 connects (PRIME_ADMIN_PORT, default 9998 = the test server) and finds the PrimeClasses object
  await lab.props(obj)                   {name: 'INT 5' | 'OBJECT 3' | 'LIST 17' | '$ 0' ...} plus '_class'
  await lab.num(obj, 'piRow')            one integer property (0 when absent)
  await lab.list(listid)                 a list decoded to python (nested lists, ints; objects as ('OBJ', id), '$' as None)
  await lab.body(bot_id)                 the body object of a bot id
  await lab.room_map()                   {roomdata id (as in the C log lines): piRoom_num}
  await lab.room_things(room_obj)        everything standing in a room: [{obj, class, kind, row, col, fr, fc, angle, hp}]
Positions: row/col are 1-based squares, fine 0..63 inside the square (FINENESS 64); rows grow SOUTH, cols grow EAST."""
import asyncio, os, re, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "prime_server", "scripts"))
import bot_scenarios as B

DOING = B.DOING
PATH_STATE = {0: "not walking", 1: "walking", 2: "arrived", 3: "no way", 4: "stuck", 5: "stopped next to the goal", 6: "fighting a blocker", 7: "fled (rescue)"}

class Lab:
    @classmethod
    async def open(cls):
        self = cls(); self.L = B.T.AdminLink(); await self.L.connect()
        self.prime = int(re.search(r"OBJECT\s+(\d+)", await self.L.run("show instances primeclasses")).group(1))
        self._cls = {}
        return self
    @classmethod
    def on(cls, link, prime):
        """a Lab around an admin link you already have"""
        self = cls(); self.L = link; self.prime = prime; self._cls = {}; return self
    async def close(self): await self.L.close()
    async def run(self, cmd): return await self.L.run(cmd)

    async def props(self, obj):
        t = await self.L.run(f"show object {obj}"); d = {}
        m = re.search(r"is CLASS (\w+)", t); d["_class"] = m.group(1) if m else "?"
        for k, v in re.findall(r"^: (\w+)\s*=\s*(.+?)\s*$", t, re.M): d[k] = v
        return d
    async def num(self, obj, name):
        m = re.search(rf"\b{name}\s*=\s*(?:INT|OBJECT)\s+(-?\d+)", await self.L.run(f"show object {obj}")); return int(m.group(1)) if m else 0

    async def list(self, lid):
        body = await self.L.run(f"show list {lid}"); toks = re.findall(r"^: (.+?)\s*$", body, re.M)
        pos = [0]
        def parse():
            out = []
            while pos[0] < len(toks):
                t = toks[pos[0]]; pos[0] += 1
                if t == "[": out.append(parse())
                elif t.startswith("]"): return out
                else:
                    m = re.match(r"(INT|OBJECT|LIST|CLASS|RESOURCE|DEBUGSTR|\$|STRING|TEMPSTRING|NIL)\s*(.*)", t)
                    kind, val = (m.group(1), m.group(2)) if m else ("?", t)
                    out.append(int(val) if kind == "INT" and re.fullmatch(r"-?\d+", val) else ("OBJ", int(val)) if kind == "OBJECT" and val.isdigit() else None if kind == "$" else (kind, val))
            return out
        r = parse(); return r[0] if r else []
    async def body(self, bot):
        m = re.search(r"^: OBJECT (\d+)", await self.L.run(f"send object {self.prime} PBotBodyOf id int {bot}"), re.M); return int(m.group(1)) if m else None

    async def room_things(self, room_obj):
        pr = await self.props(room_obj); m = re.search(r"LIST (\d+)", pr.get("plActive", ""))
        if not m: return []
        out = []
        for e in await self.list(int(m.group(1))):
            if not (isinstance(e, list) and len(e) >= 6 and isinstance(e[0], tuple)): continue
            o = e[0][1]
            if o not in self._cls:
                p = await self.props(o); c = p["_class"]
                kind = "bot" if c == "PlayerBot" else "user" if c in ("User", "Admin", "DM", "Dadmin") else "mob" if "poBrain" in p and re.search(r"OBJECT [1-9]", p.get("poBrain", "")) else "other"
                self._cls[o] = (c, kind, int(re.search(r"-?\d+", p.get("piHit_points", "0")).group(0)) if "piHit_points" in p else 0)
            c, kind, hp = self._cls[o]
            out.append({"obj": o, "class": c, "kind": kind, "angle": e[1], "row": e[2], "col": e[3], "fr": e[4], "fc": e[5], "hp": hp})
        return out

    async def room_map(self):
        """{roomdata id: nav room id (piRoom_num)} of every room on this server. The server's C log lines ('BSPFindPathStep GRID-NOWAY: room N ...') number rooms by
        roomdata id (a counter assigned at load: it changes with every server start), the Kod and the nav data by piRoom_num. ~0.05 s per room: cache the result."""
        if getattr(self, "_rm", None): return self._rm
        t = await self.L.run("show instances room"); out = {}
        for o in re.findall(r"OBJECT (\d+)", t):
            tx = await self.L.run(f"show object {o}")
            d = re.search(r"prmRoom\s*=\s*ROOM_DATA\s+(\d+)", tx); n = re.search(r"piRoom_num\s*=\s*INT\s+(\d+)", tx)
            if d and n: out[int(d.group(1))] = int(n.group(1))
        self._rm = out; return out

    async def explain_stuck(self, body, near=2.0):
        """What is around a bot that does not get on: [{kind, class, obj, dist, hp}] of every body within `near` squares (nearest first), plus the planner's refused step.
        A mob/bot there is the usual reason for a refused step (the server's move check treats bodies as blockers)."""
        import math
        p = await self.props(body); g = lambda n: int(re.search(r"-?\d+", p.get(n, "0")).group(0))
        mo = re.search(r"OBJECT (\d+)", p.get("poOwner", ""))
        if not mo: return {"near": [], "refused": None}
        me = ((g("piRow") - 1) + g("piFine_row") / 64.0, (g("piCol") - 1) + g("piFine_col") / 64.0); out = []
        for t in await self.room_things(int(mo.group(1))):
            if t["obj"] == body: continue
            d = math.hypot((t["row"] - 1) + t["fr"] / 64.0 - me[0], (t["col"] - 1) + t["fc"] / 64.0 - me[1])
            if d <= near: out.append({"kind": t["kind"], "class": t["class"], "obj": t["obj"], "dist": round(d, 2), "hp": t["hp"]})
        out.sort(key=lambda t: t["dist"]); ref = None
        m = re.search(r"LIST (\d+)", p.get("plPathDbg", ""))
        if m:
            d = await self.list(int(m.group(1)))
            if len(d) >= 7: ref = {"from": [d[0] // 64, d[1] // 64], "to": [d[2] // 64, d[3] // 64], "check": d[6]}
        return {"near": out, "refused": ref}

_DSTR = {}
def debug_strings(cls="playerbot", anchor=b"stop moving: was phase"):
    """The class's debug-string table (what the admin shows as 'DEBUGSTR n'), read from its compiled .bof: id n = the n-th string of the table.
    The table is the run of printable nul-separated strings around `anchor` (any string known to be in it); the run starts with 1-3 empty entries (the NULs of the integer before the table), then id 0.
    (Do NOT hardcode the anchor's id: adding a message or a docstring above it shifts every id.)  Re-read after every Kod compile: call with a fresh process."""
    if cls in _DSTR: return _DSTR[cls]
    W = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
    path = os.path.join(W, "build", "tree", "run", "server", "loadkod", cls + ".bof")
    b = open(path, "rb").read(); i = b.find(anchor); j = i
    while j > 0 and (b[j - 1] == 0 or 32 <= b[j - 1] < 127): j -= 1
    parts = b[j:].split(b"\0")
    lead = next((n for n, p in enumerate(parts) if p), 0)      # the leading NULs belong to the 4-byte integer before the table (1, 2 or 3 of them depending on that integer): id 0 is the first string
    assert 1 <= lead <= 3, "unexpected string table layout"
    _DSTR[cls] = {n - lead: p.decode("latin-1") for n, p in enumerate(parts) if n >= lead}
    return _DSTR[cls]
