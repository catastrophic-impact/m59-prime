# UPDATE 2026-10-31 (read this first; the tables below are from 2026-10-29)

Bots now use portal travel and PLAYER-STYLE walking (small steps the server does not check, along routes built from the client's own walk rules), and the bake no longer cuts routes the server refused. Result of REAL walking tests (a bot sent from its home town, only real kills count, strict mode; see the local dev notes):

* **Now reachable, real kills seen:** 74, 377, 378, 557 (the cliff fall is not needed any more), 858, 859, 2010, 2012, the Ko'catan jungle 2111-2114, 2121-2125, 2132, 2134, 2142-2144, and the Raza crypt 306 (a maze: the baker now adds nodes until the whole floor is covered).
* **Still no route from any town (stay on the list):** 379, 825, 827-830 (Brax interior, elevator), 1502-1505 (Sandbreak Cliffs), 2500-2504 and 2506-2508 (Ugol's Warren), 2152.
* **Reached but nothing fought in 5 minutes:** 2505 (the foes lie in parts of the room a bot cannot reach).
* **Timed out at 10 minutes (need a look, long trips):** 2131, 2141, 2154.
* 2135: no fightable monster alive when tested (boss room).
* Excluded by the owner (section 1): unchanged.
* The room maps (docs/roommaps/*.png, scripts/roommap.py) show each room's floor areas, baked nodes and routes: a floor area a bot cannot reach from the main one is drawn in another colour.
* Rooms whose graph is whole as the SERVER routes it: all 354 checked (docs/bot_room_graph_splits_after.txt: the 64 rooms that were split are whole now).

# Playerbot hunt rooms the baked room graph cannot reach (rewritten 2026-10-29)

How bots SHOULD travel (owner rule, 2026-10-29, NOT BUILT yet: bots still walk from their home town): a bot that picks a hunt destination may use ALL main-network travel portals for free (Tos 50, Marion 200, Raza 300, Jasper 350, Barloque 101, Cor Noth 150, Ko'catan 2000, Bergen 2800, Brax = g8 578, Castle Victoria 38, Proving Grounds 4300) and then walks from the portal arrival square. Reachability is therefore measured from those 11 arrivals: `python3 prime_server/scripts/worldgraph.py [--boundary]` (writes docs/world_graph.json). History and experiments: the local dev notes SESSION 14.

## 1. Excluded by owner decision (not unreachable, simply not destinations)
| room | name | level | reason |
|---|---|---|---|
| 4 | The Deep Dark Woods of Tos | 47 | never a bot destination (owner) |
| 6 | The Deep Dark Woods of Marion | 44 | never (owner) |
| 28 | The Forests of Meridian | 46 | never (owner) |
| 32 | The Berdonne Canyons | 57 | never (owner) |
| 35 | The Spider Nest | 43 | never (owner) |
| 47 | Martyr's Battleground | 140 | never (owner) |
| 546 | Deep in the Forest of Farol | 82 | orphan room: nothing links to it (D6E6 550 replaced it) |
| 550 | Deep in the Forest of Farol | 150 | trap stream: bots never enter (NO_GO d6e6) |
| 589 | Under the shadow of the Sentinel | | not a bot hunting room for now (owner, 2026-10-29) |
| 551 | Underground Lake - Home of the Mollusk | 150 | behind the trap stream |
| 556 | Deep Forest of Farol | 45 | orphan room (same) |
| 749 | Inner Sanctum of Queen Venya'cyr | 150 | bots never go there on their own (owner) |

## 2. Still unreachable: 41 rooms
Owner's reasons where given; otherwise the technical cause (a door in a disconnected piece of its room's baked graph, or no baked door). The Ko'catan jungle (2100-2199) is blocked by a guard mechanic at the east tower (owner, 2026-10-29); the baked graph also has the door out of 2115 (ka5) in a disconnected piece, but the guard is the real reason. Ask the owner how the guard works before touching it.
| room | name | level | why |
|---|---|---|---|
| 74 | The Cellar |  | Tos cellar (below Familiars): bots not needed (owner) |
| 377 | The Sewers of Jasper |  | Jasper sewers (same) |
| 378 | The Sewers of Jasper |  | Jasper sewers (same) |
| 379 | The Sewers of Jasper | 89 | Jasper sewers: excluded for now (owner) |
| 380 | The Ancient Smuggler's Crossing |  | sewers/hideouts: excluded (owner, 2026-10-31) |
| 108 | The Sewers of Barloque |  | sewers/hideouts: excluded (owner, 2026-10-31) |
| 111 | The Sewers of Barloque |  | sewers/hideouts: excluded (owner, 2026-10-31) |
| 112 | The Sewers of Barloque |  | sewers/hideouts: excluded (owner, 2026-10-31) |
| 110 | A shadowy corner |  | sewers/hideouts: excluded (owner, 2026-10-31) |
| 708 | The Sewer Hideout |  | sewers/hideouts: excluded (owner, 2026-10-31) |
| 557 | The Sweet Grass Prairies |  | reached only by falling off the cliff in Jasper (one-way): not walkable, owner can test if needed |
| 825 | The Dungeon of Castle Brax | 170 | Brax interior (elevator): excluded (owner) |
| 827 | Ancient Graveyard of Brax | 136 | Brax interior (elevator): excluded (owner) |
| 828 | Decaying City of Brax | 126 | Brax interior (elevator): excluded (owner) |
| 829 | Within the Walls of Castle Brax | 140 | Brax interior (elevator): excluded (owner) |
| 830 | Ruins of Castle Brax | 170 | Brax interior (elevator): excluded (owner) |
| 858 | Dark Caves |  | caves between the island and the mainland: excluded for bots (owner) |
| 859 | Abandoned Outpost |  | caves between the island and the mainland (same) |
| 78 | The Smuggler's Way |  | excluded (owner, 2026-10-31) |
| 77 | Abandoned Storage Room |  | excluded (owner, 2026-10-31) |
| 75 | Secret Passage |  | excluded (owner, 2026-10-31) |
| 76 | Abandoned Fountain Tavern |  | excluded (owner, 2026-10-31) |
| 860 | Rumbling Cavern |  | excluded (owner, 2026-10-31) |
| 38 | Castle Victoria |  | Castle Victoria interior: excluded for now (owner, 2026-10-31) |
| 39 | Upstairs in Castle Victoria |  | Castle Victoria interior: excluded for now (owner, 2026-10-31) |
| 41 | The Throne Room of Castle Victoria |  | Castle Victoria interior: excluded for now (owner, 2026-10-31) |
| 2 | Outside Castle Victoria |  | Castle Victoria: excluded for now, to be added back later (owner, 2026-10-31) |
| 40 | The Antechamber of Castle Victoria |  | Castle Victoria: excluded for now, to be added back later (owner, 2026-10-31) |
| 42 | Underbasement of Victoria |  | Castle Victoria: excluded for now, to be added back later (owner, 2026-10-31) |
| 206 | Green Acres Plantation |  | a lot going on in this map: excluded for now (owner, 2026-10-31) |
| 707 | Konima's Abandoned Dwelling |  | Konima: part of the cave network between the island and the mainland (owner, 2026-10-31): excluded |
| 2505 | Konima's Ascension |  | Konima: part of the cave network between the island and the mainland (owner, 2026-10-31): excluded |
| 2506 | Lair of the Orc Pit Boss |  | excluded (owner, 2026-10-31) |
| 2510 | A Spring of Vitality |  | excluded (owner, 2026-10-31) |
| 2504 | Obfal's Sepulchre |  | excluded (owner, 2026-10-31) |
| 2509 | A Tranquil Place |  | excluded (owner, 2026-10-31) |
| 27 | A Deep, Dark, Spooky, Icky Cave |  | excluded (owner, 2026-10-31) |
| 1502 | Sandbreak Cliffs | 183 | Sandbreak Cliffs: excluded for now (owner does not know the area yet) |
| 1503 | Sandbreak Cliffs | 183 | Sandbreak Cliffs (same) |
| 1504 | Sandbreak Cliffs | 183 | Sandbreak Cliffs (same) |
| 1505 | Sandbreak Cliffs | 183 | Sandbreak Cliffs (same) |
| 2111 | Cliff Hive | 122 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2112 | The Jungle Cliffs | 120 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2113 | A notch in the jungle | 120 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2114 | Into the Jungle | 120 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2121 | The Cliffs | 120 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2122 | Headquarters for the Avar Warriors | 122 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2123 | Camp of the Warrior Avars | 122 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2125 | Into the Jungle | 120 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2131 | The Chasm | 123 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2132 | Turf of the Warrior Avars | 120 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2133 | Ruins of the Riija Temple | 125 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2134 | Origin of the Kriipa | 120 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2135 | Outside the Mad Scientist's Hut |  | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2141 | Lair of the Bone Priestess | 123 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2142 | Territory of the Noble Avars | 121 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2143 | Deep in the Jungle | 120 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2144 | The Clearing of the Trading Post | 123 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2152 | Headquarters of the Noble Avars | 125 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2154 | Avar Village | 129 | Ko'catan jungle: the guard mechanic at the east tower (owner, 2026-10-29), not a pathing bug |
| 2500 | Ugol's Warren Entrance |  | Ugol's Warren: excluded for now (owner) |
| 2501 | An Enigmatic Chamber | 74 | Ugol's Warren (same) |
| 2502 | The Archaic Hollows | 108 | Ugol's Warren (same) |
| 2503 | Aqueducts of Merb | 200 | Ugol's Warren (same) |
| 2507 | Grog's Antechamber |  | Ugol's Warren (same) |
| 2508 | Brog's Antechamber |  | Ugol's Warren (same) |

## 3. Reachable from a travel portal arrival (bots only get there from their home town once portal-first travel is built) (incl. 306 Raza mausoleum since the relaxed+pruned bake; 84 rooms of the old list)
Reached from at least one travel portal by the baked graph: 27, 37, 38, 39, 40, 70, 71, 78, 108, 206, 330, 331, 516, 526, 534, 535, 536, 537, 544, 545, 547, 552, 554, 562, 563, 564, 566, 567, 568, 574, 575, 576, 578, 579, 583, 584, 585, 586, 587, 593, 596, 597, 598, 599, 603, 1500, 1512, 2010, 2012, 2115, 2505, 2600, 2601, 2602, 2603, 2808, 2809, 2810, 2811, 2812, 2813, 2815, 2816, 2817, 2818, 2819, 2820, 2850, 2851, 2852, 2853, 2854, 2900, 2901, 2902, 2904, 2950, 2951, 2952, 2953, 2954, 2960, 2961, 2962.

## 4. Exploring together later
- 550 d6e6.roo trap stream (owner screenshot 2026-10-28): a stone-walled channel with a gate runs north-south through the middle (about columns 45-55 of 100, rows 0-35; 8 squares wide at rows 27-34). A drop into it cannot be climbed out of: bots must never walk or fall into it; a bot that ends up inside needs Rescue.
- 545 West Merchant Way (d5.roo): cliffs, a fall cannot be climbed back (one-way). 536 Forest of Farol (c6.roo): narrow winding paths, mobs can block them; its door to the Old Dwarven Hall (706) is a GUILD HALL (guardian angel): bots never use guild-hall doors.
- 546/556 are orphans (nothing links to them), not mazes.
