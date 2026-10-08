// PublicPlan Server Core を **Firestore Emulator** で動かす結合 test（G-2 §12 / §13）。
//
//   npm run test:qr-map:emulator
//   （= firebase emulators:exec --config firebase/qr-map/firebase.json --only firestore --project demo-sidekick-qr-map ...）
//
// 守ること:
//   - FIRESTORE_EMULATOR_HOST が無ければ **skip ではなく FAIL**（emulator 以外で走らせない）
//   - project は demo-sidekick-qr-map（Firebase の demo project = 実 resource に触れない）
//   - 本番用の service account 環境変数は消してから始める
//   - 実 SharePlan は Planner 正本の cross-language vectors（VALID_GV-1 ほか）を使う
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const PROJECT = "demo-sidekick-qr-map";
delete process.env.QR_MAP_FIREBASE_SERVICE_ACCOUNT;
delete process.env.FIREBASE_SERVICE_ACCOUNT;
delete process.env.GOOGLE_APPLICATION_CREDENTIALS;
process.env.QR_MAP_REQUIRE_EMULATOR = "1";
process.env.QR_MAP_FIREBASE_PROJECT_ID = PROJECT;
process.env.QR_MAP_PUBLISH_ENABLED = "true";
process.env.QR_MAP_DAILY_PUBLISH_LIMIT = "1000";

const HOST = process.env.FIRESTORE_EMULATOR_HOST || "";
test("前提: Firestore Emulator 上で、demo project に接続している（本番へ接続しない）", () => {
  assert.ok(/^(127\.0\.0\.1|localhost|\[::1\]):\d+$/.test(HOST), "FIRESTORE_EMULATOR_HOST が local emulator を指していない: " + HOST);
});
if (!/^(127\.0\.0\.1|localhost|\[::1\]):\d+$/.test(HOST)) {
  throw new Error("Firestore Emulator 以外では実行しない（FIRESTORE_EMULATOR_HOST=" + HOST + "）");
}

const require = createRequire(import.meta.url);
const admin = require("firebase-admin");
const { getQrMapFirestore } = require("../../../api/_qr_map/firestore.js");
const { createStore, QrMapError } = require("../../../api/_qr_map/store.js");
const { CONSTANTS, DAY_MS } = require("../../../api/_qr_map/config.js");
const tokens = require("../../../api/_qr_map/tokens.js");
const lifecycle = require("../../../api/_qr_map/lifecycle.js");
const handler = require("../../../api/qr-map.js");

const VECTORS = JSON.parse(readFileSync(new URL("../../fixtures/qr_map/cross_language_vectors.json", import.meta.url), "utf8"));
const byId = Object.fromEntries(VECTORS.cases.map((c) => [c.id, c]));
const GV1 = byId["VALID_GV-1"].payload;          // 実 Diamond Fuji SharePlan（v1 golden）
const V2SL = byId["VALID_V2-SL-1"].payload;      // 実 太陽・月 SharePlan（v2）
const V2ST = byId["VALID_V2-ST-1"].payload;      // 実 星の軌跡 SharePlan（v2、被写体なし）

const conn = getQrMapFirestore();
const store = createStore(conn);
const { db } = conn;
const T0 = Date.UTC(2026, 9, 5, 12, 0, 0);
let keySeq = 0;
const newKey = () => "idem-key-" + String(++keySeq).padStart(8, "0") + "-" + tokens.newPlanId();

async function clearDb() {
  const res = await fetch("http://" + HOST + "/emulator/v1/projects/" + PROJECT + "/databases/(default)/documents", { method: "DELETE" });
  assert.equal(res.status, 200, "emulator の初期化に失敗");
}
async function planDoc(planId) {
  const snap = await db.collection(CONSTANTS.COLLECTION_PLANS).doc(planId).get();
  return snap.exists ? snap.data() : null;
}
async function rejects(promise, code) {
  await assert.rejects(promise, (error) => error instanceof QrMapError && error.code === code);
}
async function publish(fragment = GV1, extra = {}) {
  return store.publish({ fragment, idempotencyKey: newKey(), consentVersion: "qr-map-consent/1", nowMs: T0, ...extra });
}

test.beforeEach(async () => { await clearDb(); });

