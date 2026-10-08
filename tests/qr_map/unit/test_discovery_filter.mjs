// G-6（Map Discovery Filter）U2: 期間 × 撮影対象の絞り込み（純関数）を固定する。
//   - 未来と過去を分ける（HD-4 訂正）: 初期は「これから」（撮影日時が今以降）。過去は「過去を見る」で明示的に選んだときだけ。
//     「これから」と「過去を見る」を合わせると、G-6 前の Map に出ていた計画をちょうど覆う（重複・欠落なし）。
//   - 過去を含む表示（過去を見る・過去を含む期間指定）では、現在も撮れるとは限らないことを知らせる（pastNotice）
//   - 撮影対象は複数選択・0 件可（HD-2）・「その他」あり（HD-3）・UI に無い分類は「その他」
//   - 「今週末」等の境目は Asia/Tokyo（HD-5）、t_d は UTC のまま比べる
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const f = require("../../../assets/planner-map/discovery-filter.js");

const jst = (s) => Date.parse(s + "+09:00");                // "2026-10-10T00:00:00" を JST として
const plan = (id, categories, tD, genre) => ({ plan_id: id, categories, t_d: tD, genre: genre || "x" });
const NOW = jst("2026-10-08T12:00:00");                     // 木曜

const PLANS = [
  plan("d1", ["diamond"], "2026-10-10T03:00:00Z"),
  plan("p1", ["pearl"], "2026-10-11T10:00:00Z"),
  plan("m1", ["milky_way"], "2026-10-15T12:00:00Z"),
  plan("o1", ["other"], "2026-10-09T14:59:59Z"),
  plan("future", ["fireworks"], "2026-11-01T00:00:00Z"),           // UI に無い分類 → その他
  plan("legacy-d", undefined, "2026-10-10T05:00:00Z", "diamond_fuji"),   // 分類の無い応答 → genre から
  plan("past-p", ["pearl"], "2025-01-01T00:00:00Z"),
  plan("past-m", ["milky_way"], "2026-10-08T02:59:59Z"),          // 今（03:00Z）の 1 秒前
  plan("now", ["diamond"], "2026-10-08T03:00:00Z")                // ちょうど今 = これから
];
const ids = (list) => list.map((p) => p.plan_id);

test("初期は「これから」× すべての撮影対象。過去の計画は出ない", () => {
  const state = f.defaultState();
  assert.equal(state.period, "upcoming");
  assert.equal(f.DEFAULT_PERIOD, "upcoming");
  assert.deepEqual(state.categories, ["diamond", "pearl", "milky_way", "other"]);
  assert.ok(f.isDefault(state));
  assert.deepEqual(ids(f.filterPlans(PLANS, state, NOW)), ["d1", "p1", "m1", "o1", "future", "legacy-d", "now"]);
  assert.equal(f.pastNotice(state, NOW), false);
});

test("regression: 「これから」∪「過去を見る」= G-6 前の Map に出ていた計画（重複も欠落も無い、並びも保つ）", () => {
  const all = f.CATEGORY_IDS;
  const upcoming = f.filterPlans(PLANS, { period: "upcoming", categories: all }, NOW);
  const past = f.filterPlans(PLANS, { period: "past", categories: all }, NOW);
  assert.deepEqual(ids(past), ["past-p", "past-m"]);
  assert.equal(upcoming.filter((p) => past.includes(p)).length, 0);
  assert.deepEqual(PLANS.filter((p) => upcoming.includes(p) || past.includes(p)), PLANS);
  assert.deepEqual(ids(upcoming.concat(past)).sort(), ids(PLANS).sort());
});

test("過去の計画は「過去を見る」だけで出し、そのときだけ「現在も撮れるとは限らない」と知らせる", () => {
  assert.equal(f.PAST_NOTICE, "過去の撮影計画を表示しています。現在も同じ条件で撮影できることを示すものではありません。");
  for (const period of ["upcoming", "weekend", "days7", "days30", "custom"]) assert.equal(f.pastNotice({ period }), false, period);
  assert.equal(f.pastNotice({ period: "past" }), true);
});

test("通常の Discovery はどの期間も t_d >= 今 だけ（ダイヤ / パール / 天の川 / その他すべて同じ）", () => {
  for (const period of ["upcoming", "weekend", "days7", "days30"]) {
    const out = f.filterPlans(PLANS, { period, categories: f.CATEGORY_IDS }, NOW);
    assert.ok(out.every((p) => Date.parse(p.t_d) >= NOW), period);
  }
  const custom = f.filterPlans(PLANS, { period: "custom", from: "2000-01-01", to: "2100-12-31", categories: f.CATEGORY_IDS }, NOW);
  assert.ok(custom.every((p) => Date.parse(p.t_d) >= NOW));
  assert.deepEqual(ids(custom), ids(f.filterPlans(PLANS, f.defaultState(), NOW)));
});

