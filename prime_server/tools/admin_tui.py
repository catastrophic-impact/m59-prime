#!/usr/bin/env python3
"""Meridian 59 Prime server admin (terminal, mouse works).  Run: prime_server/scripts/admin-tui.sh

Start / stop (saves first) / restart the server, save the game, change the Prime rules, see the accounts and the logs,
and send any admin command.  Talks to the maintenance port (127.0.0.1:9999, this machine only).
Keys: Ctrl+Q quit, F5 refresh.
"""
import asyncio
import itertools
import os
import re
import subprocess
import time

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, RichLog, Static, TabbedContent, TabPane

HOST, ADMIN_PORT = "127.0.0.1", int(os.environ.get("PRIME_ADMIN_PORT", "9999"))
WORK = os.environ.get("PRIME_WORK", os.path.expanduser("~/boxes/m59-box/src/prime_work"))
OUT = os.path.join(WORK, "build", "server")
BOX = os.environ.get("PRIME_BOX", "m59-box")
IN_FLATPAK = os.path.exists("/.flatpak-info")     # VS Code sandbox: the server runs in the distrobox on the host
CLIENT_SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "prime_client", "scripts"))
IN_BOX = bool(os.environ.get("CONTAINER_ID"))

# The Prime rules (kod/object/prime/primerules.kod): name, what it does
RULES = [
    ("piDeathItemDrop", "Death costs belongings: 0 never, 1 killed by player, 2 killed by monster, 3 always"),
    ("piDeathStatLoss", "Death costs max health / skill %: 0 never, 1 killed by player, 2 by monster, 3 always"),
    ("piReagentMode", "Reagents: 0 mandatory, 1 not needed, 2 optional (weaker spell without them)"),
    ("piNoReagentPercent", "Power (%) of a spell cast without reagents (mode 2)"),
    ("pbUnlimitedEating", "Eating always possible: 1 yes, 0 no"),
    ("pbBowNoAmmo", "Bows shoot without arrows: 1 yes, 0 no"),
    ("piBowNoAmmoPercent", "Damage (%) of an arrowless shot"),
    ("piDaggerDoublePercent", "Chance (%) that a dagger hit strikes twice"),
    ("pbClassSystem", "Class system: 1 on (characters have a class), 0 off (original characters). Each character plays only in its own mode"),
    ("pbCompanionBots", "Companion bots (temporary class companions): 1 on, 0 off"),
    ("pbBotMoveLog", "TEST ONLY: log companion bot movement (BOTMOVE lines in the debug log, channel/debug.txt): 1 on, 0 off"),
    ("piBotHuntFailLimit", "Playerbots: failed attempts in a row to find or reach a foe after which a hunter gives its hunt up and picks another activity (a kill resets the count)"),
    ("piMobLeashSecs", "Monsters: seconds a chase may get nowhere before the monster gives its target up and walks back to where it stood (0 = off, it chases for ever)"),
    ("pbMobLeashHeal", "Monsters: 1 = a monster that gave a chase up is healed to full"),
    ("pbMobAggroScan", "Monsters: 1 = a monster with no target looks about once a second for someone in sight (also someone standing still); 0 = it notices only movement"),
    ("pbMobAggroPath", "Monsters: 1 = a monster does not notice someone it has no walking route to (casters excepted); 0 = sight alone"),
    ("pbMobAggroLOS", "Monsters: 1 = a monster notices someone only with a clear line of sight (not through walls); 0 = distance only, as before"),
    ("pbMurderNotPermanent", "Murder is not permanent: 1 = a murderer (red) who dies becomes an outlaw (orange), an outlaw who dies is clean; 0 = murderers stay red until pardoned"),
    ("piTownLife", "Town life: 0 wandering townsfolk (client crowds), 1 playerbots instead, 2 both"),
    ("piBotTimeScale", "Playerbot activity timers in percent of real time (100 normal, 10 = ten times faster, for testing)"),
    ("piPlayerBotCount", "How many playerbots are in the game at once"),
    ("piBotShowDoing", "Playerbots: 1 = the info window of a bot says what it is doing (\"Currently: heading to the bank...\"), 0 = description only"),
    ("pbFactionCompanions", "The old faction companion (bond, vault, hall): 1 on, 0 off (disabled; the code is kept for later)"),
    ("piMaxBots", "Most companion bots at once (the group is 5 seats; a faction companion takes one)"),
    ("piBotResummonSec", "Seconds before another bot may be summoned after one fell (0, 30, 60 or 300)"),
    ("pbBotSplitXP", "XP split: with bots in the group, a kill's XP is divided by all seats: 1 on, 0 off"),
    ("piSpiritManaPerHit", "Mana a paladin gets back for each hit that lands with a Spiritual Sword or Hammer"),
    ("pbSpiritNeutral", "Spirit weapons ignore a monster's resistance to holy: 1 yes, 0 no"),
    ("piBraxAutoSolveSec", "Brax arena solves itself every this many seconds (0 = off, the original game)"),
]


