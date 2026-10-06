// G-5.1 Production Safety Infrastructure（HD-PLANNERQRMAP-044）: emulator 不要の純関数・handler の test。
//   - 本番接続の positive allow（環境の組み合わせ）
//   - cleanup の判定（active を消さない・猶予 30 日・壊れた document）
//   - Cron endpoint（method / secret / switch / 接続不可は fail-closed）
// 本番 credential は使わない（service account は形だけの JSON）。
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { resolveConnection, QrMapConfigError } = require("../../../api/_qr_map/firestore.js");
const { CONSTANTS, DAY_MS, readEnv } = require("../../../api/_qr_map/config.js");
const lifecycle = require("../../../api/_qr_map/lifecycle.js");
const cleanup = require("../../../api/qr-map-cleanup.js");

const SA = JSON.stringify({ project_id: "sidekick-map-prod", private_key: "-----not-a-real-key-----" });
const PROD = Object.freeze({
  VERCEL_ENV: "production",
  QR_MAP_PRODUCTION_FIRESTORE: "enabled",
  QR_MAP_FIREBASE_PROJECT_ID: "sidekick-map-prod",
  QR_MAP_FIREBASE_SERVICE_ACCOUNT: SA
});

// ---- B. fail-closed: 本番接続 ---------------------------------------------------------------
test("本番接続は全条件が揃ったときだけ（positive allow）", () => {
  assert.equal(resolveConnection({ ...PROD }).mode, "production");
  assert.deepEqual(CONSTANTS.PRODUCTION_PROJECT_IDS, ["sidekick-map-prod"]);
});

test("Preview / Development / Vercel 外では、本番 credential 風の設定が揃っていても接続しない", () => {
  for (const vercelEnv of ["preview", "development", "", "Production", "prod"]) {
    assert.throws(() => resolveConnection({ ...PROD, VERCEL_ENV: vercelEnv }),
      (e) => e instanceof QrMapConfigError && /VERCEL_ENV=production/.test(e.message), "VERCEL_ENV=" + vercelEnv);
  }
  const noVercel = { ...PROD };
  delete noVercel.VERCEL_ENV;
  assert.throws(() => resolveConnection(noVercel), /VERCEL_ENV=production/);
});

test("明示 switch（QR_MAP_PRODUCTION_FIRESTORE=enabled）が無ければ接続しない", () => {
  for (const value of [undefined, "", "true", "1", "ENABLED", "enabled "]) {
    const env = { ...PROD, QR_MAP_PRODUCTION_FIRESTORE: value };
    if (value === undefined) delete env.QR_MAP_PRODUCTION_FIRESTORE;
    assert.throws(() => resolveConnection(env), /QR_MAP_PRODUCTION_FIRESTORE/, String(value));
  }
});

test("許可されていない project id（打ち間違い・別 project・既存サイト）は拒否", () => {
  for (const id of ["sidekick-map-prd", "sidekick-map-prod2", "sidekick-qr-map-prod", "other-project"]) {
    const sa = JSON.stringify({ project_id: id });
    assert.throws(() => resolveConnection({ ...PROD, QR_MAP_FIREBASE_PROJECT_ID: id, QR_MAP_FIREBASE_SERVICE_ACCOUNT: sa }),
      /許可された project ではない/, id);
  }
  assert.throws(() => resolveConnection({ ...PROD, QR_MAP_FIREBASE_PROJECT_ID: "sidekick-6cfee" }), /既存サイト/);
});

test("credential が無い・壊れている・別 project のものなら拒否", () => {
  const missing = { ...PROD };
  delete missing.QR_MAP_FIREBASE_SERVICE_ACCOUNT;
  assert.throws(() => resolveConnection(missing), /読めない/);
  assert.throws(() => resolveConnection({ ...PROD, QR_MAP_FIREBASE_SERVICE_ACCOUNT: "{not json" }), /読めない/);
  assert.throws(() => resolveConnection({ ...PROD, QR_MAP_FIREBASE_SERVICE_ACCOUNT: JSON.stringify({ project_id: "sidekick-6cfee" }) }), /一致しない/);
});

test("矛盾した環境の組み合わせは拒否（emulator と本番の混在・test 実行・demo project）", () => {
  // Vercel の production / preview に emulator 設定が紛れ込んでも emulator にも本番にも倒れない
  for (const vercelEnv of ["production", "preview"]) {
    assert.throws(() => resolveConnection({ ...PROD, VERCEL_ENV: vercelEnv, FIRESTORE_EMULATOR_HOST: "127.0.0.1:8085", QR_MAP_FIREBASE_PROJECT_ID: "demo-sidekick-qr-map" }),
      /emulator 設定を受け付けない/);
  }
  assert.throws(() => resolveConnection({ ...PROD, QR_MAP_REQUIRE_EMULATOR: "1" }), /本番へ倒れない/);
  assert.throws(() => resolveConnection({ ...PROD, NODE_ENV: "test" }), /NODE_ENV=test/);
  assert.throws(() => resolveConnection({ ...PROD, QR_MAP_FIREBASE_PROJECT_ID: "demo-sidekick-qr-map" }), /demo- project は emulator 専用/);
});

