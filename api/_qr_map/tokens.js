// plan_id / manage_token / idempotency_key / fingerprint（HD-G0-002 / -004 / -005）。
"use strict";

const crypto = require("node:crypto");

const PLAN_ID_RE = /^[0-9a-f]{32}$/;                 // 128 bit 乱数（hex）。座標・hash から導出しない
const MANAGE_TOKEN_RE = /^[A-Za-z0-9_-]{43}$/;       // 256 bit 乱数（base64url、padding 無し）
const IDEMPOTENCY_KEY_RE = /^[A-Za-z0-9_-]{22,128}$/; // client 生成（128 bit 以上を想定）

function newPlanId() {
  return crypto.randomBytes(16).toString("hex");
}

function newManageToken() {
  return crypto.randomBytes(32).toString("base64url");
}

function sha256Hex(text) {
  return crypto.createHash("sha256").update(String(text), "utf8").digest("hex");
}

// 保存してある SHA-256（hex）と、提示された raw token を比べる。長さが違っても時間差を出さない
function tokenMatches(rawToken, storedSha256Hex) {
  if (typeof rawToken !== "string" || !MANAGE_TOKEN_RE.test(rawToken)) return false;
  if (typeof storedSha256Hex !== "string" || !/^[0-9a-f]{64}$/.test(storedSha256Hex)) return false;
  const a = Buffer.from(sha256Hex(rawToken), "hex");
  const b = Buffer.from(storedSha256Hex, "hex");
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

module.exports = {
  PLAN_ID_RE, MANAGE_TOKEN_RE, IDEMPOTENCY_KEY_RE,
  newPlanId, newManageToken, sha256Hex, tokenMatches
};