def wrap(argv):
    """Run argv where the server lives (the distrobox)."""
    if IN_BOX:
        return argv
    return (["flatpak-spawn", "--host"] if IN_FLATPAK else []) + ["distrobox", "enter", BOX, "--"] + argv


class AdminLink:
    """One TCP session to the maintenance port; commands are serialised."""

    def __init__(self):
        self.reader = self.writer = None
        self.lock = asyncio.Lock()
        self._n = itertools.count(1)

    @property
    def connected(self):
        return self.writer is not None and not self.writer.is_closing()

    async def connect(self):
        self.reader, self.writer = await asyncio.wait_for(asyncio.open_connection(HOST, ADMIN_PORT), 3)
        await self._drain(0.3)

    async def close(self):
        if self.writer:
            try:
                self.writer.write(b"quit\r")
                self.writer.close()
            except Exception:
                pass
        self.reader = self.writer = None

    async def _drain(self, idle):
        buf = b""
        while True:
            try:
                d = await asyncio.wait_for(self.reader.read(65536), idle)
            except asyncio.TimeoutError:
                return buf
            if not d:
                raise ConnectionError("closed")
            buf += d

    async def run(self, cmd, timeout=60):
        try:
            return await self._run(cmd, timeout)
        except (ConnectionError, OSError):
            await self.close()
            return await self._run(cmd, timeout)

    async def _run(self, cmd, timeout):
        async with self.lock:
            if not self.connected:
                await self.connect()
            marker = f"PRIMETUI{next(self._n)}END"
            self.writer.write(f"{cmd}\r".encode("latin-1", "replace"))
            self.writer.write(f"show account {marker}\r".encode())      # silent end-of-reply marker
            await self.writer.drain()
            buf, end = b"", time.monotonic() + timeout
            while marker.encode() not in buf:
                left = end - time.monotonic()
                if left <= 0:
                    break
                try:
                    d = await asyncio.wait_for(self.reader.read(65536), left)
                except asyncio.TimeoutError:
                    break
                if not d:
                    self.writer = None
                    raise ConnectionError("closed")
                buf += d
            await self._drain(0.12)
        lines = buf.decode("latin-1").replace("\r", "").split("\n")
        out = [ln for ln in lines if marker not in ln]
        if out and out[0].startswith("> "):
            out = out[1:]
        return "\n".join(out).strip("\n")


def tail(path, n=60):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 20000))
            return f.read().decode("latin-1").splitlines()[-n:]
    except OSError:
        return [f"(no {os.path.basename(path)} yet)"]


