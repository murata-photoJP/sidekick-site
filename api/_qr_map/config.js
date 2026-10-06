// プランナーQRマップ（PublicPlan Server Core、G-2）の定数と環境設定。
// 先頭が "_" の directory は Vercel Function にならない（api/qr-map.js からだけ require する）。
//
// Human Decision: HD-G0-001〜012 / HD-G1-001〜008（G-0 / G-1 報告、2026-10-05）。
//   - 公開は Planner から明示 opt-in だけ（publish の consent_version 必須）
//   - plan_id は server 側の識別子。QR / SharePlan / fragment には入れない
//   - manage_token は server 生成の 256 bit 乱数。DB には SHA-256 だけ
//   - 掲載は「最後に詳細を開いてから 180 日」。期限切れは state ではなく導出条件
//   - unpublish / 期限切れから 30 日後に物理削除の対象
//   - アプリ DB に IP / IP hash を保存しない
"use strict";

const DAY_MS = 24 * 60 * 60 * 1000;

const CONSTANTS = Object.freeze({
  SCHEMA: "qr_map_plan/1",
  COLLECTION_PLANS: "qr_map_plans",
  COLLECTION_IDEMPOTENCY: "qr_map_idempotency",
  COLLECTION_COUNTERS: "qr_map_counters",
  // 公開時の同意文言の版。Planner の同意画面と対で上げる（未知の版は拒否）
  CONSENT_VERSIONS: Object.freeze(["qr-map-consent/1"]),
  LISTING_DAYS: 180,                 // HD-G0-006
  ACTIVITY_THROTTLE_MS: DAY_MS,      // 延長は概ね 1 日 1 回まで（HD-G0-006）
  DELETE_AFTER_DAYS: 30,             // HD-G1-005
  IDEMPOTENCY_REPLAY_MS: DAY_MS,     // 同じ idempotency_key の再送で manage_token を出し直せる期間
  MAX_BODY_BYTES: 8 * 1024,          // HD-G0 baseline（publish の body 全体）
  // fragment は share.html の raw_compressed_max（2,953 B）の base64url 長が上限。ここでは文字数の上限だけ先に見る
  MAX_FRAGMENT_CHARS: Math.ceil(2953 / 3) * 4,
  // 有限範囲の取得（HD-G0-007）: 固定の data tile 段だけを受ける（表示 zoom とは独立）
  TILE_LEVELS: Object.freeze([6, 10, 14]),
  TILE_RESULT_LIMIT: 200,            // 1 tile あたりの最大件数（超えたら truncated）
  DEFAULT_DAILY_PUBLISH_LIMIT: 200,  // global circuit breaker（1 日の公開件数の上限）
  // 公開してよい SharePlan の種類（HD-G0-009 genre allow-list）
  ALLOWED_GENRES: Object.freeze({
    1: Object.freeze(["diamond_fuji", "pearl_fuji"]),
    2: Object.freeze(["solar_lunar", "star_landscape", "star_trails"])
  }),
  // 既存サイトの Firebase project（AI Lab / DL 登録 / Activity）。QR Map は絶対に接続しない（HD-G1-001）
  DENIED_PROJECT_IDS: Object.freeze(["sidekick-6cfee"]),
  // G-5.1（HD-PLANNERQRMAP-035 / -036 / -044）: 本番として接続してよい project はこの一覧だけ（positive allow）。
  // project はまだ作っていない（作成は Production 接続の直前の Human Action）。id を変えるときはここを変える。
  PRODUCTION_PROJECT_IDS: Object.freeze(["sidekick-map-prod"]),
  // G-5.1: 物理削除 1 回あたりの上限（collection ごと）。Vercel Cron（1 日 1 回）で少しずつ消す
  CLEANUP_BATCH_LIMIT: 200,
  ALLOWED_ORIGINS: Object.freeze(["https://www.sidekick-lab.com"])
});

// Vercel の実行環境（system environment variable）。"production" / "preview" / "development"。
// Vercel の外（local・test）では空。
function vercelEnv(env) {
  return String(env.VERCEL_ENV || "");
}

// 環境変数を読む（毎回読む: test が env を切り替えられるように）
function readEnv(env = process.env) {
  const limit = Number.parseInt(env.QR_MAP_DAILY_PUBLISH_LIMIT || "", 10);
  return {
    // circuit breaker: 文字列 "true" のときだけ publish を受ける（未設定 = 停止。fail-closed）
    publishEnabled: env.QR_MAP_PUBLISH_ENABLED === "true",
    dailyPublishLimit: Number.isInteger(limit) && limit >= 0 ? limit : CONSTANTS.DEFAULT_DAILY_PUBLISH_LIMIT,
    projectId: env.QR_MAP_FIREBASE_PROJECT_ID || "",
    serviceAccountJson: env.QR_MAP_FIREBASE_SERVICE_ACCOUNT || "",
    emulatorHost: env.FIRESTORE_EMULATOR_HOST || "",
    // "1" のとき emulator 以外への接続を拒否する（tests / local 開発は必ず 1）
    requireEmulator: env.QR_MAP_REQUIRE_EMULATOR === "1",
    // G-5.1: Vercel の実行環境と、本番 Firestore への接続そのものの明示 switch（公開の switch とは別）。
    // 本番接続は VERCEL_ENV === "production" かつ この値が "enabled" のときだけ（firestore.js resolveConnection）
    vercelEnv: vercelEnv(env),
    productionFirestore: env.QR_MAP_PRODUCTION_FIRESTORE === "enabled",
    // G-5.1: 物理削除（cleanup）の明示 switch と Vercel Cron の secret。どちらか無ければ cleanup は動かない
    cleanupEnabled: env.QR_MAP_CLEANUP_ENABLED === "true",
    cronSecret: String(env.CRON_SECRET || ""),
    // local 確認用 server（http://127.0.0.1:port）の Origin。emulator 専用の設定でだけ効き、
    // Vercel の preview / production では常に無視する（G-5.1）
    devAllowedOrigins: env.QR_MAP_REQUIRE_EMULATOR === "1" && !["production", "preview"].includes(vercelEnv(env))
      ? String(env.QR_MAP_DEV_ALLOWED_ORIGINS || "").split(",").map((s) => s.trim())
        .filter((s) => /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(s))
      : []
  };
}

module.exports = { CONSTANTS, DAY_MS, readEnv };
