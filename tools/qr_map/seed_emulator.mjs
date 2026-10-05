// プランナーQRマップ（G-3）の Human Review 用 seed。Firestore Emulator 専用。
//
// 実経路を通す: 実 SharePlan（Planner 正本 cross_language_vectors の受理 case）を **G-2 publish API（HTTP）** で
// Emulator に入れ、Map は tile API で読む。marker を JS に直書きしない。
//
// 例外（API の現在時刻では作れない状態だけ G-2 の store を直接使う）:
//   - expired: store.publish({ nowMs: 200 日前 })   … G-2 と同じ publish の code path
//   - removed: store.removeByOperator()            … 運営の掲載停止（HTTP に出していない操作）
//
// 離れた地点の計画: 正本 vectors は富士周辺と鎌倉付近だけなので、被写体を持たない「星の軌跡」（VALID_V2-ST-1）の
// 観測点 o.x / o.y だけを書き換え、Planner と同じ形（compact JSON → zlib → base64url）で作り直す（derived と明記）。
// どれも G-2 の厳格な受信判定（share.html の受信口）を通ったものだけが入る。
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import zlib from "node:zlib";
import { ROOT, assertEmulatorOnly } from "./dev_server.mjs";

const require = createRequire(import.meta.url);
const DAY_MS = 24 * 60 * 60 * 1000;

const VECTORS = JSON.parse(readFileSync(join(ROOT, "tests", "fixtures", "qr_map", "cross_language_vectors.json"), "utf8"));
const byId = Object.fromEntries(VECTORS.cases.map((c) => [c.id, c]));

function derivedTrails(lat, lon) {
  const raw = Buffer.from(byId["VALID_V2-ST-1"].payload, "base64url");
  const wire = JSON.parse(zlib.inflateSync(raw).toString("utf8"));
  wire.o.x = lat;
  wire.o.y = lon;
  return zlib.deflateSync(Buffer.from(JSON.stringify(wire), "utf8"), { level: 9 }).toString("base64url");
}

// [key, fragment, category, note]
export function seedPlan() {
  return [
    ["diamond-a", byId["VALID_GV-1"].payload, "visible", "ダイヤモンド富士（GV-1）"],
    ["diamond-b", byId["VALID_GV-1"].payload, "visible", "同じ計画を別の人が公開（GV-1 をもう 1 回）"],
    ["diamond-c", byId["VALID_GV-2"].payload, "visible", "ダイヤモンド富士（GV-2、同じ地点）"],
    ["pearl", byId["VALID_GV-3"].payload, "visible", "パール富士（GV-3）"],
    ["sunmoon", byId["VALID_V2-SL-1"].payload, "visible", "太陽・月（V2-SL-1）"],
    ["milkyway", byId["VALID_V2-SLMW-1"].payload, "visible", "星景・天の川（V2-SLMW-1、同じ地点）"],
    ["starscape", byId["VALID_V2-SLST-1"].payload, "visible", "星景（V2-SLST-1、同じ地点）"],
    ["trails-kamakura", byId["VALID_V2-ST-1"].payload, "visible", "星の軌跡（V2-ST-1）"],
    ["trails-near-40m", derivedTrails(35.4183, 138.8705), "visible", "derived: 星の軌跡、太陽・月の地点から約 40 m"],
    ["trails-near-280m", derivedTrails(35.42, 138.872), "visible", "derived: 星の軌跡、約 280 m"],
    ["trails-sapporo", derivedTrails(43.0621, 141.3544), "visible", "derived: 星の軌跡（札幌）"],
    ["trails-kyoto", derivedTrails(35.0116, 135.7681), "visible", "derived: 星の軌跡（京都）"],
    ["trails-utsukushigahara", derivedTrails(36.2234, 138.1069), "visible", "derived: 星の軌跡（美ヶ原）"],
    ["expired-tokyo", derivedTrails(35.6586, 139.7454), "expired", "derived: 200 日前に公開され、その後開かれていない"],
    ["unpublished-nagoya", derivedTrails(35.1709, 136.8815), "unpublished", "derived: 公開後に取り消し"],
    ["removed-sendai", derivedTrails(38.2682, 140.8694), "removed", "derived: 運営が掲載停止"]
  ];
}

async function clearEmulator() {
  const host = process.env.FIRESTORE_EMULATOR_HOST;
  const project = process.env.QR_MAP_FIREBASE_PROJECT_ID;
  const res = await fetch("http://" + host + "/emulator/v1/projects/" + project + "/databases/(default)/documents", { method: "DELETE" });
  if (res.status !== 200) throw new Error("Emulator の初期化に失敗: " + res.status);
}

async function postJson(baseUrl, op, body) {
  const res = await fetch(baseUrl + "/api/qr-map?op=" + op, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
  });
  const json = await res.json();
  if (!res.ok) throw new Error(op + " " + res.status + " " + JSON.stringify(json));
  return json;
}

export async function seedEmulator({ baseUrl, manifestPath = process.env.PLANNER_MAP_SEED_MANIFEST } = {}) {
  assertEmulatorOnly();
  await clearEmulator();
  const { getQrMapFirestore } = require(join(ROOT, "api", "_qr_map", "firestore.js"));
  const { createStore } = require(join(ROOT, "api", "_qr_map", "store.js"));
  const store = createStore(getQrMapFirestore());
  const plans = [];
  for (const [key, fragment, category, note] of seedPlan()) {
    const idem = "seed-" + key + "-" + randomBytes(12).toString("hex");
    let r;
    if (category === "expired") {
      r = await store.publish({ fragment, idempotencyKey: idem, consentVersion: "qr-map-consent/1", nowMs: Date.now() - 200 * DAY_MS });
    } else {
      r = await postJson(baseUrl, "publish", { fragment, idempotency_key: idem, consent_version: "qr-map-consent/1" });
    }
    if (category === "unpublished") await postJson(baseUrl, "unpublish", { plan_id: r.plan_id, manage_token: r.manage_token });
    if (category === "removed") await store.removeByOperator({ planId: r.plan_id });
    const wire = JSON.parse(zlib.inflateSync(Buffer.from(fragment, "base64url")).toString("utf8"));
    const lat = wire.v === 1 ? wire.ox : wire.o.x;
    const lon = wire.v === 1 ? wire.oy : wire.o.y;
    plans.push({ key, plan_id: r.plan_id, category, note, fragment, lat, lon, genre: wire.g });
  }
  const summary = {};
  plans.forEach((p) => { summary[p.category] = (summary[p.category] || 0) + 1; });
  const manifest = { generated_at: new Date().toISOString(), summary, plans };
  if (manifestPath) writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), "utf8");
  return manifest;
}
