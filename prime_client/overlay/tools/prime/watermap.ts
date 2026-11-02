// node tools/prime/watermap.ts d6e6.roo : ASCII map of a room, 1 char = 1 square: ~ water (depth 1-3, bigger digit = deeper), . dry floor, # no sector/blocked, lowercase = a sunken floor 4+ units below its neighbours' average
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseRoo, leafAt, SF, floorHeightAt } from "../../packages/formats/src/index.ts";
const A = `${process.env.PRIME_WORK}/assets`;
const room: any = parseRoo(new Uint8Array(readFileSync(join(A, process.argv[2]!))));
const W = Math.ceil(room.width / 1024), H = Math.ceil(room.height / 1024);
const hs: (number | null)[][] = [];
for (let r = 0; r < H; r++) { hs[r] = []; for (let c = 0; c < W; c++) { const l: any = leafAt(room, (c + 0.5) * 1024, (r + 0.5) * 1024); const s = l?.sector ? room.sectors[l.sector - 1] : null; hs[r]![c] = s ? floorHeightAt(s, (c + 0.5) * 1024, (r + 0.5) * 1024) : null; } }
console.log(`${process.argv[2]} ${W}x${H} squares (rows down = south, cols right = east)`);
let head = "    "; for (let c = 0; c < W; c += 10) head += String(c).padEnd(10); console.log(head);
for (let r = 0; r < H; r++) {
  let line = String(r).padStart(3) + " ";
  for (let c = 0; c < W; c++) {
    const l: any = leafAt(room, (c + 0.5) * 1024, (r + 0.5) * 1024); const s = l?.sector ? room.sectors[l.sector - 1] : null;
    if (!s) { line += "#"; continue; }
    const d = s.flags & SF.DEPTH_MASK; if (d) { line += String(d); continue; }
    line += ".";
  }
  console.log(line);
}
