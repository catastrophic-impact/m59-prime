#!/usr/bin/env python3
"""Make the second test server dump the walkable grid of rooms for claude_tools/roomview.py (TEST SERVER ONLY: PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2).
It touches dumpgrid.txt in the server folder, sets a test bot down in each room and asks it for a short path (that makes the server build the room's grid).
Usage: roomgrid.py ROOM [ROOM ...]"""
import asyncio, json, os, re, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prime_server", "scripts"))
import bot_scenarios as B
W = os.path.expanduser("~/boxes/m59-box/src/prime_work")
def find_grid(server, roo):
    d = os.path.join(W, "build", server)
    for f in os.listdir(d):
        if f.lower() in (f"pathgrid_{roo}.bin".lower(), f"pathgrid_{roo}.roo.bin".lower()): return os.path.join(d, f)
    return os.path.join(d, f"pathgrid_{roo}.roo.bin")
async def main():
    rooms = [int(x) for x in sys.argv[1:]]
    srv = os.environ.get("PRIME_SERVER_DIR", "server2")
    open(os.path.join(W, "build", srv, "dumpgrid.txt"), "w").write("1")
    bake = {x["rid"]: x for x in json.load(open(os.path.join(W, "navtmp/navbake.json")))}
    L = B.T.AdminLink(); await L.connect()
    prime = int(re.search(r"OBJECT\s+(\d+)", await L.run("show instances primeclasses")).group(1))
    d = B.Driver(L, print, prime); bot = (await d.bots_with_bodies())[0]
    for rid in rooms:
        n = bake[rid]["nodes"]; a, b = n[0], n[-1]
        await L.run(f"send object {prime} PBotTestPath id int {bot} rid int {rid} row int {a['row']} col int {a['col']} trow int {b['row']} tcol int {b['col']}")
        roo = bake[rid]["roo"]; f = find_grid(srv, roo)
        for _ in range(60):
            if os.path.exists(f) and time.time() - os.path.getmtime(f) < 120: break
            await asyncio.sleep(1)
        print(rid, roo, "dumped" if os.path.exists(f) else "NOT dumped")
    await L.close()
if __name__ == "__main__": asyncio.run(main())
