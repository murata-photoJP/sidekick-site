// プランナーQRマップ: 物理削除の Cron endpoint（G-5.1、HD-PLANNERQRMAP-044）。
//
//   GET /api/qr-map-cleanup   Vercel Cron が 1 日 1 回呼ぶ（vercel.json crons）。Authorization: Bearer <CRON_SECRET>
//
// Firestore TTL は使わない（billing = Blaze が必要。Spark で MVP を始めるため、HD-PLANNERQRMAP-033 / G-5.0 §3.2）。
// 削除の判定・上限・前提条件は store.cleanupEligible（api/_qr_map/store.js）。
//
// fail-closed（1 つでも欠ければ何もしない）:
//   - GET 以外は 405
//   - CRON_SECRET 未設定 / QR_MAP_CLEANUP_ENABLED !== "true" は 503 CLEANUP_DISABLED（何も読まない・消さない）
//   - Authorization が一致しなければ 401
//   - Firestore の接続条件（firestore.js resolveConnection）を満たさなければ 503 QR_MAP_UNAVAILABLE
// 応答は件数だけ（plan_id・座標・fragment は返さない）。publish の circuit breaker（QR_MAP_PUBLISH_ENABLED）とは独立。
// cron を別 function にした理由: Vercel Cron の path に query を使わない・POST 用 WAF rate limit の対象から外す。
"use strict";

const crypto = require("crypto");
const { readEnv } = require("./_qr_map/config");
const { getQrMapFirestore, QrMapConfigError } = require("./_qr_map/firestore");
const { createStore } = require("./_qr_map/store");

function send(res, status, body) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Robots-Tag", "noindex, nofollow");
  res.setHeader("X-Content-Type-Options", "nosniff");
  return res.status(status).json(body);
}

// Vercel Cron の Authorization header を CRON_SECRET と定数時間で照合する
function authorized(req, secret) {
  if (!secret) return false;
  const header = String((req.headers && (req.headers.authorization || req.headers.Authorization)) || "");
  const expected = Buffer.from("Bearer " + secret, "utf8");
  const given = Buffer.from(header, "utf8");
  return given.length === expected.length && crypto.timingSafeEqual(given, expected);
}

let storeFactory = (env) => createStore(getQrMapFirestore(env), env);
function setStoreFactoryForTest(factory) { storeFactory = factory; }

async function handler(req, res) {
  const env = process.env;
  if (req.method !== "GET") { res.setHeader("Allow", "GET"); return send(res, 405, { error: "METHOD_NOT_ALLOWED" }); }
  const cfg = readEnv(env);
  if (!cfg.cronSecret || !cfg.cleanupEnabled) return send(res, 503, { error: "CLEANUP_DISABLED" });
  if (!authorized(req, cfg.cronSecret)) return send(res, 401, { error: "UNAUTHORIZED" });
  try {
    const store = storeFactory(env);
    const report = await store.cleanupEligible();
    return send(res, 200, Object.assign({ ok: true }, report));
  } catch (error) {
    if (error instanceof QrMapConfigError) {
      console.error("qr-map cleanup unavailable:", error.message);
      return send(res, 503, { error: "QR_MAP_UNAVAILABLE" });
    }
    console.error("qr-map cleanup error:", error && error.code ? error.code : "unknown");
    return send(res, 500, { error: "INTERNAL" });
  }
}

module.exports = handler;
module.exports.setStoreFactoryForTest = setStoreFactoryForTest;
module.exports.authorized = authorized;