test("期間指定に今より前の日付があれば、その部分は含めず「過去を見る」へ案内する", () => {
  assert.equal(f.CUSTOM_PAST_HINT, "今より前の撮影計画は含めていません。過去の撮影計画は「過去を見る」で表示できます。");
  assert.equal(f.customOmitsPast({ period: "custom", from: "2026-10-01", to: "2026-10-05" }, NOW), true);   // すべて過去 → 0 件
  assert.deepEqual(f.filterPlans(PLANS, { period: "custom", from: "2026-10-01", to: "2026-10-05", categories: f.CATEGORY_IDS }, NOW), []);
  assert.equal(f.customOmitsPast({ period: "custom", from: "2026-10-08", to: "2026-10-20" }, NOW), true);   // 今日 00:00 から = 今より前を含む
  assert.deepEqual(f.periodRange({ period: "custom", from: "2026-10-08", to: "2026-10-20" }, NOW),
    { start: NOW, end: jst("2026-10-20T23:59:59.999"), beforeNow: true });
  assert.equal(f.customOmitsPast({ period: "custom", from: "2026-10-09", to: "2026-10-20" }, NOW), false);  // すべて未来
  assert.equal(f.customOmitsPast({ period: "custom", from: "x", to: "y" }, NOW), false);
  assert.equal(f.customOmitsPast({ period: "upcoming" }, NOW), false);
});

test("撮影対象: 4 種の全 16 通り（0 件を含む）で、選んだ分類のどれかに当たる計画だけ（これから）", () => {
  const all = f.CATEGORY_IDS;
  const pool = f.filterPlans(PLANS, { period: "upcoming", categories: all }, NOW);
  for (let mask = 0; mask < 16; mask += 1) {
    const selected = all.filter((_, i) => mask & (1 << i));
    const out = ids(f.filterPlans(PLANS, { period: "upcoming", categories: selected }, NOW)).sort();
    const expected = ids(pool.filter((p) => f.categoriesOf(p).some((c) => selected.includes(c)))).sort();
    assert.deepEqual(out, expected, "selected=" + selected.join(","));
    if (selected.length === 0) assert.deepEqual(out, [], "0 件選択はピン 0 件");
  }
});

test("UI に無い分類は「その他」、分類の無い応答は genre から（天の川は id が無いので「その他」）", () => {
  assert.deepEqual(f.categoriesOf(plan("x", ["fireworks"])), ["other"]);
  assert.deepEqual(f.categoriesOf(plan("x", ["diamond", "fireworks"])), ["diamond", "other"]);
  assert.deepEqual(f.categoriesOf({ genre: "pearl_fuji" }), ["pearl"]);
  assert.deepEqual(f.categoriesOf({ genre: "star_landscape", sky_object_label: "天の川" }), ["other"]);
  assert.deepEqual(f.categoriesOf(null), ["other"]);
});

test("撮影日時が読めない計画は、どの期間にも入れない", () => {
  const bad = [plan("bad", ["diamond"], "not-a-date")];
  for (const period of ["upcoming", "past", "weekend", "days7"]) {
    assert.deepEqual(f.filterPlans(bad, { period, categories: f.CATEGORY_IDS }, NOW), [], period);
  }
});

test("今週末（JST）: 月〜金は次の土曜 00:00 〜 日曜 23:59:59.999、土は今〜日曜の終わり、日は今〜今日の終わり", () => {
  assert.deepEqual(f.periodRange({ period: "weekend" }, NOW), { start: jst("2026-10-10T00:00:00"), end: jst("2026-10-11T23:59:59.999") });
  const fridayLast = jst("2026-10-09T23:59:59");
  assert.deepEqual(f.periodRange({ period: "weekend" }, fridayLast), { start: jst("2026-10-10T00:00:00"), end: jst("2026-10-11T23:59:59.999") });
  const sat = jst("2026-10-10T09:00:00");
  assert.deepEqual(f.periodRange({ period: "weekend" }, sat), { start: sat, end: jst("2026-10-11T23:59:59.999") });
  const satMidnight = jst("2026-10-10T00:00:00");                 // UTC では金曜 15:00 だが JST では土曜
  assert.deepEqual(f.periodRange({ period: "weekend" }, satMidnight), { start: satMidnight, end: jst("2026-10-11T23:59:59.999") });
  const sun = jst("2026-10-11T22:00:00");
  assert.deepEqual(f.periodRange({ period: "weekend" }, sun), { start: sun, end: jst("2026-10-11T23:59:59.999") });
  const mon = jst("2026-10-12T00:00:00");
  assert.deepEqual(f.periodRange({ period: "weekend" }, mon), { start: jst("2026-10-17T00:00:00"), end: jst("2026-10-18T23:59:59.999") });
  const st = { period: "weekend", categories: f.CATEGORY_IDS };
  assert.deepEqual(ids(f.filterPlans([
    plan("edge-start", ["diamond"], "2026-10-09T15:00:00Z"),       // = 土曜 00:00 JST
    plan("edge-end", ["diamond"], "2026-10-11T14:59:59Z"),         // = 日曜 23:59:59 JST
    plan("before", ["diamond"], "2026-10-09T14:59:59Z"),           // = 金曜 23:59:59 JST
    plan("after", ["diamond"], "2026-10-11T15:00:00Z")             // = 月曜 00:00 JST
  ], st, NOW)), ["edge-start", "edge-end"]);
  // 週末の当日、すでに過ぎた時刻の計画は出さない
  assert.deepEqual(ids(f.filterPlans([plan("sat-morning", ["pearl"], "2026-10-09T22:00:00Z")], st, sat)), []);
});