test("30: 接続は emulator ＋ demo project。既定 app（既存サイト用）は作らない", () => {
  assert.equal(conn.mode, "emulator");
  assert.equal(conn.projectId, PROJECT);
  assert.deepEqual(admin.apps.map((a) => a.name), ["qr-map"]);
});

test("1 / 18: 実 SharePlan を publish → 保存される。snapshot は fragment そのもの", async () => {
  const r = await publish();
  assert.match(r.plan_id, tokens.PLAN_ID_RE);
  assert.match(r.manage_token, tokens.MANAGE_TOKEN_RE);
  assert.equal(r.replayed, false);
  assert.equal(r.expires_at, new Date(T0 + 180 * DAY_MS).toISOString());
  const doc = await planDoc(r.plan_id);
  assert.equal(doc.schema, "qr_map_plan/1");
  assert.equal(doc.snapshot.fragment, GV1);
  assert.equal(doc.snapshot.share_version, 1);
  assert.equal(doc.state, "published");
  assert.equal(doc.location_precision, "exact");
  assert.equal(doc.owner.kind, "anonymous");
  assert.equal(doc.owner.owner_user_id, null);
  assert.equal(doc.display.lat, byId["VALID_GV-1"].plan.observer_latitude_deg);
  assert.equal(lifecycle.toMs(doc.delete_after), lifecycle.deletionEligibleAtMs(doc));
});

test("2〜8: 壊れた fragment・未知 field・未対応 version / genre・大きすぎる fragment は保存せず拒否", async () => {
  // 2 invalid base64 / 3 invalid zlib / 4 invalid JSON / 5 unknown field / 6 unsupported version /
  // 7 unsupported genre / 8 payload too large。期待 code は正本 vectors に記録された値
  const ids = ["NOT_BASE64URL", "NOT_ZLIB", "INVALID_JSON", "V1_KEYS_WITH_V2",
    "V2_UNSUPPORTED_VERSION", "V2_UNSUPPORTED_GENRE", "PAYLOAD_TOO_LARGE"];
  for (const id of ids) {
    const c = byId[id];
    assert.ok(c, id);
    assert.equal(c.accepted, false, id);
    await rejects(publish(c.payload), "INVALID_SHAREPLAN:" + c.code);
  }
  const all = await db.collection(CONSTANTS.COLLECTION_PLANS).get();
  assert.equal(all.size, 0);
});

test("9: consent_version が無い・未知なら拒否", async () => {
  await rejects(publish(GV1, { consentVersion: undefined }), "CONSENT_REQUIRED");
  await rejects(publish(GV1, { consentVersion: "qr-map-consent/0" }), "CONSENT_REQUIRED");
});

test("10: circuit breaker（QR_MAP_PUBLISH_ENABLED が true 以外）なら publish だけ止まる。読む・取り消すは動く", async () => {
  const r = await publish();
  process.env.QR_MAP_PUBLISH_ENABLED = "false";
  try {
    await rejects(publish(), "PUBLISH_DISABLED");
    assert.equal((await store.openDetail({ planId: r.plan_id, nowMs: T0 })).fragment, GV1);
    assert.equal((await store.unpublish({ planId: r.plan_id, manageToken: r.manage_token, nowMs: T0 })).state, "unpublished");
  } finally {
    process.env.QR_MAP_PUBLISH_ENABLED = "true";
  }
});

test("10b: 1 日の公開件数の上限（global circuit breaker）", async () => {
  process.env.QR_MAP_DAILY_PUBLISH_LIMIT = "2";
  try {
    await publish(); await publish();
    await rejects(publish(), "PUBLISH_LIMIT_REACHED");
    await publish(GV1, { nowMs: T0 + DAY_MS }); // 翌日（UTC）は数え直し
  } finally {
    process.env.QR_MAP_DAILY_PUBLISH_LIMIT = "1000";
  }
});

