// token / lifecycle / tile / 接続先 guard（emulator 不要の純関数）。
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const tokens = require("../../../api/_qr_map/tokens.js");
const lifecycle = require("../../../api/_qr_map/lifecycle.js");
const tiles = require("../../../api/_qr_map/tiles.js");
const { resolveConnection } = require("../../../api/_qr_map/firestore.js");
const { DAY_MS } = require("../../../api/_qr_map/config.js");

test("manage_token は 256 bit（base64url 43 文字）で毎回違う。plan_id は 128 bit hex", () => {
  const seen = new Set();
  for (let i = 0; i < 1000; i += 1) {
    const t = tokens.newManageToken();
    assert.match(t, tokens.MANAGE_TOKEN_RE);
    assert.equal(Buffer.from(t, "base64url").length, 32);
    seen.add(t);
    assert.match(tokens.newPlanId(), tokens.PLAN_ID_RE);
  }
  assert.equal(seen.size, 1000);
});

test("tokenMatches: 正しい token だけ一致。形式違い・hash 違いは false", () => {
  const t = tokens.newManageToken();
  const h = tokens.sha256Hex(t);
  assert.equal(tokens.tokenMatches(t, h), true);
  assert.equal(tokens.tokenMatches(tokens.newManageToken(), h), false);
  assert.equal(tokens.tokenMatches(h, h), false);
  assert.equal(tokens.tokenMatches(undefined, h), false);
  assert.equal(tokens.tokenMatches(t, "zz"), false);
});

test("lifecycle: active = published かつ now < expires_at。expired は導出条件", () => {
  const now = Date.UTC(2026, 9, 5);
  const doc = { state: "published", expires_at: now + 1, last_activity_at: now - 179 * DAY_MS };
  assert.equal(lifecycle.isActive(doc, now), true);
  assert.equal(lifecycle.isActive({ ...doc, expires_at: now }, now), false);
  assert.equal(lifecycle.isActive({ ...doc, state: "unpublished" }, now), false);
  assert.equal(lifecycle.isActive({ ...doc, state: "removed" }, now), false);
});

test("lifecycle: activity は 24 時間以内なら記録しない。期限は activity + 180 日", () => {
  const now = Date.UTC(2026, 9, 5);
  const fresh = { state: "published", expires_at: now + DAY_MS, last_activity_at: now - DAY_MS + 1 };
  assert.equal(lifecycle.shouldRecordActivity(fresh, now), false);
  assert.equal(lifecycle.shouldRecordActivity({ ...fresh, last_activity_at: now - DAY_MS }, now), true);
  assert.equal(lifecycle.expiresAtFrom(now), now + 180 * DAY_MS);
});

test("lifecycle: 物理削除は unpublish / removed / 期限切れから 30 日後", () => {
  const t0 = Date.UTC(2026, 9, 5);
  const un = { state: "unpublished", state_changed_at: t0 };
  assert.equal(lifecycle.isDeletionEligible(un, t0 + 30 * DAY_MS - 1), false);
  assert.equal(lifecycle.isDeletionEligible(un, t0 + 30 * DAY_MS), true);
  const pub = { state: "published", expires_at: t0 };
  assert.equal(lifecycle.isDeletionEligible(pub, t0 + 29 * DAY_MS), false);
  assert.equal(lifecycle.isDeletionEligible(pub, t0 + 30 * DAY_MS), true);
});

test("tile: 公開時の key は段ごとに 1 つ。要求は決まった段・範囲内の整数だけ受ける", () => {
  const keys = tiles.tileKeysFor(35.36, 138.73);
  assert.deepEqual(Object.keys(keys), ["z6", "z10", "z14"]);
  const [z, x, y] = keys.z10.split("/");
  assert.deepEqual(tiles.parseTileRequest(z, x, y).key, keys.z10);
  assert.equal(tiles.parseTileRequest("11", "1", "1"), null);
  assert.equal(tiles.parseTileRequest("10", "1024", "0"), null);
  assert.equal(tiles.parseTileRequest("10", "-1", "0"), null);
  assert.equal(tiles.parseTileRequest("10", "1.5", "0"), null);
  assert.equal(tiles.parseTileRequest("6", "0", "0").field, "tiles.z6");
});

test("接続先 guard: 既存サイトの project・emulator 無しの test・demo の本番接続を拒否する", () => {
  // G-5.1: 本番接続は positive allow（VERCEL_ENV=production・QR_MAP_PRODUCTION_FIRESTORE=enabled・許可 project・
  // service account 一致がすべて揃ったときだけ）。組み合わせの網羅は test_production_safety.mjs
  const SA = JSON.stringify({ project_id: "sidekick-map-prod" });
  const PROD = { VERCEL_ENV: "production", QR_MAP_PRODUCTION_FIRESTORE: "enabled", QR_MAP_FIREBASE_PROJECT_ID: "sidekick-map-prod" };
  assert.throws(() => resolveConnection({ QR_MAP_FIREBASE_PROJECT_ID: "sidekick-6cfee", FIRESTORE_EMULATOR_HOST: "127.0.0.1:8085" }), /既存サイト/);
  assert.throws(() => resolveConnection({}), /未設定/);
  assert.throws(() => resolveConnection({ QR_MAP_FIREBASE_PROJECT_ID: "demo-x", QR_MAP_REQUIRE_EMULATOR: "1" }), /本番へ倒れない/);
  assert.throws(() => resolveConnection({ QR_MAP_FIREBASE_PROJECT_ID: "prod-x", FIRESTORE_EMULATOR_HOST: "127.0.0.1:8085" }), /demo-/);
  assert.throws(() => resolveConnection({ ...PROD, QR_MAP_FIREBASE_SERVICE_ACCOUNT: SA, NODE_ENV: "test" }), /NODE_ENV=test/);
  assert.throws(() => resolveConnection({ ...PROD, QR_MAP_FIREBASE_SERVICE_ACCOUNT: "{}" }), /一致しない/);
  assert.equal(resolveConnection({ QR_MAP_FIREBASE_PROJECT_ID: "demo-x", FIRESTORE_EMULATOR_HOST: "127.0.0.1:8085", QR_MAP_REQUIRE_EMULATOR: "1" }).mode, "emulator");
  assert.equal(resolveConnection({ ...PROD, QR_MAP_FIREBASE_SERVICE_ACCOUNT: SA }).mode, "production");
});
