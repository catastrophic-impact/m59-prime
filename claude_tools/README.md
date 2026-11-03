# claude_tools: debugging and analysis tools (not part of the game)

Run from the project root. Test-server tools need `PRIME_ADMIN_PORT=9998 PRIME_SERVER_DIR=server2` (the second test server, never the live one) and `$PRIME_WORK/admin-venv/bin/python`.
Server-side helpers these use stay in `prime_server/scripts/` (admin_prime.py, bot_scenarios.py, test_redeploy.sh, ...).

| tool | what it does |
|---|---|
| `roomview.py ROOM [--start R,C] [--goal R,C]` | one picture of a room: floor heights, what the server lets a body walk on, walls, objects, doors, entrances, region reachable from the start, a planned path -> `docs/roomview/` |
| `roomgrid.py ROOM ..` | makes the test server dump the walkable grid of rooms (needed by roomview/roomreach) |
| `roomreach.py ROOM ..` | no trips: which entrances and doors lie in a room's main walkable region (server rules) -> `docs/room_reachability_grid.md/.json` |
| `clientreach.ts` | the same question asked of the CLIENT's own movement code (wall sliding, small object blocking); run with node from the client build tree (see its header) |
| `place_user.py ROOM ROW COL` / `--where` | puts the logged-in character on an exact square (works on the live server) and reads back where it stands and faces |
| `worldmap.py` | offline destination map of all rooms (OPEN / EXCLUDED / GAP, hops from towns, one-way links) -> `docs/world_map.md/json`; extra exclusions in `docs/world_map_exclusions.json` |
| `botfollow.py BOT_ID` | follows ONE bot live (read-only): exact position, room, doing, stuck, goal node every 0.4 s -> `docs/botfollow/*.json`; draw with `roomview.py ROOM --trail FILE` (blue to yellow with time, red = stuck, white start, magenta end) |
| `walkcheck.py ROOM..` | WALK REGRESSION of the one walker (the planner): random start/goal pairs on test bots (server2), outcomes arrived/stuck/exited/fled/timeout, failed trips as bundles -> `docs/walkcheck/`, `docs/scenarios/` |
| `roomview.py ... --crop R,C,HALF --scale PX` | zoom on one wall/neck; with `--live snapshot.json` (from botinspect) or `--trail` |
| `botinspect.py BOT` | ONE report + picture of what a bot does RIGHT NOW: position, doing, route it holds, planner state, first refused step, nearest bodies (mobs, bots, players) with distance -> `docs/botinspect/`; library `botlab.py` |
| `botevents.py BOT [--on] [--watch N]` | the bot's FLIGHT RECORDER: its last 40 decisions in plain words (stop moving, enter room, planner refusals, give-ups), read live over admin; needs `PlayerBot.TraceRing` (server2 build 2026-11-01) and the bot trace on (`--on`) |
| `botscenario.py` | the SCENARIO LIBRARY (import): place / walk / events / inspect; failed trips return a bundle (picture, report, recorder, trail) -> `docs/scenarios/`; `walkcheck.py` is built on it |
| `exitaudit.py` | OFFLINE audit of every baked door (kind: DOOR / ZONE / EDGE / PORTAL) x every arrival square by the planner (needs `planlab.sh` built): dead doors, partial doors, per-square reach (`docs/exit_audit/`); about 50 s for all rooms |
| `planlab.sh` / `planlab.cpp` | the server's own planner (roofile.c, unchanged) as a standalone program: builds in 2 s and plans on a .roo file with NO server (also `-d` differential test of the unused client-mover port, `-p` path check) (`planlab ROOM.roo [-v] [-a row,col] < "srow scol grow gcol"`); `-v` prints grid regions, walls and bridges near Marion's south exit. Use it for every planner question before touching the server |
| `timescale.py N` | **WHOLE-SERVER TIME ACCELERATION on the test server** (patch 0081): the server clock runs N times faster (everything: regen, respawns, bot timers, hunts), measures the real factor; `1` = real time. Use `botwatch.py --scale N` with it. 10x is reliable for bots; 30x aliases the sampling |
| `botforce.py hunt\|travel\|act N` | put ALL test bots into a situation at once (each into a different hunt room / on a real journey from its town / the same activity) instead of waiting for natural behaviour; use with timescale.py and `botwatch.py --scale N --stop-on` |
| `botdash.py` | ALL bots in one table with flags (STUCK, NOMOVE, PILE, PLANNER, NOROOM, MISMATCH = piNavRid differs from the room the body stands in) |
| `botwatch.py ... --stop-on STILL,STUCK,NOWAY,MISMATCH,HOME,DEATH\|any` | long watch that ENDS at the first finding of those kinds (evidence + flight recorder captured), so the cause can be fixed at once and the watch rerun; STILL only counts a bot whose walk counters still move (a bot resting between journey legs is not still) |
| `kodbuild.sh [--c]` | build the Kod (and compiler/server) in the box; deploy notes in its header |
| `bottravel.py [--home 300 --dests 10 --bots 4 --timeout 70 --scale 10]` | **TRAVEL TEST**: test bots of one home town (default Raza 300; set a bot's home with PBotSet pos 7) are sent to hunt rooms elsewhere (the rooms the registry would offer for the bot's own health; `--all` = every hunt room) at 10x speed; per trip ARRIVED / TURNED / DROPPED / STUCK / TIMEOUT, the room trail and the flight recorder's WHY lines |
Rows grow to the SOUTH, columns to the EAST; angles east 0, south 1024, west 2048, north 3072.