test("11 / 12: raw manage_token と raw idempotency_key はどこにも保存されない（SHA-256 だけ）", async () => {
  const key = newKey();
  const r = await store.publish({ fragment: GV1, idempotencyKey: key, consentVersion: "qr-map-consent/1", nowMs: T0 });
  assert.equal(Buffer.from(r.manage_token, "base64url").length, 32);
  const dump = [];
  for (const name of [CONSTANTS.COLLECTION_PLANS, CONSTANTS.COLLECTION_IDEMPOTENCY, CONSTANTS.COLLECTION_COUNTERS]) {
    const snap = await db.collection(name).get();
    snap.forEach((d) => dump.push(d.id, JSON.stringify(d.data())));
  }
  const text = dump.join("\n");
  assert.ok(!text.includes(r.manage_token), "raw token が保存されている");
  assert.ok(!text.includes(key), "raw idempotency_key が保存されている");
  assert.ok(text.includes(tokens.sha256Hex(r.manage_token)));
  for (const forbidden of ["ip", "ip_hash", "user_agent", "x-forwarded-for"]) {
    assert.ok(!new RegExp("\"" + forbidden + "\"").test(text), "保存してはいけない: " + forbidden);
  }
});

test("13〜15: unpublish は正しい token だけ。不一致は存在を漏らさない。繰り返しても同じ", async () => {
  const r = await publish();
  await rejects(store.unpublish({ planId: r.plan_id, manageToken: tokens.newManageToken(), nowMs: T0 }), "NOT_FOUND");
  await rejects(store.unpublish({ planId: tokens.newPlanId(), manageToken: r.manage_token, nowMs: T0 }), "NOT_FOUND");
  assert.equal((await planDoc(r.plan_id)).state, "published");
  const first = await store.unpublish({ planId: r.plan_id, manageToken: r.manage_token, nowMs: T0 + 1000 });
  assert.deepEqual(first, { plan_id: r.plan_id, state: "unpublished", changed: true });
  const again = await store.unpublish({ planId: r.plan_id, manageToken: r.manage_token, nowMs: T0 + 2000 });
  assert.deepEqual(again, { plan_id: r.plan_id, state: "unpublished", changed: false });
  const doc = await planDoc(r.plan_id);
  assert.equal(lifecycle.toMs(doc.state_changed_at), T0 + 1000);
  assert.equal(doc.snapshot.fragment, GV1); // 取り消しても snapshot は変えない
  await rejects(store.openDetail({ planId: r.plan_id, nowMs: T0 + 3000 }), "NOT_FOUND");
});

test("16: 同じ idempotency_key の再送は PublicPlan を増やさない（token は出し直し、旧 token は無効）", async () => {
  const key = newKey();
  const args = { fragment: GV1, idempotencyKey: key, consentVersion: "qr-map-consent/1", nowMs: T0 };
  const a = await store.publish(args);
  const [b, c] = await Promise.all([store.publish({ ...args, nowMs: T0 + 10 }), store.publish({ ...args, nowMs: T0 + 20 })]);
  assert.equal(b.plan_id, a.plan_id);
  assert.equal(c.plan_id, a.plan_id);
  assert.equal(b.replayed, true);
  const all = await db.collection(CONSTANTS.COLLECTION_PLANS).get();
  assert.equal(all.size, 1);
  const stored = (await planDoc(a.plan_id)).owner.manage_token_sha256;
  const valid = [a, b, c].filter((x) => tokens.tokenMatches(x.manage_token, stored));
  assert.equal(valid.length, 1, "有効な token は最後に出したものだけ");
  // 同じ key で別の fragment は拒否（取り違え防止）
  await rejects(store.publish({ ...args, fragment: V2SL }), "IDEMPOTENCY_KEY_REUSED");
  // 再送できる期間を過ぎたら plan_id だけ返し、token は出さない
  const late = await store.publish({ ...args, nowMs: T0 + CONSTANTS.IDEMPOTENCY_REPLAY_MS + 1 });
  assert.deepEqual([late.plan_id, late.manage_token], [a.plan_id, null]);
});

test("17: 同じ fragment でも別の idempotency_key なら別の PublicPlan（global dedup しない）", async () => {
  const a = await publish();
  const b = await publish();
  assert.notEqual(a.plan_id, b.plan_id);
  assert.equal((await planDoc(a.plan_id)).snapshot.payload_sha256, (await planDoc(b.plan_id)).snapshot.payload_sha256);
});

test("19 / 21: 詳細を開くと元の fragment を返し、掲載期限を activity + 180 日に延ばす", async () => {
  const r = await publish();
  const t1 = T0 + 10 * DAY_MS;
  const detail = await store.openDetail({ planId: r.plan_id, nowMs: t1 });
  assert.equal(detail.fragment, GV1);
  assert.equal(detail.share_version, 1);
  assert.equal(detail.manage_token, undefined);
  assert.equal(detail.owner, undefined);
  const doc = await planDoc(r.plan_id);
  assert.equal(lifecycle.toMs(doc.last_activity_at), t1);
  assert.equal(lifecycle.toMs(doc.expires_at), t1 + 180 * DAY_MS);
  assert.equal(lifecycle.toMs(doc.delete_after), lifecycle.deletionEligibleAtMs(doc));
});

