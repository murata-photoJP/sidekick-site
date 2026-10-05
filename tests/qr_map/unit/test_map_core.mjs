// プランナーQRマップ（G-3）の地図計算（純関数）と self-host した Leaflet の同一性。
import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

const require = createRequire(import.meta.url);
const core = require("../../../assets/planner-map/map-core.js");
const tiles = require("../../../api/_qr_map/tiles.js");

test("表示 zoom → server の data tile 段（6 / 10 / 14 だけ）。引きすぎた表示では取りに行かない", () => {
  assert.equal(core.serverLevelFor(5), null);
  assert.equal(core.serverLevelFor(6), 6);
  assert.equal(core.serverLevelFor(11), 6);
  assert.equal(core.serverLevelFor(12), 10);
  assert.equal(core.serverLevelFor(15), 10);
  assert.equal(core.serverLevelFor(16), 14);
  assert.equal(core.serverLevelFor(18), 14);
  for (let z = 5; z <= 18; z += 1) {
    const level = core.serverLevelFor(z);
    if (level !== null) assert.ok(core.SERVER_LEVELS.includes(level));
  }
});

test("client と server の tile の計算は同じ式（同じ key になる）", () => {
  for (const [lat, lon] of [[35.418, 138.87], [43.0621, 141.3544], [24.34, 124.16], [-33.86, 151.2]]) {
    const keys = tiles.tileKeysFor(lat, lon);
    for (const z of core.SERVER_LEVELS) {
      const { x, y } = core.tileXY(lat, lon, z);
      assert.equal(keys["z" + z], z + "/" + x + "/" + y);
    }
  }
});

test("画面を覆う tile だけを列挙し、上限を超えたら取りに行かない（全件取得しない）", () => {
  const view = { north: 35.6, south: 35.2, east: 139.1, west: 138.6 };
  const r = core.tilesForBounds(view, 10);
  assert.equal(r.tooMany, false);
  assert.ok(r.tiles.length >= 1 && r.tiles.length <= core.MAX_TILES_PER_VIEW);
  assert.ok(r.tiles.every((t) => t.z === 10 && t.key === "10/" + t.x + "/" + t.y));
  const world = core.tilesForBounds({ north: 80, south: -80, east: 179, west: -179 }, 6);
  assert.deepEqual(world, { tiles: [], tooMany: true });
});

test("同じ tile は 1 回だけ取りに行く（実行中の共有・短時間 cache）。失敗は cache しない", async () => {
  let calls = 0;
  let fail = true;
  let t = 0;
  const loader = core.createTileLoader({
    ttlMs: 1000,
    now: () => t,
    fetchJson: async () => { calls += 1; if (fail) throw new Error("x"); return { plans: [] }; }
  });
  const tile = { key: "10/1/2" };
  await assert.rejects(loader.load(tile));
  fail = false;
  await Promise.all([loader.load(tile), loader.load(tile)]);
  assert.equal(calls, 2);              // 失敗 1 回 ＋ 同時 2 要求で 1 回
  await loader.load(tile);
  assert.equal(calls, 2);              // cache 内
  t = 1001;
  await loader.load(tile);
  assert.equal(calls, 3);              // 期限切れで取り直す
});

test("grouping は表示上のまとめ。plan は 1 件も変えず・失わず、並びは plan_id 順", () => {
  const plans = [
    { plan_id: "c", lat: 1, lon: 1 }, { plan_id: "a", lat: 1, lon: 1 }, { plan_id: "b", lat: 2, lon: 2 }
  ];
  const frozen = JSON.stringify(plans);
  const groups = core.groupPoints([
    { plan: plans[0], x: 100, y: 100 }, { plan: plans[1], x: 110, y: 100 }, { plan: plans[2], x: 300, y: 300 }
  ], 36);
  assert.equal(groups.length, 2);
  assert.deepEqual(groups[0].plans.map((p) => p.plan_id), ["a", "c"]);
  assert.deepEqual(groups[1].plans.map((p) => p.plan_id), ["b"]);
  assert.equal(JSON.stringify(plans), frozen);
  assert.equal(core.uniquePlans([[plans[0], plans[1]], [plans[1], plans[2]]]).length, 3);
});

test("「計画を見る」は既存 Viewer の /share#fragment。fragment 以外の文字は拒否", () => {
  assert.equal(core.viewerUrl("eNpNUV1v_-"), "/share#eNpNUV1v_-");
  assert.equal(core.viewerUrl("abc\"><script>"), null);
  assert.equal(core.viewerUrl(""), null);
  assert.equal(core.viewerUrl(undefined), null);
});

test("日時は日本時間で表示する", () => {
  assert.equal(core.formatJst("2027-04-07T08:43:58Z"), "2027年4月7日 17:43（日本時間）");
});

test("self-host の Leaflet は Planner の vendored copy と byte 一致（assets/vendor/leaflet-1.9.4/README.md）", () => {
  const expected = {
    "leaflet.js": "db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a",
    "leaflet.css": "a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6",
    "LICENSE": "53e8dc25862014e4324741ca18fbe3611e11d42ef69f59f86ea8c5389647d4cb",
    "images/layers-2x.png": "066daca850d8ffbef007af00b06eac0015728dee279c51f3cb6c716df7c42edf",
    "images/layers.png": "1dbbe9d028e292f36fcba8f8b3a28d5e8932754fc2215b9ac69e4cdecf5107c6",
    "images/marker-icon-2x.png": "00179c4c1ee830d3a108412ae0d294f55776cfeb085c60129a39aa6fc4ae2528",
    "images/marker-icon.png": "574c3a5cca85f4114085b6841596d62f00d7c892c7b03f28cbfa301deb1dc437",
    "images/marker-shadow.png": "264f5c640339f042dd729062cfc04c17f8ea0f29882b538e3848ed8f10edb4da"
  };
  for (const [name, sha] of Object.entries(expected)) {
    // 改行は変換しない（.gitattributes の assets/vendor/** -text）。raw bytes で照合する
    const bytes = readFileSync(new URL("../../../assets/vendor/leaflet-1.9.4/" + name, import.meta.url));
    assert.equal(createHash("sha256").update(bytes).digest("hex"), sha, name);
  }
});

test("G-3.1: ジャンル → pin の記号（Planner 正本 ☀ / ☾ に合わせる。未知の genre は汎用）", () => {
  assert.equal(core.genreSymbol("diamond_fuji"), "sun");
  assert.equal(core.genreSymbol("pearl_fuji"), "moon");
  assert.equal(core.genreSymbol("solar_lunar"), "sunmoon");
  assert.equal(core.genreSymbol("star_landscape"), "star");
  assert.equal(core.genreSymbol("star_trails"), "trails");
  assert.equal(core.genreSymbol("future_genre"), "generic");
  assert.equal(core.genreSymbol("__proto__"), "generic");
});

test("G-3.1: card の短い日時と、marker の名前（ジャンル ＋ 被写体 / 天体）", () => {
  assert.equal(core.formatJstCompact("2027-04-07T08:43:58Z"), "2027/04/07 17:43");
  assert.equal(core.planCaption({ genre_label: "ダイヤモンド富士", target_label: "富士山" }), "ダイヤモンド富士（富士山）");
  assert.equal(core.planCaption({ genre_label: "星景", target_label: "富士山", sky_object_label: "オリオン座" }), "星景（オリオン座）");
  assert.equal(core.planCaption({ genre_label: "星景（星の軌跡）", target_label: null }), "星景（星の軌跡）");
});
