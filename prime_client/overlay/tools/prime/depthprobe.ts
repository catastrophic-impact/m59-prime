// node tools/prime/depthprobe.ts d5.roo 21.5 28 37 : sector water depth (0-3) along a vertical line
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseRoo, leafAt, SF, floorHeightAt } from "../../packages/formats/src/index.ts";
const A = `${process.env.PRIME_WORK}/assets`;
const [roo, x, y0, y1] = process.argv.slice(2);
const room: any = parseRoo(new Uint8Array(readFileSync(join(A, roo!))));
let line = "";
for (let y = Number(y0); y <= Number(y1); y += 0.5) {
  const leaf: any = leafAt(room, Number(x) * 1024, y * 1024);
  const s = leaf?.sector ? room.sectors[leaf.sector - 1] : null;
  line += `${y}:${s ? (s.flags & SF.DEPTH_MASK) + "/h" + Math.round(floorHeightAt(s, Number(x) * 1024, y * 1024) / 16) : "none"} `;
}
console.log(line);