test("22: 24 時間以内の再オープンでは書き込まない", async () => {
  const r = await publish();
  const t1 = T0 + 2 * DAY_MS;
  await store.openDetail({ planId: r.plan_id, nowMs: t1 });
  await store.openDetail({ planId: r.plan_id, nowMs: t1 + DAY_MS - 1 });
  assert.equal(lifecycle.toMs((await planDoc(r.plan_id)).last_activity_at), t1);
  await store.openDetail({ planId: r.plan_id, nowMs: t1 + DAY_MS });
  assert.equal(lifecycle.toMs((await planDoc(r.plan_id)).last_activity_at), t1 + DAY_MS);
});

test("20 / 25: 期限切れは詳細も Map も返さない（state は published のまま = 導出条件）", async () => {
  const r = await publish();
  const after = T0 + 180 * DAY_MS;
  await rejects(store.openDetail({ planId: r.plan_id, nowMs: after }), "NOT_FOUND");
  assert.equal((await planDoc(r.plan_id)).state, "published");
  const doc = await planDoc(r.plan_id);
  const [z, x, y] = doc.tiles.z10.split("/");
  assert.equal((await store.getTile({ z, x, y, nowMs: after })).plans.length, 0);
  assert.equal((await store.getTile({ z, x, y, nowMs: after - 1 })).plans.length, 1);
});

test("23: Map の tile 取得は activity を更新しない。fragment も token hash も返さない", async () => {
  const r = await publish();
  const doc = await planDoc(r.plan_id);
  const [z, x, y] = doc.tiles.z14.split("/");
  const tile = await store.getTile({ z, x, y, nowMs: T0 + 5 * DAY_MS });
  assert.equal(tile.plans.length, 1);
  assert.equal(tile.plans[0].plan_id, r.plan_id);
  assert.equal(tile.plans[0].lat, doc.display.lat);
  assert.equal(tile.plans[0].fragment, undefined);
  assert.ok(!JSON.stringify(tile).includes(doc.owner.manage_token_sha256));
  assert.equal(lifecycle.toMs((await planDoc(r.plan_id)).last_activity_at), T0);
});

test("24 / 26: unpublished と removed は Map に出ない", async () => {
  const a = await publish();
  const b = await publish();
  const c = await publish();
  await store.unpublish({ planId: a.plan_id, manageToken: a.manage_token, nowMs: T0 });
  await store.removeByOperator({ planId: b.plan_id, nowMs: T0 });
  const [z, x, y] = (await planDoc(c.plan_id)).tiles.z6.split("/");
  const tile = await store.getTile({ z, x, y, nowMs: T0 + 1 });
  assert.deepEqual(tile.plans.map((p) => p.plan_id), [c.plan_id]);
  await rejects(store.openDetail({ planId: b.plan_id, nowMs: T0 + 1 }), "NOT_FOUND");
});

test("27: 1 tile の件数には上限がある（超えたら truncated ＋ 件数だけ集計）。範囲外の tile は拒否", async () => {
  for (let i = 0; i < CONSTANTS.TILE_RESULT_LIMIT + 5; i += 1) await publish(); // 日次 counter の競合を避けて順に
  const any = (await db.collection(CONSTANTS.COLLECTION_PLANS).limit(1).get()).docs[0].data();
  const [z, x, y] = any.tiles.z10.split("/");
  const tile = await store.getTile({ z, x, y, nowMs: T0 + 1 });
  assert.equal(tile.plans.length, CONSTANTS.TILE_RESULT_LIMIT);
  assert.equal(tile.truncated, true);
  assert.equal(tile.count, CONSTANTS.TILE_RESULT_LIMIT + 5);
  await rejects(store.getTile({ z: 3, x: 0, y: 0, nowMs: T0 }), "INVALID_TILE");
  await rejects(store.getTile({ z: 10, x: 99999, y: 0, nowMs: T0 }), "INVALID_TILE");
});

