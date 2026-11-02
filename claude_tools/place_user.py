#!/usr/bin/env python3
"""Put a logged-in character on an exact square of a room, and read back where it stands (uses the game's own SYS.UtilGoNearSquare, so the client stays in sync).
Usage: PRIME_ADMIN_PORT=9999 place_user.py ROOM ROW COL [--angle N|north|south|east|west] [--user OBJ] [--where]
  --where : do not move, only print where the character is (room, row, col, facing) and what the four directions mean.
Without --user it picks the only logged-in character (and refuses when there are several).  Directions: row grows to the SOUTH, col grows to the EAST; angles: east 0, south 1024, west 2048, north 3072."""
import os, re, subprocess, sys
ADM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prime_server", "scripts", "admin_prime.py")
def adm(c): return subprocess.run([sys.executable, ADM, c], capture_output=True, text=True, timeout=60).stdout
def users():
    out = []
    for o in re.findall(r"OBJECT (\d+)", adm("show instances user")):
        t = adm(f"show object {o}")
        m = re.search(r"poOwner\s*=\s*OBJECT (\d+)", t)
        if m: out.append((int(o), int(m.group(1))))
    return out
def where(u):
    t = adm(f"show object {u}")
    g = lambda n: (re.search(n + r"\s*=\s*INT (-?\d+)", t) or [0, "?"])[1]
    ang = re.search(r"INT (-?\d+)", adm(f"send object {u} GetAngle").split("return")[-1])
    a = int(ang.group(1)) if ang else None
    face = "?" if a is None else ["east", "south-east", "south", "south-west", "west", "north-west", "north", "north-east"][((a + 256) % 4096) // 512]
    room = re.search(r"poOwner\s*=\s*OBJECT (\d+)", t)
    rn = re.search(r"INT (\d+)", adm(f"send object {room.group(1)} GetRoomNum").split("return")[-1]) if room else None
    return f"room {rn.group(1) if rn else '?'} row {g('piRow')} col {g('piCol')} (fine {g('piFine_row')},{g('piFine_col')}), facing {face} (angle {a})"
def main():
    a = sys.argv[1:]
    def opt(n, d=None):
        if n in a: i = a.index(n); v = a[i + 1]; del a[i:i + 2]; return v
        return d
    user = opt("--user"); angle = opt("--angle", "north"); only = "--where" in a
    if only: a.remove("--where")
    if user is None:
        us = users()
        if len(us) != 1: sys.exit(f"{len(us)} characters are logged in {us}: give --user OBJ")
        user = str(us[0][0])
    if only: print(where(user)); return
    rid, row, col = int(a[0]), int(a[1]), int(a[2])
    ang = {"east": 0, "south": 1024, "west": 2048, "north": 3072}.get(angle) if not angle.isdigit() else int(angle)
    room = re.findall(r"OBJECT (\d+)", adm(f"send object 0 FindRoomByNum num int {rid}"))[-1]
    out = adm(f"send object 0 UtilGoNearSquare what object {user} where object {room} new_row int {row} new_col int {col} new_angle int {ang}")
    print(where(user))
if __name__ == "__main__": main()
