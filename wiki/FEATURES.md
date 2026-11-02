# Meridian 59 Prime: features

Meridian 59 Prime is a custom Meridian 59 built on two pinned upstream projects, each kept as *pinned upstream + numbered patches + our own overlay files*:

- **Server:** [jboullion/shards-server](https://github.com/jboullion/shards-server) (Server 104, 64-bit Linux build), `prime_server/`
- **Client:** [jboullion/meridian-shards](https://github.com/jboullion/meridian-shards) (TypeScript web client), `prime_client/`

This file lists what Prime adds, grouped by area, as it works today. `wiki/changes.txt` is the detailed per-patch log (what changed, in order, and how it was tested). Everything marked *(rule)* can be switched in the admin TUI, Rules tab.

## Classes
- Four playable classes: **Warrior, Monk, Paladin, Elementalist**, each with a six-level ability table; a class level opens when the best three abilities of the previous level reach the usual threshold.
- Fixed class stats and starting gear; level-1 abilities at creation; class-specific trainers (the priestess of a class's god teaches the whole table).
- Class rules: warrior threat and Second Wind, monk Dodge worth more in light armor, Holy Touch is flat damage, Mana Focus is free, Mystic Touch gives mana, Ice Shard snares and Ice Nova freezes, disciple-robe spell bonus by class level, Sword of Riija bonuses.
- Armor and weapon numbers rebalanced; ShortSword is the "dagger" with a chance to hit twice.
- **Class system switch** *(rule `pbClassSystem`)*: classes on, or original classless characters. Each character plays only in the mode it was made in; the character list greys out the other mode's characters. Ten character slots per account.
- Paladin spirit weapons return mana on each hit and ignore a monster's holy resistance *(rules)*.

## Groups
- Groups of up to five seats (players, bots and companions all count), invitations, shared health and mana window, no friendly fire, XP and heals shared by group.
- Group window in the client: click a row to target, Invite, Leave, stance buttons and an **Attack** button for your companions.

## Companion bots
- Temporary class companions you summon from the Companion window: **Warrior, Monk, Paladin, Elementalist**; up to four at once *(rules `pbCompanionBots`, `piMaxBots`, `piBotResummonSec`, `pbBotSplitXP`)*.
- **Built from the player's own numbers:** health is the player's base health up to a class cap (100 + class stamina); skills and spells come from spending the player's total ability percent evenly level by level, as a player would; hit, defense, damage and spell power use the player formulas; spells cost their real mana.
- Behaviours: emergency heals, buffs before fights, Monk and Elementalist Mana Focus, Elementalist mana battery, Paladin spirit sword or hammer, Elementalist Touch of Flame (cast animation, sounds, fire damage).
- Orders: Follow, Defend, Stay, Passive, Attack (group window button and a hotbar slot), Appearance (look editor), Dismiss; stances apply to every bot.
- Movement fixes: a follower drops obstacle-avoidance when it has a clear line to its owner; a test-only movement log *(rule `pbBotMoveLog`)*.
- The old **faction companion** (Duke, Princess, Rebel; bond, vault, pack, hall, revival) is **switched off** *(rule `pbFactionCompanions`)*; its code is kept in `util/companionbook.kod` for the planned playerbots.

## Admin and testing tools
- **In-game admin console** (admin characters only): Travel, Players, Self (with creature disguise), World (weather here or everywhere), Items (every item, give to anyone), Creatures (spawn), Character (list, add, remove or set skills and spells; base health).
- **Admin TUI** (terminal): start and stop the whole stack (server and web client) with ports shown, rules, accounts (create, rename, password, ban, unban, delete) and characters; an `admin` / `admin` account is recreated on every start.
- Scripts: full and quick builds, an 8-second hot reload, patch begin and end helpers, a headless protocol client for scripted tests (commands, object commands, sound log), and a browser screenshot driver.

## Game rules and options
- Death: item and stat loss options *(rule)*; murder is not permanent *(rule `pbMurderNotPermanent`: a murderer who dies becomes an outlaw, an outlaw who dies is clean)*.
- Reagents mandatory, optional (weaker spell) or not needed; unlimited eating; bows without arrows; dagger double-hit chance.
- **Brax arena solves itself** on a timer *(rule `piBraxAutoSolveSec`, 0 = original)*.
- Locked doors play a woman's own hurt cry for female characters instead of a man's grunt.
- Companions no longer play the faction troop's "aware" shout.

## Client (web)
- Class picker, classless creator, greyed other-mode characters.
- Group window, monster health bars, floating damage and heal numbers, friendly targets in green, "select a target before attacking".
- Companion window with the bots section, bot appearance dialog, hotbar "Companions attack" slot.
- Retried picture loads, cleaner new-character start, Prime title and logo, an Electron launcher.
- Preferences and Configuration apply each change as you make it (Cancel puts back what the window opened with), and the login screen has a sound on/off button.

## Server fixes in C
- The server no longer dies silently when a client disconnects while it is sending (SIGPIPE is ignored and written to `crash.txt` with any fatal signal and a backtrace).
- 64-bit Linux build; MD5 fixed on 64-bit (admin-created accounts can log in); duplicate class loading fixed; real account deletion on Linux.
- **Linux file names:** seven rooms (Raza's bank and vault, two guild halls and the maze and desert entrances) and three monster classes (Tyrant, Fortuna, jGeneral) were never loaded or compiled on Linux because the Kod and makefiles spell their file names with different capitals; the server now finds the rooms and the makefiles match the files.
- **Linux server stability:** `show status` no longer hangs or crashes, closed sessions no longer log errors or leak a mutex, and a save no longer crashes on a deleted object's room blocker.

## Playerbots (in progress)
- **Phase 1 works:** persistent characters (300 names, men with men's names and women with women's) that appear in "who", log in and out live, answer tells, live in nine towns (Tos with East Ende, both Barloques and its port, Cor Noth, Marion, Raza, both Jaspers, Ko'catan, Bergensdorf, Jixa) and speak to players nearby *(rules `piTownLife`, `piPlayerBotCount`)*.
- **Town life option** *(rule `piTownLife`)*: 0 = the wandering townsfolk crowds only (original ambience), 1 = playerbots instead of the crowds, 2 = both.
- **Activities (Phase 2a, current code):** every 5 to 30 minutes a bot chooses to hunt (most often), shop, hang about town or sit in the inn. Shopping is simulated without transactions: a bot chooses a linked merchant room, stays in limbo while it is empty, and materializes there when a player is present. This was hot-reloaded but is not yet verified in-game; if no linked active seller is found, shopping falls back to town. Hunting is real (see below). Occupied-route visibility remains unimplemented *(rule `piBotTimeScale` speeds the activity clock up for testing)*.
- **Town and inn social idling (in progress, not yet verified):** the broad activity timer decides whether a bot hangs out in town, socialises in an inn, explores, or hunts/farms. In town streets, innocent/non-criminal bots pick a reachable spot and stay there for a random 1–3 real-time minutes, independent of piBotTimeScale. At each local check they have 50/50 odds to stay or relocate within that same room. In inns, they remain at one spot for the whole activity and turn to look in a new direction every 10–30 seconds; they do not locally relocate. The activity timer decides when they change maps. This replaces continuous local wandering. Town local stays use real time even when the high-level activity clock is accelerated. Inn idling is stationary with 10–30 second look turns. The movement uses baked room graphs from `navbake.ts`; transit waypoint checks were tightened to reduce stops between squares (in-game result not yet verified). Paired bot interactions (approach, face, emote or speak) are a later extension.
- **Info window:** every bot has its own description (three parts picked from lists of 20, so no two read alike) and, with rule `piBotShowDoing` (on), a line such as "Currently: heading to the bank in Marion." or "Currently: farming giant rats in Room X." for debugging.
- **Minimap:** bots show as players (blue dot), not as monsters.
- They are the companion body with no owner, so they will use the same fight, class and gear code as companion bots.
- **Bots rest and talk only in towns:** passing the time, moods and chat happen only in the streets and inns of the nine towns; a bot anywhere else (a hunting ground) only hunts, travels or looks about.
- **Bots cry out when hit:** a hurt playerbot makes the same cry as a player of its gender, more pained the less health it has left.
- **Hunting rules** *(admin rules)*: `piBotHuntMargin` 200, `piBotFightMargin` 140 and `piBotFleePct` 35 (how sure a bot must be of winning), `piBotHuntBandLow` 1 and `piBotHuntBandHigh` 85 (it hunts rooms whose monsters are that percent of its own health), `piBotHuntPauseSecs` 10 (a hunter stands still that long after a kill and its loot, while it heals, unless something attacks it).
- **Parked bot moods (stage 4):** a bot standing in a street or inn picks a mood for 2 to 6 real minutes. In the four inns with a globe (Cor Noth, both Barloques, Jasper) a fifth of the bots read the globe (info window "reading the announcements globe", at most two at a time), a fifth are away from the keyboard (they never turn), a fifth are chatty and walk over to talk with another bot, and the rest hang about, looking around every 10 to 30 seconds, often at another bot. Elsewhere: a quarter away, a quarter chatty, the rest hanging about.
- **Playerbot hunting (real):** a bot walks to its hunt room in plain sight (see travel above) and fights real monsters there, whether or not a player is present; bots keep a monster room active like a player does. It goes for the nearest monster; after every kill it picks up what the foe dropped (gold and reagents are counted for the character, everything else is cleared away), then rests until its health and mana are full unless something attacks it, and runs for a door when badly hurt. Levels and ability grow with the foes it really beat. Hunt rooms are chosen from every surveyed monster room with monsters of 40 to 110 percent of the bot's level that it can reach survivably, so bots spread over the whole map, not just outside town. A bot beaten in a fight goes to the underworld for a while and comes back in its home town. Still to come: bot groups, the real underworld portal, the player market.
- **Better bot routes (2026-10-29):** room-edge exits are found where the floor really meets the border (about 100 more exits placed), door searches reach further, and routes inside a room that were cut apart by furniture are joined again where the server's movement check allows it. Bots reach more hunt rooms on foot; some places stay out of reach on purpose (see docs/bot_unreachable_rooms.md). *Planned:* bots will use the free travel portals between towns before they set out.
- **Portal travel (2026-10-31):** a bot that picks a faraway hunt room takes the free town travel portals to the town nearest to it (Tos, Marion, Raza, Jasper, Barloque, Cor Noth, Ko'catan, Brax, Castle Victoria, Proving Grounds), then walks; Bergen's portal is not used yet.
- **Bots plan their own way (2026-11-02):** a bot no longer follows pre-baked routes. It plans a path over the room's real floor (the server's own A* with the client's wall rules), takes one step a tick like a player and goes round walls (it slides along them the way the client does), round creatures and round every door square except the one it is walking to. The step size matches the server's own monster step so the walking animation stays smooth. The baked graph is still used to choose where to go (spots, doors, portals), not how to get there.
- **A creature in the way (2026-11-02):** a travelling bot is blocked by creatures and other bots only within a quarter of a square (what the client blocks a player with). If a creature still blocks it, it steps sideways round it and plans again; if that fails it works out, from its own and the creature's hit points, hit chance, damage and attack speed, whether it can kill it before it dies: if so it fights it and walks on, else it flees, casts Rescue, is taken home and picks a new activity.
- **Doors are not floor (2026-11-02):** a bot walking inside a room never steps on a door square except its own destination, so it no longer walks out of a room by accident.
- **Sealed entrances:** a few entrances put a bot on a platform with no way out (West Jasper's east gate is one). Such a bot gets "no way", counts it as a failed walk, and after six in two minutes casts Rescue; the room is logged as `PBOT-SEALED` so the entrances can be removed from the destination map.
- **Rooms covered by the bake (2026-10-31):** every room has a graph of spots and doors built from the client's own walk rules (big mazes and caves get spots across the whole floor); the way between spots is planned by the bot itself. Hunt rooms bots really reach and fight in include the Ko'catan jungle, the Jasper sewers, the Sweet Grass Prairies and the Raza crypt; the Brax interior, Sandbreak Cliffs, Ugol's Warren and a few others are excluded (list in docs/bot_unreachable_rooms.md, destination map in docs/world_map.md).
- **Giving up (rule `piBotHuntFailLimit`, 3):** a hunter that fails three times in a row to find or reach a foe (no route, not getting closer for 8 seconds, no damage for 20) gives its hunt up and picks another activity; a kill resets the count.
- **Bots leave rooms through the real edge (2026-11-01):** a bot travelling through a room-edge exit now walks to the floor where the room really meets that side, not to a point in the middle of the side that often lies outside the floor (before, such bots stood still and were rescued minutes later).
- **Debug tools for bots (claude_tools/, see claude_tools/README.md):** a live bot inspector (position, route goal, planner state, the server's reason for a refused step, everything standing near), a flight recorder (a bot's last 40 decisions, readable at once), a dashboard of all bots with flags, PNG room pictures with walls, heights, the bot's trail and the exact wall that stopped it, and a scenario library for tests.

## Monsters
- **Leash (rules `piMobLeashSecs`, `pbMobLeashHeal`):** a monster that gets nowhere in a chase for the set number of seconds (not in reach, not a square closer, nobody hurt) gives its target up: it ignores that target for 30 seconds, heals if the rule says so, drops its aggro and walks back to where it stood. 0 = off (original behaviour).
- **Line-of-sight aggro (rule `pbMobAggroLOS`):** a monster notices someone only with a clear line of sight to them, not through walls; anyone who attacks it is always noticed.
- **Aggro scan (rule `pbMobAggroScan`):** a monster that is moving about with nothing on it looks around once a second for a player, playerbot or companion in its sight, so someone who stands still is noticed too (before, only movement was noticed).
- **Route-checked aggro (rule `pbMobAggroPath`):** a monster does not notice someone it has no walking route to (the room's walking graph has no way between them: across water, behind a wall it cannot pass), unless it casts spells from afar. Rooms without a graph go by sight alone.

## Planned
- Crafting (not in Server 104), Priest class, spell damage normalisation.
- Monsters: pathfinding to a target when a chase is stuck, a proximity check so standing still near a mob triggers aggro, a level-gap rule. Playerbots: bot groups, inviting a bot, the market.
