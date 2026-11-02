// Prime (ours): dump what the client nav grid knows about every room, for drawing room maps (scripts/roommap.py).
//   node tools/prime/navdump.ts --assets <assets dir> --out <dir>      -> <dir>/<roo>.json { roo, rows, cols, areas: string[] (one char per square), walls: [[x0,y0,x1,y1]] in squares }
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { FINENESS, SF, parseRoo } from "../../packages/formats/src/index.ts";
import { buildNavGrid, cellAt, isOpen } from "../../packages/world/src/navGrid.ts";
const { values: o } = parseArgs({ options: { assets: { type: "string" }, out: { type: "string" } } });
const SQ = FINENESS;
const TOWN = new Set(["tos", "toseast", "tosinn", "tostavern", "barls", "barln", "barlport", "barinn", "barlbar1", "cornoth", "corinn", "marion", "greenplantation", "marinn", "raza", "razainn", "razabar", "jaseast", "jaswest", "jasinn", "jastavrn", "settle1", "settle2", "kocinn", "koctav", "bergcity", "berginn", "jixa", "jixa_inn"]);
mkdirSync(o.out!, { recursive: true });
let n = 0;
for (const f of readdirSync(o.assets!).filter((x) => x.endsWith(".roo"))) {
  const roo = f.replace(/\.roo$/i, "").toLowerCase();
  try {
    const raw = parseRoo(new Uint8Array(readFileSync(join(o.assets!, f))));
    const room = TOWN.has(roo) ? raw : { ...raw, sectors: raw.sectors.map((s) => ({ ...s, flags: s.flags & ~SF.DEPTH_MASK })) };
    const g = buildNavGrid(room, new Set<number>());
    const areas: string[] = [];
    for (let r = 1; r <= room.rows; r++) {
      let line = "";
      for (let c = 1; c <= room.cols; c++) {
        let best = 0;
        for (const [dy, dx] of [[0, 0], [0, 0.5], [0.5, 0], [0.5, 0.5], [0.25, 0.25]]) {
          const cell = cellAt(g, (c - 1 + dx) * SQ + SQ / 4, (r - 1 + dy) * SQ + SQ / 4);
          if (cell >= 0 && isOpen(g, cell) && g.area[cell] > 0 && (best === 0 || g.area[cell] < best)) best = g.area[cell];
        }
        line += best === 0 ? "." : best > 9 ? "+" : String(best);
      }
      areas.push(line);
    }
    // x0,y0,x1,y1 in squares; a,b,c = the wall's separator in the grid's own units (side = a*x + b*y + c, x and y in 1/1024 squares); fromPos / fromNeg = it stops people coming from that side
    const walls = g.blockers.map((b) => [+(b.x0 / SQ).toFixed(2), +(b.y0 / SQ).toFixed(2), +(b.x1 / SQ).toFixed(2), +(b.y1 / SQ).toFixed(2), b.a, b.b, b.c, b.fromPos ? 1 : 0, b.fromNeg ? 1 : 0]);
    writeFileSync(join(o.out!, `${roo}.json`), JSON.stringify({ roo, rows: room.rows, cols: room.cols, areas, walls }));
    n++;
  } catch (e) { console.error(`${roo}: ${(e as Error).message}`); }
}
console.error(`dumped ${n} rooms`);
