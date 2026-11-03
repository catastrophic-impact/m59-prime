// Prime (ours): bake where playerbots may stand and walk in every room, for the SERVER (Blakod), from the same nav grid the
// ambient townsfolk walk on (packages/world/src/navGrid.ts: walls, steps, roofs and water judged the way move.c does, so a person could walk
// every path). Output: prime_server/overlay/kod/object/prime/primenavdata.kod (class PrimeNavData) and a readable summary (navbake.json).
//   node tools/prime/navbake.ts --assets <assets dir> --kod <server kod dir> --out <primenavdata.kod> [--json navbake.json] [--blocked navblocked.json]
// Options: --closer N (cells closed round a server-refused point, default 1), --relax / --hard <file> / --prune <file> (relaxed rooms routes, server-checked: see claude_dev_notes.txt SESSION 14).
// Per room: nodes on its walkable floor, routes between neighbouring nodes, and links to other rooms. Town regions remain separately listed for current town-life behavior.
import { readFileSync, readdirSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { FINENESS, SF, parseRoo } from "../../packages/formats/src/index.ts";
import { buildNavGrid, cellAt, cellCentre, findCells, isOpen, nearestCell, walkable as walkableGeom, type NavGrid } from "../../packages/world/src/navGrid.ts";
import { findWaterTextures } from "../assets/waterTextures.ts";

const { values: o } = parseArgs({
  options: { probe: { type: "string" }, assets: { type: "string" }, kod: { type: "string" }, out: { type: "string" }, json: { type: "string" }, blocked: { type: "string" }, objects: { type: "string" }, closer: { type: "string" }, relax: { type: "boolean" }, hard: { type: "string" }, prune: { type: "string" }, landings: { type: "string" }, trap: { type: "string" }, noway: { type: "string" }, edges: { type: "string" } },
});
const ASSETS = o.assets!, KOD = o.kod!;
// ZONE EXITS (prime_server/scripts/extract_zones.py from the Kod): a room's SomethingMoved sends a body that steps on ANY square satisfying a condition (Marion: row > 83 and col > 48 goes to c5). roomexits.json
// holds only a CORNER square of such a zone ((84,49) in Marion, which lies in a floor pocket nobody can walk to): the door square of a zone exit is a floor square INSIDE the zone that the main floor reaches.
const SQUARES: Record<string, Record<string, [number, number]>> = (() => { try { return JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), "exit_squares.json"), "utf8")); } catch { return {}; } })();
const OVR: Record<string, [number, number]> = (() => { try { return JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), "exit_overrides.json"), "utf8")).exits ?? {}; } catch { return {}; } })();
const ZONES: Record<string, { to: string; when: string }[]> = (() => { try { return JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), "roomzones.json"), "utf8")).zones ?? {}; } catch { return {}; } })();
// THE GAME'S OWN EXIT TABLES (claude_tools/kodexits.py -> docs/kod_exits.json): per room, the door squares with the square each one lands on, and the edge exits with theirs. A door of the bake takes the landing
// of the nearest real door square (not a guess per room pair). TRAP = landings the planner cannot leave (claude_tools/reachmatrix.py): [destRid, row, col]; a door whose own landing is a trap takes another
// square's landing of the same pair, or is dropped.
const KODX: Record<string, { doors: number[][]; edges: [string, number, number, number, number[]?][] }> = o.landings ? JSON.parse(readFileSync(o.landings, "utf8")) : {};
// EDGE LANDINGS (claude_tools/edgelanding.py --baker): where the SERVER's floor (the grid the bots walk) meets the side of a room, per edge exit {rid: {'toRoo:side': [row, col]}}; used when the baker's own floor disagrees.
// The room a player lands in when he walks off `side` at square (row, col), by the game's own rule (room.kod StandardLeaveDir; claude_tools/kodexits.py edge_taken): an edge exit may be bound to
// the row or column he leaves from (ROW_IS_LESS_THAN n ...), so the door square of an edge exit must be a square that leads to ITS room (Jixa west side: rows below 19 go to 2902, rows above 20 to 2952).
const edgeTaken = (edges: [string, number, number, number, number[]?][], side: string, row: number, col: number): number | undefined => {
  let fallback: number | undefined;
  for (const e of edges) {
    if (e[0] !== side) continue;
    const c = e[4] ?? [];
    if (!c.length) return e[1];
    const [t, n] = c;
    if ((t === 1 && row > n) || (t === 2 && row < n) || (t === 3 && col > n) || (t === 4 && col < n)) return e[1];
    if (t === 5) fallback = e[1];
  }
  return fallback;
};
const EDGEL: Record<string, Record<string, [number, number]>> = o.edges ? JSON.parse(readFileSync(o.edges, "utf8")) : {};
// NOWAY = the planner's verdict per arrival square and door of a room (claude_tools/reachmatrix.py -> docs/reach_matrix/matrix.json, "noway_pairs": "arrRow,arrCol>doorRow,doorCol"):
// a bot that lands on that arrival square has no way to that door. Each door lists those arrival squares (row * 1000 + col) as BLOCKED, and the route search skips the door for a bot that came in there.
const NOWAY = new Map<number, string[]>();
if (o.noway) for (const e of JSON.parse(readFileSync(o.noway, "utf8")) as { rid: number; noway_pairs?: string[] }[]) if (e.noway_pairs?.length) NOWAY.set(e.rid, e.noway_pairs);
const TRAP = new Set<string>((o.trap ? (JSON.parse(readFileSync(o.trap, "utf8")) as number[][]) : []).map((t) => t.join(",")));

// ---- what gets a graph ---------------------------------------------------------------------------------------------------------------
// region: the bot's home town (a room number: its identity's field 7); street rooms first, then inns
const REGIONS: { home: number; name: string; streets: string[]; inns: string[] }[] = [
  { home: 50, name: "Tos", streets: ["tos", "toseast"], inns: ["tosinn", "tostavern"] },
  { home: 102, name: "Barloque", streets: ["barls", "barln", "barlport"], inns: ["barinn", "barlbar1"] },
  { home: 150, name: "Cor Noth", streets: ["cornoth"], inns: ["corinn"] },
  { home: 200, name: "Marion", streets: ["marion", "greenplantation"], inns: ["marinn"] },
  { home: 300, name: "Raza", streets: ["raza"], inns: ["razainn", "razabar"] },
  { home: 350, name: "Jasper", streets: ["jaseast", "jaswest"], inns: ["jasinn", "jastavrn"] },
  { home: 2000, name: "Ko'catan", streets: ["settle1", "settle2"], inns: ["kocinn", "koctav"] },
  { home: 2800, name: "Bergensdorf", streets: ["bergcity"], inns: ["berginn"] },
  { home: 2903, name: "Jixa", streets: ["jixa"], inns: ["jixa_inn"] },
];
/** Door destinations that are errands: [file pattern, purpose] (the purpose numbers are PBP_* in primeplayerbots.kod) */
const ERRANDS: [RegExp, number][] = [
  [/bank|vault/, 1],
  [/smith|weaponsm/, 2],
  [/apoth/, 3],
  [/hall/, 4],
  [/heal/, 6],
  [/merch|store|groc|tail|market|auc/, 5],
];
const MAX_NODES = 40, MAX_DOORS = 40;
/** The main-network travel portals (util/travelnet.kod GetPoints): room, portal square, arrival square. Bots use them for free (owner rule 2026-10-29). */
const PORTALS: { rid: number; row: number; col: number; arrRow: number; arrCol: number }[] = [
  { rid: 50, row: 29, col: 5, arrRow: 29, arrCol: 6 }, { rid: 200, row: 5, col: 4, arrRow: 6, arrCol: 5 }, { rid: 300, row: 23, col: 8, arrRow: 23, arrCol: 9 },
  { rid: 350, row: 57, col: 43, arrRow: 57, arrCol: 42 }, { rid: 101, row: 4, col: 13, arrRow: 4, arrCol: 14 }, { rid: 150, row: 44, col: 47, arrRow: 44, arrCol: 48 },
  { rid: 2000, row: 48, col: 9, arrRow: 48, arrCol: 11 }, // Bergen (2800, 52,73) is left out: the baked street floor ends at row ~40, no node lies within 12 squares of the portal
  { rid: 578, row: 46, col: 48, arrRow: 46, arrCol: 47 },
  { rid: 38, row: 7, col: 6, arrRow: 7, arrCol: 4 }, { rid: 4300, row: 11, col: 20, arrRow: 12, arrCol: 20 },
];

