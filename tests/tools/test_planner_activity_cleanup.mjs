// api/planner-activity-cleanup.js の contract test（HD-PLANNERACTIVITY-012、AI-6215）。
// firebase-admin を in-memory の fake に差し替えて、「expire_at <= now だけ」「500 件単位」「冪等」
// 「aggregate に触れない」「secret 無しは動かない」を固定する。
//   node --test tests/tools/test_planner_activity_cleanup.mjs
import assert from "node:assert/strict";
import test from "node:test";
import Module from "node:module";
import { createRequire } from "node:module";

// ---- fake firebase-admin ------------------------------------------------
function makeFakeDb() {
  const store = new Map(); // "collection/doc" -> data ; expire_at は Date
  const touched = [];      // 触った collection 名（aggregate を触らないことの検査）
  const db = {
    store, touched,
    collection(name) {
      touched.push(name);
      const col = {
        where(field, op, value) {
          assert.equal(field, "expire_at"); assert.equal(op, "<=");
          return {
            orderBy() { return this; },
            limit(n) { this._limit = n; return this; },
            async get() {
              const rows = [...store.entries()]
                .filter(([k, v]) => k.startsWith(name + "/") && v.expire_at instanceof Date && v.expire_at.getTime() <= value.getTime())
                .sort((a, b) => a[1].expire_at - b[1].expire_at)
                .slice(0, this._limit || Infinity)
                .map(([k]) => ({ ref: { key: k } }));
              return { empty: rows.length === 0, forEach(fn) { rows.forEach(fn); } };
            }
          };
        }
      };
      return col;
    },
    batch() {
      const ops = [];
      return {
        delete(ref) { ops.push(ref.key); },
        async commit() { for (const k of ops) store.delete(k); }
      };
    }
  };
  return db;
}
let fakeDb = makeFakeDb();
const fakeAdmin = {
  apps: [{}],
  credential: { cert: () => ({}) },
  initializeApp() {},
  firestore: Object.assign(() => fakeDb, {
    Timestamp: { fromDate: (d) => d }
  })
};
const originalLoad = Module._load;
Module._load = function (request, ...rest) {
  if (request === "firebase-admin") return fakeAdmin;
  return originalLoad.call(this, request, ...rest);
};
const require = createRequire(import.meta.url);
const api = require("../../api/planner-activity-cleanup.js");

function fakeRes() {
  const res = { statusCode: null, headers: {}, body: undefined };
  res.setHeader = (k, v) => { res.headers[k] = v; };
  res.status = (c) => { res.statusCode = c; return res; };
  res.end = () => res;
  res.json = (b) => { res.body = b; return res; };
  return res;
}
const NOW = new Date("2026-09-19T18:30:00Z");
const past = (days) => new Date(NOW.getTime() - days * 86400000);
const future = (days) => new Date(NOW.getTime() + days * 86400000);
function seed(db) {
  db.store.set("planner_activity_events/ttl-bootstrap", { bootstrap: true, expire_at: past(1) });
  db.store.set("planner_activity_events/" + "a".repeat(32), { event: "share_viewed", expire_at: past(30) });
  db.store.set("planner_activity_events/" + "b".repeat(32), { event: "share_created", expire_at: future(400) });
  db.store.set("planner_activity_events/" + "c".repeat(32), { event: "share_created" });           // expire_at 無し
  db.store.set("planner_activity_daily/2026-09-19", { share_created: 3, expire_at: past(1) });      // 触らない
  db.store.set("planner_activity_totals/all", { share_created: 3 });
}
async function run(headers = {}, env = { CRON_SECRET: "s3cret" }) {
  const saved = process.env.CRON_SECRET;
  if (env.CRON_SECRET === undefined) delete process.env.CRON_SECRET; else process.env.CRON_SECRET = env.CRON_SECRET;
  const res = fakeRes();
  try { await api({ method: "GET", headers }, res); }
  finally { if (saved === undefined) delete process.env.CRON_SECRET; else process.env.CRON_SECRET = saved; }
  return res;
}

