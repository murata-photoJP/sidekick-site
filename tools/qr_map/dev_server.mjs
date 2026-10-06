// プランナーQRマップ（G-3）の local 確認用 server。Firestore Emulator 上でだけ動く。
//
//   npm run qr-map:dev        （= firebase emulators:exec … "node tools/qr_map/dev_server.mjs --seed"）
//   → http://127.0.0.1:8787/planner-map
//
// - 静的 file（planner-map.html / share.html / assets / share-assets）と、/api/qr-map を本物の handler
//   （api/qr-map.js、G-2）へ渡すだけ。Vercel の req / res の形（req.query / req.body / res.status().json()）に合わせる。
// - FIRESTORE_EMULATOR_HOST が local でなければ起動しない（本番 Firestore へ倒れない）。
// - --seed: tools/qr_map/seed_emulator.mjs で Emulator を初期化し、実 SharePlan を publish API 経由で入れる。
import http from "node:http";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);

export function assertEmulatorOnly(env = process.env) {
  const host = env.FIRESTORE_EMULATOR_HOST || "";
  if (!/^(127\.0\.0\.1|localhost|\[::1\]):\d+$/.test(host)) {
    throw new Error("Firestore Emulator が無い（FIRESTORE_EMULATOR_HOST=" + host + "）。本番には接続しない。");
  }
  env.QR_MAP_REQUIRE_EMULATOR = "1";
  env.QR_MAP_FIREBASE_PROJECT_ID = env.QR_MAP_FIREBASE_PROJECT_ID || "demo-sidekick-qr-map";
  if (!env.QR_MAP_FIREBASE_PROJECT_ID.startsWith("demo-")) throw new Error("demo- project だけを使う");
  delete env.QR_MAP_FIREBASE_SERVICE_ACCOUNT;
  delete env.FIREBASE_SERVICE_ACCOUNT;
  delete env.GOOGLE_APPLICATION_CREDENTIALS;
  if (env.QR_MAP_PUBLISH_ENABLED === undefined) env.QR_MAP_PUBLISH_ENABLED = "true";
}

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml", ".txt": "text/plain; charset=utf-8"
};
const ROUTES = { "/planner-map": "planner-map.html", "/planner-map.html": "planner-map.html", "/share": "share.html", "/share.html": "share.html" };
const STATIC_PREFIXES = ["/assets/", "/share-assets/"];

function resolveStatic(pathname) {
  if (ROUTES[pathname]) return join(ROOT, ROUTES[pathname]);
  if (!STATIC_PREFIXES.some((p) => pathname.startsWith(p))) return null;
  const full = normalize(join(ROOT, decodeURIComponent(pathname)));
  if (!full.startsWith(ROOT + sep)) return null; // path traversal
  return full;
}

function adaptRes(res) {
  const out = {
    setHeader: (k, v) => res.setHeader(k, v),
    status(code) { res.statusCode = code; return out; },
    json(body) {
      if (!res.getHeader("Content-Type")) res.setHeader("Content-Type", "application/json; charset=utf-8");
      res.end(JSON.stringify(body));
      return out;
    },
    end(text) { res.end(text); return out; }
  };
  return out;
}

async function readBody(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 64 * 1024) break; // handler 側でも 8 KB に制限する
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

export async function startServer({ port = 8787, host = "127.0.0.1" } = {}) {
  assertEmulatorOnly();
  const handler = require(join(ROOT, "api", "qr-map.js"));
  const cleanupHandler = require(join(ROOT, "api", "qr-map-cleanup.js"));
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, "http://" + host);
      if (url.pathname === "/api/qr-map-cleanup") {
        // G-5.1: 物理削除の Cron endpoint（emulator 専用。CRON_SECRET / QR_MAP_CLEANUP_ENABLED が無ければ 503）
        await cleanupHandler({ method: req.method, headers: req.headers, query: {}, body: undefined }, adaptRes(res));
        return;
      }
      if (url.pathname === "/api/qr-map") {
        const raw = req.method === "POST" ? await readBody(req) : undefined;
        let body = raw;
        const type = String(req.headers["content-type"] || "").split(";")[0].trim();
        if (raw !== undefined && type === "application/json") {
          try { body = JSON.parse(raw); } catch (_) { body = raw; } // Vercel と同じく parse 失敗は文字列のまま
        }
        const query = Object.fromEntries(url.searchParams.entries());
        await handler({ method: req.method, headers: req.headers, query, body }, adaptRes(res));
        return;
      }
      const file = resolveStatic(url.pathname);
      if (!file || req.method !== "GET") { res.statusCode = 404; res.end("not found"); return; }
      const data = await readFile(file);
      res.setHeader("Content-Type", TYPES[extname(file)] || "application/octet-stream");
      res.setHeader("Cache-Control", "no-store");
      res.end(data);
    } catch (error) {
      if (error && error.code === "ENOENT") { res.statusCode = 404; res.end("not found"); return; }
      res.statusCode = 500;
      res.end("dev server error");
    }
  });
  await new Promise((resolve) => server.listen(port, host, resolve));
  const baseUrl = "http://" + host + ":" + server.address().port;
  // browser の POST（open）は Origin: http://127.0.0.1:port を付ける。emulator 専用設定でだけ許可される
  process.env.QR_MAP_DEV_ALLOWED_ORIGINS = baseUrl;
  return { server, baseUrl };
}

async function main() {
  const port = Number(process.env.PLANNER_MAP_PORT || 8787);
  const { baseUrl } = await startServer({ port });
  if (process.argv.includes("--seed")) {
    const { seedEmulator } = await import("./seed_emulator.mjs");
    const manifest = await seedEmulator({ baseUrl });
    console.log("seeded:", JSON.stringify(manifest.summary));
  }
  console.log("プランナーQRマップ（Emulator）: " + baseUrl + "/planner-map");
  console.log("終了: Ctrl+C（Emulator も止まります）");
  await new Promise(() => {}); // emulators:exec が終わるまで動かし続ける
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().catch((error) => { console.error(error.message); process.exit(1); });
}
