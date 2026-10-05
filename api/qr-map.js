// プランナーQRマップ PublicPlan API（G-2 Server Core）。
//
// 既存の QR / SharePlan / 共有ページ（/share）には一切関与しない。ここが止まっても QR → Viewer は動く。
//
// route（1 function に集約: Hobby の関数数 12 本の余裕を残し、WAF rate limit rule を 1 つの path に当てられる）:
//   POST /api/qr-map?op=publish    { fragment, idempotency_key, consent_version }  → 201 { plan_id, manage_token, ... }
//   POST /api/qr-map?op=unpublish  { plan_id, manage_token }                        → 200 { plan_id, state }
//   POST /api/qr-map?op=open       { plan_id }   詳細を明示的に開く（= activity）   → 200 { fragment, ... }
//   GET  /api/qr-map?op=tile&z=&x=&y=           1 data tile 分（activity は更新しない）
//
// 詳細は POST にする: link の先読みや crawler の GET で掲載期限が延びないように。
// 保存も log もしないもの: IP / IP hash / User-Agent / raw token / fragment の中身。
"use strict";

const { CONSTANTS } = require("./_qr_map/config");
const { getQrMapFirestore, QrMapConfigError } = require("./_qr_map/firestore");
const { createStore, QrMapError } = require("./_qr_map/store");

function send(res, status, body, cacheControl) {
  res.setHeader("Cache-Control", cacheControl || "no-store");
  res.setHeader("X-Robots-Tag", "noindex, nofollow");
  res.setHeader("X-Content-Type-Options", "nosniff");
  return res.status(status).json(body);
}

function originAllowed(req) {
  const origin = req.headers && req.headers.origin;
  if (!origin) return true; // Sidekick Planner（desktop、Python 側から送る）は Origin を付けない
  return CONSTANTS.ALLOWED_ORIGINS.includes(origin);
}

function isJsonRequest(req) {
  const type = String((req.headers && req.headers["content-type"]) || "").toLowerCase();
  return type.split(";")[0].trim() === "application/json";
}

// body を上限付きで object にする（Vercel が parse 済みの object でも長さを測り直す）
function readJsonBody(req) {
  const body = req.body;
  let text;
  if (typeof body === "string") text = body;
  else if (Buffer.isBuffer(body)) text = body.toString("utf8");
  else if (body && typeof body === "object" && !Array.isArray(body)) text = JSON.stringify(body);
  else return { error: "INVALID_BODY" };
  if (Buffer.byteLength(text, "utf8") > CONSTANTS.MAX_BODY_BYTES) return { error: "BODY_TOO_LARGE" };
  let value = body;
  if (typeof body === "string" || Buffer.isBuffer(body)) {
    try { value = JSON.parse(text); } catch (_) { return { error: "INVALID_BODY" }; }
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return { error: "INVALID_BODY" };
  return { value };
}

let storeFactory = (env) => createStore(getQrMapFirestore(env), env);
function setStoreFactoryForTest(factory) { storeFactory = factory; }

async function handler(req, res) {
  const op = req.query && typeof req.query.op === "string" ? req.query.op : "";
  const env = process.env;
  try {
    if (!originAllowed(req)) return send(res, 403, { error: "ORIGIN_NOT_ALLOWED" });

    if (op === "tile") {
      if (req.method !== "GET") { res.setHeader("Allow", "GET"); return send(res, 405, { error: "METHOD_NOT_ALLOWED" }); }
      const store = storeFactory(env);
      const q = req.query;
      const tile = await store.getTile({ z: q.z, x: q.x, y: q.y });
      return send(res, 200, tile, "public, max-age=0, s-maxage=60");
    }

    if (op === "publish" || op === "unpublish" || op === "open") {
      if (req.method !== "POST") { res.setHeader("Allow", "POST"); return send(res, 405, { error: "METHOD_NOT_ALLOWED" }); }
      if (!isJsonRequest(req)) return send(res, 415, { error: "UNSUPPORTED_MEDIA_TYPE" });
      const parsed = readJsonBody(req);
      if (parsed.error) return send(res, parsed.error === "BODY_TOO_LARGE" ? 413 : 400, { error: parsed.error });
      const body = parsed.value;
      const store = storeFactory(env);
      if (op === "publish") {
        const result = await store.publish({
          fragment: body.fragment,
          idempotencyKey: body.idempotency_key,
          consentVersion: body.consent_version
        });
        return send(res, result.replayed ? 200 : 201, result);
      }
      if (op === "unpublish") {
        const result = await store.unpublish({ planId: body.plan_id, manageToken: body.manage_token });
        return send(res, 200, result);
      }
      const detail = await store.openDetail({ planId: body.plan_id });
      return send(res, 200, detail);
    }

    return send(res, 404, { error: "UNKNOWN_OP" });
  } catch (error) {
    if (error instanceof QrMapError) return send(res, error.status, { error: error.code });
    if (error instanceof QrMapConfigError) {
      console.error("qr-map unavailable:", error.message);
      return send(res, 503, { error: "QR_MAP_UNAVAILABLE" });
    }
    console.error("qr-map internal error:", error && error.code ? error.code : "unknown");
    return send(res, 500, { error: "INTERNAL" });
  }
}

module.exports = handler;
module.exports.setStoreFactoryForTest = setStoreFactoryForTest;
module.exports.readJsonBody = readJsonBody;
module.exports.originAllowed = originAllowed;