test("28 / 29: 物理削除は unpublish / 期限切れから 30 日後だけ", async () => {
  const keep = await publish();
  const gone = await publish();
  await store.unpublish({ planId: gone.plan_id, manageToken: gone.manage_token, nowMs: T0 });
  let res = await store.deleteEligible({ nowMs: T0 + 30 * DAY_MS - 1 });
  assert.equal(res.plans, 0);
  res = await store.deleteEligible({ nowMs: T0 + 30 * DAY_MS });
  assert.equal(res.plans, 1);
  assert.equal(await planDoc(gone.plan_id), null);
  assert.ok(await planDoc(keep.plan_id));
  // 公開中のものは期限切れ（180 日）＋ 30 日まで残る
  res = await store.deleteEligible({ nowMs: T0 + 210 * DAY_MS - 1 });
  assert.equal(res.plans, 0);
  res = await store.deleteEligible({ nowMs: T0 + 210 * DAY_MS });
  assert.equal(res.plans, 1);
});

test("v2 の実 SharePlan（太陽・月 / 星の軌跡）も publish・詳細・Map で往復する", async () => {
  for (const fragment of [V2SL, V2ST]) {
    const r = await publish(fragment);
    const d = await store.openDetail({ planId: r.plan_id, nowMs: T0 + 1 });
    assert.equal(d.fragment, fragment);
    assert.equal(d.share_version, 2);
  }
});

// ---- live local smoke: HTTP handler → 実 store（emulator）→ 実 SharePlan ----------------------------
function fakeRes() {
  const res = { statusCode: null, headers: {}, body: undefined };
  res.setHeader = (k, v) => { res.headers[k] = v; };
  res.status = (c) => { res.statusCode = c; return res; };
  res.json = (b) => { res.body = b; return res; };
  return res;
}
async function http(method, op, body, query = {}) {
  const res = fakeRes();
  await handler({ method, query: { op, ...query }, headers: { "content-type": "application/json" }, body }, res);
  return res;
}

test("live local smoke（HTTP 経由）: publish → tile → open（元の fragment）→ unpublish → 消える", async () => {
  const pub = await http("POST", "publish", { fragment: GV1, idempotency_key: newKey(), consent_version: "qr-map-consent/1" });
  assert.equal(pub.statusCode, 201, JSON.stringify(pub.body));
  const planId = pub.body.plan_id;
  const doc = await planDoc(planId);
  const [z, x, y] = doc.tiles.z10.split("/");
  const tile = await http("GET", "tile", undefined, { z, x, y });
  assert.equal(tile.statusCode, 200);
  assert.ok(tile.body.plans.some((p) => p.plan_id === planId));
  const open = await http("POST", "open", { plan_id: planId });
  assert.equal(open.statusCode, 200);
  assert.equal(open.body.fragment, GV1); // 既存 Viewer（/share#fragment）へそのまま渡せる
  const un = await http("POST", "unpublish", { plan_id: planId, manage_token: pub.body.manage_token });
  assert.deepEqual([un.statusCode, un.body.state], [200, "unpublished"]);
  assert.equal((await http("POST", "open", { plan_id: planId })).statusCode, 404);
});

// ---- G-5.1 Production Safety Infrastructure（HD-PLANNERQRMAP-044）------------------------------------------
const cleanupHandler = require("../../../api/qr-map-cleanup.js");

async function withEnv(patch, fn) {
  const saved = {};
  for (const [k, v] of Object.entries(patch)) {
    saved[k] = process.env[k];
    if (v === undefined) delete process.env[k]; else process.env[k] = v;
  }
  try { return await fn(); }
  finally {
    for (const [k, v] of Object.entries(saved)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; }
  }
}

