// G-6（Map Discovery Filter）U1: PublicPlan の discovery 分類（display.categories）を、Planner 正本の実 SharePlan
// （cross-language vectors）で固定する。分類は genre と空の対象 id だけで決まり、表示文字列（「天の川」）に依存しない。
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import zlib from "node:zlib";

const require = createRequire(import.meta.url);
const { parsePublishableFragment } = require("../../../api/_qr_map/shareplan.js");
const discovery = require("../../../api/_qr_map/discovery.js");
const { createStore } = require("../../../api/_qr_map/store.js");

const VECTORS = JSON.parse(readFileSync(new URL("../../fixtures/qr_map/cross_language_vectors.json", import.meta.url), "utf8"));
const byId = Object.fromEntries(VECTORS.cases.map((c) => [c.id, c]));

const EXPECTED = {
  "VALID_GV-1": ["diamond"],
  "VALID_GV-2": ["diamond"],
  "VALID_GV-3": ["pearl"],
  "VALID_V2-SL-1": ["other"],
  "VALID_V2-SLMW-1": ["milky_way"],
  "VALID_V2-SLST-1": ["other"],
  "VALID_V2-ST-1": ["other"],
  "VALID_V2-ST-REAL": ["other"]
};

function wireOf(fragment) {
  return JSON.parse(zlib.inflateSync(Buffer.from(fragment, "base64url")).toString("utf8"));
}

function fragmentOf(wire) {
  return zlib.deflateSync(Buffer.from(JSON.stringify(wire), "utf8"), { level: 9 }).toString("base64url");
}

test("公開時: 実 SharePlan（v1 / v2）から display.categories が導かれる", async () => {
  for (const [id, expected] of Object.entries(EXPECTED)) {
    const parsed = await parsePublishableFragment(byId[id].payload);
    assert.deepEqual(parsed.display.categories, expected, id);
  }
});

test("公開時の display は G-6 前の値を変えない（categories が足されるだけ）", async () => {
  const parsed = await parsePublishableFragment(byId["VALID_V2-SLMW-1"].payload);
  const { categories, ...rest } = parsed.display;
  assert.deepEqual(Object.keys(rest).sort(), ["genre", "genre_label", "lat", "lon", "sky_object_label", "t_d", "target_label"]);
  assert.equal(rest.genre, "star_landscape");
  assert.equal(rest.sky_object_label, "天の川");
  assert.deepEqual(categories, ["milky_way"]);
});

test("分類は空の対象 id で決まり、表示文字列「天の川」には依存しない", () => {
  const mw = wireOf(byId["VALID_V2-SLMW-1"].payload);
  const other = wireOf(byId["VALID_V2-SLST-1"].payload);
  assert.equal(mw.b.o, "milky_way");
  assert.notEqual(other.b.o, "milky_way");
  // ラベルが「天の川」でも、id が milky_way でなければ天の川にしない
  const lying = { display: { genre: "star_landscape", sky_object_label: "天の川" },
    snapshot: { share_version: 2, fragment: byId["VALID_V2-SLST-1"].payload } };
  assert.deepEqual(discovery.categoriesOfDocument(lying), ["other"]);
  // ラベルが別の表記（翻訳等）でも、id が milky_way なら天の川
  const translated = { display: { genre: "star_landscape", sky_object_label: "Milky Way" },
    snapshot: { share_version: 2, fragment: byId["VALID_V2-SLMW-1"].payload } };
  assert.deepEqual(discovery.categoriesOfDocument(translated), ["milky_way"]);
  // source にも、ラベルでの判定が無い
  const src = readFileSync(new URL("../../../api/_qr_map/discovery.js", import.meta.url), "utf8");
  assert.ok(!src.includes("sky_object_label ==") && !/["']天の川["']/.test(src), "discovery.js がラベル文字列で判定している");
});

test("G-6 より前の document（display.categories 無し）は取得時に導く（migration しない）", async () => {
  for (const [id, expected] of Object.entries(EXPECTED)) {
    const parsed = await parsePublishableFragment(byId[id].payload);
    const { categories, ...legacyDisplay } = parsed.display;
    const legacy = { display: legacyDisplay, snapshot: parsed.snapshot };
    assert.deepEqual(discovery.categoriesOfDocument(legacy), expected, id + "（fallback）");
    assert.deepEqual(discovery.categoriesOfDocument({ display: parsed.display, snapshot: parsed.snapshot }), expected, id + "（保存値）");
  }
});

test("想定外の入力は公開を止めず other にする / 保存値が壊れていれば導き直す", () => {
  assert.deepEqual(discovery.categoriesFor({ genre: "fireworks_future" }), ["other"]);
  assert.deepEqual(discovery.categoriesFor({ genre: "star_landscape", skyObject: null }), ["other"]);
  assert.deepEqual(discovery.categoriesFromDecoded({}), ["other"]);
  assert.deepEqual(discovery.categoriesOfDocument({ display: { genre: "pearl_fuji", categories: ["<b>"] }, snapshot: {} }), ["pearl"]);
  assert.deepEqual(discovery.categoriesOfDocument({ display: { genre: "star_landscape" }, snapshot: { share_version: 2, fragment: "@@@" } }), ["other"]);
  assert.deepEqual(discovery.categoriesOfDocument(null), ["other"]);
});

test("分類は表で拡張できる（genre の追加で API / DB を作り直さない）", () => {
  const ids = discovery.DISCOVERY_CATEGORIES.map((c) => c.id);
  assert.deepEqual(ids, ["diamond", "pearl", "milky_way"]);
  assert.ok(!ids.includes(discovery.OTHER));
  for (const c of discovery.DISCOVERY_CATEGORIES) assert.ok(Array.isArray(c.match.genres) && c.match.genres.length > 0, c.id);
});

test("tile の応答（publicView）に categories が足され、既存の項目は変わらない", async () => {
  const parsed = await parsePublishableFragment(byId["VALID_GV-3"].payload);
  const doc = {
    plan_id: "a".repeat(32), state: "published", location_precision: "exact",
    display: parsed.display, snapshot: parsed.snapshot,
    expires_at: { toMillis: () => Date.now() + 86400000 }
  };
  const fakeDb = {
    collection: () => ({
      where() { return this; },
      limit() { return { get: async () => ({ docs: [{ data: () => doc }] }) }; }
    })
  };
  const store = createStore({ db: fakeDb, Timestamp: { fromMillis: (ms) => ({ toMillis: () => ms }) } }, {});
  const tile = await store.getTile({ z: 6, x: 56, y: 25 });
  assert.equal(tile.plans.length, 1);
  assert.deepEqual(Object.keys(tile.plans[0]).sort(),
    ["categories", "genre", "genre_label", "lat", "location_precision", "lon", "plan_id", "sky_object_label", "t_d", "target_label"]);
  assert.deepEqual(tile.plans[0].categories, ["pearl"]);
});