// Points the SERVER's own movement check refused (found by PBotTestEdges, collected by prime_server/scripts/navblocked.py): { "<rid>": [[x, y], ...] } in
// fine units from the room's corner. Those cells are closed, so the routes go round them (the client grid thought the floor was open there).
const blockedPts: Record<string, [number, number][]> = o.blocked && existsSync(o.blocked) ? JSON.parse(readFileSync(o.blocked, "utf8")) : {};

// Solid room objects (tables, stools, keepers who stand still: the server's blockers, radius 0.75 square), dumped by PBotTestBlockers / scripts/navobjects.py:
// { "<rid>": [[x, y], ...] } in fine units from the room's corner. Cells within about a square of each are closed.
const objectPts: Record<string, [number, number][]> = o.objects && existsSync(o.objects) ? JSON.parse(readFileSync(o.objects, "utf8")) : {};

// Points the server refused on a RELAXED route (navcheck against a --relax bake): closed for good, relaxation cannot re-open them
const hardPts: Record<string, [number, number][]> = o.hard && existsSync(o.hard) ? JSON.parse(readFileSync(o.hard, "utf8")) : {};
// Routes (node pairs, 0-based, of exactly this bake) the server's movement check refused (prime_server/scripts/navcheck.py with NAVCHECK_PRUNE): removed from the graph at the end
const prunePairs: Record<string, [number, number][]> = o.prune && existsSync(o.prune) ? JSON.parse(readFileSync(o.prune, "utf8")) : {};
let pruned = 0;
const rooms = JSON.parse(readFileSync(join(ASSETS, "rooms.json"), "utf8")) as { rid: number; name: string; roo: string }[];
const exits = JSON.parse(readFileSync(join(ASSETS, "roomexits.json"), "utf8")) as Record<
  string,
  { doors: [number, number, string | null][]; edges?: { side: "N" | "S" | "E" | "W"; to: string }[]; arrivals: [number, number][] }
>;
const ridOf = (roo: string) => {
  const all = rooms.filter((r) => r.roo === roo && r.name !== "Death Realm");
  return (all.filter((r) => r.name !== "Room").length ? all.filter((r) => r.name !== "Room") : all).map((r) => r.rid).sort((a, b) => a - b)[0];
};
const nameOf = (rid: number) => rooms.find((r) => r.rid === rid)?.name ?? "";

const parsed = new Map<string, ReturnType<typeof parseRoo>>();
const load = (roo: string) => {
  if (!parsed.has(roo)) parsed.set(roo, parseRoo(new Uint8Array(readFileSync(join(ASSETS, roo)))));
  return parsed.get(roo)!;
};
const water = findWaterTextures(readdirSync(ASSETS).filter((f) => f.endsWith(".roo")).map(load));

// globes: the news / announcement globes a room's Kod creates, with where it puts them
const globes = new Map<string, [number, number][]>();
const walkDir = (d: string): string[] =>
  readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walkDir(join(d, e.name)) : e.name.endsWith(".kod") ? [join(d, e.name)] : []));