test("G-5.1 cleanup: active は残す・期限切れ / 取り消しは猶予 30 日の後だけ削除・再実行は安全", async () => {
  const active = await publish();
  const expired = await publish(GV1, { nowMs: T0 - 200 * DAY_MS });           // 180 日前に期限切れ ＋ 20 日経過
  const expiredGone = await publish(GV1, { nowMs: T0 - 220 * DAY_MS });       // 期限切れ ＋ 40 日経過
  const unpublished = await publish();
  const unpublishedGone = await publish(GV1, { nowMs: T0 - 40 * DAY_MS });
  await store.unpublish({ planId: unpublished.plan_id, manageToken: unpublished.manage_token, nowMs: T0 - 10 * DAY_MS });
  await store.unpublish({ planId: unpublishedGone.plan_id, manageToken: unpublishedGone.manage_token, nowMs: T0 - 31 * DAY_MS });
  const report = await store.cleanupEligible({ nowMs: T0 });
  assert.equal(report.deleted.plans, 2, JSON.stringify(report));
  assert.equal(report.malformed, 0);
  assert.ok(await planDoc(active.plan_id), "active は残る");
  assert.ok(await planDoc(expired.plan_id), "期限切れ ＋ 猶予の途中は残る");
  assert.ok(await planDoc(unpublished.plan_id), "取り消し ＋ 猶予の途中は残る");
  assert.equal(await planDoc(expiredGone.plan_id), null);
  assert.equal(await planDoc(unpublishedGone.plan_id), null);
  const again = await store.cleanupEligible({ nowMs: T0 });                    // 再実行（retry）
  assert.deepEqual(again.deleted, { plans: 0, idempotency: 0, counters: 0 });
  assert.ok(await planDoc(active.plan_id));
});

test("G-5.1 cleanup: 壊れた document は消さずに数える（他の削除は続ける）", async () => {
  const gone = await publish(GV1, { nowMs: T0 - 40 * DAY_MS });
  await store.unpublish({ planId: gone.plan_id, manageToken: gone.manage_token, nowMs: T0 - 31 * DAY_MS });
  const past = admin.firestore.Timestamp.fromMillis(T0 - 100 * DAY_MS);
  const plans = db.collection(CONSTANTS.COLLECTION_PLANS);
  await plans.doc("f".repeat(32)).set({ state: "deleted", delete_after: past, expires_at: past });   // 未知の state
  await plans.doc("e".repeat(32)).set({ state: "unpublished", delete_after: past });                 // 時刻が欠けている
  const report = await store.cleanupEligible({ nowMs: T0 });
  assert.equal(report.malformed, 2, JSON.stringify(report));
  assert.equal(report.deleted.plans, 1);
  assert.ok((await plans.doc("f".repeat(32)).get()).exists);
  assert.ok((await plans.doc("e".repeat(32)).get()).exists);
  assert.equal(await planDoc(gone.plan_id), null);
});

test("G-5.1 cleanup: 1 回の件数には上限がある（more: true、次回で続きを消す）。補助 document も期限後に消す", async () => {
  const ids = [];
  for (let i = 0; i < 3; i += 1) {
    const r = await publish(GV1, { nowMs: T0 - 40 * DAY_MS });
    await store.unpublish({ planId: r.plan_id, manageToken: r.manage_token, nowMs: T0 - 31 * DAY_MS });
    ids.push(r.plan_id);
  }
  const first = await store.cleanupEligible({ nowMs: T0, limit: 2 });
  assert.equal(first.deleted.plans, 2);
  assert.equal(first.more, true);
  const second = await store.cleanupEligible({ nowMs: T0, limit: 2 });
  assert.equal(second.deleted.plans, 1);
  for (const id of ids) assert.equal(await planDoc(id), null);
  // 上限を超える limit は CONSTANTS.CLEANUP_BATCH_LIMIT に丸める（無制限の削除経路を作らない）
  const huge = await store.cleanupEligible({ nowMs: T0, limit: 10 ** 9 });
  assert.equal(huge.more, false);
  // idempotency（created + 30 日）と日次 counter（+30 日）も、期限後の実行で消える（上の実行で一部は消えている）
  const total = first.deleted.idempotency + second.deleted.idempotency + huge.deleted.idempotency;
  assert.equal(total, 3, JSON.stringify({ first, second, huge }));
  assert.ok((await db.collection(CONSTANTS.COLLECTION_IDEMPOTENCY).get()).empty);
  assert.ok((await db.collection(CONSTANTS.COLLECTION_COUNTERS).get()).empty);
});

