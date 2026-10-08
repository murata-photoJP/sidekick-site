/* プランナーQRマップ G-6「Map Discovery Filter」: 期間 × 撮影対象の絞り込み（純関数）。browser（window.PlannerMapFilter）と
 * Node test の両方から使う。
 *
 * - 地域は今までどおり「表示している範囲」= 取得した tile（G-3 の自動更新のまま、HD-1）。ここは取得済みの計画を絞るだけで、
 *   server へ全件を求めない。
 * - 撮影対象は PublicPlan の `categories`（Map discovery の分類層。Planner の genre そのものではない）で絞る。複数選択・0 件可（HD-2）。
 *   UI の選択肢にない分類（将来 server が増やしたもの）は「その他」として扱う。
 * - 期間は撮影日時 `t_d`（UTC、保存値のまま）で絞る。境目は Asia/Tokyo（MVP は固定、HD-5）。
 * - **未来と過去を分ける（HD-4 訂正）。** PublicPlan は「この場所でこの対象が撮れる」恒久的な地点情報ではなく、特定の日時に
 *   対する撮影計画の snapshot。Discovery の単位は 撮影地点 × 撮影日時 × 分類 で、どの分類（ダイヤ / パール / 天の川 / その他）も
 *   日時で成り立つものとして同じに扱う。通常の Discovery（今後すべて・今週末・7日間・30日間・期間指定）は t_d >= 今 だけ。
 *   過去の計画は「過去を見る」で明示的に選んだときだけ出し、「現在も同じ条件で撮影できることを示すものではない」と知らせる。
 *   QR / SharePlan / Viewer / snapshot は変えない（古い QR は「その日時の撮影計画の記録」として有効）。
 */
