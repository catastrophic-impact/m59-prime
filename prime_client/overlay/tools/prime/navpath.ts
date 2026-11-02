// Prime (ours), experiment: the route a PLAYER could walk in one room, from the client's own nav grid (no server refusals), as waypoints with fine positions.
//   node tools/prime/navpath.ts --assets <assets dir> --room ka5 --from 44,24 --to 23,41 [--water]   -> JSON [[row,col,fineRow,fineCol], ...] on stdout
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { FINENESS, SF, parseRoo } from "../../packages/formats/src/index.ts";
import { buildNavGrid, cellAt, cellCentre, findCells, isOpen, type NavGrid } from "../../packages/world/src/navGrid.ts";
const { values: o } = parseArgs({ options: { assets: { type: "string" }, room: { type: "string" }, from: { type: "string" }, to: { type: "string" }, water: { type: "boolean" }, map: { type: "boolean" } } });
const SQ = FINENESS;
const raw = parseRoo(new Uint8Array(readFileSync(join(o.assets!, `${o.room}.roo`))));
// dungeon / wilderness rooms: the same wading rule as navbake.ts
const room = o.water ? raw : { ...raw, sectors: raw.sectors.map((s) => ({ ...s, flags: s.flags & ~SF.DEPTH_MASK })) };
const g: NavGrid = buildNavGrid(room, new Set<number>());
if (o.map) {
  // one character per square: the area number (largest = 1) of the best open cell in it, '.' when none; floor height steps are not shown
  const rows = room.rows, cols = room.cols;
  for (let r = 1; r <= rows; r++) {
    let line = "";
    for (let c = 1; c <= cols; c++) {
      let best = 0;
      for (const [dy, dx] of [[0, 0], [0, 0.5], [0.5, 0], [0.5, 0.5], [0.25, 0.25]]) {
        const cell = cellAt(g, (c - 1 + dx) * SQ + SQ / 4, (r - 1 + dy) * SQ + SQ / 4);
        if (cell >= 0 && isOpen(g, cell) && g.area[cell] > 0 && (best === 0 || g.area[cell] < best)) best = g.area[cell];
      }
      line += best === 0 ? "." : best > 9 ? "+" : String(best);
    }
    console.log(line);
  }
  process.exit(0);
}
const sq = (s: string) => s.split(",").map(Number) as [number, number];
const cellOfSquare = ([row, col]: [number, number]) => cellAt(g, (col - 1) * SQ + SQ / 2, (row - 1) * SQ + SQ / 2);
const a = cellOfSquare(sq(o.from!)), b = cellOfSquare(sq(o.to!));
console.error(`from cell ${a} open ${isOpen(g, a)} area ${g.area[a]}; to cell ${b} open ${isOpen(g, b)} area ${g.area[b]}; grid ${g.cols}x${g.rows}`);
const cells = findCells(g, a, b, 2000000);
if (!cells) { console.error("NO PATH on the client grid"); process.exit(2); }
const out = cells.map((c) => {
  const p = cellCentre(g, c);
  const row = Math.floor(p.y / SQ) + 1, col = Math.floor(p.x / SQ) + 1;
  // the client measures a square as FINENESS (1024) units, the server as 64: the fine position is converted to the server's
  return [row, col, Math.round(((p.y - (row - 1) * SQ) * 64) / SQ), Math.round(((p.x - (col - 1) * SQ) * 64) / SQ)];
});
console.error(`path: ${out.length} cells`);
console.log(JSON.stringify(out));