class PrimeAdmin(App):
    TITLE = "Meridian 59 Prime - server admin"
    BINDINGS = [Binding("ctrl+q", "quit", "Quit"), Binding("f5", "refresh", "Refresh")]
    CSS = """
    Screen { layers: base overlay; }
    #loading { layer: overlay; width: 100%; height: 100%; content-align: center middle; text-align: center; background: $surface 92%; color: $text; text-style: bold; }
    #status { height: 5; padding: 0 1; border: round $accent; }
    .bar { height: 3; }
    .bar Button { margin-right: 1; }
    #msg { height: 1; padding: 0 1; color: $text-muted; }
    #log, #out { height: 1fr; border: round $primary; }
    #rules, #accounts, #bots { height: 1fr; }
    TabbedContent { height: 1fr; }
    TabPane { height: 1fr; padding: 0; }
    #rulebar { dock: bottom; height: 3; }
    .bar Input { width: 24; }
    #accounts, #chars { height: 1fr; }
    #ruleval { width: 20; }
    """

    def __init__(self):
        super().__init__()
        self.link = AdminLink()
        self.prime_id = None
        self.busy = False
        self.acct_delete_armed = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("checking ...", id="status")
        with Horizontal(classes="bar"):
            yield Button("Start", id="start", variant="success")
            yield Button("Stop (saves first)", id="stop", variant="error")
            yield Button("Restart", id="restart", variant="warning")
            yield Button("Save game", id="save", variant="primary")
        yield Label("", id="msg")
        with TabbedContent():
            with TabPane("Server", id="tab-server"):
                yield RichLog(id="log", wrap=False, highlight=False, markup=False)
            with TabPane("Rules", id="tab-rules"):
                yield DataTable(id="rules", cursor_type="row")
                with Horizontal(id="rulebar"):
                    yield Label("New value for the selected rule:")
                    yield Input(id="ruleval", placeholder="number")
                    yield Button("Set", id="ruleset", variant="primary")
            with TabPane("Accounts", id="tab-acc"):
                yield DataTable(id="accounts", cursor_type="row")
                yield Label("Account access: blank = User, A = Admin, D = DM, G = Guest. This is separate from character class; full in-game admin access needs an Admin account and an Admin character.")
                with Horizontal(classes="bar"):
                    yield Input(id="newname", placeholder="new account name")
                    yield Input(id="newpass", placeholder="password", password=True)
                    yield Input(id="newtype", placeholder="account type: user | admin | dm", value="user")
                    yield Button("Create", id="mkacct", variant="primary")
                with Horizontal(classes="bar"):
                    yield Button("Create Admin character in selected account", id="mkadmin", variant="warning")
                    yield Button("Create DM character in selected account", id="mkdm", variant="warning")
                with Horizontal(classes="bar"):
                    yield Input(id="editname", placeholder="new name for the selected account")
                    yield Button("Rename", id="acc_rename", variant="primary")
                    yield Input(id="editpass", placeholder="new password", password=True)
                    yield Button("Set password", id="acc_pass", variant="primary")
                with Horizontal(classes="bar"):
                    yield Button("Ban", id="acc_ban", variant="error")
                    yield Button("Unban", id="acc_unban", variant="success")
                    yield Button("Delete account", id="acc_delete", variant="error")
            with TabPane("Characters", id="tab-chars"):
                yield DataTable(id="chars", cursor_type="row")
                yield Label("Character class is separate from account type. The server can create Admin/DM characters, but cannot promote an existing character.")
                with Horizontal(classes="bar"):
                    yield Button("Create Admin character for selected character's account", id="mkadmin_char", variant="warning")
                    yield Button("Create DM character for selected character's account", id="mkdm_char", variant="warning")
                with Horizontal(classes="bar"):
                    yield Input(id="clvl", placeholder="class level 1-6", value="3")
                    yield Input(id="cpct", placeholder="percent", value="70")
                    yield Button("Give class level", id="dolevel", variant="primary")
                with Horizontal(classes="bar"):
                    yield Input(id="chp", placeholder="max health", value="500")
                    yield Button("Set health", id="dohp", variant="primary")
                    yield Input(id="cgold", placeholder="shillings", value="5000")
                    yield Button("Give shillings", id="dogold", variant="primary")
            with TabPane("Bots", id="tab-bots"):
                yield DataTable(id="bots", cursor_type="row")
            with TabPane("Console", id="tab-console"):
                yield Input(id="cmd", placeholder="admin command, Enter to send (e.g. show accounts)")
                yield RichLog(id="out", wrap=True, markup=False)
        yield Footer()
        yield Static("Loading ...", id="loading")

    def set_loading(self, text=None):
        """Cover the whole UI with a message (clicks cannot reach the tabs below) until set_loading() clears it."""
        w = self.query_one("#loading", Static)
        if text:
            w.update(text)
        w.display = bool(text)

    async def on_mount(self):
        r = self.query_one("#rules", DataTable)
        r.add_columns("Rule", "Value", "What it does")
        a = self.query_one("#accounts", DataTable)
        a.add_columns("ID", "Account", "Access", "Email", "Suspended", "Credits", "Last login")
        c = self.query_one("#chars", DataTable)
        c.add_columns("Account", "Object", "Class", "Name")
        b = self.query_one("#bots", DataTable)
        b.add_columns("Bot", "Class", "Activity", "Status", "Current map")
        self.set_interval(3, self.refresh_status)
        self.set_interval(10, self.refresh_bots)
        self.run_worker(self.first_load(), exclusive=False)

    async def first_load(self):
        """Startup work runs in a worker so the UI keeps drawing; the overlay blocks input until it is done."""
        self.set_loading("Loading ... (checking the server)")
        try:
            await self.refresh_status()
            if await self.admin_up():
                if await self.ensure_admin_account():
                    self.say("Admin character created: restarting the server once so it takes effect ...")
                    await self.stop_server()
                    await self.start_server()
            await self.action_refresh()
        finally:
            self.set_loading(None)

    async def on_unmount(self):
        await self.link.close()      # a session that is just dropped keeps the server's admin port busy for a while

    # ------------------------------------------------------------------ status
    def say(self, text):
        self.query_one("#msg", Label).update(text)
        if self.query_one("#loading", Static).display:       # a long step: show its progress on the cover too
            self.query_one("#loading", Static).update(text)

    async def admin_up(self):
        """Is the server answering the admin port? Only through our one persistent session: probing the ports with extra connections
        (or the game port at all) garbles the server's admin session."""
        try:
            if not self.link.connected:
                await self.link.connect()
            await self.link.run("show account PRIMEPING", 6)
            return True
        except Exception:
            await self.link.close()
            return False

    async def port_open(self, port):
        """Plain TCP check of the web client's port only (never the game or admin ports: see admin_up)."""
        try:
            _, w = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), 2)
            w.close()
            return True
        except Exception:
            return False

    async def refresh_status(self):
        up = await self.admin_up()
        txt = "SERVER " + ("RUNNING" if up else "STOPPED (or not answering)")
        if up and not self.busy:
            try:
                out = await self.link.run("show accounts", 6)
                txt += f"   accounts: {max(0, len([l for l in out.splitlines() if l.strip()]) - 1)}"
            except Exception:
                pass
        web = await self.port_open(5173)
        txt += "\nGame port 5960 (raw game protocol, not for browsers)   Admin port 9999 (this tool)"
        txt += "\nWeb client http://127.0.0.1:5173 " + ("is UP" if web else "is DOWN (Start brings it up)")
        self.query_one("#status", Static).update(txt)
        log = self.query_one("#log", RichLog)
        log.clear()
        for name in ("log.txt", "error.txt"):
            log.write(f"== {name} (last lines)")
            for ln in tail(os.path.join(OUT, "channel", name), 25):
                log.write(ln)

    async def action_refresh(self):
        self.set_loading("Loading ...")
        try:
            await self._refresh()
        finally:
            self.set_loading(None)

    async def _refresh(self):
        await self.refresh_status()
        if not await self.admin_up():
            return
        try:
            await self.load_rules()
            await self.load_accounts()
            await self.load_chars()
            await self.load_bots()
        except Exception as e:
            self.say(f"refresh failed: {e}")

    def bot_names(self):
        """pbn_* resource id -> display name, from the overlay source."""
        if not hasattr(self, "_bot_names"):
            names = {}
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "overlay", "kod", "object", "prime", "primeplayerbots.kod")
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    names = dict(re.findall(r'^\s*(pbn_\w+)\s*=\s*"([^"]*)"', f.read(), re.M))
            except OSError:
                pass
            self._bot_names = names
        return self._bot_names

    async def load_bots(self):
        """List persistent playerbots and their live activity, phase, and room."""
        if getattr(self, "_loading_bots", False):
            return
        self._loading_bots = True
        try:
            await self._load_bots()
        finally:
            self._loading_bots = False

    def room_names(self):
        """Room number -> map name, read once from the build tree (blakston.khd RID_ constants + the room .kod files)."""
        if not hasattr(self, "_room_names"):
            tree = os.path.join(WORK, "build", "tree", "kod")
            rids, names = {}, {}
            try:
                with open(os.path.join(tree, "include", "blakston.khd"), encoding="utf-8", errors="replace") as f:
                    rids = {k: int(v) for k, v in re.findall(r"^\s*(RID_\w+)\s*=\s*(\d+)", f.read(), re.M)}
                for root, _, files in os.walk(os.path.join(tree, "object", "active", "holder", "room")):
                    for fn in files:
                        if not fn.endswith(".kod"):
                            continue
                        with open(os.path.join(root, fn), encoding="utf-8", errors="replace") as f:
                            text = f.read()
                        num = re.search(r"^\s*piRoom_num\s*=\s*(RID_\w+|\d+)", text, re.M)
                        res = re.search(r"^\s*vrName\s*=\s*(\w+)", text, re.M)
                        label = re.search(rf'^\s*{re.escape(res.group(1))}\s*=\s*"([^"]*)"', text, re.M) if res else None
                        if num and label:
                            n = num.group(1)
                            names[rids.get(n, int(n) if n.isdigit() else 0)] = label.group(1)
            except OSError:
                pass
            self._room_names = names
        return self._room_names

    def map_name(self, rid):
        if not rid:
            return "limbo"
        return self.room_names().get(rid, f"RID {rid}")

    async def _load_bots(self):
        table = self.query_one("#bots", DataTable)
        out = await self.link.run("show instances PlayerBot")
        ids = list(dict.fromkeys(re.findall(r"OBJECT\s+(\d+)", out)))
        # piDoing values of playerbot.kod (PBD_*); keep in step with that list
        activities = {
            1: "Idle", 2: "Relaxing", 3: "Walking", 4: "Errand", 5: "Talking",
            6: "Traveling", 7: "Reading globe", 8: "Leaving town", 9: "Relaxing at inn", 10: "Shopping", 11: "Hunting", 12: "In the underworld",
        }
        phases = {0: "resting", 1: "walking", 2: "talking"}
        names = self.bot_names()
        if not hasattr(self, "_bot_name_cache"):
            self._bot_name_cache = {}       # object id -> display name (a bot's name never changes; saves one admin call per bot)
        if not hasattr(self, "_bot_class_cache"):
            self._bot_class_cache = {}      # object id -> class name (companion kind 4-7), fixed for a bot's life
        kinds = {4: "Warrior", 5: "Monk", 6: "Paladin", 7: "Elementalist"}
        rows = []
        for object_id in ids:
            detail = await self.link.run(f"show object {object_id}")

            def number(prop):
                match = re.search(rf"\b{prop}\s*(?::|=)?\s*(?:INT\s*)?(\d+)", detail, re.I)
                return int(match.group(1)) if match else None

            bot_id = number("piBotId")
            doing = number("piDoing")
            phase = number("piPhase")
            room = number("piNavRid")
            name = self._bot_name_cache.get(object_id)
            if name is None:
                name_out = await self.link.run(f"send object {object_id} GetName")
                name_match = re.search(r'(?:STRING|RESOURCE)\s+["\']?([^\r\n"\']+)', name_out)
                name = name_match.group(1).strip() if name_match else f"Bot {bot_id or object_id}"
                name = names.get(name, name)
                self._bot_name_cache[object_id] = name
            cls = self._bot_class_cache.get(object_id)
            if cls is None:
                kind_out = await self.link.run(f"send object {object_id} GetKind")
                kind_match = re.search(r"INT\s+(\d+)", kind_out)
                cls = kinds.get(int(kind_match.group(1)), "Adventurer") if kind_match else "?"
                self._bot_class_cache[object_id] = cls
            activity = activities.get(doing, f"Activity {doing}")
            # the final map of a journey (a hunter on its way is still piDoing hunt), else the next map on the way
            dest = number("piJourneyRid") or (number("piDoingArg") if doing == 6 else None)
            if dest and dest != room:
                activity = f"Traveling to: {self.map_name(dest)}"
            rows.append((object_id, (name, cls, activity, phases.get(phase, "unknown"), self.map_name(room))))
        keep = table.cursor_row if table.row_count else 0
        table.clear()
        for object_id, cells in rows:
            table.add_row(*cells, key=object_id)
        if table.row_count:
            table.move_cursor(row=min(keep, table.row_count - 1))

    async def refresh_bots(self):
        if not self.busy and await self.admin_up():
            await self.load_bots()

    # ------------------------------------------------------------------ server control
    def spawn_server(self):
        cmd = f"cd {OUT} && exec ./blakserv </dev/null >console.out 2>&1"
        subprocess.Popen(wrap(["bash", "-c", cmd]), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)

    def kill_server(self):
        script = 'for p in $(pgrep -x blakserv); do case "$(readlink /proc/$p/cwd)" in *prime_work*|"") kill $p;; esac; done'
        subprocess.run(wrap(["bash", "-c", script]), capture_output=True, timeout=30)

    async def start_client(self):
        """The web client (gateway ws 8059 + dev web server 5173), so that Start brings up everything needed to play."""
        if await self.port_open(5173):
            return
        self.say("Starting the web client ...")
        script = os.path.join(CLIENT_SCRIPTS, "run_dev.sh")
        await asyncio.to_thread(lambda: subprocess.run(wrap(["env", f"PRIME_WORK={WORK}", "bash", script]), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120))
        for _ in range(30):
            if await self.port_open(5173):
                return
            await asyncio.sleep(2)
        self.say("The web client did not come up: see client_build/vite.log and gateway.log in the work folder.")

    async def stop_client(self):
        script = os.path.join(CLIENT_SCRIPTS, "stop_dev.sh")
        await asyncio.to_thread(lambda: subprocess.run(wrap(["env", f"PRIME_WORK={WORK}", "bash", script]), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60))

    async def start_server(self):
        if await self.admin_up():
            self.say("The server is already running.")
            await self.start_client()
            return
        if not os.path.exists(os.path.join(OUT, "blakserv")):
            self.say(f"No server build at {OUT}: run prime_server/scripts/build.sh --fresh first.")
            return
        self.say("Starting the server (about a minute) ...")
        await asyncio.to_thread(self.spawn_server)
        for _ in range(120):
            await asyncio.sleep(2)
            if await self.admin_up():
                self.prime_id = None
                if await self.ensure_admin_account():
                    self.say("Admin character created: restarting the server once so it takes effect ...")
                    await self.stop_server()
                    await self.start_server()
                    return
                await self.start_client()
                if await self.port_open(5173):
                    self.say("Everything is running: play at http://127.0.0.1:5173")
                return
        self.say("The server did not answer in 4 minutes: look at the log.")

    async def stop_server(self):
        if not await self.admin_up():
            await self.stop_client()
            self.say("The server is not running (or not answering); the web client was stopped.")
            return
        self.say("Saving the game ...")
        try:
            out = await self.link.run("save game", 120)
            self.say("Saved: " + out.strip().splitlines()[-1][:80] if out.strip() else "Saved.")
        except Exception as e:
            self.say(f"Save failed ({e}): the server was NOT stopped.")
            return
        await self.link.close()
        await self.stop_client()
        await asyncio.to_thread(self.kill_server)
        for _ in range(30):
            await asyncio.sleep(1)
            if not await self.admin_up():
                self.say("Everything was saved and stopped.")
                return
        self.say("The server is still answering after 30 s: it may be saving; check the log.")

    async def control(self, what):
        if self.busy:
            return
        self.busy = True
        self.set_loading({"start": "Starting the server ...", "stop": "Saving and stopping ...", "restart": "Restarting ...",
                          "save": "Saving ..."}.get(what, "Working ..."))
        try:
            if what == "start":
                await self.start_server()
            elif what == "stop":
                await self.stop_server()
            elif what == "restart":
                await self.stop_server()
                await self.start_server()
            elif what == "save":
                self.say("Saving ...")
                out = await self.link.run("save game", 120)
                self.say(out.strip().splitlines()[-1][:100] if out.strip() else "Saved.")
        except Exception as e:
            self.say(f"Failed: {e} (is the server running?)")
        finally:
            self.busy = False
        self.set_loading("Loading ...")
        try:
            await self.refresh_status()
            await self._refresh()
        finally:
            self.set_loading(None)

    @on(Button.Pressed, "#start")
    async def _start(self):
        self.run_worker(self.control("start"))

    @on(Button.Pressed, "#stop")
    async def _stop(self):
        self.run_worker(self.control("stop"))

    @on(Button.Pressed, "#restart")
    async def _restart(self):
        self.run_worker(self.control("restart"))

    @on(Button.Pressed, "#save")
    async def _save(self):
        self.run_worker(self.control("save"))

    # ------------------------------------------------------------------ rules
    async def find_prime(self):
        if self.prime_id:
            return self.prime_id
        await self.link.run("send class system GetPrime")
        out = await self.link.run("show instances primeclasses")
        for tok in out.split("OBJECT")[1:2]:
            self.prime_id = tok.split()[0]
        return self.prime_id

    async def load_rules(self, keep=0):
        pid = await self.find_prime()
        table = self.query_one("#rules", DataTable)
        table.clear()
        if not pid:
            return
        out = await self.link.run(f"show object {pid}")
        vals = {}
        for ln in out.splitlines():
            if "=" in ln:
                left, right = ln.split("=", 1)
                vals[left.strip(": ").strip()] = right.strip()
        for name, doc in RULES:
            table.add_row(name, vals.get(name, "?").replace("INT ", ""), doc, key=name)
        table.move_cursor(row=keep)

    @on(Button.Pressed, "#ruleset")
    async def _ruleset(self):
        table = self.query_one("#rules", DataTable)
        val = self.query_one("#ruleval", Input).value.strip()
        if table.row_count == 0 or not val.lstrip("-").isdigit():
            self.say("Select a rule and type a whole number.")
            return
        name = RULES[table.cursor_row][0]
        pid = await self.find_prime()
        await self.link.run(f"set object {pid} {name} int {val}")
        self.say(f"{name} = {val} (live now; press Save game to keep it over a restart).")
        await self.load_rules(keep=table.cursor_row)

    # ------------------------------------------------------------------ accounts and console
    async def load_accounts(self):
        table = self.query_one("#accounts", DataTable)
        keep = table.cursor_row if table.row_count else 0
        table.clear()
        out = await self.link.run("show accounts")
        for ln in out.splitlines():
            parts = ln.split()
            if len(parts) < 4:
                continue
            m = re.fullmatch(r"(\d+)([ADG]?)", parts[0])
            if not m:
                continue
            account_id, marker = m.groups()
            access = {"": "User", "A": "Admin", "D": "DM", "G": "Guest"}[marker]
            # The suspended-time field is blank for an active account, so its
            # omission shifts the remaining fixed-width columns one place.
            suspended = parts[3] if parts[3].endswith("h") else "—"
            credits_at = 4 if suspended != "—" else 3
            credits = parts[credits_at] if len(parts) > credits_at else "—"
            last_login = " ".join(parts[credits_at + 1 :]) or "—"
            table.add_row(account_id, parts[1], access, parts[2], suspended, credits, last_login, key=account_id)
        if table.row_count:
            table.move_cursor(row=min(keep, table.row_count - 1))

    def selected_acct(self):
        """The id and name of the selected account row, else None."""
        table = self.query_one("#accounts", DataTable)
        if table.row_count == 0:
            self.say("No account selected.")
            return None
        row = table.get_row_at(table.cursor_row)
        if len(row) < 2 or not row[0].isdigit():
            self.say("Select an account row (not the heading).")
            return None
        return row[0], row[1]

    async def ensure_admin_account(self):
        """The admin account (name $M59_ADMIN_ACCOUNT, default admin) always exists, with an admin character, so the in-game admin console is at hand. Its password is $M59_ADMIN_PASSWORD, or a random one shown once when the account is made."""
        acct_name = os.environ.get("M59_ADMIN_ACCOUNT", "admin")
        out = await self.link.run(f"show account {acct_name}")
        if "Cannot find account" in out:
            import secrets
            pw = os.environ.get("M59_ADMIN_PASSWORD") or secrets.token_urlsafe(9)
            await self.link.run(f"create account {acct_name} {pw} {acct_name} none")
            self.say(f"Admin account '{acct_name}' created, password: {pw} (write it down: it is not stored anywhere else)")
            out = await self.link.run(f"show account {acct_name}")
        m = re.search(rf"^\s*(\d+)A?\s+{re.escape(acct_name)}\b", out, re.M)
        if not m:
            return False
        acct = m.group(1)
        created = " Admin " not in out      # a new admin character only works after a server restart
        have = len(re.findall(rf"^\s*{acct}\s+\d+\s", out, re.M))
        # ordinary slots first and the admin character last: the character list shows the newest first, so the Admin slot is the first row
        if " Admin " not in out:
            for _ in range(max(0, 9 - have)):
                await self.link.run(f"create user {acct}")
            await self.link.run(f"create admin {acct}")
        else:
            for _ in range(max(0, 10 - have)):
                await self.link.run(f"create user {acct}")
        await self.ensure_dev_admin(acct_name, os.environ.get("M59_ADMIN_CHAR", "dadmin"))
        return created

    async def ensure_dev_admin(self, account, charname):
        """Name an unnamed (User123456) admin character of the account, so it is not <New character> in the client."""
        out = await self.link.run(f"show account {account}")
        m = re.search(r"^\s*\d+\s+(\d+)\s+Admin\s+User\d+", out, re.M)
        if m:
            await self.link.run(f"send o 0 AdminChangeUserName oUser o {m.group(1)} sName q {charname}")
            # never logged in = listed as "<New character>" by the client: mark the character as already created
            await self.link.run(f"set object {m.group(1)} piLastLoginTime int 1000000")

    async def account_action(self, what):
        sel = self.selected_acct()
        if not sel:
            return
        acct, name = sel
        if what == "rename":
            new = self.query_one("#editname", Input).value.strip()
            if not new:
                return self.say("Type the new name first.")
            cmd = f"set account name {acct} {new}"
        elif what == "pass":
            new = self.query_one("#editpass", Input).value.strip()
            if not new:
                return self.say("Type the new password first.")
            cmd = f"set account password {acct} {new}"
        elif what == "ban":
            cmd = f"suspend account 87600 {acct}"          # ten years
        elif what == "unban":
            cmd = f"unsuspend account {acct}"
        else:
            if self.acct_delete_armed != acct:
                self.acct_delete_armed = acct
                return self.say(f"Delete account {name} and its characters for good? Press Delete again to confirm.")
            self.acct_delete_armed = None
            cmd = f"delete account {acct}"
        out = await self.link.run(cmd)
        self.say((out.strip().splitlines() or ["done"])[-1][:120])
        await self.load_accounts()

    @on(Button.Pressed, "#acc_rename")
    async def _acc_rename(self):
        await self.account_action("rename")

    @on(Button.Pressed, "#acc_pass")
    async def _acc_pass(self):
        await self.account_action("pass")

    @on(Button.Pressed, "#acc_ban")
    async def _acc_ban(self):
        await self.account_action("ban")

    @on(Button.Pressed, "#acc_unban")
    async def _acc_unban(self):
        await self.account_action("unban")

    @on(Button.Pressed, "#acc_delete")
    async def _acc_delete(self):
        await self.account_action("delete")

    async def load_chars(self):
        table = self.query_one("#chars", DataTable)
        keep = table.cursor_row if table.row_count else 0
        table.clear()
        out = await self.link.run("show users")
        for ln in out.splitlines():
            parts = ln.split()
            # "   2    6305 User    Tele"  (blank creator slots have a long numeric name and trailing columns)
            if len(parts) == 4 and parts[0].isdigit() and parts[1].isdigit() and parts[2] in ("User", "Admin", "DM", "Creator"):
                table.add_row(parts[0], parts[1], parts[2], parts[3], key=parts[1])
        if table.row_count:
            table.move_cursor(row=min(keep, table.row_count - 1))

    def selected_char(self):
        table = self.query_one("#chars", DataTable)
        if table.row_count == 0:
            self.say("No character selected.")
            return None
        return table.get_row_at(table.cursor_row)

    async def prime_call(self, text):
        pid = await self.find_prime()
        return await self.link.run(f"send object {pid} {text}")

    @on(Button.Pressed, "#dolevel")
    async def _dolevel(self):
        row = self.selected_char()
        if not row:
            return
        lvl = self.query_one("#clvl", Input).value.strip() or "3"
        pct = self.query_one("#cpct", Input).value.strip() or "70"
        out = await self.prime_call(f"AdminGiveClassLevel oTarget object {row[1]} iLevel int {lvl} iPercent int {pct}")
        self.say(f"{row[3]}: class level {lvl} abilities at {pct}% (a character with no class gets nothing)." if "INT 1" in out else f"{row[3]} has no class or the call failed.")

    @on(Button.Pressed, "#dohp")
    async def _dohp(self):
        row = self.selected_char()
        if not row:
            return
        hp = self.query_one("#chp", Input).value.strip() or "500"
        out = await self.prime_call(f"AdminSetHealth oTarget object {row[1]} iHealth int {hp}")
        got = [l for l in out.splitlines() if "INT" in l]
        self.say(f"{row[3]}: max health now {got[-1].split('INT')[-1].strip() if got else '?'} (capped at 100 + stamina).")

    @on(Button.Pressed, "#dogold")
    async def _dogold(self):
        row = self.selected_char()
        if not row:
            return
        g = self.query_one("#cgold", Input).value.strip() or "5000"
        await self.prime_call(f"AdminGiveGold oTarget object {row[1]} iAmount int {g}")
        self.say(f"{row[3]} was given {g} shillings.")

    @on(Button.Pressed, "#mkacct")
    async def _mkacct(self):
        name = self.query_one("#newname", Input).value.strip()
        pw = self.query_one("#newpass", Input).value.strip()
        typ = self.query_one("#newtype", Input).value.strip().lower() or "user"
        if not name or not pw or typ not in ("user", "admin", "dm", "guest"):
            self.say("Give a name, a password and a type: user, admin, dm or guest.")
            return
        # a normal account is made with all its character slots (NumSlots in blakserv.cfg, 10 at most)
        cmd = f"create automated {name} {pw} {name}@prime.local" if typ == "user" else f"create account {typ} {name} {pw} {name}@prime.local"
        out = await self.link.run(cmd)
        self.say(out.strip().splitlines()[-1] if out.strip() else "done")
        await self.load_accounts()

    @on(Button.Pressed, "#mkdm")
    async def _mkdm(self):
        await self._mkchar("dm")

    @on(Button.Pressed, "#mkadmin_char")
    async def _mkadmin_char(self):
        await self._mkchar_for_selected("admin")

    @on(Button.Pressed, "#mkdm_char")
    async def _mkdm_char(self):
        await self._mkchar_for_selected("dm")

    async def _mkchar_for_selected(self, kind):
        row = self.selected_char()
        if not row:
            return
        # `show users` begins each row with its account id, so this is the same
        # create-admin/create-dm operation as in Accounts, now reachable in context.
        out = await self.link.run(f"create {kind} {row[0]}")
        self.say((out.strip().splitlines() or [f"Created a {kind.upper()} character in account {row[0]}"])[-1][:120])
        await self.load_chars()

    @on(Button.Pressed, "#mkadmin")
    async def _mkadmin(self):
        await self._mkchar("admin")

    async def _mkchar(self, kind):
        table = self.query_one("#accounts", DataTable)
        if table.row_count == 0:
            self.say("No account selected.")
            return
        acct = table.get_row_at(table.cursor_row)[0].split()[0].rstrip("ADG")
        out = await self.link.run(f"create {kind} {acct}")
        self.say((out.strip().splitlines() or ["done"])[-1][:120])
        await self.load_chars()

    @on(Input.Submitted, "#cmd")
    async def _cmd(self, ev):
        cmd = ev.value.strip()
        ev.input.value = ""
        if not cmd:
            return
        out = self.query_one("#out", RichLog)
        out.write(f"> {cmd}")
        try:
            out.write(await self.link.run(cmd))
        except Exception as e:
            out.write(f"failed: {e}")


if __name__ == "__main__":
    PrimeAdmin().run()
