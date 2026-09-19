// api/planner-activity.js の contract test（HD-PLANNERACTIVITY-001〜011、AI-6205）。
// firebase-admin を in-memory の fake に差し替えて、allow-list・冪等・集計・k >= 5 を固定する。
//   node --test tests/tools/test_planner_activity_api.mjs
import assert from "node:assert/strict";
import test from "node:test";
import Module from "node:module";
import { createRequire } from "node:module";

// ---- fake firebase-admin ------------------------------------------------
const INC = Symbol("increment");
const SERVER_TS = Symbol("serverTimestamp");
function makeFakeDb() {
  const store = new Map(); // "collection/doc" -> data
  const key = (c, d) => c + "/" + d;
  function applyMerge(existing, data) {
    const out = { ...(existing || {}) };
    for (const k of Object.keys(data)) {
      const v = data[k];
      if (v && v[INC] !== undefined) out[k] = (out[k] || 0) + v[INC];
      else if (v === SERVER_TS) out[k] = "server-ts";
      else out[k] = v;
    }
    return out;
  }
  const db = {
    store,
    collection(name) {
      return {
        doc(id) {
          return {
            async create(data) {
              if (store.has(key(name, id))) { const e = new Error("6 ALREADY_EXISTS: already exists"); e.code = 6; throw e; }
              store.set(key(name, id), applyMerge({}, data));
            },
            async set(data, opts) {
              const existing = opts && opts.merge ? store.get(key(name, id)) : {};
              store.set(key(name, id), applyMerge(existing, data));
            },
            async get() {
              const data = store.get(key(name, id));
              return { exists: data !== undefined, data: () => data };
            }
          };
        },
        where(field, op, value) {
          assert.equal(op, ">=");
          return { orderBy() { return { async get() {
            const rows = [...store.entries()].filter(([k, v]) => k.startsWith(name + "/") && v[field] >= value)
              .sort((a, b) => (a[1][field] < b[1][field] ? -1 : 1));
            return { forEach(fn) { rows.forEach(([k, v]) => fn({ id: k.split("/")[1], data: () => v })); } };
          } }; } };
        }
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
    FieldValue: { increment: (n) => ({ [INC]: n }), serverTimestamp: () => SERVER_TS },
    Timestamp: { fromDate: (d) => d }
  })
};
const originalLoad = Module._load;
Module._load = function (request, ...rest) {
  if (request === "firebase-admin") return fakeAdmin;
  return originalLoad.call(this, request, ...rest);
};
const require = createRequire(import.meta.url);
const api = require("../../api/planner-activity.js");

// ---- helpers --------------------------------------------------------------
function fakeRes() {
  const res = { statusCode: null, headers: {}, body: undefined };
  res.setHeader = (k, v) => { res.headers[k] = v; };
  res.status = (c) => { res.statusCode = c; return res; };
  res.end = () => res;
  res.json = (b) => { res.body = b; return res; };
  return res;
}
const hex = (n) => n.toString(16).padStart(32, "0");
const VIEWER_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1";
async function post(body, headers = {}) {
  const req = { method: "POST", headers: { "user-agent": VIEWER_UA, ...headers }, body };
  const res = fakeRes();
  await api(req, res);
  return res;
}

// ---- pure functions ---------------------------------------------------------
test("UA は分類してから捨てる", () => {
  assert.equal(api.classifyUserAgent("SidekickPlanner/1.0.0-beta.1"), "planner");
  assert.equal(api.classifyUserAgent(VIEWER_UA), "mobile");
  assert.equal(api.classifyUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128"), "desktop");
  assert.equal(api.classifyUserAgent("facebookexternalhit/1.1"), "preview_fetch");
  assert.equal(api.classifyUserAgent("Python-urllib/3.11"), "bot");
  assert.equal(api.classifyUserAgent(""), "unknown");
});

test("at は 1 時間粒度・実在・過去 400 日 / 未来 1 日以内。外れたら server 時刻へ", () => {
  const now = new Date("2026-09-19T08:34:56Z");
  assert.equal(api.normalizeAt("2026-09-19T07:00Z", now).toISOString(), "2026-09-19T07:00:00.000Z");
  assert.equal(api.normalizeAt("2026-09-19T07:15Z", now).toISOString(), "2026-09-19T08:00:00.000Z");
  assert.equal(api.normalizeAt("2026-02-30T07:00Z", now).toISOString(), "2026-09-19T08:00:00.000Z");
  assert.equal(api.normalizeAt("2020-01-01T00:00Z", now).toISOString(), "2026-09-19T08:00:00.000Z");
  assert.equal(api.normalizeAt("2026-09-25T00:00Z", now).toISOString(), "2026-09-19T08:00:00.000Z");
  assert.equal(api.normalizeAt(undefined, now).toISOString(), "2026-09-19T08:00:00.000Z");
});

test("allow-list: plan_ref / poi_id / 緯度経度 / installation_id / country は捨てる", () => {
  const now = new Date("2026-09-19T08:00:00Z");
  const r = api.normalizeEvent({
    schema: "planner_activity/1", event: "share_created", event_id: hex(1), at: "2026-09-19T07:00Z",
    category: "mountain", transport: "viewer",
    plan_ref: "0123456789abcdef", poi_id: "fuji", latitude: 35.36, longitude: 139.13, utc_datetime: "2027-03-31T08:34:00Z",
    installation_id: "x", country: "JP", fragment: "eJx..."
  }, "planner", now);
  assert.deepEqual(Object.keys(r.doc).sort(), ["at", "category", "client_kind", "day", "event", "schema", "transport"]);
  assert.equal(r.doc.category, "mountain");
  assert.equal(r.doc.transport, "viewer");
});

test("schema / event / event_id が違えば無視", () => {
  const now = new Date();
  assert.equal(api.normalizeEvent({ schema: "planner_activity/2", event: "share_created", event_id: hex(1) }, "planner", now), null);
  assert.equal(api.normalizeEvent({ schema: "planner_activity/1", event: "search_a", event_id: hex(1) }, "planner", now), null);
  assert.equal(api.normalizeEvent({ schema: "planner_activity/1", event: "share_created", event_id: "abc" }, "planner", now), null);
  assert.equal(api.normalizeEvent(["share_created"], "planner", now), null);
});

test("未知の category / transport は unknown に倒す（送信を止めない）", () => {
  const r = api.normalizeEvent({ schema: "planner_activity/1", event: "share_created", event_id: hex(2), category: "fuji", transport: "copy_link" }, "planner", new Date());
  assert.equal(r.doc.category, "unknown");
  assert.equal(r.doc.transport, "unknown");
});

test("increments: category / transport / unique / client / code", () => {
  assert.deepEqual(api.incrementsFor({ event: "share_created", category: "structure", transport: "planner" }),
    { share_created: 1, share_created_category_structure: 1, share_created_transport_planner: 1 });
  assert.deepEqual(api.incrementsFor({ event: "share_viewed", repeat: false, client_kind: "mobile" }),
    { share_viewed: 1, share_viewed_client_mobile: 1, share_viewed_unique: 1 });
  assert.deepEqual(api.incrementsFor({ event: "share_viewed", repeat: true, client_kind: "desktop" }),
    { share_viewed: 1, share_viewed_client_desktop: 1 });
  assert.deepEqual(api.incrementsFor({ event: "share_view_failed", code: "UNSUPPORTED_BROWSER" }),
    { share_view_failed: 1, share_view_failed_code_UNSUPPORTED_BROWSER: 1 });
});

test("publicView: 細粒度は k >= 5 未満を伏せ、主要件数はそのまま", () => {
  assert.deepEqual(api.publicView({ share_created: 3, share_created_category_mountain: 3, share_viewed: 12, share_viewed_client_mobile: 5, day: "2026-09-19", updated_at: "x" }),
    { share_created: 3, share_viewed: 12, share_viewed_client_mobile: 5 });
});

// ---- handler ------------------------------------------------------------------
test("POST: 正常 event は 204、raw doc に禁止 field が無く、daily / totals が増える", async () => {
  fakeDb = makeFakeDb();
  const res = await post({ schema: "planner_activity/1", event: "share_created", event_id: hex(10), at: "2026-09-19T07:00Z", category: "mountain", transport: "viewer", plan_ref: "deadbeef", poi_id: "fuji" },
    { "user-agent": "SidekickPlanner/1.0.0-beta.1" });
  assert.equal(res.statusCode, 204);
  const raw = fakeDb.store.get("planner_activity_events/" + hex(10));
  assert.ok(raw);
  for (const k of ["plan_ref", "poi_id", "ip", "user_agent", "country", "latitude", "longitude"]) assert.equal(k in raw, false, k);
  assert.equal(raw.client_kind, "planner");
  assert.equal(raw.received_at, "server-ts");
  assert.ok(raw.expire_at instanceof Date);
  assert.equal(Math.round((raw.expire_at - raw.at) / 86400000), 425);
  const daily = fakeDb.store.get("planner_activity_daily/2026-09-19");
  assert.equal(daily.share_created, 1);
  assert.equal(daily.share_created_transport_viewer, 1);
  assert.equal(fakeDb.store.get("planner_activity_totals/all").share_created_category_mountain, 1);
});

test("POST: 同じ event_id の再送は冪等（raw 1 件、集計 1 回）", async () => {
  fakeDb = makeFakeDb();
  const ev = { schema: "planner_activity/1", event: "share_viewed", event_id: hex(11), at: "2026-09-19T07:00Z", repeat: false };
  await post(ev); await post(ev);
  assert.equal([...fakeDb.store.keys()].filter((k) => k.startsWith("planner_activity_events/")).length, 1);
  assert.equal(fakeDb.store.get("planner_activity_totals/all").share_viewed, 1);
  assert.equal(fakeDb.store.get("planner_activity_totals/all").share_viewed_unique, 1);
});

test("POST: batch（events 配列）は個別 doc、batch id は保存しない、50 件で切る", async () => {
  fakeDb = makeFakeDb();
  const events = Array.from({ length: 60 }, (_, i) => ({ schema: "planner_activity/1", event: "share_created", event_id: hex(100 + i), at: "2026-09-19T07:00Z", category: "structure", transport: "planner" }));
  const res = await post({ events, batch_id: "b1" }, { "user-agent": "SidekickPlanner/1.0.0-beta.1" });
  assert.equal(res.statusCode, 204);
  const raws = [...fakeDb.store.entries()].filter(([k]) => k.startsWith("planner_activity_events/"));
  assert.equal(raws.length, 50);
  for (const [, v] of raws) assert.equal("batch_id" in v, false);
  assert.equal(fakeDb.store.get("planner_activity_totals/all").share_created, 50);
});

test("POST: 壊れた body・他 origin・未知 schema は 204 で何も保存しない", async () => {
  fakeDb = makeFakeDb();
  assert.equal((await post("not json")).statusCode, 204);
  assert.equal((await post({ schema: "planner_activity/9", event: "share_created", event_id: hex(1) })).statusCode, 204);
  assert.equal((await post({ schema: "planner_activity/1", event: "share_created", event_id: hex(1) }, { origin: "https://evil.example" })).statusCode, 204);
  assert.equal(fakeDb.store.size, 0);
  assert.equal((await post({ schema: "planner_activity/1", event: "share_created", event_id: hex(1) }, { origin: "https://www.sidekick-lab.com" })).statusCode, 204);
  assert.equal(fakeDb.store.size, 3);
});

test("POST: 文字列 body（sendBeacon の text/plain）も受ける", async () => {
  fakeDb = makeFakeDb();
  const res = await post(JSON.stringify({ schema: "planner_activity/1", event: "share_view_failed", event_id: hex(12), code: "UNSUPPORTED_BROWSER" }));
  assert.equal(res.statusCode, 204);
  assert.equal(fakeDb.store.get("planner_activity_totals/all").share_view_failed_code_UNSUPPORTED_BROWSER, 1);
});

test("GET: totals ＋ 直近 30 日 daily、細粒度は k >= 5 未満を伏せる、cache 5 分", async () => {
  fakeDb = makeFakeDb();
  for (let i = 0; i < 3; i++) await post({ schema: "planner_activity/1", event: "share_created", event_id: hex(200 + i), at: "2026-09-18T07:00Z", category: "mountain", transport: "viewer" }, { "user-agent": "SidekickPlanner/1.0.0-beta.1" });
  const req = { method: "GET", headers: {} };
  const res = fakeRes();
  await api(req, res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.headers["Cache-Control"], "public, max-age=300");
  assert.equal(res.body.schema, "planner_activity_aggregate/1");
  assert.equal(res.body.totals.share_created, 3);
  assert.equal("share_created_category_mountain" in res.body.totals, false);
  assert.equal(res.body.daily["2026-09-18"].share_created, 3);
  assert.equal("updated_at" in res.body.daily["2026-09-18"], false);
});

test("その他の method は 405", async () => {
  const res = fakeRes();
  await api({ method: "DELETE", headers: {} }, res);
  assert.equal(res.statusCode, 405);
});
