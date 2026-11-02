// Prime (ours): offline look at a room's nav grid: node tools/prime/gridprobe.ts d6e6.roo 3 7   (room file, x square, y square of the spot)
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { parseRoo } from "../../packages/formats/src/index.ts";
import { buildNavGrid, nearestCell } from "../../packages/world/src/navGrid.ts";
import { findWaterTextures } from "../assets/waterTextures.ts";
const A = `${process.env.PRIME_WORK}/assets`;
const [roo, sx, sy] = process.argv.slice(2);
const water = new Set(findWaterTextures(readdirSync(A).filter((f) => f.endsWith(".roo")).map((f) => parseRoo(new Uint8Array(readFileSync(join(A, f)))))));
const room = parseRoo(new Uint8Array(readFileSync(join(A, roo!))));
const g = buildNavGrid(room, process.env.NOWATER ? undefined : water, true, true, 2);
const c0 = nearestCell(g, Number(sx) * 1024, Number(sy) * 1024, 8, 0, false);
const sizes = new Map<number, number>();
for (let i = 0; i < g.area.length; i++) if (g.area[i]) sizes.set(g.area[i]!, (sizes.get(g.area[i]!) ?? 0) + 1);
console.log(`${roo}: grid ${g.cols}x${g.rows} cells (half squares); start cell ${c0} area ${g.area[c0]} size ${sizes.get(g.area[c0]!)}; biggest areas ${[...sizes.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([a, n]) => a + ":" + n).join(" ")}`);
const mark = (i: number) => (i === c0 ? "@" : !g.walk[i] ? "#" : g.area[i] === g.area[c0] ? "o" : String.fromCharCode(97 + (g.area[i]! % 26)));
const step = Math.max(1, Math.ceil(g.cols / 110));
for (let r = 0; r < (process.env.QUIET ? 0 : g.rows); r += step) { let l = ""; for (let c = 0; c < g.cols; c += step) l += mark(r * g.cols + c); console.log(l); }
