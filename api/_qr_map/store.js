// PublicPlan の保存・取得（Firestore）。HTTP からは独立（tests は emulator で直接呼ぶ）。
//
// collection:
//   qr_map_plans/{plan_id}             PublicPlan 本体（1 公開 = 1 document。配列に積まない）
//   qr_map_idempotency/{sha256(key)}   publish の再送吸収（plan_id と fragment fingerprint だけ）
//   qr_map_counters/publish-YYYY-MM-DD  global circuit breaker の日次件数
//
// 保存しないもの: raw manage_token / raw idempotency_key / IP / IP hash / User-Agent。
"use strict";

const { CONSTANTS, readEnv } = require("./config");
const { newPlanId, newManageToken, sha256Hex, tokenMatches, PLAN_ID_RE, IDEMPOTENCY_KEY_RE } = require("./tokens");
const { parsePublishableFragment, SharePlanError } = require("./shareplan");
const { tileKeysFor, parseTileRequest } = require("./tiles");
const lifecycle = require("./lifecycle");

class QrMapError extends Error {
  constructor(code, status) {
    super(code);
    this.code = code;
    this.status = status;
  }
}

const NOT_FOUND = () => new QrMapError("NOT_FOUND", 404);

function dayKey(nowMs) {
  return "publish-" + new Date(nowMs).toISOString().slice(0, 10);
}

function idempotencyDocId(key) {
  return sha256Hex("qr-map-idempotency:" + key);
}

// 外へ出す PublicPlan の表示値（manage_token hash・idempotency・delete_after は出さない）
function publicView(doc, withFragment) {
  const out = {
    plan_id: doc.plan_id,
    lat: doc.display.lat,
    lon: doc.display.lon,
    genre: doc.display.genre,
    genre_label: doc.display.genre_label,
    target_label: doc.display.target_label,
    sky_object_label: doc.display.sky_object_label,
    t_d: doc.display.t_d,
    location_precision: doc.location_precision
  };
  if (withFragment) {
    out.fragment = doc.snapshot.fragment;
    out.share_version = doc.snapshot.share_version;
    out.published_at = new Date(lifecycle.toMs(doc.published_at)).toISOString();
  }
  return out;
}

