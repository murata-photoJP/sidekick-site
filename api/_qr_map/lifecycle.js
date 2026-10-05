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

module.exports = {
  STATES, toMs, expiresAtFrom, deleteAfterFrom,
  isActive, shouldRecordActivity, deletionEligibleAtMs, isDeletionEligible
};
