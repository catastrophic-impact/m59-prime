import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { parseRoo } from "../../packages/formats/src/index.ts";
import { buildNavGrid, nearestCell } from "../../packages/world/src/navGrid.ts";
import { findWaterTextures } from "../assets/waterTextures.ts";
const A = `${process.env.PRIME_WORK}/assets`;
const [roo, sx, sy] = process.argv.slice(2);
const water = new Set(findWaterTextures(readdirSync(A).filter((f) => f.endsWith(".roo")).map((f) => parseRoo(new Uint8Array(readFileSync(join(A, f)))))));
const g = buildNavGrid(parseRoo(new Uint8Array(readFileSync(join(A, roo!)))), water);
const c0 = nearestCell(g, Number(sx) * 1024, Number(sy) * 1024, 8, 0, false), a0 = g.area[c0]!;
const big = (() => { const m = new Map<number, number>(); for (const a of g.area) if (a) m.set(a, (m.get(a) ?? 0) + 1); return [...m.entries()].sort((a, b) => b[1] - a[1])[0]![0]; })();
for (const reach of [1, 2, 3]) {
  const hits: string[] = [];
  for (let i = 0; i < g.area.length; i++) {
    if (g.area[i] !== a0) continue;
    const r = Math.floor(i / g.cols), c = i % g.cols;
    for (let dr = -reach; dr <= reach; dr++) for (let dc = -reach; dc <= reach; dc++) {
      const rr = r + dr, cc = c + dc; if (rr < 0 || cc < 0 || rr >= g.rows || cc >= g.cols) continue;
      if (g.area[rr * g.cols + cc] === big) hits.push(`(${(c / 2).toFixed(1)},${(r / 2).toFixed(1)})~(${(cc / 2).toFixed(1)},${(rr / 2).toFixed(1)})`);
    }
  }
  console.log(`pocket area ${a0} touches the main area within ${reach} cells (incl. diagonal) at ${hits.length} pairs: ${hits.slice(0, 4).join(" ")}`);
}