test("authorized: Bearer <CRON_SECRET> だけ。secret 未設定は常に false", () => {
  assert.equal(api.authorized({ headers: { authorization: "Bearer x" } }, "x"), true);
  assert.equal(api.authorized({ headers: { authorization: "Bearer y" } }, "x"), false);
  assert.equal(api.authorized({ headers: {} }, "x"), false);
  assert.equal(api.authorized({ headers: { authorization: "Bearer x" } }, ""), false);
});

test("期限切れだけ消す。未来・expire_at 無し・aggregate は残る。ttl-bootstrap が消える", async () => {
  fakeDb = makeFakeDb(); seed(fakeDb);
  const result = await api.cleanupExpired(fakeDb, NOW);
  assert.deepEqual(result, { deleted: 2, batches: 1, exhausted: false });
  assert.equal(fakeDb.store.has("planner_activity_events/ttl-bootstrap"), false);
  assert.equal(fakeDb.store.has("planner_activity_events/" + "a".repeat(32)), false);
  assert.equal(fakeDb.store.has("planner_activity_events/" + "b".repeat(32)), true);
  assert.equal(fakeDb.store.has("planner_activity_events/" + "c".repeat(32)), true);
  assert.equal(fakeDb.store.has("planner_activity_daily/2026-09-19"), true);   // expire_at があっても別 collection は触らない
  assert.equal(fakeDb.store.has("planner_activity_totals/all"), true);
  assert.deepEqual([...new Set(fakeDb.touched)], ["planner_activity_events"]);
});

test("冪等: 2 回目は 0 件", async () => {
  fakeDb = makeFakeDb(); seed(fakeDb);
  await api.cleanupExpired(fakeDb, NOW);
  const again = await api.cleanupExpired(fakeDb, NOW);
  assert.equal(again.deleted, 0);
});

test("500 件単位で最大 MAX_BATCHES 回。それ以上は次回に持ち越す（exhausted）", async () => {
  fakeDb = makeFakeDb();
  const total = api.BATCH_SIZE * api.MAX_BATCHES + 7;
  for (let i = 0; i < total; i++) fakeDb.store.set("planner_activity_events/" + String(i).padStart(32, "0"), { expire_at: past(2) });
  const result = await api.cleanupExpired(fakeDb, NOW);
  assert.equal(result.deleted, api.BATCH_SIZE * api.MAX_BATCHES);
  assert.equal(result.batches, api.MAX_BATCHES);
  assert.equal(result.exhausted, true);
  assert.equal([...fakeDb.store.keys()].length, 7);
  const rest = await api.cleanupExpired(fakeDb, NOW);
  assert.equal(rest.deleted, 7);
});

test("handler: secret 未設定は 503 で何もしない、不一致は 401、一致で削除して 200", async () => {
  fakeDb = makeFakeDb(); seed(fakeDb);
  const r1 = await run({ authorization: "Bearer s3cret" }, { CRON_SECRET: undefined });
  assert.equal(r1.statusCode, 503);
  assert.equal(fakeDb.store.has("planner_activity_events/ttl-bootstrap"), true);
  const r2 = await run({ authorization: "Bearer wrong" });
  assert.equal(r2.statusCode, 401);
  assert.equal(fakeDb.store.has("planner_activity_events/ttl-bootstrap"), true);
  const r3 = await run({ authorization: "Bearer s3cret" });
  assert.equal(r3.statusCode, 200);
  assert.equal(r3.body.ok, true);
  assert.equal(r3.body.collection, "planner_activity_events");
  assert.equal(r3.body.deleted, 2);
  assert.equal(fakeDb.store.has("planner_activity_events/ttl-bootstrap"), false);
});

test("handler: GET 以外は 405", async () => {
  const res = fakeRes();
  await api({ method: "POST", headers: {} }, res);
  assert.equal(res.statusCode, 405);
});