function createStore({ db, Timestamp }, env = process.env) {
  const plans = db.collection(CONSTANTS.COLLECTION_PLANS);
  const idempotency = db.collection(CONSTANTS.COLLECTION_IDEMPOTENCY);
  const counters = db.collection(CONSTANTS.COLLECTION_COUNTERS);
  const ts = (ms) => Timestamp.fromMillis(ms);

  async function publish({ fragment, idempotencyKey, consentVersion, nowMs = Date.now() }) {
    const cfg = readEnv(env);
    if (!cfg.publishEnabled) throw new QrMapError("PUBLISH_DISABLED", 503);
    if (typeof consentVersion !== "string" || !CONSTANTS.CONSENT_VERSIONS.includes(consentVersion)) {
      throw new QrMapError("CONSENT_REQUIRED", 400);
    }
    if (typeof idempotencyKey !== "string" || !IDEMPOTENCY_KEY_RE.test(idempotencyKey)) {
      throw new QrMapError("INVALID_IDEMPOTENCY_KEY", 400);
    }
    let parsed;
    try {
      parsed = await parsePublishableFragment(fragment);
    } catch (error) {
      if (error instanceof SharePlanError) throw new QrMapError("INVALID_SHAREPLAN:" + error.code, 400);
      throw error;
    }
    const idemRef = idempotency.doc(idempotencyDocId(idempotencyKey));
    const counterRef = counters.doc(dayKey(nowMs));

    return db.runTransaction(async (tx) => {
      const idemSnap = await tx.get(idemRef);
      if (idemSnap.exists) {
        // 再送（retry / double click / network retry）: 新しい PublicPlan を作らない
        const idem = idemSnap.data();
        if (idem.payload_sha256 !== parsed.snapshot.payload_sha256) {
          throw new QrMapError("IDEMPOTENCY_KEY_REUSED", 409);
        }
        const planRef = plans.doc(idem.plan_id);
        const planSnap = await tx.get(planRef);
        const plan = planSnap.exists ? planSnap.data() : null;
        let manageToken = null;
        // 最初の応答を失った client が管理用 token を受け取れるよう、短い期間だけ出し直す（旧 token は無効になる）
        if (plan && plan.state === "published" && nowMs - lifecycle.toMs(idem.created_at) < CONSTANTS.IDEMPOTENCY_REPLAY_MS) {
          manageToken = newManageToken();
          tx.update(planRef, { "owner.manage_token_sha256": sha256Hex(manageToken) });
        }
        return {
          plan_id: idem.plan_id,
          manage_token: manageToken,
          replayed: true,
          published_at: plan ? new Date(lifecycle.toMs(plan.published_at)).toISOString() : null,
          expires_at: plan ? new Date(lifecycle.toMs(plan.expires_at)).toISOString() : null
        };
      }

      const counterSnap = await tx.get(counterRef);
      const count = counterSnap.exists ? counterSnap.data().count || 0 : 0;
      if (count >= cfg.dailyPublishLimit) throw new QrMapError("PUBLISH_LIMIT_REACHED", 503);

      const planId = newPlanId();
      const manageToken = newManageToken();
      const expiresMs = lifecycle.expiresAtFrom(nowMs);
      const planDoc = {
        schema: CONSTANTS.SCHEMA,
        plan_id: planId,
        snapshot: parsed.snapshot,
        display: parsed.display,
        tiles: tileKeysFor(parsed.display.lat, parsed.display.lon),
        owner: { kind: "anonymous", manage_token_sha256: sha256Hex(manageToken), owner_user_id: null },
        state: "published",
        consent_version: consentVersion,
        location_precision: "exact",
        published_at: ts(nowMs),
        state_changed_at: ts(nowMs),
        last_activity_at: ts(nowMs),
        expires_at: ts(expiresMs),
        delete_after: ts(lifecycle.deleteAfterFrom(expiresMs)),
        idempotency_key_sha256: idemRef.id
      };
      tx.create(plans.doc(planId), planDoc);
      tx.create(idemRef, {
        plan_id: planId,
        payload_sha256: parsed.snapshot.payload_sha256,
        created_at: ts(nowMs),
        delete_after: ts(lifecycle.deleteAfterFrom(nowMs))
      });
      tx.set(counterRef, { count: count + 1, delete_after: ts(lifecycle.deleteAfterFrom(nowMs)) });
      return {
        plan_id: planId,
        manage_token: manageToken,
        replayed: false,
        published_at: new Date(nowMs).toISOString(),
        expires_at: new Date(expiresMs).toISOString()
      };
    });
  }

  async function unpublish({ planId, manageToken, nowMs = Date.now() }) {
    if (typeof planId !== "string" || !PLAN_ID_RE.test(planId)) throw NOT_FOUND();
    const ref = plans.doc(planId);
    return db.runTransaction(async (tx) => {
      const snap = await tx.get(ref);
      // 存在しない / token 不一致は同じ応答（存在を推測させない）
      if (!snap.exists || !tokenMatches(manageToken, snap.data().owner.manage_token_sha256)) throw NOT_FOUND();
      const doc = snap.data();
      if (doc.state !== "published") return { plan_id: planId, state: doc.state, changed: false };
      tx.update(ref, {
        state: "unpublished",
        state_changed_at: ts(nowMs),
        delete_after: ts(lifecycle.deleteAfterFrom(nowMs))
      });
      return { plan_id: planId, state: "unpublished", changed: true };
    });
  }

  // 詳細を明示的に開く（= activity）。active でなければ NOT_FOUND
  async function openDetail({ planId, nowMs = Date.now() }) {
    if (typeof planId !== "string" || !PLAN_ID_RE.test(planId)) throw NOT_FOUND();
    const ref = plans.doc(planId);
    return db.runTransaction(async (tx) => {
      const snap = await tx.get(ref);
      if (!snap.exists) throw NOT_FOUND();
      const doc = snap.data();
      if (!lifecycle.isActive(doc, nowMs)) throw NOT_FOUND();
      if (lifecycle.shouldRecordActivity(doc, nowMs)) {
        const expiresMs = lifecycle.expiresAtFrom(nowMs);
        tx.update(ref, {
          last_activity_at: ts(nowMs),
          expires_at: ts(expiresMs),
          delete_after: ts(lifecycle.deleteAfterFrom(expiresMs))
        });
      }
      return publicView(doc, true);
    });
  }

  // 1 data tile 分の公開中 PublicPlan（読むだけ。activity は更新しない）
  async function getTile({ z, x, y, nowMs = Date.now() }) {
    const tile = parseTileRequest(String(z), String(x), String(y));
    if (!tile) throw new QrMapError("INVALID_TILE", 400);
    const base = plans
      .where("state", "==", "published")
      .where(tile.field, "==", tile.key)
      .where("expires_at", ">", ts(nowMs));
    const snap = await base.limit(CONSTANTS.TILE_RESULT_LIMIT + 1).get();
    const docs = snap.docs.map((d) => d.data()).filter((doc) => lifecycle.isActive(doc, nowMs));
    const truncated = docs.length > CONSTANTS.TILE_RESULT_LIMIT;
    const result = {
      z: tile.z, x: tile.x, y: tile.y,
      truncated,
      plans: docs.slice(0, CONSTANTS.TILE_RESULT_LIMIT).map((doc) => publicView(doc, false))
    };
    if (truncated) {
      // 件数だけは集計 query で返す（document は読まない）。cluster 表示用
      const agg = await base.count().get();
      result.count = agg.data().count;
    } else {
      result.count = result.plans.length;
    }
    return result;
  }

  // 運営による掲載停止（HTTP には出さない。運用 script / test から呼ぶ）
  async function removeByOperator({ planId, nowMs = Date.now() }) {
    const ref = plans.doc(planId);
    return db.runTransaction(async (tx) => {
      const snap = await tx.get(ref);
      if (!snap.exists) throw NOT_FOUND();
      tx.update(ref, { state: "removed", state_changed_at: ts(nowMs), delete_after: ts(lifecycle.deleteAfterFrom(nowMs)) });
      return { plan_id: planId, state: "removed" };
    });
  }

  // 物理削除（HD-G1-005）。delete_after <= now のものを上限付きで消す。cron への配線は後続 Gate
  async function deleteEligible({ nowMs = Date.now(), limit = 500 } = {}) {
    const result = { plans: 0, idempotency: 0, counters: 0 };
    for (const [name, col] of [["plans", plans], ["idempotency", idempotency], ["counters", counters]]) {
      const snap = await col.where("delete_after", "<=", ts(nowMs)).limit(limit).get();
      if (snap.empty) continue;
      const batch = db.batch();
      snap.docs.forEach((d) => batch.delete(d.ref));
      await batch.commit();
      result[name] = snap.size;
    }
    return result;
  }

  return { publish, unpublish, openDetail, getTile, removeByOperator, deleteEligible };
}

module.exports = { createStore, QrMapError, publicView, idempotencyDocId, dayKey };