(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PlannerMapFilter = factory();
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var TIME_ZONE = "Asia/Tokyo";
  var DAY_MS = 86400000;
  var OTHER = "other";

  // UI の撮影対象（表示順）。id は server の discovery 分類（api/_qr_map/discovery.js）と同じ語彙。「その他」は最後
  var CATEGORIES = [
    { id: "diamond", label: "ダイヤモンド" },
    { id: "pearl", label: "パール" },
    { id: "milky_way", label: "天の川" },
    { id: OTHER, label: "その他" }
  ];
  var CATEGORY_IDS = CATEGORIES.map(function (c) { return c.id; });

  // 未来の検索（初期 = 今後すべて）と、明示的に選ぶ「過去を見る」を分ける。
  // 「今後すべて」= t_d >= 今・終わり無し（Human Review で「これから」から表記だけ変更。id は upcoming のまま）
  var PERIODS = [
    { id: "upcoming", label: "今後すべて" },
    { id: "weekend", label: "今週末" },
    { id: "days7", label: "7日間" },
    { id: "days30", label: "30日間" },
    { id: "custom", label: "期間指定" },
    { id: "past", label: "過去を見る" }
  ];
  var DEFAULT_PERIOD = "upcoming";

  var PAST_NOTICE = "過去の撮影計画を表示しています。現在も同じ条件で撮影できることを示すものではありません。";

  // 分類の無い応答（G-6 前の API）への保険: genre から分かる分だけ導く（天の川は id が無いと分からないので「その他」）
  var GENRE_FALLBACK = { diamond_fuji: "diamond", pearl_fuji: "pearl" };

  function defaultState() {
    return { period: DEFAULT_PERIOD, from: "", to: "", categories: CATEGORY_IDS.slice() };
  }

  // UI の撮影対象の集合に写した、その計画の分類（必ず 1 つ以上）
  function categoriesOf(plan) {
    var raw = plan && Array.isArray(plan.categories) && plan.categories.length
      ? plan.categories
      : [GENRE_FALLBACK[plan && plan.genre] || OTHER];
    var out = [];
    raw.forEach(function (c) {
      var id = CATEGORY_IDS.indexOf(c) >= 0 ? c : OTHER;
      if (out.indexOf(id) < 0) out.push(id);
    });
    return out;
  }

  // ---- 期間（Asia/Tokyo の日付で境目を決め、UTC の ms で比べる） ----------------------------------
  function zonedParts(ms, timeZone) {
    var parts = new Intl.DateTimeFormat("en-US", {
      timeZone: timeZone, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", weekday: "short"
    }).formatToParts(new Date(ms));
    var v = {};
    parts.forEach(function (p) { v[p.type] = p.value; });
    var weekdays = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
    return { y: Number(v.year), m: Number(v.month), d: Number(v.day), h: Number(v.hour), min: Number(v.minute),
      s: Number(v.second), weekday: weekdays[v.weekday] };
  }

  // その timezone の y-m-d 00:00:00.000 の UTC ms（固定 offset でも夏時間でも、offset を 2 回確かめる）
  function zonedMidnightMs(y, m, d, timeZone) {
    var guess = Date.UTC(y, m - 1, d);
    for (var i = 0; i < 2; i += 1) {
      var p = zonedParts(guess, timeZone);
      var asUtc = Date.UTC(p.y, p.m - 1, p.d, p.h, p.min, p.s);
      guess += Date.UTC(y, m - 1, d) - asUtc;
    }
    return guess;
  }

  function addDays(y, m, d, n) {
    var t = new Date(Date.UTC(y, m - 1, d) + n * DAY_MS);
    return { y: t.getUTCFullYear(), m: t.getUTCMonth() + 1, d: t.getUTCDate() };
  }

  function endOfDayMs(day, timeZone) {
    var next = addDays(day.y, day.m, day.d, 1);
    return zonedMidnightMs(next.y, next.m, next.d, timeZone) - 1;   // その日の 23:59:59.999
  }

  var DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
  function parseDate(text) {
    var m = DATE_RE.exec(String(text || ""));
    if (!m) return null;
    var y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]);
    var t = new Date(Date.UTC(y, mo - 1, d));
    if (t.getUTCFullYear() !== y || t.getUTCMonth() !== mo - 1 || t.getUTCDate() !== d) return null;
    return { y: y, m: mo, d: d };
  }

  // 期間 → { start, end }（UTC ms、両端を含む。null の端は無制限）。不正なら { invalid: true }。
  //   今後すべて: 今 〜（終わり無し）。過去を見る: （始まり無し）〜 今の直前。
  //   今週末: 月〜金 = 次の土曜 00:00 〜 日曜 23:59:59.999。土 = 今 〜 日曜 23:59:59.999。日 = 今 〜 今日 23:59:59.999。
  //   7日間 / 30日間: 今 〜（今日 + 7 / 30 日）23:59:59.999。
  //   期間指定: 開始日 00:00 〜 終了日 23:59:59.999。ただし実際の開始は max(開始日 00:00, 今) で、今より前は含めない
  //   （beforeNow = 切り捨てた部分がある。allPast = 期間がすべて過ぎていて 0 件。自動で「過去を見る」には切り替えない）。
  //   期間指定で過去の計画を通常の Discovery へ戻す抜け道は作らない。分類ごとの特例も無い（どの分類も同じ t_d で比べる）。
  function periodRange(state, nowMs, timeZone) {
    var tz = timeZone || TIME_ZONE;
    var period = (state && state.period) || DEFAULT_PERIOD;
    if (period === "upcoming") return { start: nowMs, end: null };
    if (period === "past") return { start: null, end: nowMs - 1 };
    var today = zonedParts(nowMs, tz);
    var day = { y: today.y, m: today.m, d: today.d };
    if (period === "weekend") {
      if (today.weekday === 6) return { start: nowMs, end: endOfDayMs(addDays(day.y, day.m, day.d, 1), tz) };
      if (today.weekday === 0) return { start: nowMs, end: endOfDayMs(day, tz) };
      var sat = addDays(day.y, day.m, day.d, 6 - today.weekday);
      return { start: zonedMidnightMs(sat.y, sat.m, sat.d, tz), end: endOfDayMs(addDays(sat.y, sat.m, sat.d, 1), tz) };
    }
    if (period === "days7" || period === "days30") {
      return { start: nowMs, end: endOfDayMs(addDays(day.y, day.m, day.d, period === "days7" ? 7 : 30), tz) };
    }
    if (period === "custom") {
      var from = parseDate(state.from);
      var to = parseDate(state.to);
      if (!from || !to) return { invalid: true };
      var start = zonedMidnightMs(from.y, from.m, from.d, tz);
      var end = endOfDayMs(to, tz);
      if (start > end) return { invalid: true };
      // 期間指定も通常の Discovery（t_d >= 今）。今より前の部分は含めない（過去は「過去を見る」だけ）
      if (end < nowMs) return { start: nowMs, end: nowMs - 1, beforeNow: true, allPast: true };   // 空の範囲
      return { start: Math.max(start, nowMs), end: end, beforeNow: start < nowMs };
    }
    return { invalid: true };
  }

  function inRange(plan, range) {
    if (range.invalid) return false;
    var t = Date.parse(plan && plan.t_d);
    if (isNaN(t)) return false;
    return (range.start === null || t >= range.start) && (range.end === null || t <= range.end);
  }

  // 過去の撮影計画を表示している状態か。過去は「過去を見る」だけで出す（通常の Discovery はすべて t_d >= 今）。
  function pastNotice(state) {
    return !!state && state.period === "past";
  }

  // 期間指定に今より前の日付が含まれていて、その部分を表示していないか（「過去を見る」へ案内するため）
  function customOmitsPast(state, nowMs, timeZone) {
    if (!state || state.period !== "custom") return false;
    var range = periodRange(state, nowMs, timeZone);
    return !range.invalid && !!range.beforeNow;
  }

  // 期間指定が今より前を含むときの状態: "none"（すべて今以降）/ "partial"（今より前の部分を除いた）/ "all"（すべて過ぎている = 0 件）
  function customPastState(state, nowMs, timeZone) {
    if (!state || state.period !== "custom") return "none";
    var range = periodRange(state, nowMs, timeZone);
    if (range.invalid || !range.beforeNow) return "none";
    return range.allPast ? "all" : "partial";
  }

  var CUSTOM_PAST_HINT = "過去の撮影計画は含まれません。過去の計画は「過去を見る」から確認できます。";
  var CUSTOM_ALL_PAST_HINT = "指定した期間はすでに過ぎています。過去の撮影計画は「過去を見る」から確認できます。";

  function isDefault(state) {
    return !!state && (state.period || DEFAULT_PERIOD) === DEFAULT_PERIOD && Array.isArray(state.categories)
      && CATEGORY_IDS.every(function (id) { return state.categories.indexOf(id) >= 0; });
  }

  // 計画の配列を絞る（入力の並びを保つ）
  function filterPlans(plans, state, nowMs, timeZone) {
    var selected = (state && Array.isArray(state.categories)) ? state.categories : CATEGORY_IDS;
    var range = periodRange(state, nowMs, timeZone);
    return plans.filter(function (p) {
      var cats = categoriesOf(p);
      var hit = cats.some(function (c) { return selected.indexOf(c) >= 0; });
      return hit && inRange(p, range);
    });
  }

  // 絞り込みの短い要約（ボタン・件数の横に出す）
  function summary(state) {
    var id = (state && state.period) || DEFAULT_PERIOD;
    var period = PERIODS.filter(function (p) { return p.id === id; })[0];
    var periodText = period ? period.label : PERIODS[0].label;
    if (id === "custom" && state.from && state.to) periodText = state.from.replace(/-/g, "/") + "〜" + state.to.replace(/-/g, "/");
    if (id === "past") periodText = "過去";
    var cats = CATEGORIES.filter(function (c) { return state.categories.indexOf(c.id) >= 0; }).map(function (c) { return c.label; });
    var catText = cats.length === CATEGORIES.length ? "すべての撮影対象" : (cats.length ? cats.join(" / ") : "撮影対象なし");
    return periodText + "・" + catText;
  }

  return {
    TIME_ZONE: TIME_ZONE,
    OTHER: OTHER,
    CATEGORIES: CATEGORIES,
    CATEGORY_IDS: CATEGORY_IDS,
    PERIODS: PERIODS,
    DEFAULT_PERIOD: DEFAULT_PERIOD,
    PAST_NOTICE: PAST_NOTICE,
    defaultState: defaultState,
    categoriesOf: categoriesOf,
    periodRange: periodRange,
    filterPlans: filterPlans,
    pastNotice: pastNotice,
    customOmitsPast: customOmitsPast,
    customPastState: customPastState,
    CUSTOM_PAST_HINT: CUSTOM_PAST_HINT,
    CUSTOM_ALL_PAST_HINT: CUSTOM_ALL_PAST_HINT,
    isDefault: isDefault,
    summary: summary,
    zonedMidnightMs: zonedMidnightMs
  };
}));
