// プランナーQRマップ専用の Firestore 接続（HD-G1-001 + G-2 Safety Decision）。
//
// 守ること:
//   - 既存サイトの Firebase project（sidekick-6cfee: AI Lab / DL 登録 / Activity）には絶対に接続しない
//   - 既存 api/*.js の既定 app（admin.apps[0]）と混ざらないよう、名前付き app "qr-map" を使う
//   - QR_MAP_REQUIRE_EMULATOR=1（tests / local 開発）のときは emulator 以外を拒否する
//   - emulator を使うときは project ID が "demo-" で始まること（Firebase の demo project は実 resource に触れない）
//   - 設定が足りないときは黙って別の接続先へ倒れず、QrMapConfigError を投げる（API は 503）
"use strict";

const { CONSTANTS, readEnv } = require("./config");

class QrMapConfigError extends Error {
  constructor(message) {
    super(message);
    this.code = "QR_MAP_UNAVAILABLE";
  }
}

let adminModule = null;
function loadAdmin() {
  if (!adminModule) adminModule = require("firebase-admin");
  return adminModule;
}

// 純関数: env から接続方法を決める（test 対象）。戻り値 { mode: "emulator" | "production", projectId, credentialJson }
function resolveConnection(env = process.env) {
  const cfg = readEnv(env);
  const projectId = cfg.projectId;
  if (!projectId) throw new QrMapConfigError("QR_MAP_FIREBASE_PROJECT_ID が未設定");
  if (CONSTANTS.DENIED_PROJECT_IDS.includes(projectId)) {
    throw new QrMapConfigError("既存サイトの Firebase project には接続しない: " + projectId);
  }
  if (cfg.emulatorHost) {
    if (!projectId.startsWith("demo-")) {
      throw new QrMapConfigError("emulator では demo- で始まる project ID だけを使う");
    }
    return { mode: "emulator", projectId, emulatorHost: cfg.emulatorHost, credentialJson: null };
  }
  if (cfg.requireEmulator) {
    throw new QrMapConfigError("QR_MAP_REQUIRE_EMULATOR=1 なのに FIRESTORE_EMULATOR_HOST が無い（本番へ倒れない）");
  }
  if (env.NODE_ENV === "test") {
    throw new QrMapConfigError("NODE_ENV=test では本番 Firestore に接続しない");
  }
  if (projectId.startsWith("demo-")) {
    throw new QrMapConfigError("demo- project は emulator 専用");
  }
  let serviceAccount;
  try { serviceAccount = JSON.parse(cfg.serviceAccountJson || ""); }
  catch (_) { throw new QrMapConfigError("QR_MAP_FIREBASE_SERVICE_ACCOUNT が読めない"); }
  if (!serviceAccount || serviceAccount.project_id !== projectId) {
    throw new QrMapConfigError("service account の project_id が QR_MAP_FIREBASE_PROJECT_ID と一致しない");
  }
  return { mode: "production", projectId, emulatorHost: null, credentialJson: serviceAccount };
}

const APP_NAME = "qr-map";
let cached = null;

function getQrMapFirestore(env = process.env) {
  const conn = resolveConnection(env);
  const cacheKey = conn.mode + "|" + conn.projectId + "|" + (conn.emulatorHost || "");
  if (cached && cached.key === cacheKey) return cached.value;
  const admin = loadAdmin();
  const existing = admin.apps.find((app) => app && app.name === APP_NAME);
  if (existing) {
    // 別の接続設定で作られた app は使い回さない（test が env を切り替える場合）
    if (!cached || cached.key !== cacheKey) {
      throw new QrMapConfigError("qr-map app が別設定で初期化済み");
    }
  }
  const options = { projectId: conn.projectId };
  if (conn.mode === "production") options.credential = admin.credential.cert(conn.credentialJson);
  const app = admin.initializeApp(options, APP_NAME);
  const value = { db: app.firestore(), Timestamp: admin.firestore.Timestamp, mode: conn.mode, projectId: conn.projectId, app };
  cached = { key: cacheKey, value };
  return value;
}

module.exports = { QrMapConfigError, resolveConnection, getQrMapFirestore };