test("7日間 / 30日間: 今 〜（今日 + 7 / 30 日）23:59:59.999 JST。年末年始もまたぐ。過去は入らない", () => {
  assert.deepEqual(f.periodRange({ period: "days7" }, NOW), { start: NOW, end: jst("2026-10-15T23:59:59.999") });
  assert.deepEqual(f.periodRange({ period: "days30" }, NOW), { start: NOW, end: jst("2026-11-07T23:59:59.999") });
  const nye = jst("2026-12-31T20:00:00");
  assert.deepEqual(f.periodRange({ period: "days7" }, nye), { start: nye, end: jst("2027-01-07T23:59:59.999") });
  // m1 = 10/15 21:00 JST（最終日）、o1 = 10/09 23:59:59 JST。future（11/01）と過去は範囲外
  assert.deepEqual(ids(f.filterPlans(PLANS, { period: "days7", categories: f.CATEGORY_IDS }, NOW)), ["d1", "p1", "m1", "o1", "legacy-d", "now"]);
});

test("期間指定: 開始日 00:00 〜 終了日 23:59:59.999 JST（未来の部分）。不正な日付・逆順は 0 件", () => {
  assert.deepEqual(f.periodRange({ period: "custom", from: "2026-10-10", to: "2026-10-10" }, NOW),
    { start: jst("2026-10-10T00:00:00"), end: jst("2026-10-10T23:59:59.999"), beforeNow: false });
  assert.deepEqual(f.periodRange({ period: "custom", from: "2027-02-30", to: "2027-03-01" }, NOW), { invalid: true });
  assert.deepEqual(f.periodRange({ period: "custom", from: "2026-10-11", to: "2026-10-10" }, NOW), { invalid: true });
  assert.deepEqual(f.filterPlans(PLANS, { period: "custom", from: "x", to: "y", categories: f.CATEGORY_IDS }, NOW), []);
  const st = { period: "custom", from: "2025-01-01", to: "2026-10-10", categories: f.CATEGORY_IDS };
  assert.deepEqual(ids(f.filterPlans(PLANS, st, NOW)), ["d1", "o1", "legacy-d", "now"]);   // 過去（past-p / past-m）は入らない
});

test("期間 × 撮影対象の組み合わせ（例: 今週末 × ダイヤ / パール）", () => {
  const st = { period: "weekend", categories: ["diamond", "pearl"] };
  assert.deepEqual(ids(f.filterPlans(PLANS, st, NOW)), ["d1", "p1", "legacy-d"]);
});

test("要約の文", () => {
  assert.equal(f.summary(f.defaultState()), "これから・すべての撮影対象");
  assert.equal(f.summary({ period: "weekend", categories: ["diamond", "pearl"] }), "今週末・ダイヤモンド / パール");
  assert.equal(f.summary({ period: "past", categories: f.CATEGORY_IDS }), "過去・すべての撮影対象");
  assert.equal(f.summary({ period: "upcoming", categories: [] }), "これから・撮影対象なし");
  assert.equal(f.summary({ period: "custom", from: "2026-10-10", to: "2026-10-12", categories: ["milky_way"] }), "2026/10/10〜2026/10/12・天の川");
});

test("server の分類（api/_qr_map/discovery.js）と UI の撮影対象の語彙が一致する（「その他」以外）", () => {
  const discovery = require("../../../api/_qr_map/discovery.js");
  const server = discovery.DISCOVERY_CATEGORIES.map((c) => c.id).concat([discovery.OTHER]);
  assert.deepEqual(f.CATEGORY_IDS, server);
});
