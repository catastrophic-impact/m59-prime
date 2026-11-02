// Prime (ours): WHAT A PLAYER CAN REACH, by the client's own movement code (packages/world/src/movement.ts = clientd3d/move.c, with its wall sliding and its small object blocking).
//   node tools/prime/clientreach.ts (kept in claude_tools/, copy it to the client build tree: tools/prime/) --assets <dir with the .roo files> --bake <navbake.json> [--objects <navobjects.json>] --rooms 330,206 --out <result.json> [--cell 128]
// For every room: a breadth-first walk from each entrance square: from a cell centre a real PlayerMover step is made in each of 8 directions; where it ends (wall slides included) is the cell it reaches.
// Result per room: the regions found, for every entrance and door whether it lies in the biggest region reached from the entrances (same layout as prime_server/scripts/roomreach.py's json).
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { FINENESS, parseRoo } from "../../packages/formats/src/index.ts";
import { PlayerMover, MOVEON } from "../../packages/world/src/movement.ts";
const { values: o } = parseArgs({ options: { assets: { type: "string" }, bake: { type: "string" }, objects: { type: "string" }, rooms: { type: "string" }, out: { type: "string" }, cell: { type: "string" }, box: { type: "string" }, walk: { type: "string" }, from: { type: "string" } } });
const CELL = Number(o.cell ?? 128);
// --box r0,c0,r1,c1 (squares): only cells inside it are walked (a quick look at one spot instead of the whole room)
const BOX = o.box ? o.box.split(",").map(Number) : null;
const bake = JSON.parse(readFileSync(o.bake!, "utf8")) as any[];
const objectsAll: Record<string, [number, number][]> = o.objects ? JSON.parse(readFileSync(o.objects, "utf8")) : {};
const byRid = new Map<number, any>(bake.map((r) => [r.rid, r]));
const sink = { move() {}, turn() {} };
const DIRS = [0, 1, 2, 3, 4, 5, 6, 7].map((k) => ({ angle: k * 512, dc: Math.round(Math.cos((k * Math.PI) / 4)), dr: Math.round(Math.sin((k * Math.PI) / 4)) }));

