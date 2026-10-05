/* プランナーQRマップ（G-3）: 地図の計算だけを持つ純関数。browser（window.PlannerMapCore）と Node test の両方から使う。
 *
 * - 表示 zoom から server の data tile 段（6 / 10 / 14、G-2 / HD-PLANNERQRMAP-008）を選ぶ
 * - 画面の範囲を覆う data tile だけを列挙する（全件取得をしない。1 画面あたりの上限つき）
 * - 同じ tile の取得をまとめる（実行中の要求の共有 ＋ 短時間の client cache）
 * - 近い計画を画面上でまとめる（表示上の grouping。plan の identity・保存・並び順の意味は変えない）
 * - 既存 Viewer への URL（/share#fragment）を作る
 */
(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PlannerMapCore = factory();
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var SERVER_LEVELS = [6, 10, 14];
  var MIN_FETCH_ZOOM = 6;          // これより引いた表示では計画を取りに行かない（日本全体より広い）
  var MAX_TILES_PER_VIEW = 30;     // 1 画面で要求する data tile の上限（超えたら取りに行かない）
  var MAX_LAT = 85.05112878;

  // 表示 zoom → server の data tile 段。data tile が画面の tile より細かくならないようにする
  // （細かいと 1 画面の要求数が急増する）。
  function serverLevelFor(zoom) {
    if (!(zoom >= MIN_FETCH_ZOOM)) return null;
    if (zoom < 12) return 6;
    if (zoom < 16) return 10;
    return 14;
  }

  // server（api/_qr_map/tiles.js）と同じ式
  function tileXY(lat, lon, z) {
    var clampedLat = Math.max(-MAX_LAT, Math.min(MAX_LAT, lat));
    var n = Math.pow(2, z);
    var rad = clampedLat * Math.PI / 180;
    var x = Math.floor((lon + 180) / 360 * n);
    var y = Math.floor((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2 * n);
    return { x: Math.min(n - 1, Math.max(0, x)), y: Math.min(n - 1, Math.max(0, y)) };
  }

  // bounds = { north, south, east, west }（度）。日付変更線をまたぐ表示は扱わない（日本向け MVP）
  function tilesForBounds(bounds, level) {
    var nw = tileXY(bounds.north, bounds.west, level);
    var se = tileXY(bounds.south, bounds.east, level);
    var count = (se.x - nw.x + 1) * (se.y - nw.y + 1);
    if (!(count > 0)) return { tiles: [], tooMany: false };
    if (count > MAX_TILES_PER_VIEW) return { tiles: [], tooMany: true };
    var tiles = [];
    for (var x = nw.x; x <= se.x; x += 1) {
      for (var y = nw.y; y <= se.y; y += 1) {
        tiles.push({ z: level, x: x, y: y, key: level + "/" + x + "/" + y });
      }
    }
    return { tiles: tiles, tooMany: false };
  }

  // 同じ data tile の要求をまとめる。失敗は cache しない（再試行できるように）
  function createTileLoader(options) {
    var fetchJson = options.fetchJson;
    var ttlMs = options.ttlMs || 60000;
    var now = options.now || function () { return Date.now(); };
    var cache = new Map();     // key -> { at, data }
    var inflight = new Map();  // key -> Promise
    return {
      load: function (tile) {
        var hit = cache.get(tile.key);
        if (hit && now() - hit.at < ttlMs) return Promise.resolve(hit.data);
        var pending = inflight.get(tile.key);
        if (pending) return pending;
        var p = fetchJson(tile).then(function (data) {
          inflight.delete(tile.key);
          cache.set(tile.key, { at: now(), data: data });
          return data;
        }, function (error) {
          inflight.delete(tile.key);
          throw error;
        });
        inflight.set(tile.key, p);
        return p;
      },
      clear: function () { cache.clear(); }
    };
  }

  // 表示上の grouping。points = [{ plan, x, y }]（画面 px）。半径 radiusPx 以内を 1 つにまとめる。
  // 並びは plan_id 順に固定（人気・新しさ等の意味を持たせない）。plan は 1 件も変更・統合しない。
  function groupPoints(points, radiusPx) {
    var sorted = points.slice().sort(function (a, b) {
      return a.plan.plan_id < b.plan.plan_id ? -1 : a.plan.plan_id > b.plan.plan_id ? 1 : 0;
    });
    var groups = [];
    var r2 = radiusPx * radiusPx;
    sorted.forEach(function (p) {
      var target = null;
      for (var i = 0; i < groups.length; i += 1) {
        var dx = groups[i].ax - p.x;
        var dy = groups[i].ay - p.y;
        if (dx * dx + dy * dy <= r2) { target = groups[i]; break; }
      }
      if (!target) {
        target = { ax: p.x, ay: p.y, plans: [], lat: 0, lon: 0 };
        groups.push(target);
      }
      target.plans.push(p.plan);
    });
    groups.forEach(function (g) {
      var lat = 0;
      var lon = 0;
      g.plans.forEach(function (plan) { lat += plan.lat; lon += plan.lon; });
      g.lat = lat / g.plans.length;
      g.lon = lon / g.plans.length;
    });
    return groups;
  }

  // 同じ plan_id を 1 件にする（隣り合う tile の重複に備える。値は書き換えない）
  function uniquePlans(lists) {
    var seen = new Map();
    lists.forEach(function (list) {
      list.forEach(function (plan) { if (!seen.has(plan.plan_id)) seen.set(plan.plan_id, plan); });
    });
    return Array.from(seen.values());
  }

  var FRAGMENT_RE = /^[A-Za-z0-9_-]+$/;
  // 既存 Viewer（/share）へそのまま渡す。Viewer の仕様は変えない
  function viewerUrl(fragment) {
    if (typeof fragment !== "string" || !FRAGMENT_RE.test(fragment)) return null;
    return "/share#" + fragment;
  }

  // "YYYY-MM-DDTHH:MM:SSZ" → 日本時間の表示
  function formatJst(utc) {
    var d = new Date(utc);
    if (isNaN(d.getTime())) return "";
    var parts = new Intl.DateTimeFormat("ja-JP", {
      timeZone: "Asia/Tokyo", year: "numeric", month: "numeric", day: "numeric",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23"
    }).formatToParts(d);
    var v = {};
    parts.forEach(function (p) { v[p.type] = p.value; });
    return v.year + "年" + v.month + "月" + v.day + "日 " + v.hour + ":" + v.minute + "（日本時間）";
  }

  // 一覧・カード用の短い日時（例 "2027/04/07 17:43"）。日本時間
  function formatJstCompact(utc) {
    var d = new Date(utc);
    if (isNaN(d.getTime())) return "";
    var parts = new Intl.DateTimeFormat("ja-JP", {
      timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23"
    }).formatToParts(d);
    var v = {};
    parts.forEach(function (p) { v[p.type] = p.value; });
    return v.year + "/" + v.month + "/" + v.day + " " + v.hour + ":" + v.minute;
  }

  // ジャンル → pin の記号（表示だけ）。意味は Planner の正本 SUN_MOON_OBJECT_GLYPHS（☀ = 太陽、☾ = 月、
  // planner.js）に合わせる。星景・星の軌跡は Planner に正本の記号が無いので形で表し、名前は必ず文字でも出す。
  // 未知の genre は汎用の点（新しい genre が増えても壊れない）。
  var GENRE_SYMBOLS = {
    diamond_fuji: "sun",
    pearl_fuji: "moon",
    solar_lunar: "sunmoon",
    star_landscape: "star",
    star_trails: "trails"
  };
  function genreSymbol(genre) {
    return Object.prototype.hasOwnProperty.call(GENRE_SYMBOLS, genre) ? GENRE_SYMBOLS[genre] : "generic";
  }

  // 1 件の計画の短い説明（marker の名前・tooltip 用）。例 "ダイヤモンド富士（富士山）"
  function planCaption(p) {
    var subject = p.sky_object_label || p.target_label || "";
    return (p.genre_label || "撮影計画") + (subject ? "（" + subject + "）" : "");
  }

  return {
    GENRE_SYMBOLS: GENRE_SYMBOLS,
    genreSymbol: genreSymbol,
    planCaption: planCaption,
    formatJstCompact: formatJstCompact,
    SERVER_LEVELS: SERVER_LEVELS,
    MIN_FETCH_ZOOM: MIN_FETCH_ZOOM,
    MAX_TILES_PER_VIEW: MAX_TILES_PER_VIEW,
    serverLevelFor: serverLevelFor,
    tileXY: tileXY,
    tilesForBounds: tilesForBounds,
    createTileLoader: createTileLoader,
    groupPoints: groupPoints,
    uniquePlans: uniquePlans,
    viewerUrl: viewerUrl,
    formatJst: formatJst
  };
}));
