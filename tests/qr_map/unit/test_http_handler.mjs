// api/qr-map.js の HTTP 境界（method / Origin / Content-Type / body 上限 / error → status / cache header）。
// store は fake に差し替える（Firestore の挙動は tests/qr_map/emulator/ が実 emulator で見る）。
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const handler = require("../../../api/qr-map.js");
const { QrMapError } = require("../../../api/_qr_map/store.js");
const { CONSTANTS } = require("../../../api/_qr_map/config.js");

const calls = [];
let nextError = null;
handler.setStoreFactoryForTest(() => ({
  async publish(args) { calls.push(["publish", args]); if (nextError) throw nextError; return { plan_id: "p", manage_token: "t", replayed: false }; },
  async unpublish(args) { calls.push(["unpublish", args]); if (nextError) throw nextError; return { plan_id: "p", state: "unpublished" }; },
  async openDetail(args) { calls.push(["open", args]); if (nextError) throw nextError; return { plan_id: "p", fragment: "f" }; },
  async getTile(args) { calls.push(["tile", args]); if (nextError) throw nextError; return { plans: [] }; }
}));

function fakeRes() {
  const res = { statusCode: null, headers: {}, body: undefined };
  res.setHeader = (k, v) => { res.headers[k] = v; };
  res.status = (c) => { res.statusCode = c; return res; };
  res.json = (b) => { res.body = b; return res; };
  return res;
}
async function call({ method = "POST", op, body, headers = {}, query = {} }) {
  const req = { method, query: { op, ...query }, headers: { "content-type": "application/json", ...headers }, body };
  const res = fakeRes();
  await handler(req, res);
  return res;
}

test("publish: 201、no-store、noindex。body の値をそのまま store へ渡す", async () => {
  calls.length = 0; nextError = null;
  const res = await call({ op: "publish", body: { fragment: "x", idempotency_key: "k", consent_version: "c", lat: 1 } });
  assert.equal(res.statusCode, 201);
  assert.equal(res.headers["Cache-Control"], "no-store");
  assert.equal(res.headers["X-Robots-Tag"], "noindex, nofollow");
  assert.deepEqual(calls[0], ["publish", { fragment: "x", idempotencyKey: "k", consentVersion: "c" }]); // 送られた lat は使わない
});

test("POST 系は GET を拒否、tile は POST を拒否", async () => {
  assert.equal((await call({ method: "GET", op: "publish" })).statusCode, 405);
  assert.equal((await call({ method: "POST", op: "tile" })).statusCode, 405);
});

test("Origin: 付いていれば www.sidekick-lab.com だけ。無し（Planner）は通す", async () => {
  nextError = null;
  assert.equal((await call({ op: "open", body: { plan_id: "p" }, headers: { origin: "https://evil.example" } })).statusCode, 403);
  assert.equal((await call({ op: "open", body: { plan_id: "p" }, headers: { origin: "https://www.sidekick-lab.com" } })).statusCode, 200);
  assert.equal((await call({ op: "open", body: { plan_id: "p" } })).statusCode, 200);
});

test("local 確認用 Origin は emulator 専用設定のときだけ。本番設定では無視される", () => {
  const req = { headers: { origin: "http://127.0.0.1:8787" } };
  assert.equal(handler.originAllowed(req, { QR_MAP_DEV_ALLOWED_ORIGINS: "http://127.0.0.1:8787" }), false);
  assert.equal(handler.originAllowed(req, { QR_MAP_DEV_ALLOWED_ORIGINS: "http://127.0.0.1:8787", QR_MAP_REQUIRE_EMULATOR: "1" }), true);
  assert.equal(handler.originAllowed({ headers: { origin: "https://evil.example" } },
    { QR_MAP_DEV_ALLOWED_ORIGINS: "https://evil.example", QR_MAP_REQUIRE_EMULATOR: "1" }), false); // http://127.0.0.1 / localhost だけ
});

test("Content-Type が JSON でなければ 415", async () => {
  assert.equal((await call({ op: "publish", body: "{}", headers: { "content-type": "text/plain" } })).statusCode, 415);
});

test("body 上限（parse 済み object でも測り直す）を超えたら 413", async () => {
  const big = { fragment: "A".repeat(CONSTANTS.MAX_BODY_BYTES) };
  assert.equal((await call({ op: "publish", body: big })).statusCode, 413);
  assert.equal((await call({ op: "publish", body: JSON.stringify(big) })).statusCode, 413);
  assert.equal((await call({ op: "publish", body: "not json" })).statusCode, 400);
  assert.equal((await call({ op: "publish", body: [1] })).statusCode, 400);
});

test("store の error code と status をそのまま返す。内部 error は詳細を出さない", async () => {
  nextError = new QrMapError("PUBLISH_DISABLED", 503);
  let res = await call({ op: "publish", body: {} });
  assert.deepEqual([res.statusCode, res.body], [503, { error: "PUBLISH_DISABLED" }]);
  nextError = new Error("boom secret");
  res = await call({ op: "unpublish", body: {} });
  assert.deepEqual([res.statusCode, res.body], [500, { error: "INTERNAL" }]);
  nextError = null;
});

test("tile は CDN cache（s-maxage）。未知の op は 404", async () => {
  nextError = null;
  const res = await call({ method: "GET", op: "tile", query: { z: "10", x: "1", y: "2" } });
  assert.equal(res.statusCode, 200);
  assert.match(res.headers["Cache-Control"], /s-maxage=60/);
  assert.equal((await call({ op: "list_all" })).statusCode, 404);
});