for (const f of walkDir(join(KOD, "object", "active", "holder", "room"))) {
  const t = readFileSync(f, "latin1");
  if (!/Create\(&NewsLink/i.test(t)) continue;
  const roo = t.match(/([a-z0-9_]+\.roo)/i)?.[1]?.toLowerCase();
  const m = t.match(/Create\(&NewsLink[\s\S]*?#what\s*=\s*(\w+)[\s\S]*?#new_row\s*=\s*(\d+)\s*,\s*#new_col\s*=\s*(\d+)/i);
  if (roo && m) globes.set(roo, [...(globes.get(roo) ?? []), [Number(m[2]), Number(m[3])]]);
}


// ---- server-probed rooms ----------------------------------------------------------------------------------------------------------------
// A room with a file <probe dir>/<rid>_x2.json (scripts/probe.py: which half-square steps the SERVER's own movement check lets a bot body take) takes its
// walkable cells and links from that, not from the client grid: the client judges what a player can do, the server what a monster can, and the old bake
// cut every route the server refused (that split rooms such as 2115). Bits as the client grid: DIRS below.
const PROBE_DIR = o.probe ?? "";
const NAV_DIRS: [number, number][] = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
const loadProbe = (rid: number): { rows: number; cols: number; grid: number[][] } | null => {
  const f = join(PROBE_DIR, `${rid}_x2.json`);
  return PROBE_DIR && existsSync(f) ? JSON.parse(readFileSync(f, "utf8")) : null;
};
function applyProbe(g: NavGrid, pr: { rows: number; cols: number; grid: number[][] }): void {
  for (let r = 0; r < g.rows; r++) for (let c = 0; c < g.cols; c++) {
    const i = r * g.cols + c, m = pr.grid[r]?.[c] ?? 0;
    g.links[i] = m; g.walk[i] = m ? 1 : 0; g.closed[i] = 0;
  }
  // connected areas, two-way links only, numbered largest first
  const label = new Int32Array(g.cols * g.rows).fill(-1);
  const sizes: number[] = [];
  for (let s0 = 0; s0 < label.length; s0++) {
    if (!g.walk[s0] || label[s0] >= 0) continue;
    const id = sizes.length; let size = 0; label[s0] = id;
    const st = [s0];
    while (st.length) {
      const i = st.pop()!; size++;
      for (let d = 0; d < 8; d++) {
        if (!(g.links[i] & (1 << d))) continue;
        const cc = (i % g.cols) + NAV_DIRS[d][0], rr = Math.floor(i / g.cols) + NAV_DIRS[d][1];
        if (cc < 0 || rr < 0 || cc >= g.cols || rr >= g.rows) continue;
        const j = rr * g.cols + cc;
        if (label[j] < 0 && g.links[j] & (1 << ((d + 4) & 7))) { label[j] = id; st.push(j); }
      }
    }
    sizes.push(size);
  }
  const rank = new Map(sizes.map((n, id) => ({ n, id })).sort((a, b) => b.n - a.n).map((x, k) => [x.id, k + 1] as [number, number]));
  for (let i = 0; i < label.length; i++) g.area[i] = label[i] >= 0 ? Math.min(65535, rank.get(label[i])!) : 0;
  (g as unknown as { probed: boolean }).probed = true;
}
/** walkable() of the client grid, or for a probed room: the line followed cell by cell, every step an open link of the server's own check */
function walkable(g: NavGrid, ax: number, ay: number, bx: number, by: number, clearance?: number): boolean {
  if (!(g as unknown as { probed?: boolean }).probed) return walkableGeom(g, ax, ay, bx, by, clearance);
  const NC = FINENESS / 2;
  let c = Math.round(ax / NC), r = Math.round(ay / NC);
  const c1 = Math.round(bx / NC), r1 = Math.round(by / NC);
  const n = Math.max(Math.abs(c1 - c), Math.abs(r1 - r));
  for (let k = 1; k <= n; k++) {
    const nc = Math.round(c + ((c1 - c) * k) / n) , nr = Math.round(r + ((r1 - r) * k) / n);
    return_: {
      const pc = k === 1 ? c : Math.round(c + ((c1 - c) * (k - 1)) / n), pr = k === 1 ? r : Math.round(r + ((r1 - r) * (k - 1)) / n);
      const d = NAV_DIRS.findIndex(([dc, dr]) => dc === nc - pc && dr === nr - pr);
      if (d < 0 || pc < 0 || pr < 0 || pc >= g.cols || pr >= g.rows) return false;
      if (!(g.links[pr * g.cols + pc] & (1 << d))) return false;
      break return_;
    }
  }
  return true;
}

// ---- the graph of one room -----------------------------------------------------------------------------------------------------------
const SQ = FINENESS;
let relaxedRoutes = 0;
const centre = (row: number, col: number) => ({ x: (col - 1) * SQ + SQ / 2, y: (row - 1) * SQ + SQ / 2 });
const squareOf = (x: number, y: number) => ({ row: Math.floor(y / SQ) + 1, col: Math.floor(x / SQ) + 1 });
const dist = (a: { x: number; y: number }, b: { x: number; y: number }) => Math.hypot(a.x - b.x, a.y - b.y);

interface Via { row: number; col: number; fr?: number; fc?: number }
interface Door { row: number; col: number; to: string | null; node: number; kind: number; purpose: number; destRid: number; arrRow: number; arrCol: number; edge: number; blocked?: number[] }
interface Graph {
  roo: string; rid: number; name: string; kind: "street" | "inn" | "room"; region: number;
  nodes: { row: number; col: number }[]; adj: { to: number; via: Via[] }[][]; doors: Door[]; globes: { row: number; col: number; node: number }[];
}

/** A square centre a person can stand on with clear floor all round (a doorway or a wall's edge is not) */
function interior(g: NavGrid, cell: number, ring: number): boolean {
  if (!isOpen(g, cell) || g.links[cell] !== 255) return false;
  const c = cellCentre(g, cell);
  // a square centre: cell centres are multiples of half a square, odd multiples are the centres
  if (Math.round((c.x - SQ / 2) % SQ) !== 0 || Math.round((c.y - SQ / 2) % SQ) !== 0) return false;
  // the ring two cells out is open too
  for (let dr = -ring; dr <= ring; dr++)
    for (let dc = -ring; dc <= ring; dc++) {
      const cc = cell + dr * g.cols + dc;
      const r = Math.floor(cell / g.cols) + dr, k = (cell % g.cols) + dc;
      if (r < 0 || k < 0 || r >= g.rows || k >= g.cols || !isOpen(g, cc)) return false;
    }
  return true;
}

function bake(roo: string, rid: number, kind: Graph["kind"], region: number, byRoo: Map<string, number>, want: number): Graph & { parts: number } {
  // Dungeon and wilderness rooms: monsters, and so hunters, wade through shallow water and sewer channels (the townsfolk grid treats a
  // depth sector as a wall), so for those rooms the depth flag is cleared and no floor texture counts as water.
  const raw = load(roo + ".roo");
  const wading = kind === "room";
  const room = wading ? { ...raw, sectors: raw.sectors.map((s) => ({ ...s, flags: s.flags & ~SF.DEPTH_MASK })) } : raw;
  const g = buildNavGrid(room, wading ? new Set<number>() : new Set(water));
  const probe = loadProbe(rid);
  if (probe) { applyProbe(g, probe); console.log(`  ${roo} (rid ${rid}): walkable cells and links from the server's own movement check`); }
  const ex = exits[roo + ".roo"] ?? { doors: [], arrivals: [] };
  const blockedCells: number[] = [];
  let relaxed = false;
  for (const [bx, by] of (probe ? [] : blockedPts[String(rid)] ?? [])) {
    // the server refuses the point itself: a solid object stands there (a tree, a statue: the room's objects are not in the client grid), so the cells round it close too
    const CR = Number(o.closer ?? 1);
    for (let dy = -CR; dy <= CR; dy++) for (let dx = -CR; dx <= CR; dx++) {
      const c = cellAt(g, bx + dx * (SQ / 2), by + dy * (SQ / 2));
      if (c >= 0) { if (!g.closed[c]) blockedCells.push(c); g.closed[c] = 1; }
    }
  }
  for (const [bx, by] of (probe ? [] : objectPts[String(rid)] ?? [])) {
    for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
      if (dx * dx + dy * dy > 5) continue;
      const c = cellAt(g, bx + dx * (SQ / 2), by + dy * (SQ / 2));
      if (c >= 0) g.closed[c] = 1;
    }
  }
  for (const [bx, by] of (probe ? [] : hardPts[String(rid)] ?? [])) {
    const CRh = Number(o.closer ?? 1);
    for (let dy = -CRh; dy <= CRh; dy++) for (let dx = -CRh; dx <= CRh; dx++) {
      const c = cellAt(g, bx + dx * (SQ / 2), by + dy * (SQ / 2));
      if (c >= 0) g.closed[c] = 1;
    }
  }
  if (blockedPts[String(rid)]) console.log(`  ${roo} (rid ${rid}): ${g.closed.reduce((a, b) => a + b, 0)} cells closed by ${blockedPts[String(rid)].length} server-refused points`);
  const clearOfClosed = (ax: number, ay: number, bx: number, by: number) => {
    if (probe || (!blockedPts[String(rid)] && !hardPts[String(rid)] && !objectPts[String(rid)]) || (relaxed && !hardPts[String(rid)] && !objectPts[String(rid)])) return true;
    const n = Math.max(1, Math.ceil(dist({ x: ax, y: ay }, { x: bx, y: by }) / (SQ / 4)));
    for (let k = 0; k <= n; k++) {
      const c = cellAt(g, ax + ((bx - ax) * k) / n, ay + ((by - ay) * k) / n);
      if (c >= 0 && g.closed[c]) return false;
    }
    return true;
  };

  // door groups (neighbouring door squares are one door)
  // (only squares with the SAME landing are one door: each door square of the game has its own landing, see KODX)
  const groups: { rows: number[]; cols: number[]; to: string | null; land?: [number, number] }[] = [];
  for (const [row, col, to] of ex.doors) {
    const kd = KODX[String(ridOf(roo + ".roo"))]?.doors.find((x) => x[0] === row && x[1] === col);
    const land = kd ? ([kd[3], kd[4]] as [number, number]) : undefined;
    const same = (a?: [number, number], b?: [number, number]) => (!a && !b) || (!!a && !!b && a[0] === b[0] && a[1] === b[1]);
    const grp = groups.find((d) => d.to === to && same(d.land, land) && d.rows.some((r, k) => Math.abs(r - row) <= 1 && Math.abs(d.cols[k] - col) <= 1));
    if (grp) { grp.rows.push(row); grp.cols.push(col); } else groups.push({ rows: [row], cols: [col], to, land });
  }
  const mean = (v: number[]) => v.reduce((a, b) => a + b, 0) / v.length;

  // the floor to use: the area most doors open on (the biggest one is often the roofs or the outskirts), so a roof is never used
  const doorAt: { at: { x: number; y: number }; to: string | null; row: number; col: number; land?: [number, number]; edgeSide?: "N" | "S" | "E" | "W"; borderSide?: "N" | "S" | "E" | "W" }[] = [];
  const hits = new Map<number, number>();
  const hit = (x: number, y: number, w: number) => {
    const c = nearestCell(g, x, y, 6, 0, false);
    if (c >= 0 && g.area[c]) hits.set(g.area[c], (hits.get(g.area[c]) ?? 0) + w);
  };
  for (const d of groups) {
    let row = Math.round(mean(d.rows)), col = Math.round(mean(d.cols));
    // a doorway is often several adjacent squares the game lists with one landing; the AVERAGE square can be one no body can walk to (Jixa inn (9,8) of (8,8)+(9,8), the floor ends at row 8): the door
    // square is the member the planner reaches from the most arrival squares (docs/exit_audit/squares.json from claude_tools/exitaudit.py), the one nearest the average on a tie
    const sqr = SQUARES[String(rid)];
    if (sqr && d.rows.length > 0) {
      let bk = -1, bs = -1, bd = Infinity;
      d.rows.forEach((r0, k) => { const v = sqr[`${r0},${d.cols[k]}`]; if (!v) return; const sc = v[1] ? v[0] / v[1] : 0, dd = Math.hypot(r0 - mean(d.rows), d.cols[k] - mean(d.cols)); if (sc > bs + 1e-9 || (Math.abs(sc - bs) < 1e-9 && dd < bd)) { bk = k; bs = sc; bd = dd; } });
      const cur = sqr[`${row},${col}`]; const curSc = cur && cur[1] ? cur[0] / cur[1] : -1;   // (the average square stays unless a member is better: no churn)
      if (bk >= 0 && bs > curSc + 1e-9 && (d.rows[bk] !== row || d.cols[bk] !== col)) { console.log(`  ${roo}: door to ${d.to}: square ${row},${col} -> ${d.rows[bk]},${d.cols[bk]} (the member of the doorway the planner reaches from ${Math.round(bs * 100)} percent of the arrivals)`); row = d.rows[bk]; col = d.cols[bk]; }
    }
    const at = { x: (col - 1) * SQ + SQ / 2, y: (row - 1) * SQ + SQ / 2 };
    // a door square on (or next to) the room border is a border crossing too: its square may be wall, so it is placed like an edge exit (below), near its own position
    const borderSide = row <= 2 ? "N" : row >= room.rows - 1 ? "S" : col <= 2 ? "W" : col >= room.cols - 1 ? "E" : undefined;
    doorAt.push({ at, to: d.to, row, col, borderSide, land: d.land });
    hit(at.x, at.y, d.to ? 2 : 1);
  }
  // Outdoor region transitions are recorded as room edges, not ordinary doors.
  // The original town-only baker ignored them, which left the world graph split
  // into isolated islands. Represent each crossing as a transit point on that
  // side and pair it with the nearest arrival on the reciprocal side.
  for (const edge of ex.edges ?? []) {
    const row = edge.side === "N" ? 1 : edge.side === "S" ? room.rows : Math.round(room.rows / 2);
    const col = edge.side === "W" ? 1 : edge.side === "E" ? room.cols : Math.round(room.cols / 2);
    const at = centre(row, col);
    doorAt.push({ at, to: edge.to, row, col, edgeSide: edge.side });
    hit(at.x, at.y, 2);
  }
  for (const [row, col] of ex.arrivals) {
    const p = centre(row, col);
    hit(p.x, p.y, 1);
  }
  const sizes = new Map<number, number>();
  for (const a of g.area) if (a) sizes.set(a, (sizes.get(a) ?? 0) + 1);
  let mainArea = [...hits.entries()].sort((a, b) => b[1] - a[1] || (sizes.get(b[0]) ?? 0) - (sizes.get(a[0]) ?? 0))[0]?.[0] ?? [...sizes.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? 0;
  if (kind === "room") {
    // a few cells where a door happens to land (a ledge, a stair top) must not beat the real floor: among the areas a door or arrival
    // touches, a tiny one gives way to the biggest
    const touched = [...hits.keys()].sort((a, b) => (sizes.get(b) ?? 0) - (sizes.get(a) ?? 0));
    if (touched.length && (sizes.get(mainArea) ?? 0) * 4 < (sizes.get(touched[0]) ?? 0)) mainArea = touched[0];
  }
  console.log(`  ${roo}: floor area ${mainArea} (${sizes.get(mainArea)} cells of ${[...sizes.values()].reduce((x, y) => x + y, 0)}; doors by area ${JSON.stringify([...hits.entries()])})`);

  // candidates, then the farthest-point spread of them. A narrow crypt or corridor has no floor square with the full clear ring, so a
  // room that comes out too sparse (a bot cannot roam on one to four nodes) is tried again with a thinner ring and a closer spacing.
  const collect = (ring: number) => {
    const out: number[] = [];
    for (let i = 0; i < g.walk.length; i++) if (g.area[i] === mainArea && interior(g, i, ring)) out.push(i);
    return out;
  };
  const spread = (cand: number[], gap: number) => {
    const out: number[] = [];
    const d2 = new Float64Array(cand.length).fill(Infinity);
    let next = 0;
    while (out.length < want && cand.length) {
      out.push(cand[next]);
      const p = cellCentre(g, cand[next]);
      let far = -1, farD = 0;
      for (let k = 0; k < cand.length; k++) {
        d2[k] = Math.min(d2[k], dist(p, cellCentre(g, cand[k])));
        if (d2[k] > farD) { farD = d2[k]; far = k; }
      }
      if (far < 0 || farD < gap * SQ) break;
      next = far;
    }
    return out;
  };
  let cand = collect(kind === "inn" ? 1 : 2);
  let picked = spread(cand, kind === "inn" ? 2 : 3);
  for (const [ring, gap] of [[1, 2.5], [0, 2], [0, 1.5]]) {
    if (picked.length >= Math.min(want, 8)) break;
    const c2 = collect(ring), p2 = spread(c2, gap);
    if (p2.length > picked.length) { cand = c2; picked = p2; }
  }
  // a maze or a big cave: the attempts above stop at 8 nodes, which left most of the Raza crypt (306) with no node at all. Keep adding square centres of the main
  // floor, always the one farthest from every node so far, until nothing lies more than 5 squares from a node or the room has `want` nodes.
  if (kind === "room" && picked.length < want) {
    const isSqC = (p: { x: number; y: number }) => Math.round((p.x - SQ / 2) % SQ) === 0 && Math.round((p.y - SQ / 2) % SQ) === 0;
    const all: number[] = [];
    for (let i = 0; i < g.walk.length; i++) if (g.area[i] === mainArea && isOpen(g, i) && g.links[i] && isSqC(cellCentre(g, i))) all.push(i);
    const near = all.map((c) => picked.reduce((m, q) => Math.min(m, dist(cellCentre(g, c), cellCentre(g, q))), Infinity));
    while (picked.length < want && all.length) {
      let far = -1, farD = 0;
      for (let k = 0; k < all.length; k++) if (near[k] > farD) { farD = near[k]; far = k; }
      if (far < 0 || farD < 5 * SQ) break;
      picked.push(all[far]);
      const pc = cellCentre(g, all[far]);
      for (let k = 0; k < all.length; k++) near[k] = Math.min(near[k], dist(cellCentre(g, all[k]), pc));
    }
  }
  const pts = picked.map((c) => cellCentre(g, c));
  const nodes = pts.map((p) => squareOf(p.x, p.y));
  // the door approaches: the main-floor square nearest each door that matters, a node of its own unless one is a square or so away
  const approach = new Map<number, number>();
  doorAt.forEach((d, di) => {
    if (!d.to) return;
    // the open square-centre cell of the main floor nearest the door
    let c = -1, cd = Infinity, cb = 0;
    const side = d.edgeSide ?? d.borderSide;
    if (side) {
      // a room-edge exit: the crossing is wherever the main floor reaches that border (not the middle of the side, which is often wall or water),
      // so take the main-floor square centre nearest the border, a little in favour of the middle of the side
      const W = room.cols * SQ, H = room.rows * SQ;
      // an edge exit bound to a row or column of the side (see edgeTaken): only squares the game sends to THIS exit's room
      const kxE = d.edgeSide ? KODX[String(ridOf(roo + ".roo"))]?.edges : undefined;
      const destE = d.edgeSide && d.to ? byRoo.get(d.to.replace(/\.roo$/, "").toLowerCase()) : undefined;
      for (let i = 0; i < g.walk.length; i++) {
        if (!isOpen(g, i) || g.area[i] !== mainArea) continue;
        const q = cellCentre(g, i);
        if (Math.round((q.x - SQ / 2) % SQ) !== 0 || Math.round((q.y - SQ / 2) % SQ) !== 0) continue;
        if (kxE?.length && destE !== undefined) { const s0 = squareOf(q.x, q.y); if (edgeTaken(kxE, side, s0.row, s0.col) !== destE) continue; }
        const border = side === "N" ? q.y : side === "S" ? H - q.y : side === "W" ? q.x : W - q.x;
        const ref = d.edgeSide ? { x: W / 2, y: H / 2 } : d.at;
        const along = side === "N" || side === "S" ? Math.abs(q.x - ref.x) : Math.abs(q.y - ref.y);
        // floor that touches the side (within one square of it) wins, the one nearest the middle of the side first; with none, the floor nearest the side
        const sc = (border <= SQ ? 0 : border) * 1000 + along;
        if (sc < cd) { cd = sc; c = i; cb = border; }
      }
      if (c >= 0 && cb > 12 * SQ) c = -1;
    } else {
    const c0 = Math.floor(d.at.x / (SQ / 2) + 0.5), r0 = Math.floor(d.at.y / (SQ / 2) + 0.5);
    // 24 cells = 12 squares: a door into a cave or a cliff can lie further from the main floor than the old 5 squares
    for (let r = r0 - 24; r <= r0 + 24; r++)
      for (let k2 = c0 - 24; k2 <= c0 + 24; k2++) {
        if (k2 < 0 || r < 0 || k2 >= g.cols || r >= g.rows) continue;
        const i = r * g.cols + k2;
        if (!isOpen(g, i) || g.area[i] !== mainArea) continue;
        const q = cellCentre(g, i);
        if (Math.round((q.x - SQ / 2) % SQ) !== 0 || Math.round((q.y - SQ / 2) % SQ) !== 0) continue;
        const dd = dist(q, d.at);
        if (dd < cd) { cd = dd; c = i; }
      }
    }
    if (c < 0) return;
    const cc = cellCentre(g, c);
    const sq = squareOf(cc.x, cc.y);
    const sp = centre(sq.row, sq.col);
    let k = pts.findIndex((p) => dist(p, sp) < 1.5 * SQ);
    if (k < 0) {
      if (nodes.length >= MAX_NODES) return;
      pts.push(sp); nodes.push(sq);
      k = pts.length - 1;
    }
    approach.set(di, k);
  });

  // edges: A* over the real grid between neighbouring nodes, the path cut down to the square centres it must pass (so a bend round a house is a via point)
  const cellOfNode = pts.map((p) => cellAt(g, p.x, p.y));
  const edge = new Map<string, { a: number; b: number; len: number; via: Via[] }>();
  const routeStrict = (a: number, b: number) => {
    const key = a < b ? `${a},${b}` : `${b},${a}`;
    if (edge.has(key)) return edge.get(key)!;
    const cells = findCells(g, cellOfNode[a], cellOfNode[b], 600000);
    if (!cells) { console.log(`  ${roo}: no path between nodes ${a} and ${b} (cells ${cellOfNode[a]} ${cellOfNode[b]}, areas ${g.area[cellOfNode[a]]} ${g.area[cellOfNode[b]]}, open ${isOpen(g, cellOfNode[a])} ${isOpen(g, cellOfNode[b])})`); return null; }
    const cp = cells.map((c) => cellCentre(g, c));
    let len = 0;
    for (let i = 1; i < cp.length; i++) len += dist(cp[i - 1], cp[i]);
    // greedy: from the last kept point, the farthest later square-centre point still in a clear straight line
    const isSq = (p: { x: number; y: number }) => Math.round((p.x - SQ / 2) % SQ) === 0 && Math.round((p.y - SQ / 2) % SQ) === 0;
    const via: Via[] = [];
    let cur = 0;
    while (cur < cp.length - 1) {
      let nxt = cur + 1;
      for (let j = cp.length - 1; j > cur; j--) {
        if ((j === cp.length - 1 || probe || isSq(cp[j])) && walkable(g, cp[cur].x, cp[cur].y, cp[j].x, cp[j].y) && clearOfClosed(cp[cur].x, cp[cur].y, cp[j].x, cp[j].y)) { nxt = j; break; }
      }
      if (nxt < cp.length - 1) {
        const q = squareOf(cp[nxt].x, cp[nxt].y);
        // a probed room keeps the half-square position of a bend: its corridors can be one cell wide
        via.push(probe ? { ...q, fr: Math.round(cp[nxt].y - (q.row - 1) * SQ), fc: Math.round(cp[nxt].x - (q.col - 1) * SQ) } : q);
      }
      cur = nxt;
    }
    const e = { a: Math.min(a, b), b: Math.max(a, b), len, via: a < b ? via : via.slice().reverse() };
    edge.set(key, e);
    return e;
  };
  // --relax: a pair the refused-point closures cut apart is tried once more with those closures re-opened (a point may block less than its 3x3 block);
  // navcheck on a running server then says whether the server accepts the route, and refuses (and so re-closes) what it does not
  const route = (a: number, b: number) => {
    let e = routeStrict(a, b);
    if (!e && o.relax && blockedCells.length) {
      for (const c of blockedCells) g.closed[c] = 0;
      relaxed = true;
      try { e = routeStrict(a, b); } finally { relaxed = false; for (const c of blockedCells) g.closed[c] = 1; }
      if (e) relaxedRoutes++;
    }
    return e;
  };
  // k nearest each, shortest first; a spanning tree first, then the short ones that make loops
  const pairs: { a: number; b: number; d: number }[] = [];
  for (let a = 0; a < pts.length; a++) {
    const near = pts.map((p, b) => ({ b, d: dist(pts[a], p) })).filter((x) => x.b !== a).sort((x, y) => x.d - y.d).slice(0, 5);
    for (const n of near) if (!pairs.some((c) => (c.a === a && c.b === n.b) || (c.a === n.b && c.b === a))) pairs.push({ a, b: n.b, d: n.d });
  }
  const uf = pts.map((_, i) => i);
  const find = (x: number): number => (uf[x] === x ? x : (uf[x] = find(uf[x])));
  const chosen: { a: number; b: number; len: number; via: Via[] }[] = [];
  const degree = new Array<number>(pts.length).fill(0);
  const take = (e: { a: number; b: number; len: number; via: Via[] }) => {
    chosen.push(e); degree[e.a]++; degree[e.b]++;
  };
  const routed = pairs.map((c) => ({ c, e: route(c.a, c.b) })).filter((x) => x.e).sort((x, y) => x.e!.len - y.e!.len);
  for (const { e } of routed) if (find(e!.a) !== find(e!.b)) { uf[find(e!.a)] = find(e!.b); take(e!); }
  for (const { e } of routed) {
    if (chosen.includes(e!) || degree[e!.a] >= 4 || degree[e!.b] >= 4) continue;
    // a loop only for a nearly straight neighbour
    if (e!.len <= 1.5 * dist(pts[e!.a], pts[e!.b]) && e!.len <= 14 * SQ) take(e!);
  }
  // pieces the nearest-five missed: the closest pair of two pieces, until one
  for (let guard = 0; guard < 60; guard++) {
    let best: { a: number; b: number; d: number } | null = null;
    for (let a = 0; a < pts.length; a++) for (let b = a + 1; b < pts.length; b++) if (find(a) !== find(b) && (!best || dist(pts[a], pts[b]) < best.d)) best = { a, b, d: dist(pts[a], pts[b]) };
    if (!best) break;
    const e = route(best.a, best.b);
    if (!e) { uf[find(best.a)] = find(best.b); continue; }
    uf[find(e.a)] = find(e.b); take(e);
  }
  const adj: { to: number; via: Via[] }[][] = pts.map(() => []);
  for (const e of chosen) {
    adj[e.a].push({ to: e.b, via: e.via });
    adj[e.b].push({ to: e.a, via: e.via.slice().reverse() });
  }
  // a node keeps a via list only in the direction it was cut for: e.via is a -> b
  const comp = () => {
    const c = new Array<number>(pts.length).fill(-1);
    let n = 0;
    for (let s0 = 0; s0 < pts.length; s0++) {
      if (c[s0] >= 0) continue;
      const st = [s0]; c[s0] = n;
      while (st.length) for (const m of adj[st.pop()!]) if (c[m.to] < 0) { c[m.to] = n; st.push(m.to); }
      n++;
    }
    return { c, n };
  };

  const nodeFor = (p: { x: number; y: number }) => {
    let b = -1, bd = Infinity;
    for (let k = 0; k < pts.length; k++) {
      const d = dist(pts[k], p);
      if (d < bd && walkable(g, p.x, p.y, pts[k].x, pts[k].y, 64)) { bd = d; b = k; }
    }
    return b;
  };

  const doors: Door[] = [];
  for (let di = 0; di < doorAt.length; di++) {
    const d = doorAt[di];
    if (!d.to) continue;
    const toRoo = d.to.replace(/\.roo$/, "").toLowerCase();
    const node = approach.get(di);
    if (node === undefined) { console.log(`  ${roo}: door to ${toRoo} at ${d.row},${d.col} dropped: no floor beside it`); continue; }
    let kindD = 0, purpose = 0, destRid = 0, arrRow = 0, arrCol = 0;
    if (byRoo.has(toRoo)) {
      kindD = 1;
      destRid = byRoo.get(toRoo)!;
      const arr = exits[toRoo + ".roo"]?.arrivals ?? [];
      const kx = KODX[String(ridOf(roo + ".roo"))];
      let landings: [number, number][] = [];
      if (kx) {
        // the game's landing(s) for this exit, the nearest door square first; a landing that is a trap is not used
        const cand = d.edgeSide ? kx.edges.filter((e) => e[0] === d.edgeSide && e[1] === destRid).map((e) => ({ dist: 0, a: [e[2], e[3]] as [number, number] }))
          : kx.doors.filter((x) => x[2] === destRid).map((x) => ({ dist: Math.hypot(x[0] - d.row, x[1] - d.col), a: [x[3], x[4]] as [number, number] })).filter((c) => c.dist <= 6);
        if (d.land) cand.unshift({ dist: -1, a: d.land });   // the door's own landing first
        landings = cand.sort((p, q) => p.dist - q.dist).map((c) => c.a).filter((a) => !TRAP.has(`${destRid},${a[0]},${a[1]}`));
        if (cand.length && !landings.length) { console.log(`  ${roo}: door ${d.row},${d.col} to ${toRoo} dropped: every landing it has is a trap`); continue; }
      }
      if (landings.length) {
        [arrRow, arrCol] = landings[0];
      } else if (d.edgeSide && arr.length) {
        const opposite: Record<string, "N" | "S" | "E" | "W"> = { N: "S", S: "N", E: "W", W: "E" };
        const reverse = (exits[toRoo + ".roo"]?.edges ?? []).find((e) => e.to.toLowerCase() === roo + ".roo".toLowerCase());
        const side = reverse?.side ?? opposite[d.edgeSide];
        const dest = load(toRoo + ".roo");
        const edgeDistance = (p: [number, number]) => side === "N" ? p[0] - 1 : side === "S" ? dest.rows - p[0] : side === "W" ? p[1] - 1 : dest.cols - p[1];
        const a = arr.slice().sort((p, q) => edgeDistance(p) - edgeDistance(q))[0];
        arrRow = a[0]; arrCol = a[1];
      } else {
        // the arrival in that room nearest its door back to this one
        const back = (exits[toRoo + ".roo"]?.doors ?? []).filter((x) => x[2]?.toLowerCase() === roo + ".roo");
        if (back.length && arr.length) {
          const br = mean(back.map((x) => x[0])), bc = mean(back.map((x) => x[1]));
          const a = arr.slice().sort((p, q) => Math.hypot(p[0] - br, p[1] - bc) - Math.hypot(q[0] - br, q[1] - bc))[0];
          arrRow = a[0]; arrCol = a[1];
        }
      }
      if (!arrRow && arr.length) {
        // no door of that room leads back here (the way back is a zone or a one-way drop): any square the room lists as an arrival will do
        [arrRow, arrCol] = arr[0];
        console.log(`  ${roo}: door to ${toRoo}: no way back listed, arrival ${arrRow},${arrCol} of its list`);
      }
      if (!arrRow) { console.log(`  ${roo}: door to ${toRoo} dropped: no arrival`); continue; }
    } else {
      const e = ERRANDS.find(([re]) => re.test(toRoo));
      if (!e) { console.log(`  ${roo}: door to ${toRoo} is neither`); continue; }
      kindD = 2; purpose = e[1];
    }
    // a room-edge exit has no square of its own (the baker put one in the middle of the side, often in the void beyond the floor, where no bot can plan to): its door square is the
    // main-floor square where the floor reaches that side (the approach node). edge = 1 marks it (the walker may step on it while travelling elsewhere: it is not a door square).
    const isEdge = d.edgeSide !== undefined && !process.env.NAV_NO_LANDING;   // (NAV_NO_LANDING: control bake without the landing squares, for comparisons)
    const probed = isEdge ? EDGEL[String(ridOf(roo + ".roo"))] : undefined;      // a room that edgeprobe.py tested: an edge exit missing from its list has no landing the planner can reach
    const kxO = isEdge ? KODX[String(ridOf(roo + ".roo"))]?.edges : undefined;
    const ov0 = probed?.[`${toRoo}:${d.edgeSide}`];
    const ov = ov0 && kxO?.length && edgeTaken(kxO, d.edgeSide!, ov0[0], ov0[1]) !== byRoo.get(toRoo) ? undefined : ov0;      // (a probed landing on a square the game sends elsewhere is not used)
    if (probed && !ov0) { console.log(`  ${roo}: edge exit ${d.edgeSide} to ${toRoo} dropped: no square on that side can be reached by the planner (edgeprobe.py)`); continue; }
    let sq = isEdge ? (ov ? { row: ov[0], col: ov[1] } : nodes[node]) : { row: d.row, col: d.col };
    if (!isEdge) {
      // a ZONE exit: the door square is the zone square on the main floor nearest the approach node (not the zone's corner, which may be unreachable)
      const zs = (ZONES[roo + ".roo"] ?? []).filter((z) => z.to.toLowerCase() === d.to!.toLowerCase());
      if (zs.length) {
        const fns = zs.map((z) => new Function("new_row", "new_col", "ROWS", "COLS", `return !!(${z.when});`) as (r: number, c: number, R: number, C: number) => boolean);
        const from = centre(nodes[node].row, nodes[node].col);
        let best = -1, bd = Infinity, bsq = sq;
        for (let i = 0; i < g.walk.length; i++) {
          if (!isOpen(g, i) || g.area[i] !== mainArea) continue;
          const q = cellCentre(g, i);
          if (Math.round((q.x - SQ / 2) % SQ) !== 0 || Math.round((q.y - SQ / 2) % SQ) !== 0) continue;
          const s2 = squareOf(q.x, q.y);
          if (!fns.some((f) => f(s2.row, s2.col, room.rows, room.cols))) continue;
          const dd = dist(q, from);
          if (dd < bd) { bd = dd; best = i; bsq = s2; }
        }
        if (best >= 0) { if (bsq.row !== sq.row || bsq.col !== sq.col) console.log(`  ${roo}: zone exit to ${toRoo}: door square ${sq.row},${sq.col} -> ${bsq.row},${bsq.col} (a zone square on the main floor)`); sq = bsq; }
        else console.log(`  ${roo}: zone exit to ${toRoo}: no main-floor square inside the zone, door square ${sq.row},${sq.col} kept`);
      }
    }
    if (isEdge) {
      // an edge exit whose side the floor never comes near cannot be walked to (nobody can leave there): left out, and logged for the manual audit
      const gap = d.edgeSide === "N" ? sq.row - 1 : d.edgeSide === "S" ? room.rows - sq.row : d.edgeSide === "W" ? sq.col - 1 : room.cols - sq.col;
      if (gap > 2.5) { console.log(`  ${roo}: edge exit ${d.edgeSide} to ${toRoo} dropped: the floor ends ${gap} squares short of that side`); continue; }
    }
    { const ov2 = OVR[`${roo}:${toRoo}`]; if (ov2) { if (ov2[0] !== sq.row || ov2[1] !== sq.col) console.log(`  ${roo}: exit to ${toRoo}: square ${sq.row},${sq.col} -> ${ov2[0]},${ov2[1]} (the square the game fired when the owner walked out)`); sq = { row: ov2[0], col: ov2[1] }; } }
    doors.push({ row: sq.row, col: sq.col, to: toRoo, node, kind: kindD, purpose, destRid, arrRow, arrCol, edge: isEdge ? 1 : 0 });
  }
  // a door square NO arrival can reach (exit audit: 0 of N) while another door of the room leads to the same room is a dead duplicate (Jasper East (45,32) next to (44,32), both to Jasper West): left out,
  // so no route is planned through a door a bot cannot walk to. A room's only door to a destination is kept even when unreachable (the audit lists it for a look).
  {
    const sq0 = SQUARES[String(rid)];
    for (let k = doors.length - 1; k >= 0 && sq0; k--) {
      const d0 = doors[k], v = sq0[`${d0.row},${d0.col}`];
      if (d0.edge || !v || v[1] === 0 || v[0] > 0) continue;
      if (doors.some((o, j) => j !== k && !o.edge && o.to === d0.to && (sq0[`${o.row},${o.col}`]?.[0] ?? 0) > 0)) { console.log(`  ${roo}: door ${d0.row},${d0.col} to ${d0.to} left out: no arrival reaches it and another door to ${d0.to} does`); doors.splice(k, 1); }
    }
  }
  // a town with a travel portal: a free transit door to every other portal's arrival square, standing at the portal itself
  const myPortal = PORTALS.find((p) => p.rid === rid);
  const portalDoors: Door[] = [];
  if (myPortal) {
    // the portal square may be blocked for the nav grid: then the bot stands at the arrival square beside it (the portal's range is 3 squares)
    let pr = myPortal.row, pc = myPortal.col, node = nodeFor(centre(pr, pc));
    if (node < 0) { pr = myPortal.arrRow; pc = myPortal.arrCol; node = nodeFor(centre(pr, pc)); }
    if (node < 0) {
      // still none (the nav grid has no walkable line to it): the nearest node within 12 squares; the server's own movement check (navcheck) judges the walk
      let bd = 12 * SQ;
      const a = centre(pr, pc);
      for (let k = 0; k < pts.length; k++) { const d = dist(pts[k], a); if (d < bd) { bd = d; node = k; } }
      console.log(`  ${roo}: portal ${pr},${pc} uses the nearest node ${node}`);
    }
    if (node < 0) console.log(`  ${roo}: PORTAL has no floor beside it, no portal doors`);
    else for (const q of PORTALS) {
      if (q.rid === rid) continue;
      portalDoors.push({ row: pr, col: pc, to: "portal", node, kind: 1, purpose: 0, destRid: q.rid, arrRow: q.arrRow, arrCol: q.arrCol, edge: 0 });
    }
  }
  // a hall's door is where its globe is read; more than MAX_DOORS cannot be written as one list (the portal doors always fit)
  doors.length = Math.min(doors.length, MAX_DOORS - portalDoors.length);
  doors.push(...portalDoors);
  for (const pair of NOWAY.get(rid) ?? []) {
    const [a, b] = pair.split(">").map((x) => x.split(",").map(Number));
    const d = doors.find((x) => x.to !== "portal" && x.row === b[0] && x.col === b[1]);
    if (d) (d.blocked ??= []).push(a[0] * 1000 + a[1]);
  }

  const gl = (globes.get(roo + ".roo") ?? [])
    .map(([row, col]) => ({ row, col, node: nodeFor(centre(row, col)) }))
    .filter((x) => x.node >= 0);

  return { roo, rid, name: nameOf(rid), kind, region, nodes, adj, doors, globes: gl, parts: comp().n };
}

// ---- go ---------------------------------------------------------------------------------------------------------------------------------
const byRoo = new Map<string, number>();
// Keep the named town regions for the current town-life routines, then add every
// other unique room asset. Duplicate room records (notably Death Realm entries)
// share a .roo; ridOf selects the playable room number for that asset.
for (const r of REGIONS) for (const roo of [...r.streets, ...r.inns]) byRoo.set(roo, ridOf(roo + ".roo"));
for (const roo of new Set(rooms.filter((r) => r.name !== "Death Realm").map((r) => r.roo.replace(/\.roo$/i, "").toLowerCase()))) {
  if (!byRoo.has(roo)) byRoo.set(roo, ridOf(roo + ".roo"));
}
const graphs: Graph[] = [];
// as many spread nodes as keep the graph in one piece within the 40 a list may hold (the door approaches take their share)
const bakeRoom = (roo: string, kind: Graph["kind"], home: number) => {
  let g!: Graph & { parts: number };
  for (let want = kind === "inn" ? 14 : 26; want >= 4; want -= 3) {
    g = bake(roo, byRoo.get(roo)!, kind, home, byRoo, want);
    if (g.parts === 1) break;
  }
  if (g.parts !== 1) console.log(`!! ${roo}: ${g.parts} pieces`);
  for (const [a, b] of (loadProbe(byRoo.get(roo)!) ? [] : prunePairs[String(byRoo.get(roo))] ?? [])) {
    const n0 = g.adj[a]?.length ?? 0;
    if (g.adj[a]) g.adj[a] = g.adj[a].filter((e) => e.to !== b);
    if (g.adj[b]) g.adj[b] = g.adj[b].filter((e) => e.to !== a);
    if (n0 !== (g.adj[a]?.length ?? 0)) pruned++;
  }
  return g;
};
for (const r of REGIONS) {
  for (const roo of r.streets) graphs.push(bakeRoom(roo, "street", r.home));
  for (const roo of r.inns) graphs.push(bakeRoom(roo, "inn", r.home));
}
const townRoos = new Set(REGIONS.flatMap((r) => [...r.streets, ...r.inns]));
for (const [roo] of byRoo) {
  if (!townRoos.has(roo)) graphs.push(bakeRoom(roo, "room", 0));
}

// ---- Blakod ---------------------------------------------------------------------------------------------------------------------------
const lit = (v: unknown): string => {
  if (!Array.isArray(v)) return String(v);
  if (!v.length) return "$";
  // Blakod list literals are limited to 40 entries. Very long maze routes are
  // emitted as Cons chains so their full path is retained without an oversized
  // literal.
  if (v.length > 40) return `Cons(${lit(v[0])},${lit(v.slice(1))})`;
  return `[${v.map(lit).join(",")}]`;
};
let k = `// GENERATED by prime_client/overlay/tools/prime/navbake.ts from the client's nav grid (${new Date().toISOString().slice(0, 10)}): do not edit by hand.\n`;
k += `// Navmeshes for every room asset with usable floor. Current town-life behavior uses the nine regions listed below.\n`;
k += `// Room IDs follow the playable room numbers in rooms.json.\n\n`;
k += `PrimeNavData is PrimeBots\n\nconstants:\n\n   include blakston.khd\n\nresources:\n\nclassvars:\n\nproperties:\n\nmessages:\n\n`;
k += `   NavVersion()\n   "Minutes since 1970 when this data was baked: the cached door tables of the route search are dropped when it changes."\n   {\n      return ${Math.floor(Date.now() / 60000)};\n   }\n\n`;
k += `   NavTowns()\n   "[ [ home room number, [ street rooms ], [ inns ] ], ... ] of the towns bots live in."\n   {\n      return [\n`;
k += REGIONS.map((r) => `         ${lit([r.home, r.streets.map((s) => byRoo.get(s)), r.inns.map((s) => byRoo.get(s))])}`).join(",\n");
k += `\n      ];\n   }\n\n`;
// one message per part of a room (the compiler allows 50 locals and parameters in a message)
const parts: string[] = [];
k += `   NavRoom(rid = 0)\n   "[ nodes [ [row,col] ], routes [ for each node [ [neighbour node, via squares [ [row,col] ] or $ ] ] ], doors [ [row,col,node,kind (1 transit, 2 errand),purpose,destination room,arrival row,arrival col] ], globes [ [row,col,node] ] ] of a room, or $."\n   {\n`;
for (const g of graphs) {
  k += `      if rid = ${g.rid}\n      {\n         // ${g.name} (${g.roo}.roo, ${g.nodes.length} nodes)\n         return [ Send(self,@NavN${g.rid}), Send(self,@NavR${g.rid}), Send(self,@NavD${g.rid}), Send(self,@NavG${g.rid}) ];\n      }\n\n`;
  parts.push(`   NavN${g.rid}()\n   {\n      return ${lit(g.nodes.map((n) => [n.row, n.col]))};\n   }\n`);
  // Keep long walk paths out of the route message: nested Cons expressions
  // can exceed Blakod's per-message temporary/local limit.
  const routeRows = g.adj.map((a, ni) => a.map((e, ei) => {
    if (e.via.length <= 20) return [e.to + 1, e.via.length ? e.via.map((v) => (v.fr === undefined ? [v.row, v.col] : [v.row, v.col, v.fr, v.fc])) : "$" ];
    const helper = `NavP${g.rid}_${ni}_${ei}`;
    const path = e.via.map((v) => (v.fr === undefined ? [v.row, v.col] : [v.row, v.col, v.fr, v.fc]));
    parts.push(`   ${helper}()\n   {\n      local l;\n\n      l = $;\n` + path.slice().reverse().map((p) => `      l = Cons(${lit(p)},l);\n`).join("") + `      return l;\n   }\n`);
    return [e.to + 1, `Send(self,@${helper})`];
  }));
  // Build each node's adjacency list separately so the full room graph does
  // not accumulate compiler temporaries in one message.
  routeRows.forEach((a, ni) => parts.push(`   NavA${g.rid}_${ni}()\n   {\n      return ${lit(a)};\n   }\n`));
  parts.push(`   NavR${g.rid}()\n   {\n      local l;\n\n      l = $;\n` + routeRows.map((_, ni) => `      l = Cons(Send(self,@NavA${g.rid}_${ni}),l);\n`).reverse().join("") + `\n      return l;\n   }\n`);
  parts.push(`   NavD${g.rid}()\n   {\n      return ${lit(g.doors.map((d) => [d.row, d.col, d.node + 1, d.kind, d.purpose, d.destRid, d.arrRow, d.arrCol, d.edge, d.blocked ?? []]))};\n   }\n`);
  parts.push(`   NavG${g.rid}()\n   {\n      return ${lit(g.globes.map((x) => [x.row, x.col, x.node + 1]))};\n   }\n`);
}
k += `      return $;\n   }\n\n` + parts.join("\n") + `\nend\n`;
writeFileSync(o.out!, k);
if (o.json) writeFileSync(o.json, JSON.stringify(graphs, null, 1));
console.log(`relaxed routes: ${relaxedRoutes}, pruned routes: ${pruned}`);
for (const g of graphs) {
  console.log(`${String(g.rid).padStart(5)} ${g.roo.padEnd(16)} ${g.kind.padEnd(6)} nodes ${String(g.nodes.length).padStart(2)} links ${String(g.adj.reduce((a, b) => a + b.length, 0) / 2).padStart(3)} via ${g.adj.reduce((a, b) => a + b.reduce((x, y) => x + y.via.length, 0), 0) / 2} doors ${g.doors.length} (transit ${g.doors.filter((d) => d.kind === 1).length}) globes ${g.globes.length}`);
}
