// PublicPlan の lifecycle（純関数。HD-G0-006 / HD-G1-005）。
//
//   state: "published" | "unpublished" | "removed"（removed は運営による掲載停止）
//   active（Map / 詳細に出る）= state == "published" && now < expires_at   ← expired は state にしない
//   activity = 詳細を明示的に開いたときだけ。expires_at = activity + 180 日。前回から 24 時間以内なら更新しない
//   物理削除の対象 = unpublished / removed になってから 30 日、または expires_at から 30 日を過ぎたもの
//   delete_after を document に持たせ、状態が変わるたびに書き直す（cleanup は delete_after <= now の 1 query）
"use strict";

const { CONSTANTS, DAY_MS } = require("./config");

const STATES = Object.freeze(["published", "unpublished", "removed"]);

function toMs(value) {
  if (value instanceof Date) return value.getTime();
  if (value && typeof value.toMillis === "function") return value.toMillis(); // Firestore Timestamp
  if (typeof value === "number") return value;
  return NaN;
}

function expiresAtFrom(activityMs) {
  return activityMs + CONSTANTS.LISTING_DAYS * DAY_MS;
}

function deleteAfterFrom(baseMs) {
  return baseMs + CONSTANTS.DELETE_AFTER_DAYS * DAY_MS;
}

function isActive(doc, nowMs) {
  return !!doc && doc.state === "published" && nowMs < toMs(doc.expires_at);
}

// 詳細を開いたときに延長すべきか（24 時間以内の再アクセスでは書かない）
function shouldRecordActivity(doc, nowMs) {
  if (!isActive(doc, nowMs)) return false;
  const last = toMs(doc.last_activity_at);
  return !(nowMs - last < CONSTANTS.ACTIVITY_THROTTLE_MS);
}

// 物理削除の対象になる時刻（state から導く。delete_after と一致することを test で固定する）
function deletionEligibleAtMs(doc) {
  if (!doc) return NaN;
  if (doc.state === "published") return deleteAfterFrom(toMs(doc.expires_at));
  if (doc.state === "unpublished" || doc.state === "removed") return deleteAfterFrom(toMs(doc.state_changed_at));
  return NaN;
}

function isDeletionEligible(doc, nowMs) {
  const at = deletionEligibleAtMs(doc);
  return Number.isFinite(at) && nowMs >= at;
}

// G-5.1（HD-PLANNERQRMAP-044）: 物理削除してよいかの判定（cleanup は query の delete_after だけを信用しない）。
//   "delete"    : 削除してよい
//   "keep"      : まだ削除しない（active・猶予 30 日の途中・delete_after と state の不一致など）
//   "malformed" : 形が壊れている（state 不明・時刻が無い / Timestamp でない）→ 削除せず数えるだけ
// 誤削除防止を最優先: active（published かつ now < expires_at）は delete_after が何であっても削除しない。
// 削除するのは「state から導いた削除可能時刻」と「保存された delete_after」の両方が now 以前のときだけ。
function planCleanupVerdict(doc, nowMs) {
  if (!doc || typeof doc !== "object" || !STATES.includes(doc.state)) return "malformed";
  const deleteAfter = toMs(doc.delete_after);
  const expires = toMs(doc.expires_at);
  if (!Number.isFinite(deleteAfter) || !Number.isFinite(expires)) return "malformed";
  if (doc.state !== "published" && !Number.isFinite(toMs(doc.state_changed_at))) return "malformed";
  if (isActive(doc, nowMs)) return "keep";
  if (nowMs < deleteAfter) return "keep";
  return isDeletionEligible(doc, nowMs) ? "delete" : "keep";
}

// idempotency / counter の補助 document: delete_after だけで決まる（Timestamp でなければ malformed）
function auxCleanupVerdict(doc, nowMs) {
  if (!doc || typeof doc !== "object") return "malformed";
  const deleteAfter = toMs(doc.delete_after);
  if (!Number.isFinite(deleteAfter)) return "malformed";
  return nowMs >= deleteAfter ? "delete" : "keep";
}

module.exports = {
  STATES, toMs, expiresAtFrom, deleteAfterFrom,
  isActive, shouldRecordActivity, deletionEligibleAtMs, isDeletionEligible,
  planCleanupVerdict, auxCleanupVerdict
};