// --walk "r1,c1:r2,c2" (rooms: one): a PLAYER's walk with the client's own mover: it faces the goal and holds the walk key; when it makes no progress it turns 45 or 90 degrees either way (like someone
// steering round an obstacle). Prints whether it got within a square of the goal, or walked off the room's edge there (a door in the edge), and its path.
if (o.walk) {
  const [a, b] = o.walk.split(":").map((x) => x.split(",").map(Number));
  const rid = Number(o.rooms);
  const info = byRid.get(rid)!;
  const room = parseRoo(new Uint8Array(readFileSync(join(o.assets!, info.roo + ".roo"))));
  let edgeAsked = false;
  const mover = new PlayerMover({ move() { edgeAsked = true; }, turn() {} });
  mover.room = room;
  const objs = (objectsAll[String(rid)] ?? []).map(([x, y], i) => ({ id: 1000 + i, x, y, info: { moveOnType: MOVEON.NO } }));
  const gx = (b[1] - 0.5) * FINENESS, gy = (b[0] - 0.5) * FINENESS;
  mover.place((a[1] - 0.5) * FINENESS, (a[0] - 0.5) * FINENESS, 0);
  let now = 1_000_000, best = 1e18, stuck = 0, steps = 0, trail: string[] = [];
  const offsets = [0, 512, -512, 1024, -1024, 1536, -1536, 2048];
  for (; steps < 6000; steps++) {
    const toGoal = Math.round((Math.atan2(gy - mover.y, gx - mover.x) * 4096) / (2 * Math.PI)) & 4095;
    const d = Math.hypot(gx - mover.x, gy - mover.y);
    if (d < FINENESS) break;
    if (edgeAsked && d < 3 * FINENESS) break;
    if (d < best - 8) { best = d; stuck = 0; } else stuck++;
    const off = stuck < 3 ? 0 : offsets[1 + (Math.floor(stuck / 3) % 7)];
    mover.angle = (toGoal + off + 4096) & 4095;
    const bx = mover.x, by = mover.y;
    now += 100;
    mover.update({ forward: 1, strafe: 0, run: false }, 85, now, objs, -1);
    if (steps % 40 === 0) trail.push(`(${(mover.y / FINENESS + 0.5).toFixed(1)},${(mover.x / FINENESS + 0.5).toFixed(1)})`);
    if (Math.hypot(mover.x - bx, mover.y - by) < 1) stuck++;
  }
  const d = Math.hypot(gx - mover.x, gy - mover.y) / FINENESS;
  console.log(`walk ${a} -> ${b} in room ${rid}: ${steps} steps, ends at (${(mover.y / FINENESS + 0.5).toFixed(2)},${(mover.x / FINENESS + 0.5).toFixed(2)}), ${d.toFixed(2)} squares from the goal, edge exit asked: ${edgeAsked}`);
  console.log("trail: " + trail.join(" "));
  process.exit(0);
}
const result: any[] = [];
for (const rid of (o.rooms ?? "").split(",").map(Number)) {
  const info = byRid.get(rid);
  if (!info) { console.error(`no room ${rid}`); continue; }
  const t0 = Date.now();
  const room = parseRoo(new Uint8Array(readFileSync(join(o.assets!, info.roo + ".roo"))));
  const mover = new PlayerMover(sink);
  mover.room = room;
  const nc = Math.ceil((room.cols * FINENESS) / CELL) + 1, nr = Math.ceil((room.rows * FINENESS) / CELL) + 1;
  const objs = (objectsAll[String(rid)] ?? []).map(([x, y], i) => ({ id: 1000 + i, x, y, info: { moveOnType: MOVEON.NO } }));
  const label = new Int32Array(nc * nr); // 0 not visited
  const sizes: number[] = [0];
  let now = 1_000_000;
  const cellOf = (x: number, y: number) => { const c = Math.min(nc - 1, Math.max(0, Math.round(x / CELL - 0.5))), r = Math.min(nr - 1, Math.max(0, Math.round(y / CELL - 0.5))); return r * nc + c; };
  const centre = (i: number): [number, number] => [((i % nc) + 0.5) * CELL, (Math.floor(i / nc) + 0.5) * CELL];
  const flood = (start: number): number => {
    const id = sizes.length; sizes.push(0);
    const q = [start]; label[start] = id;
    for (let h = 0; h < q.length; h++) {
      const cur = q[h]; sizes[id]++;
      const [cx, cy] = centre(cur);
      for (const d of DIRS) {
        mover.place(cx, cy, now); mover.angle = d.angle; now += 200;
        // a step of one cell: distance = MOVEUNITS (FINENESS/4) * dt / 85 for dt < 85
        const diag = d.dc !== 0 && d.dr !== 0;
        const want = CELL * (diag ? Math.SQRT2 : 1);
        const dt = Math.max(1, Math.round((want / (FINENESS / 4)) * 85));
        if (dt >= 85) { mover.update({ forward: 1, strafe: 0, run: false }, 85, now, objs, -1); const rest = want - FINENESS / 4; if (rest > 0) mover.update({ forward: 1, strafe: 0, run: false }, Math.round((rest / (FINENESS / 4)) * 85), now + 100, objs, -1); }
        else mover.update({ forward: 1, strafe: 0, run: false }, dt, now, objs, -1);
        const nx = mover.x, ny = mover.y;
        if (Math.abs(nx - cx) + Math.abs(ny - cy) < CELL * 0.5) continue; // did not really move
        const n = cellOf(nx, ny);
        if (BOX) { const [qx, qy] = centre(n); const sr = qy / FINENESS + 0.5, sc = qx / FINENESS + 0.5; if (sr < BOX[0] - 0.5 || sr > BOX[2] + 0.5 || sc < BOX[1] - 0.5 || sc > BOX[3] + 0.5) continue; }
        if (n !== cur && label[n] === 0) { label[n] = id; q.push(n); }
      }
    }
    return id;
  };
  // --from r,c (with --box r0,c0,r1,c1 and a coarse --cell 256): what the CLIENT's rules let a player reach from ONE square (a landing): the cells reached and their extent. A pocket reaches a few cells; a free landing fills the box.
  if (o.from) {
    const [fr, fc] = o.from.split(",").map(Number); flood(cellOf((fc - 0.5) * FINENESS, (fr - 0.5) * FINENESS));
    let n = 0, r0 = 1e9, r1 = -1e9, c0 = 1e9, c1 = -1e9;
    for (let i = 0; i < label.length; i++) if (label[i]) { n++; const [x, y] = centre(i); const rr = y / FINENESS + 0.5, cc = x / FINENESS + 0.5; r0 = Math.min(r0, rr); r1 = Math.max(r1, rr); c0 = Math.min(c0, cc); c1 = Math.max(c1, cc); }
    console.log(`room ${rid} from ${o.from}: the client's rules reach ${n} cells (${((Date.now() - t0) / 1000).toFixed(1)} s), rows ${r0.toFixed(1)}..${r1.toFixed(1)}, cols ${c0.toFixed(1)}..${c1.toFixed(1)}`);
    continue;
  }
  // entrances (squares where other rooms put you down) and doors of this room
  const ents = new Map<string, { sq: [number, number]; from: string[] }>();
  for (const r2 of bake) for (const d of r2.doors) if (d.destRid === rid) { const k = `${d.arrRow},${d.arrCol}`; if (!ents.has(k)) ents.set(k, { sq: [d.arrRow, d.arrCol], from: [] }); ents.get(k)!.from.push(r2.roo); }
  const sqCell = (row: number, col: number) => cellOf((col - 0.5) * FINENESS, (row - 0.5) * FINENESS);
  const regionOf = (row: number, col: number, near: number): number[] => {
    const base = sqCell(row, col), bc = base % nc, br = Math.floor(base / nc), out: number[] = [];
    for (let dr = -near; dr <= near; dr++) for (let dc = -near; dc <= near; dc++) { const c = bc + dc, r = br + dr; if (c >= 0 && r >= 0 && c < nc && r < nr && label[r * nc + c]) out.push(label[r * nc + c]); }
    return out;
  };
  // flood from every entrance (each unreached one starts a region), then from the doors' surroundings
  const entRes = [...ents.values()];
  for (const e of entRes) { const s = sqCell(e.sq[0], e.sq[1]); if (!label[s]) flood(s); }
  const main = sizes.length > 1 ? sizes.indexOf(Math.max(...sizes.slice(1))) : 0;
  const nearCells = Math.round((1.5 * FINENESS) / CELL);
  const res = {
    rid, name: info.name, roo: info.roo, walk: sizes.slice(1).reduce((a, b) => a + b, 0), regions: sizes.length - 1, main: sizes[main] ?? 0, seconds: (Date.now() - t0) / 1000,
    ent: entRes.map((e) => { const c = label[sqCell(e.sq[0], e.sq[1])]; return { sq: e.sq, from: e.from.sort(), in_main: c === main && c > 0, region_cells: c ? sizes[c] : 0 }; }),
    door: info.doors.map((d: any) => { const rs = regionOf(d.row, d.col, nearCells); let best = 1e9; for (let i = 0; i < label.length; i++) if (label[i] === main) { const [x, y] = centre(i); const dd = Math.hypot(x / FINENESS + 0.5 - d.col, y / FINENESS + 0.5 - d.row); if (dd < best) best = dd; } return { sq: [d.row, d.col], to: d.to, in_main: rs.includes(main), region_cells: rs.length ? Math.max(...rs.map((x) => sizes[x])) : 0, nearest_reached_squares: Math.round(best * 100) / 100 }; }),
  };
  result.push(res);
  for (const d of res.door) console.log(`  door ${d.sq} -> ${d.to}: nearest cell the client rules reach is ${(d as any).nearest_reached_squares} squares away`);
  console.log(`room ${rid} ${info.name}: ${res.seconds}s, ${nc}x${nr} cells, region from entrances ${res.main} cells; entrances in main ${res.ent.filter((e: any) => e.in_main).length}/${res.ent.length}, doors reachable ${res.door.filter((d: any) => d.in_main).length}/${res.door.length}`);
}
writeFileSync(o.out!, JSON.stringify(result));
