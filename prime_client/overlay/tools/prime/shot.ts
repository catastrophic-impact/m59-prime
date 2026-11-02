// Prime (ours): drive the web client in a headless browser and take screenshots (needs `npx playwright install chromium`,
// the dev stack from prime_client/scripts/run_dev.sh and a running Prime server).
//   node tools/prime/shot.ts --do "click:Log in" --do "fill:0=name" --do "fill:1=pw" --do "click:Log In" --do "wait:6" --do "shot:/tmp/a.png"
// steps run in order: click:<text> (visible text, substring) | clickexact:<text> | fill:<input index>=<value> | select:<select index>=<option value> | drag:<visible text>><css selector> | clickat:x,y | wait:<seconds> | shot:<file> | key:<key> | down:<key> | up:<key> | eval:<js>
import { parseArgs } from "node:util";
import { chromium } from "@playwright/test";

const { values: o } = parseArgs({
  options: {
    url: { type: "string", default: "http://127.0.0.1:5173/" },
    do: { type: "string", multiple: true },
    width: { type: "string", default: "1280" }, height: { type: "string", default: "800" },
    log: { type: "boolean", default: false },
  },
});
const browser = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"] });
const page = await browser.newPage({ viewport: { width: Number(o.width), height: Number(o.height) } });
if (o.log) page.on("console", (m) => console.log("[browser]", m.type(), m.text()));
page.on("requestfailed", (r) => console.log("[reqfailed]", r.url()));
page.on("response", (r) => { if (r.status() >= 400) console.log("[http " + r.status() + "]", r.url()); });
page.on("pageerror", (e) => console.log("[pageerror]", e.message));
await page.goto(o.url!);
await page.waitForTimeout(2000);
for (const step of o.do ?? []) {
  const i = step.indexOf(":");
  const op = step.slice(0, i), arg = step.slice(i + 1);
  if (op === "click") await page.getByText(arg, { exact: false }).first().click();
  else if (op === "clickexact") await page.getByText(arg, { exact: true }).first().click();
  else if (op === "fill") { const j = arg.indexOf("="); await page.locator("input").nth(Number(arg.slice(0, j))).fill(arg.slice(j + 1)); }
  else if (op === "select") { const j = arg.indexOf("="); await page.locator("select").nth(Number(arg.slice(0, j))).selectOption(arg.slice(j + 1)); }
  else if (op === "drag") { const [a, b] = arg.split(">"); await page.getByText(a, { exact: false }).first().dragTo(page.locator(b).first()); }
  else if (op === "clickat") { const [x, y] = arg.split(",").map(Number); await page.mouse.click(x, y); }
  else if (op === "wait") await page.waitForTimeout(Number(arg) * 1000);
  else if (op === "down") await page.keyboard.down(arg);
  else if (op === "up") await page.keyboard.up(arg);
  else if (op === "key") await page.keyboard.press(arg);
  else if (op === "eval") console.log("eval ->", JSON.stringify(await page.evaluate(arg)));
  else if (op === "shot") { await page.screenshot({ path: arg }); console.log("saved", arg); }
  else console.log("unknown step", step);
  if (op === "click" || op === "clickexact" || op === "fill") await page.waitForTimeout(700);
}
await browser.close();
