// The web server of the portable release: serves the built client (client/web) and passes the browser's WebSocket (/ws, /social) on to the gateway, like the dev server's proxy
// and Caddy do elsewhere. Only Node is needed.   node serve.mjs --dir web [--port 8080] [--host 127.0.0.1] [--gateway 127.0.0.1:8059]
import { createServer } from "node:http";
import { connect } from "node:net";
import { createReadStream, statSync } from "node:fs";
import { extname, join, normalize, sep } from "node:path";
import { parseArgs } from "node:util";

const { values: o } = parseArgs({ options: { port: { type: "string", default: "8080" }, host: { type: "string", default: "127.0.0.1" }, dir: { type: "string" }, gateway: { type: "string", default: "127.0.0.1:8059" } } });
if (!o.dir) { console.error("usage: node serve.mjs --dir <web folder> [--port 8080] [--host 127.0.0.1] [--gateway 127.0.0.1:8059]"); process.exit(2); }
const root = normalize(o.dir), [gwHost, gwPort] = o.gateway.split(":");
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".webp": "image/webp", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".woff": "font/woff", ".woff2": "font/woff2", ".wasm": "application/wasm", ".txt": "text/plain" };

const fileFor = (urlPath) => {
  let p; try { p = normalize(join(root, decodeURIComponent(urlPath.split("?")[0]))); } catch { return null; }
  if (p !== root && !p.startsWith(root + sep)) return null;      // never above the web folder
  try { const st = statSync(p); if (st.isDirectory()) return fileFor(join(urlPath, "index.html")); return st.isFile() ? { p, st } : null; } catch { return null; }
};

const server = createServer((req, res) => {
  let f = fileFor(req.url ?? "/");
  if (!f && !extname((req.url ?? "/").split("?")[0])) f = fileFor("/index.html");      // the client's own routes
  if (!f) { res.writeHead(404, { "content-type": "text/plain" }); res.end("not found"); return; }
  res.writeHead(200, { "content-type": MIME[extname(f.p).toLowerCase()] ?? "application/octet-stream", "content-length": f.st.size, "cache-control": /\.(?:bgf|roo|ogg|png|webp|jpg)$/i.test(f.p) ? "public, max-age=86400" : "no-cache" });
  createReadStream(f.p).pipe(res);
});

// WebSocket upgrade: /ws -> the gateway's game path "/", /social -> the gateway's friends/arena feed; the real client address goes along as X-Forwarded-For (the gateway limits connections per address)
server.on("upgrade", (req, socket, head) => {
  const url = req.url ?? "";
  const path = url.startsWith("/ws") ? "/" : url.startsWith("/social") ? url : null;
  if (!path) { socket.destroy(); return; }
  const up = connect(Number(gwPort), gwHost, () => {
    const lines = [`GET ${path} HTTP/1.1`];
    for (let i = 0; i < req.rawHeaders.length; i += 2) if (req.rawHeaders[i].toLowerCase() !== "x-forwarded-for") lines.push(`${req.rawHeaders[i]}: ${req.rawHeaders[i + 1]}`);
    lines.push(`X-Forwarded-For: ${socket.remoteAddress ?? "127.0.0.1"}`);
    up.write(lines.join("\r\n") + "\r\n\r\n");
    if (head && head.length) up.write(head);
    up.pipe(socket); socket.pipe(up);
  });
  up.on("error", () => socket.destroy()); socket.on("error", () => up.destroy()); up.on("close", () => socket.destroy()); socket.on("close", () => up.destroy());
});

server.listen(Number(o.port), o.host, () => console.log(`web client on http://${o.host}:${o.port} (gateway ${o.gateway})`));
