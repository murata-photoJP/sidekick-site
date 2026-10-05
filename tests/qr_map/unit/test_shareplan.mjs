// server の SharePlan 受信判定が、Python canonical ／ 共有ページ（share.html）と同じであることを
// Planner 正本の cross-language vectors（105 case、tests/fixtures/qr_map/README.md）で固定する。
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import zlib from "node:zlib";

const require = createRequire(import.meta.url);
const { parsePublishableFragment, SharePlanError } = require("../../../api/_qr_map/shareplan.js");
const { CONSTANTS } = require("../../../api/_qr_map/config.js");

const VECTORS = JSON.parse(readFileSync(new URL("../../fixtures/qr_map/cross_language_vectors.json", import.meta.url), "utf8"));
const byId = Object.fromEntries(VECTORS.cases.map((c) => [c.id, c]));

async function verdict(fragment) {
  try {
    return { accepted: true, value: await parsePublishableFragment(fragment) };
  } catch (error) {
    assert.ok(error instanceof SharePlanError, "SharePlanError 以外: " + error);
    return { accepted: false, code: error.code };
  }
}

test("cross-language vectors 全 105 case で、受理 / 拒否と code が正本と一致する", async () => {
  assert.equal(VECTORS.cases.length, 105);
  for (const c of VECTORS.cases) {
    const v = await verdict(c.payload);
    assert.equal(v.accepted, c.accepted, c.id + " の受理判定");
    if (!c.accepted) assert.equal(v.code, c.code, c.id + " の code");
  }
});

test("v1 golden（VALID_GV-1）: 表示値は fragment から server が導く（座標・日時・被写体）", async () => {
  const c = byId["VALID_GV-1"];
  const { value } = await verdict(c.payload);
  assert.equal(value.display.lat, c.plan.observer_latitude_deg);
  assert.equal(value.display.lon, c.plan.observer_longitude_deg);
  assert.equal(value.display.t_d, c.plan.utc_datetime);
  assert.equal(value.display.genre, "diamond_fuji");
  assert.equal(value.snapshot.fragment, c.payload);
  assert.equal(value.snapshot.share_version, 1);
  assert.match(value.snapshot.payload_sha256, /^[0-9a-f]{64}$/);
});

test("v2 golden（星景・太陽月・星の軌跡）: 観測点は wire の o.x / o.y、星の軌跡は被写体なし", async () => {
  for (const id of ["VALID_V2-SL-1", "VALID_V2-SLST-1", "VALID_V2-ST-1"]) {
    const c = byId[id];
    const { value } = await verdict(c.payload);
    assert.equal(value.snapshot.share_version, 2, id);
    assert.equal(value.display.lat, c.plan_v2.o.x, id);
    assert.equal(value.display.lon, c.plan_v2.o.y, id);
    assert.equal(value.display.t_d, c.plan_v2.t.d, id);
    if (c.plan_v2.g === "star_trails") assert.equal(value.display.target_label, null, id);
    else assert.equal(typeof value.display.target_label, "string", id);
  }
});

test("zlib stream の後ろの余計な byte は拒否する", async () => {
  const raw = Buffer.from(byId["VALID_GV-1"].payload, "base64url");
  const tampered = Buffer.concat([raw, Buffer.from([0x00, 0x01])]).toString("base64url");
  const v = await verdict(tampered);
  assert.equal(v.accepted, false);
});

test("大きすぎる fragment は decode 前に拒否する", async () => {
  const v = await verdict("A".repeat(CONSTANTS.MAX_FRAGMENT_CHARS + 1));
  assert.deepEqual(v, { accepted: false, code: "PAYLOAD_TOO_LARGE" });
});

test("未知の field（例: plan_id を足した SharePlan）は拒否する（closed schema）", async () => {
  const raw = Buffer.from(byId["VALID_GV-1"].payload, "base64url");
  const wire = JSON.parse(zlib.inflateSync(raw).toString("utf8"));
  wire.plan_id = "0123456789abcdef0123456789abcdef";
  const fragment = zlib.deflateSync(Buffer.from(JSON.stringify(wire), "utf8")).toString("base64url");
  assert.deepEqual(await verdict(fragment), { accepted: false, code: "INVALID_SCHEMA" });
});

test("空・文字列以外は EMPTY_FRAGMENT", async () => {
  assert.deepEqual(await verdict(""), { accepted: false, code: "EMPTY_FRAGMENT" });
  assert.deepEqual(await verdict(null), { accepted: false, code: "EMPTY_FRAGMENT" });
});