test("G-5.1 circuit breaker: 公開だけを止める（tile・詳細・取り消しは動く）", async () => {
  const r = await publish();
  const doc = await planDoc(r.plan_id);
  const [z, x, y] = doc.tiles.z10.split("/");
  await withEnv({ QR_MAP_PUBLISH_ENABLED: undefined }, async () => {
    await rejects(publish(), "PUBLISH_DISABLED");
    const tile = await store.getTile({ z, x, y, nowMs: T0 + 1 });
    assert.ok(tile.plans.some((p) => p.plan_id === r.plan_id));            // Map の読み取りは続く
    const detail = await store.openDetail({ planId: r.plan_id, nowMs: T0 + 2 * DAY_MS });
    assert.equal(detail.fragment, GV1);                                    // 詳細 → 既存 Viewer へ渡せる
    assert.equal(lifecycle.toMs((await planDoc(r.plan_id)).last_activity_at), T0 + 2 * DAY_MS);   // activity 更新も動く
    const un = await store.unpublish({ planId: r.plan_id, manageToken: r.manage_token, nowMs: T0 + 3 * DAY_MS });
    assert.equal(un.state, "unpublished");                                 // 緊急停止中でも利用者は取り消せる
  });
});

test("G-5.1 live local smoke（HTTP 経由・Cron endpoint）: publish → 詳細 → 取り消し → 猶予後に cleanup で削除", async () => {
  const pub = await http("POST", "publish", { fragment: GV1, idempotency_key: newKey(), consent_version: "qr-map-consent/1" });
  assert.equal(pub.statusCode, 201);
  const planId = pub.body.plan_id;
  assert.equal((await http("POST", "open", { plan_id: planId })).statusCode, 200);
  // 取り消しの時刻を 31 日前にする（実時間を待たない）
  await store.unpublish({ planId, manageToken: pub.body.manage_token, nowMs: Date.now() - 31 * DAY_MS });
  const call = async (env, auth) => withEnv(env, async () => {
    const res = fakeRes();
    await cleanupHandler({ method: "GET", headers: auth ? { authorization: auth } : {}, query: {} }, res);
    return res;
  });
  assert.equal((await call({ CRON_SECRET: undefined, QR_MAP_CLEANUP_ENABLED: undefined })).statusCode, 503);
  assert.ok(await planDoc(planId), "switch が無ければ何も消さない");
  assert.equal((await call({ CRON_SECRET: "local-secret", QR_MAP_CLEANUP_ENABLED: "true" }, "Bearer nope")).statusCode, 401);
  const ok = await call({ CRON_SECRET: "local-secret", QR_MAP_CLEANUP_ENABLED: "true" }, "Bearer local-secret");
  assert.equal(ok.statusCode, 200, JSON.stringify(ok.body));
  assert.ok(ok.body.deleted.plans >= 1);
  assert.equal(JSON.stringify(ok.body).includes(planId), false);           // 応答に plan_id を出さない
  assert.equal(await planDoc(planId), null);
});

// ---- G-6（Map Discovery Filter）U1: display.categories --------------------------------------------
test("G-6: publish で display.categories を保存し、tile の応答に返す（実 SharePlan、v1 / v2）", async () => {
  const cases = [["VALID_GV-1", ["diamond"]], ["VALID_GV-3", ["pearl"]], ["VALID_V2-SLMW-1", ["milky_way"]],
    ["VALID_V2-SLST-1", ["other"]], ["VALID_V2-SL-1", ["other"]], ["VALID_V2-ST-1", ["other"]]];
  for (const [id, expected] of cases) {
    const r = await publish(byId[id].payload);
    const doc = await planDoc(r.plan_id);
    assert.deepEqual(doc.display.categories, expected, id + "（保存値）");
    const [z, x, y] = doc.tiles.z6.split("/").map(Number);
    const tile = await store.getTile({ z, x, y, nowMs: T0 + 1 });
    const mine = tile.plans.find((p) => p.plan_id === r.plan_id);
    assert.deepEqual(mine.categories, expected, id + "（tile の応答）");
    assert.equal(mine.fragment, undefined);
  }
});

test("G-6: G-6 より前の document（categories 無し）も tile で分類を返す（migration しない、取得時に導く）", async () => {
  const r = await publish(byId["VALID_V2-SLMW-1"].payload);
  const ref = db.collection(CONSTANTS.COLLECTION_PLANS).doc(r.plan_id);
  await ref.update({ "display.categories": admin.firestore.FieldValue.delete() });
  const doc = await planDoc(r.plan_id);
  assert.equal(doc.display.categories, undefined);
  const [z, x, y] = doc.tiles.z6.split("/").map(Number);
  const tile = await store.getTile({ z, x, y, nowMs: T0 + 1 });
  assert.deepEqual(tile.plans.find((p) => p.plan_id === r.plan_id).categories, ["milky_way"]);
});
