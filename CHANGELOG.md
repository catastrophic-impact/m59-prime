# Changelog

Newest first. Each push to GitHub gets an entry.

## Unreleased

## 2026-11-01 - First upload of the m59-prime repository
- One-script setup for Linux with distrobox: `m59primesetup.sh` creates the build box, builds the server and the web client, downloads the pinned game files and writes a portable `release/` folder (server, client, Node runtime, start/stop/admin scripts).
- The game files (art, sounds, rooms) are not in the repository; they are downloaded from one pinned Meridian Shards release, checked by SHA-256 (`prime_client/ASSETS.txt`).
- The patch series now builds from a clean tree: server patch 0075 now carries the grid path planner it depends on, client patch 0028 no longer edits a file the overlay provides.
- The admin account's password is random (or `M59_ADMIN_PASSWORD`) instead of a fixed test login; every new install gets its own random login key.
- Playerbots: exact door landings from the game's own exit tables, verified edge exits, trap landings avoided, restart reset, night-only hunting rooms, main underworld portal for ghosts, fewer hunting deaths; tools to watch and test bots (`claude_tools/`).
- New title screen logo; README, BUILDING.md and the feature list rewritten.


### Class overhaul (meridian59_prime) - design log, for the future wiki
Design only so far; no code written yet. Full details in docs/class_overhaul_design.txt.
- Characters will be wiped; the class is chosen at character creation (look + name only), never switched, no second class.
- Stats are fixed per class and do not grow with ECL. Warrior: 50 Might / 50 Stamina / 50 Agility / 50 Aim / 1 Intellect / 1 Mysticism.
- Trainers serve several classes but only teach the player's own class's skills. Unlock of the next level uses vanilla Meridian's threshold.
- **Warrior skill list (v4, six levels)**: L1 Slash, Mace Fighting, Second Wind (known from the start); L2 Dodge, Create Weapon, Fencing; L3 Axe, Block, Magic Shield; L4 Hammer, Parry, Shield Slam; L5 Resist Magic, Bless, Scimitar; L6 Disarm (Free Action removed, see CC immunity). Whirlwind, Taunt and a separate Long Sword were dropped (Fencing is the long-sword skill; warriors make extra threat per attack instead of Taunt).
- **Second Wind**: passive, WoW style. After 10 s out of combat health regenerates faster: 1 / 2 / 3 / 4 hp per second at skill 1-33 / 34-66 / 67-98 / 99%+. Also regenerates mana, with the same hp/s tiers (confirmed).
- Disarm, Dodge, Parry, Block are automatic as in vanilla. Shield Slam is active and needs a shield.
- Kraanan spells already scale with Stamina in vanilla (spell.kod GetDivisionReq); Warriors have 50 so no change is needed. Kraanan robe boosts them as in vanilla; robe colour will show class level.
- **Create Weapon** stays vanilla but only creates weapons the class may use (Warriors: no daggers).
- **Short swords are renamed Daggers**; only certain classes may use them (e.g. the future Shadowblade/rogue).
- Reagent-using class abilities follow the "weaker without reagents" rule; companions stay exempt.
- **10 character slots per account** (implemented). Server (blakserv/game.c, GameTryGetUser, constant CHARACTER_SLOTS_PER_ACCOUNT): when an account asks for its character list the server tops it up to 10 user objects (class by account type: normal / admin / DM); unused ones are empty slots. Client (CharSelect.cs, GameClient.ChooseCharacter): a "Choose your character" screen lists used characters first, then empty slots ("create a character" opens the creation screen). Scripted runs (--connect) take the first used character automatically; set env M59_PICKER=1 to see the picker in a test screenshot. Tested: tester account shows Tester + 9 empty slots.
- Disciple quests are removed (design). Fencing = the long-sword skill; Short Sword proficiency becomes Dagger. Warriors start with a Mace item. Characters may be wiped freely during testing.
- **Class framework (implemented, first slice)**:
  - Server (kod): new `CLASS_NONE/CLASS_WARRIOR` constants (blakston.khd) and player property `piPlayerClass`. `player.kod`: `ClassAbilityTable` (Warrior table: ability -> class level 1-6), `GetClassLevel`, `GrantClassStart` (fixed Warrior stats 50/1/50/50/1/50 and the level 1 abilities), `PlayerCanLearnClass` (called from `PlayerCanLearn` for classed players: abilities outside the class table cannot be learned; level 1 is free; a level opens with the vanilla rule: best three abilities of the previous level vs the vanilla threshold, Intellect still lowers it, scarcity scaling for levels with fewer than three; anything from a higher level known opens the rest of the level).
  - Creation: the client sends the class as pseudo skill `1000 + class`; `PlayerNewCharInfo` then ignores picked stats/spells/skills, applies the class and gives the starting Mace.
  - Trainer: `kranprst.kod` now also teaches the Warrior skills and Magic Shield / Free Action; `monster.kod` `AbilityLevelFor` makes "level N" requests list the abilities of the asker's class level instead of the vanilla level. Disciple quests removed (`HasDoneLearnQuest` always true).
  - Client: creation screen = look + name + class (Warrior only so far; text with stats and abilities); stats/spell/skill pickers removed. New test options: `--char NAME` (pick a character in scripted runs), env `M59_SAYWAIT` (frames before `--say`).
  - Tested: created a Warrior (class 1, stats and 3 level-1 skills correct, Mace in pack); Dodge/Fencing/Create Weapon (level 2) need more than the level-1 skills, unlock after raising them (checked 70% and 90%), Block (level 3) stays locked with only Dodge, Short Sword / Lightning Bolt are refused as not class abilities, level lists report class levels.
  - **Second Wind reworked (implemented)**: passive regeneration instead of the vanilla vigor boost. `player.kod` `SecondWindTimer` runs every second while logged in (started in UserLogonHook, stopped in UserLogoffHook); when the player has the skill and 10 s have passed since the last combat (`piLastCombatTime`, set when taking damage in AssessDamage and when attacking in UserAttack) it heals health AND mana by 1 / 2 / 3 / 4 per second at skill 1-33 / 34-66 / 67-98 / 99%+. Every 10th regenerating second rolls a normal skill improvement. `secwind.kod`: DoSkill is now a no-op (the old vigor effect is gone), new description. Tested: with the combat timer blocked health only regenerated at the slow vanilla rate; unblocked it regenerated about 3 per second at ~90% skill. Admin (DM class) characters take no damage, so the 10 s delay after a real hit still needs a test with a normal account.
  - **Crowd-control immunity + Stun + Shield Slam (implemented)**:
    - Rule (per CC type): after a CC of a type starts, the target is immune to THAT type from the start until twice the CC length after it ends (a 5 s stun = 5 s stunned + 10 s immune). Types: `CC_HOLD, CC_BLIND, CC_DAZZLE, CC_STUN` (blakston.khd); a spell declares its type in `viCCType`. `battler.kod`: `plCCImmune`, `CCImmuneTo(cc)`, `RecordCC(cc, ms)`; recorded in `StartEnchantment` of players and monsters. Hold, Blind and Dazzle refuse to be cast on an immune target (`CCBlocked` in CanPayCosts, plus checks in DoHold / DoBlind / DoDazzle used by items, traps and monsters) and tell the caster "<target> cannot be affected by that effect again yet.". Different types do not block each other (stun, then hold, then blind is possible).
    - New `Stun` (passive/spell/stun.kod, SID_STUN 199, subclass of Hold: cannot move, fight or cast; own messages and paralysis effect), applied with `DoStun`.
    - New skill `ShieldSlam` (passive/skill/shldslam.kod, SKID_SHIELD_SLAM 407, Warrior level 4, taught by the Kraanan priestess): active, needs a shield (`IsUsingA(&Shield)`), target must be a battler in the same room within 2 squares, stun = 5 s x skill % x (Might + Stamina)/100 (min 1 s, max 5 s), costs vigor, can improve with use, works on monsters and players with the same duration, blocked by stun immunity ("... cannot be stunned again yet.").
    - Using active skills: new client -> server extension commands `EXT_CMD_SKILL_TARGET` (24, object = target) then `EXT_CMD_USE_SKILL` (23, object = the skill object from BP_SKILLS) handled in `user.kod` (`UserUseSkill`); automatic skills answer that they work by themselves. Client: a skill dragged to the hotbar now uses it on the current target (`GameClient.UseSkill`).
    - Free Action removed from the Warrior table (CC immunity replaces it); Warrior level 6 is now Disarm only. The vanilla Free Action spell still exists but is not taught to Warriors.
    - `tools/deploy_kod.sh` now also runs `CreateAllSpellsIfNew` / `CreateAllSkillsIfNew` after the server is up: new spell or skill classes only exist in an existing save after that.
    - Tested through the admin console: Stun on an Orc succeeded, a second stun was refused (immune), Hold on the stunned orc still worked, immunity expired after the computed time (2 s stun -> 7 s total); Shield Slam through the new extension commands: out of range message, then "Priestess Qerti'nya is stunned by your blow!" and "cannot be stunned again yet." Not yet tested: clicking the hotbar button in the client, a shield slam on a player, blind/dazzle immunity in play.
  - **Shield Slam attack rules (fix)**: it now uses the same checks as a normal hit (`CanMonsterFight` for monsters, so safe NPCs such as the Kraanan priestess cannot be slammed, plus `AllowPlayerAttack` for room rules, PvP and outlaw rules). Compiled; the range-limited test could not be repeated, so this is untested in play.
  - **Short Sword renamed Dagger (implemented)**: the item (class still `ShortSword`), its proficiency skill ("dagger fighting"), the Temple of Kraanan and trophy-room texts now say dagger. Class restrictions: new `ClassAllowsItem` in `player.kod`, checked in `TryUseItem`: Warriors cannot use daggers (ShortSword, BlackDagger) or ranged weapons (`RangedWeapon`: bows); message "Your training does not allow you to use the dagger." Tested: a Warrior cannot wield a dagger or a bow, but can wield a mace and a shield.
  - **Create Weapon**: stays vanilla but replaces a dagger result with a hammer when the caster's class cannot use daggers (code in `creaweap.kod`; not observed in play because casting it through the admin console created nothing).
  - **Starting mace is equipped (fix)**: classed characters get their Mace in hand at creation (`AddDefaultObjects` calls `TryUseItem`); before, it sat unequipped in the pack so the attack button showed fists. Tested with a new Warrior: mace marked as in use, mace on the attack hotbar button.
  - **Warrior threat (implemented)**: `Battler.GetThreatBonus` (0; `Player` returns `WARRIOR_THREAT` = 5 for Warriors). (1) `monster.kod` AssessDamage: every hit by the monster's current target adds that bonus on top of the vanilla +1 hatred, so a warrior it fights is held much harder (3 hits: Tester 3, Warrior 18). (2) `brain.kod` GetHatred: when a warrior hits a monster (`TS_FIGHT_ME_VICTIM`) its hatred for the warrior is raised by 6 x the bonus (30), so the monster turns on a warrior who hits it more readily than on other attackers. The vanilla single-target hatred model is kept (no threat table yet); healing does not generate threat; companions will use the same hook once the Warrior companion exists. The brain part was compiled but not observed in a real fight.
  - **Trainer reply for abilities outside the class (implemented)**: `PlayerCanLearnClass` returns the new `PLAYER_LEARN_NOTCLASS`; `CanDoTeach` then has the teacher say "You need to seek training elsewhere."; asking a trainer for a level where the classed player has nothing to learn gives the same answer (`ReportLevel`). Compiled; the spoken reply itself was not observed in the client.
  - **Robe colours show the class level (implemented)**: `DiscipleRobe.ResetColors` uses `GetClassTier` (highest class level of any known ability, capped at 5) when the wearer has a class and the robe is of the class's god (`ClassGodSchool`: Warrior = Kraanan): level 0-4 use the vanilla colour steps, 5 and above the master colour (Kraanan = blue); other gods' robes show no knowledge. Robes are refreshed when a skill is learned (`AddSkill`). Spell bonus of the robe is unchanged (+4 per level up to +20 for the god's school). Not observed in play: the test characters are admin (DM) characters, which always get the DM sky-blue robe.
  - **Warrior companion (implemented)**: the Tank is now `CompanionWarrior` (compwarr.kod, role `COMPANION_ROLE_WARRIOR` = 3): plate, knight shield, longsword; the taunt loop is gone, instead `GetThreatBonus` returns `WARRIOR_THREAT` so it holds monsters like a player warrior; offense/defense are fixed (250 / 320, the old tank values at ECL 10) instead of growing with the master's ECL (its health still follows the master). Mage, Healer and Fighter companions are disabled (`CompanionCall` answers "not available yet"); the client's companion window only offers Warrior. Tested: calling a warrior companion joined the group ("Lorenzo", effective level 21).
  - Stats and ECL: player stats never grew with level in this game (health grows, stats come only from creation; boons/quest rewards only change the temporary modifier), so nothing had to change for players; the companion rule above covers the ECL scaling that existed.
  - No armour restrictions for Warriors (decision); only daggers and ranged weapons are barred.
  - NOT done yet: Shield Slam hotbar click test, level-up reward balance, weapon proficiency restrictions for other classes, other classes (Ranger, Shadowblade, Mage ...), Sword of the Hunt / Amulet of the Three redesign.
- **Design: Shield Slam and crowd control**. Shield Slam = active, shield required, 5 s stun at full effect (Might/Stamina/skill %), works on monsters and players (full time on players), no cooldown. Instead, game-wide rule: any CC effect (hold, stun, blind, dazzle ...) makes the target immune to CC for double its length; using a CC on an immune target only reports that it cannot be affected yet. Free Action is therefore removed from the Warrior list.
- **Imported from Meridian Shards (jboullion/shards-server, with the author's permission)**: the **Holy Blaze** spell (Shal'ille level 4 attack spell, SID_HOLY_BLAZE 93: short range holy energy that heals good targets and harms evil / undead ones by karma) and the **Nerudite Shield** (elemental resistance shield). Their Blakod was converted for our compiler (`//` comments -> `%`, `foreach` -> `for`, `else if` -> nested `if`, the language include removed). The Holy Blaze icon and the shield graphics (`iholybl.bgf`, `nerushld.bgf`, `povshldi.bgf`) live in `assets_extra/shards/`; the client now also looks for graphics in `assets_extra/` (retail files win when a name exists in both). Credits in NOTICE.md. Tested: both exist in the running server (`CreateAllSpellsIfNew` registered the spell), a Nerudite Shield in the pack shows its green icon in the client; the spell was added to a character, but not yet cast in a fight.
- **Playtest fixes (2026-10-20, Priest in Raza)**:
  - **Stuck yellow glow after casting (fixed, client)**: when the first-person hand animation of a cast finished (group 0) its glow overlays were left on screen; `UpdatePov` now hides them. Reproduced with Forces of Light on a new Priest, confirmed gone.
  - **Holy Touch casting kept failing (fixed)**: the earlier test used an admin character, and admins never fail a cast. On a normal (non-admin) Priest, casting Holy Touch failed about 2 times in 8 and spell casts in general had a vanilla chance of `Mysticism + (100 - Mysticism) x skill%` (about 55-60% at the start for Mysticism 50). Now a classed player's spell succeeds with 80% + 20% x skill% (the old 95% cap still applies). Tested on a normal Priest: 15 successes and 1 failure in 16 casts. Also new: a brand-new account without character slots could not enter the game (stuck on "Entering game"); `synched.c` now creates the first slot when an account with none enters.
  - **Holy Touch missing almost always** (the to-hit part, separate from casting): A touch spell is an enchantment, then each hit rolls to-hit (`GetOffense` = stroke x3 + proficiency x2 + Aim x4 + base health x1.5). With Aim 1 the Priest lost ~200 points a Warrior has. Touch spells are now aimed with Mysticism when it is higher than Aim (`player.kod` GetOffense). Normal spell casting chance is vanilla: `requisite stat + (100 - stat) x skill% / 100` (about 55-60% for a fresh Priest with Mysticism 50); not changed.
  - **Karma is off for players**: `GetKarma` returns 0, `AddKarma / LoseKarma / GainKarma` do nothing, spell karma requirements were already off. Forces of Light helped only players with positive karma; now everyone in the room benefits. Spots that read karma and now see 0 (to review when we get to them): Minor Heal / Hospice / Major Heal (small bonus from the target's karma), Dazzle duration, Holy Symbol, Breath of Life, Ivy Circlet (needs karma < 50) and Orc Shield (karma > -50) which now always pass, Sword of the Hunt, Amulet of the Three, mana nodes, fey forest, monsters that hate by karma, Karma potions.
  - **Self portrait faces the camera**: the target window / look picture of our own character was drawn from behind (our own figure uses the opposite angle convention); fixed in `FaceOf`.
  - **Attacks need a target**: the attack button and key no longer pick the nearest creature in front; with nothing selected they say "Select a target first (click it, or press Tab)." Spells that need no target, wall spells and so on are not affected.
  - **About me window**: right-click your own portrait: an info window (picture, name and an editable text box) that sends `ChangeDescription` so other players read your text when they look at you; Save and Close buttons.
- **Priest class (implemented, first slice)**: `CLASS_PRIEST` = 2. `player.kod`: Priest ability table (the six levels listed below), fixed stats 50/50/50/1/50/1 (Might, Intellect, Stamina, Agility 1, Mysticism, Aim 1), god school Shal'ille for robe colours, level 1 spells granted at creation, starts in light robes (no mace). `ClassAllowsItem`: Priests cannot use any weapon, any armour except leather armour and robes, any helmet except circlet and ivy circlet, any shield except the small round (metal) shield, soldiers' / faction shields and the torch; `UserAttack` refuses fists ("A priest does not fight with fists. Cast a touch spell such as Holy Touch first."). Trainer: the Shal'ille priestess (`shalprst.kod`) also teaches Zap, Mana Focus, Hospice, Lightning Bolt, Holy Blaze, Shocking Fury, Purge, Lightning Wall and Truce (the class filter shows each player only their own list). Client: Priest in the class picker; env `M59_CLASS=2` preselects it for tests. **Mana Focus** now also boosts touch attacks (Zap, Holy Touch; `touchatk.kod` FindDamage) and its text says all attack spells (the attack-spell bonus was already class-wide). **Holy damage without karma**: Holy Blaze (reworked: plain holy attack, +20% vs undead, no healing, no karma) and Holy Touch (undead x2, no karma modifier). Tested: a new Priest got the right stats and class; Holy Touch / Minor Heal known; Holy Blaze and Lightning Bolt need level 3/4 knowledge ("no base"), Fireball refused as not class; mace, plate armour and knight's shield refused; metal shield, circlet, ivy circlet, soldier's shield, torch, leather armour and light robes allowed; helm, dagger, chain armour, bow refused; fists refused. Not tested: casting the spells in a fight, Mana Focus bonus numbers, the trainer's spoken lists.
- **Priest class design** (docs/class_overhaul_design.txt): stats 50/50/1/50/50/1, robes + leather only, six spell levels (L1 Holy Touch, Minor Heal, Forces of Light; L2 Zap, Mana Focus, Rescue; L3 Hospice, Remove Curse, Lightning Bolt; L4 Purify, Holy Blaze, Dazzle; L5 Shocking Fury, Major Heal, Purge; L6 Lightning Wall, Portal of Life, Truce). Mana Focus will boost all spell damage. Not implemented yet.
- No per-account class limit (any class, any number, within the 10 slots).
- Tank companion becomes the Warrior companion; Fighter companion dropped.

- Hotbar window no longer taller than its slots (slots look square again).
- Fighter companion matches a player who was just handed a bow: arrows 1-5 (a little more per level of its master's ECL), one shot per second. It used to hit for ~8 every 1.5 s.
- Companions (not playerbots): never limited by the reagent rule, always regenerate like 200 vigor, fighters have endless arrows and pick the arrow the target is weakest against (silver / fire / nerudite / plain).
- Group window: the targeted member is framed, dead / away members are dimmed and labelled, no "In a group of N" line.
- Target and Look windows show the whole character (as the original info window) for players, companions and bots, instead of only the torso.

### Mail, Who and Guild windows
- New top bar buttons: **Mail** (the original mailbox icon), **Who** and **Guild**.
- **Mail**: read, reply, delete and write letters. Like the original client the letters are handed over by the server and kept on your side (`userdata/mail_<character>.json`). New mail is fetched when you log in and when the server says you have some, unread letters are marked and the Mail button turns yellow.
- **Who**: the list of players who are online, kept up to date as people come and go. Double-click a name (or "Send mail") to write to them.
- **Guild**: your guild's name, your rank and its members, with Invite target, Exile, Leave, Hand over and Disband (greyed out when your rank may not do it). When the server offers to found a guild you can pick the name and the five rank titles.

### Mob aggro
- **Fixed: aggressive monsters ignored players who were close but not right next to them** (seen with the mummies in the Mausoleum). In proximity mode a monster now always goes for a visible player inside its aggro radius with a line of sight, however weak or strong the player is; before, the old hatred sum was often zero for easy monsters beyond a square or two. Tested with a mummy five squares away: it targeted the player and chased.
- Lines of sight (aggro, ranged attacks, spells) always use the coarse grid again; the "accurate walls" setting now only decides where creatures walk.

### Windows
- **No title bars any more**: drag any window by any empty spot (borders, labels, empty areas). Only the character window keeps its name on top. A small x closes the Look window.
- **Stats is now a tab** of the bottom-right window next to Inventory, Spells and Skills (the old Stats window is gone). Its lines wrap, so nothing is cut off at the edge.
- **Trade windows** (buy list, offers) open to the right of the Look window instead of on top of it, and their Buy / Cancel / Accept buttons stay in view while the item list scrolls.
- **New default layout** (windows sit flush against the screen edges, the top bar and each other; used until you move windows, or after Interface > Reset window layout): character top left with its target to the right and the group below it, map top right, chat bottom left, hotbar bottom centre, the pack (inventory, spells, skills, stats) bottom right. The Look window and every other window open in the middle of the screen.

### Growth bar
- A thin purple **growth bar** under the vigor bar in your character window shows the hidden counter behind getting tougher: the chance (shown in the tooltip and in the Stats window) that your next kill of a creature tougher than you adds a point of maximum health. Killing weaker creatures sets it back. It refreshes every few seconds (our server only).

### Details (stats) window
- New **Stats** button on the top bar opens a window with the numbers the server keeps behind the character, refreshed every 1.5 seconds: attributes (current value, base value and what effects such as Bless add or take away, in green or red), vitals (health, mana, vigor, carried bulk and weight), **offense** and **defense** ratings with what gear and effects contribute, weapon skill and proficiency, the **universal bonus**, your **chance to hit the creature you have targeted and its chance to hit you** (the server's own hit formula, 10 to 95 percent), and your **resistances and weaknesses** by attack type.
- Works with our server only (new extension message `EXT_MSG_DETAILS`); damage per hit, regeneration and more are planned.

### Window and layouts
- The client now starts **maximized**; F11 or the Interface window's "Full screen" switch toggles real full screen (and back to maximized).
- **Layout templates**: in the Interface window pick a ready-made window layout and press Use, or arrange your windows and save them under a name. Your own layouts are in `userdata/layouts`; layouts shipped with the client go in `client/layouts`.
- Music and ambient loops stop when you return to the login screen.
- Name tags are hidden while their owner is behind a wall or ceiling.

### Hand glow
- While you cast a spell with bare hands, your hand glows as in the original (the server sends a glow overlay that sits on the hand's hotspot).

### Attack icon
- The Attack button (hotbar and Skills list) now shows what you fight with: the weapon you wield, the **touch spell** you have on when your hands are empty (Holy Touch, Flame Touch, ...), or the punch icon for bare hands, and its tooltip names it. Fixed: while you were walking or fighting the server could drop the client's request (its spam check counts movement packets), so the button kept showing a fist after equipping a weapon; the weapon, details and target-health requests are now always answered. The server tells the client which weapon is in use whenever you change equipment (new server message, our server only).

### Cleanup
- The client is quiet by default: the per-stat and unhandled-message lines are only printed with `M59_TRACE=1`.
- Tooltips, the menu and the chat hint show your own key bindings.
- New `docs/TESTING.md` lists every test flag and environment variable.

### Interface window
- The Interface window now opens big enough to show all of its settings (it used to keep an old saved size and hide the newer ones), comes to the front, and stays on screen.

### Key remapping
- New **Keys...** button in the Interface window: change the keys for walking, stepping, turning, running, use, attack, rest, next target, chat, camera and the inventory / spells / skills tabs. Click an action, press the new key (Esc cancels). A key used twice swaps with the other action. Saved in `userdata/keys.json`; "Reset to defaults" restores the old keys. The hotbar stays on 1-0 and the arrow keys still walk.

### Camera
- The third-person camera no longer ends up behind walls, above ceilings or below floors when you zoom out: it now stops short of the real room surfaces, with a bit of clearance round the camera so a wall seen at a shallow angle does not poke through (idea from the meridian-shards project, written our own way).

### Room changes from the server
- Walls, floors and ceilings that the server re-textures (for example the lit and unlit spires in the Brax arena) now change on screen (official BP_CHANGE_TEXTURE).

### Testing
- Shop buying, selling to a merchant and player-to-player offers were tested end to end and work. New test hooks: `M59_TRADEITEM`, `M59_TRADEPLAYER`, and `M59_TRADEAUTO` now also answers offers.

### Weather
- **Rain** comes in five strengths, from a light sprinkle to a downpour, and sometimes a moderate or heavy shower is a **thunderstorm** with rare lightning flashes and rolling thunder (strikes about every 30 to 120 seconds, a little more often in a downpour).
- **Overcast**: when it rains outdoors the sky turns grey and dark and the light dims, more the harder it rains. Indoors you stay dry and it fades smoothly as you walk through a door.
- Tiny splashes where drops hit the ground near you, and a rain sound (and thunder) that is louder in heavier rain and muffled indoors. Sounds are made in code for now.
- **Weather zones**: each room is in a zone and each zone has its own weather. Mainland and Ko'catan have rain; deserts, badlands, lava, caves, mines, sewers and the underworld never do. A room class can set its own zone (zone 3 is reserved for a colder north, where snow will come later).
- The sandstorm spell is drawn as in the original. No seasons.
- New admin settings: rain on/off, chance to start and to go on per game hour (5 real minutes), chance of a thunderstorm. New Interface option "Weather (rain, snow, sand)".

### Companion bots
- New **Fighter** bot: shoots a bow from up to 9 squares (no archery skill needed) and fights in melee when the enemy is close.
- **Tank taunt**: enemies attacking other group members switch to the tank.
- Bots only fight enemies that are attacking the group (or that you are fighting). Melee bots wait until the enemy is within 7 squares; the mage and fighter fire from up to 12 squares with line of sight.
- Bots ignore enemies they cannot walk to instead of standing still.
- The Passive order now holds even after the bot receives a buff.
- Bots only teleport to you as a last resort (more than 25 squares away, or stuck for about 11 seconds). New admin setting to turn this off.

### Movement
- The server now uses the accurate room walk map for creatures and players (admin setting "Walls / line of sight accuracy"). Mobs and bots no longer get stuck where players can walk.
- Route following no longer gives up early, which stops bots pacing back and forth at corners.
- The client moves other creatures through every position the server reports, and teleports appear instantly instead of sliding through walls.

### Client
- **Water and other scrolling floors** now flow at the original speed. They were moving 16 times too fast, which made ponds like the one in Raza look like rivers.
- **Shops and trading**: right-click a shop keeper, banker or player and the Look window shows the trade buttons that apply (Buy, Sell / offer, and Withdraw / Deposit for bankers). Buying shows the seller's list with prices and amounts; offers to players or shop keepers open an offer window where the other side's answer appears and you accept or cancel.
- The Look window text is smaller and scrolls when a description is long.
- **Doors and animated walls**: the client now follows the server's wall changes (guild hall doors, secret walls, clock faces): texture changes, one-shot and looping animations, and walls that become passable, impassable or invisible.
- Gates and lifts now show the state the server sets when you enter a room (before, early messages were dropped and gates flickered between open and closed). New Interface option "Flashing wall textures" for walls that animate on their own.
- Top bar has separate **Bots** and **Group** buttons.
- Group state is cleared when you log in with another account.
- Interface window is scrollable and resizable.
- Debug log has a movement topic, and chat messages become markers in the log.

### Admin console
- Starts the server automatically when it is not running, and asks whether to stop it when you quit.
- New settings: bot teleport, wall accuracy. The death setting is now called "Lose HP / skills on death".

## 2026-10-19 - Initial public import
- Server (with admin console), client, tools and docs. Game assets are not included.

## 2026-10-20 (later): target ring, loot picking, vigor 200

- **Target ring (client):** the selected target gets a coloured ring on the floor (red = hostile creature, green = player/companion, yellow = NPC/other), sized to its sprite. Test hook: env `M59_AUTOTARGET=1` selects the nearest creature and turns to it.
- **Loot picking (client):** `PickObjectAt` now prefers loose (gettable) items over whatever else is under the cursor, so clicking loot lying on a corpse no longer hits the corpse. Not yet verified in a real kill.
- **Vigor:** the bar now runs to 200 for every class (food can fill it all the way). Resting alone only reaches the rest threshold, which is now 100 (was 80); a white tick on the bar marks it. Server: `piVigor_rest_threshold` default 100 in player.kod. Existing characters keep their stored value (fix with `send object <id> SetVigorRestThreshold amount int 100`).
- **Corpse pickup error (server):** double-clicking a corpse sent `ReqNewOwnerAttributes` to `DeadBody`, which had no handler (logged an interpreter error in channel/error). `DeadBody` now answers FALSE (a corpse can never be picked up).
- **Companion pathing:** a companion more than 4 squares from its master now always walks a planned route (breadth-first over the room grid, up to 1200 cells, re-planned every 5 seconds or when the master moves away from the route's end). `MoveTowards` got a `use_path` parameter; only `Companion.MoveToMaster` sets it. The old last-resort jump to the master (stuck ~11 s, or 25+ squares) is unchanged, and also covers masters in a region with no route.
- **Client:** a paralysis flag left over from an old room is cleared on room entry. Test log line `[autowalk]` prints position every half second during `--autowalk`.