test("LOCAL / TEST は従来どおり emulator（demo project）に接続できる", () => {
  const conn = resolveConnection({ QR_MAP_FIREBASE_PROJECT_ID: "demo-sidekick-qr-map", FIRESTORE_EMULATOR_HOST: "127.0.0.1:8086", QR_MAP_REQUIRE_EMULATOR: "1", NODE_ENV: "test" });
  assert.deepEqual([conn.mode, conn.credentialJson], ["emulator", null]);
  // `vercel dev`（VERCEL_ENV=development）でも emulator は使える
  assert.equal(resolveConnection({ QR_MAP_FIREBASE_PROJECT_ID: "demo-x", FIRESTORE_EMULATOR_HOST: "localhost:8085", VERCEL_ENV: "development" }).mode, "emulator");
});

test("local 確認用 Origin は Vercel の preview / production では常に無視する", () => {
  const base = { QR_MAP_REQUIRE_EMULATOR: "1", QR_MAP_DEV_ALLOWED_ORIGINS: "http://127.0.0.1:8787" };
  assert.deepEqual(readEnv(base).devAllowedOrigins, ["http://127.0.0.1:8787"]);
  assert.deepEqual(readEnv({ ...base, VERCEL_ENV: "preview" }).devAllowedOrigins, []);
  assert.deepEqual(readEnv({ ...base, VERCEL_ENV: "production" }).devAllowedOrigins, []);
});

test("circuit breaker の switch は文字列の完全一致だけ（未設定・別表記は OFF）", () => {
  for (const value of [undefined, "", "1", "TRUE", "yes", "true "]) {
    const env = value === undefined ? {} : { QR_MAP_PUBLISH_ENABLED: value, QR_MAP_CLEANUP_ENABLED: value };
    assert.equal(readEnv(env).publishEnabled, false, String(value));
    assert.equal(readEnv(env).cleanupEnabled, false, String(value));
  }
  assert.equal(readEnv({ QR_MAP_PUBLISH_ENABLED: "true" }).publishEnabled, true);
  assert.equal(readEnv({ QR_MAP_CLEANUP_ENABLED: "true" }).cleanupEnabled, true);
});

// ---- C. cleanup の判定 ----------------------------------------------------------------------
const T0 = Date.UTC(2026, 9, 6, 0, 0, 0);
const ts = (ms) => ({ toMillis: () => ms });          // Firestore Timestamp の形（toMillis だけ使う）
function planDoc(state, { activity = T0, changed = T0 } = {}) {
  const expires = lifecycle.expiresAtFrom(activity);
  const deleteAfter = state === "published" ? lifecycle.deleteAfterFrom(expires) : lifecycle.deleteAfterFrom(changed);
  return { state, last_activity_at: ts(activity), expires_at: ts(expires), state_changed_at: ts(changed), delete_after: ts(deleteAfter) };
}

test("cleanup: active（published かつ期限内）は削除しない（delete_after が過去でも）", () => {
  const doc = planDoc("published");
  assert.equal(lifecycle.planCleanupVerdict(doc, T0 + DAY_MS), "keep");
  const corrupted = { ...doc, delete_after: ts(T0 - DAY_MS) };   // delete_after だけ過去（不整合）
  assert.equal(lifecycle.planCleanupVerdict(corrupted, T0 + DAY_MS), "keep");
});

test("cleanup: 期限切れ（180 日）でも猶予 30 日の途中は残す、過ぎたら削除", () => {
  const doc = planDoc("published");
  const expiredAt = T0 + 180 * DAY_MS;
  assert.equal(lifecycle.planCleanupVerdict(doc, expiredAt + 1), "keep");
  assert.equal(lifecycle.planCleanupVerdict(doc, expiredAt + 30 * DAY_MS - 1), "keep");
  assert.equal(lifecycle.planCleanupVerdict(doc, expiredAt + 30 * DAY_MS), "delete");
});

test("cleanup: 取り消し / 運営停止から 30 日の途中は残す、過ぎたら削除", () => {
  for (const state of ["unpublished", "removed"]) {
    const doc = planDoc(state, { changed: T0 + 5 * DAY_MS });
    assert.equal(lifecycle.planCleanupVerdict(doc, T0 + 35 * DAY_MS - 1), "keep", state);
    assert.equal(lifecycle.planCleanupVerdict(doc, T0 + 35 * DAY_MS), "delete", state);
  }
  // delete_after が state から導いた時刻より早く書かれていても、導いた時刻まで残す
  const early = { ...planDoc("unpublished", { changed: T0 }), delete_after: ts(T0) };
  assert.equal(lifecycle.planCleanupVerdict(early, T0 + DAY_MS), "keep");
});

