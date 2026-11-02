// Prime (ours): where the time goes between pressing Play and a finished first picture. Drives the web client in a headless browser (like shot.ts), and prints a timeline:
// every picture/json/sound request (seconds after Play), when the "Loading"/"Entering" overlay shows and goes, and when the requests stop.
//   node tools/prime/loadtime.ts --user NAME --pass PW [--char-click "Name"] [--url http://127.0.0.1:5173/] [--seconds 25]
import { parseArgs } from "node:util";
import { chromium } from "@playwright/test";

const { values: o } = parseArgs({
  options: {
    url: { type: "string", default: "http://127.0.0.1:5173/" },
    user: { type: "string" }, pass: { type: "string" },
    play: { type: "string", default: "OK" },
    seconds: { type: "string", default: "25" },
  },
});
const browser = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
let t0 = 0;
const now = () => ((performance.now() - t0) / 1000).toFixed(2);
const reqs: { t: string; url: string; ms?: number }[] = [];
const started = new Map<string, number>();
page.on("request", (r) => { if (t0) started.set(r.url(), performance.now()); });
page.on("requestfinished", (r) => {
  if (!t0) return;
  const s = started.get(r.url()) ?? performance.now();
  reqs.push({ t: ((s - t0) / 1000).toFixed(2), url: r.url().replace(/^https?:\/\/[^/]+/, ""), ms: Math.round(performance.now() - s) });
});
page.on("console", (m) => { if (m.text().includes("[prime]")) console.log(`${now()}s`, m.text()); });
page.on("pageerror", (e) => console.log("[pageerror]", e.message));
await page.goto(o.url!);
await page.waitForTimeout(2500);
await page.getByText("Log in", { exact: false }).first().click();
await page.waitForTimeout(700);
await page.locator("input").nth(0).fill(o.user!);
await page.locator("input").nth(1).fill(o.pass!);
await page.getByText("Log In", { exact: true }).first().click();
await page.waitForTimeout(6000);
t0 = performance.now();
await page.getByText(o.play!, { exact: true }).first().click();
const marks: string[] = [];
let overlay = false;
const end = performance.now() + Number(o.seconds) * 1000;
while (performance.now() < end) {
  const on = await page.evaluate(() => {
    const e = document.querySelector(".loading");
    return !!e && (e as HTMLElement).offsetParent !== null ? (e.textContent ?? "") : "";
  });
  if (!!on !== overlay) { overlay = !!on; marks.push(`${now()}s overlay ${overlay ? `on (${on})` : "off"}`); }
  await page.waitForTimeout(100);
}
await page.screenshot({ path: "/tmp/loadtime.png" });
console.log(marks.join("\n"));
console.log(`${reqs.length} requests after Play:`);
const kinds = new Map<string, number>();
for (const r of reqs) { const k = r.url.split("?")[0].split(".").pop() ?? ""; kinds.set(k, (kinds.get(k) ?? 0) + 1); }
console.log([...kinds.entries()].map(([k, n]) => `${k}:${n}`).join(" "));
const last = reqs.length ? Math.max(...reqs.map((r) => Number(r.t) + (r.ms ?? 0) / 1000)) : 0;
console.log(`last request ends ${last.toFixed(2)}s after Play`);
for (const r of reqs.slice().sort((a, b) => Number(a.t) - Number(b.t)).filter((r) => Number(r.t) > 3.0)) console.log(` ${r.t}s ${r.ms}ms ${r.url}`);
await browser.close();