test("cleanup: 壊れた document は削除せず malformed として数える", () => {
  const ok = planDoc("unpublished");
  const late = T0 + 400 * DAY_MS;
  for (const bad of [null, "x", { ...ok, state: "deleted" }, { ...ok, state: undefined }, { ...ok, delete_after: undefined },
    { ...ok, delete_after: "2026-01-01" }, { ...ok, expires_at: null }, { ...ok, state_changed_at: undefined }]) {
    assert.equal(lifecycle.planCleanupVerdict(bad, late), "malformed", JSON.stringify(bad));
  }
  assert.equal(lifecycle.auxCleanupVerdict({ delete_after: ts(T0) }, T0), "delete");
  assert.equal(lifecycle.auxCleanupVerdict({ delete_after: ts(T0) }, T0 - 1), "keep");
  for (const bad of [null, {}, { delete_after: "x" }]) assert.equal(lifecycle.auxCleanupVerdict(bad, late), "malformed");
});

// ---- Cron endpoint（api/qr-map-cleanup.js）---------------------------------------------------
function fakeRes() {
  const res = { statusCode: null, headers: {}, body: undefined };
  res.setHeader = (k, v) => { res.headers[k] = v; };
  res.status = (c) => { res.statusCode = c; return res; };
  res.json = (b) => { res.body = b; return res; };
  return res;
}
async function callCleanup(env, { method = "GET", auth } = {}) {
  const saved = { ...process.env };
  for (const k of ["CRON_SECRET", "QR_MAP_CLEANUP_ENABLED"]) delete process.env[k];
  Object.assign(process.env, env);
  try {
    const res = fakeRes();
    await cleanup({ method, headers: auth ? { authorization: auth } : {}, query: {} }, res);
    return res;
  } finally {
    for (const k of Object.keys(process.env)) if (!(k in saved)) delete process.env[k];
    Object.assign(process.env, saved);
  }
}

test("Cron endpoint: GET 以外は 405、switch か secret が無ければ 503（何もしない）、secret 違いは 401", async () => {
  let calls = 0;
  cleanup.setStoreFactoryForTest(() => ({ cleanupEligible: async () => { calls += 1; return { deleted: {}, kept: 0, malformed: 0, conflicts: 0, more: false }; } }));
  const ON = { CRON_SECRET: "s3cret-value", QR_MAP_CLEANUP_ENABLED: "true" };
  assert.equal((await callCleanup(ON, { method: "POST", auth: "Bearer s3cret-value" })).statusCode, 405);
  assert.deepEqual((await callCleanup({ CRON_SECRET: "s3cret-value" }, { auth: "Bearer s3cret-value" })).body, { error: "CLEANUP_DISABLED" });
  assert.deepEqual((await callCleanup({ QR_MAP_CLEANUP_ENABLED: "true" }, { auth: "Bearer " })).body, { error: "CLEANUP_DISABLED" });
  for (const auth of [undefined, "Bearer wrong", "s3cret-value", "Bearer s3cret-value ", "bearer s3cret-value"]) {
    assert.equal((await callCleanup(ON, { auth })).statusCode, 401, String(auth));
  }
  assert.equal(calls, 0);                              // ここまで store には一度も触れていない
  const ok = await callCleanup(ON, { auth: "Bearer s3cret-value" });
  assert.deepEqual([ok.statusCode, ok.body.ok, ok.headers["Cache-Control"]], [200, true, "no-store"]);
  assert.equal(calls, 1);
});

test("Cron endpoint: 接続条件を満たさなければ 503（本番へ倒れない）、応答に詳細を出さない", async () => {
  cleanup.setStoreFactoryForTest(() => { throw new QrMapConfigError("本番 Firestore へは VERCEL_ENV=production でだけ接続する"); });
  const res = await callCleanup({ CRON_SECRET: "x", QR_MAP_CLEANUP_ENABLED: "true" }, { auth: "Bearer x" });
  assert.deepEqual([res.statusCode, res.body], [503, { error: "QR_MAP_UNAVAILABLE" }]);
  cleanup.setStoreFactoryForTest(() => ({ cleanupEligible: async () => { throw new Error("boom C:/secret/path"); } }));
  const err = await callCleanup({ CRON_SECRET: "x", QR_MAP_CLEANUP_ENABLED: "true" }, { auth: "Bearer x" });
  assert.deepEqual([err.statusCode, err.body], [500, { error: "INTERNAL" }]);
});
