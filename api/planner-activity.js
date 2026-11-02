// Sidekick Planner Activity 受け口（B2+ anonymous aggregate。HD-PLANNERACTIVITY-001〜011、2026-09-19、AI-6205）
//
// 何を受けるか（allow-list。これ以外の key は捨てる）:
//   schema     "planner_activity/1"
//   event      "share_created" | "share_viewed" | "share_view_failed"
//   event_id   32 hex（random 128 bit。冪等キー = Firestore の document id）
//   at         "YYYY-MM-DDTHH:00Z"（client 時刻、1 時間粒度。不正なら server 時刻を 1 時間に丸める）
//   category   "mountain" | "structure"（share_created のみ。HD-010 C-2）
//   transport  "viewer" | "planner"（share_created のみ。HD-011）
//   repeat     true | false（share_viewed のみ。Viewer の localStorage 由来の 1 bit）
//   code       contract の error code 語彙（share_view_failed のみ）
//
// 何を保存しないか（HD-004〜006、AI-6001 §3）:
//   plan_ref / installation_id / poi_id / 緯度経度 / 撮影日時 / payload / fragment / country /
//   IP / User-Agent 生文字列。UA は client.kind（mobile / desktop / preview_fetch / bot / planner / unknown）
//   に分類してから捨てる。x-vercel-ip-* header は読まない。
//
// 応答: POST は body が壊れていても 204（Viewer の表示・Planner の QR 発行を止めない。add-contact.js と同じ思想）。
//       GET は集計（totals ＋ 直近 30 日の daily）を返す。細粒度（category / transport / client）は k >= 5 未満を伏せる（HD-009）。
//
// 保存先（Firestore、Admin SDK、FIREBASE_SERVICE_ACCOUNT env は add-contact.js と共通）:
//   planner_activity_events/{event_id}   raw event。expire_at = at + 425 日（HD-007: β ＋ 12 か月）。期限切れは
//                                        api/planner-activity-cleanup.js（Vercel Cron、1 日 1 回）が削除する
//                                        （HD-PLANNERACTIVITY-012。Firestore TTL は Blaze 前提で β1.00 では不使用）
//   planner_activity_daily/{YYYY-MM-DD}  日次 increment（永久）
//   planner_activity_totals/all          累計 increment（永久）
//
// 将来の B3（HD-003 V1 以降）: event に optional field（plan_ref 等）を足すときは allow-list と schema version を
// 上げるだけで、collection / document 形は変えない。β1.00 では plan_ref を受け取っても捨てる。
//
// 開発者の識別（HD-PLANNERACTIVITY-014、2026-11-02、AI-29516）:
//   開発者が実際に発行した QR の share_created を、一般の集計から外す。body の allow-list は変えない。
//   - Authorization header が無い（一般の利用者・Viewer）: 従来どおり。204、daily / totals に加算する。
//   - Authorization: Bearer <PLANNER_ACTIVITY_DEVELOPER_TOKEN> が一致: 同じ planner_activity_events/{event_id} に
//     audience: "developer" を付けて create し、daily / totals には加算しない（開発者用の集計は作らない）。
//     event_id の冪等は一般と開発者をまたいで効く（先に入った分類のまま）。
//   - Authorization があるが一致しない / server の env が未設定・短すぎる: 何も保存せず 401。
//     Planner は送信失敗として backlog を保持する（開発者の分が一般に混ざらない）。
//   - GET ?check=<event_id>: 認証が一致した時だけ、開発者の event の有無と受信時刻を返す（no-store）。
//     認証なしは 401。一般の event は found: false（一覧は返さない）。?check の無い GET は従来どおり。
//   token・その hash は保存も log もしない。開発者を示すのは audience の 1 項目だけ。

const crypto = require('crypto');
const admin = require('firebase-admin');

const SCHEMA = 'planner_activity/1';
const EVENTS = ['share_created', 'share_viewed', 'share_view_failed'];
const CATEGORIES = ['mountain', 'structure'];
const TRANSPORTS = ['viewer', 'planner'];
const CLIENT_KINDS = ['mobile', 'desktop', 'preview_fetch', 'bot', 'planner', 'unknown'];
const MAX_BODY_BYTES = 8 * 1024;
const MAX_EVENTS_PER_REQUEST = 50;
const EVENT_ID_RE = /^[0-9a-f]{32}$/;
const AT_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):00Z$/;
const CODE_RE = /^[A-Z_]{1,40}$/;
const RETENTION_DAYS = 425;
const PUBLIC_K = 5;
const DAILY_WINDOW_DAYS = 30;
const ALLOWED_ORIGINS = ['https://www.sidekick-lab.com'];
const AUDIENCE_DEVELOPER = 'developer';
const DEVELOPER_TOKEN_MIN_LENGTH = 32;

// --------------------------------------------------------------------
// Firestore
// --------------------------------------------------------------------
function getFirestore() {
  try {
    if (!admin.apps.length) {
      const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT || '{}');
      if (!serviceAccount.project_id) {
        console.error('FIREBASE_SERVICE_ACCOUNT not set or invalid');
        return null;
      }
      admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
    }
    return admin.firestore();
  } catch (err) {
    console.error('firebase-admin init failed:', err.message);
    return null;
  }
}

// --------------------------------------------------------------------
// 分類（pure。test 対象）
// --------------------------------------------------------------------
function classifyUserAgent(ua) {
  const s = String(ua || '');
  if (/^SidekickPlanner\//.test(s)) return 'planner';
  if (/facebookexternalhit|Twitterbot|Slackbot|Discordbot|TelegramBot|WhatsApp|LinkedInBot|Applebot|Line\/|LINE/.test(s)) return 'preview_fetch';
  if (/bot|crawler|spider|curl\/|python-requests|Python-urllib|HeadlessChrome/i.test(s)) return 'bot';
  if (/Mobile|Android|iPhone|iPad|iPod/.test(s)) return 'mobile';
  if (/Windows|Macintosh|X11|CrOS/.test(s)) return 'desktop';
  return 'unknown';
}

// at の正当性: 形式 ＋ 実在する日時 ＋ 未来 1 日 / 過去 400 日以内（offline backlog を許す）。
function normalizeAt(value, now) {
  const m = AT_RE.exec(String(value || ''));
  if (m) {
    const t = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4]);
    const d = new Date(t);
    const roundTrip = d.getUTCFullYear() === +m[1] && d.getUTCMonth() === +m[2] - 1 &&
      d.getUTCDate() === +m[3] && d.getUTCHours() === +m[4];
    const ageDays = (now.getTime() - t) / 86400000;
    if (roundTrip && ageDays <= 400 && ageDays >= -1) return d;
  }
  const fallback = new Date(now.getTime());
  fallback.setUTCMinutes(0, 0, 0);
  return fallback;
}

// 1 event を allow-list で正規化する。受理できなければ null（無視）。
function normalizeEvent(raw, clientKind, now) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  if (raw.schema !== SCHEMA) return null;
  if (!EVENTS.includes(raw.event)) return null;
  if (!EVENT_ID_RE.test(String(raw.event_id || ''))) return null;
  const at = normalizeAt(raw.at, now);
  const out = {
    schema: SCHEMA,
    event: raw.event,
    at: at,
    day: at.toISOString().slice(0, 10),
    client_kind: CLIENT_KINDS.includes(clientKind) ? clientKind : 'unknown'
  };
  if (raw.event === 'share_created') {
    out.category = CATEGORIES.includes(raw.category) ? raw.category : 'unknown';
    out.transport = TRANSPORTS.includes(raw.transport) ? raw.transport : 'unknown';
  } else if (raw.event === 'share_viewed') {
    out.repeat = raw.repeat === true;
  } else if (raw.event === 'share_view_failed') {
    out.code = CODE_RE.test(String(raw.code || '')) ? raw.code : 'UNKNOWN';
  }
  return { id: raw.event_id, doc: out };
}

// daily / totals へ加算する field 名（増分は create 成功時だけ）。
function incrementsFor(doc) {
  const inc = { [doc.event]: 1 };
  if (doc.event === 'share_created') {
    inc['share_created_category_' + doc.category] = 1;
    inc['share_created_transport_' + doc.transport] = 1;
  } else if (doc.event === 'share_viewed') {
    inc['share_viewed_client_' + doc.client_kind] = 1;
    if (!doc.repeat) inc.share_viewed_unique = 1;
  } else if (doc.event === 'share_view_failed') {
    inc['share_view_failed_code_' + doc.code] = 1;
  }
  return inc;
}

function parseBody(req) {
  const body = req.body;
  if (body == null) return null;
  if (typeof body === 'string') {
    if (Buffer.byteLength(body, 'utf8') > MAX_BODY_BYTES) return null;
    try { return JSON.parse(body); } catch (_) { return null; }
  }
  if (Buffer.isBuffer(body)) {
    if (body.length > MAX_BODY_BYTES) return null;
    try { return JSON.parse(body.toString('utf8')); } catch (_) { return null; }
  }
  if (typeof body === 'object') return body;
  return null;
}

function eventsOf(parsed) {
  if (!parsed || typeof parsed !== 'object') return [];
  if (Array.isArray(parsed.events)) return parsed.events.slice(0, MAX_EVENTS_PER_REQUEST);
  return [parsed];
}

// browser から来る request（Origin あり）は同一 site だけ。Planner（Origin なし）は通す。
function originAllowed(req) {
  const origin = req.headers && req.headers.origin;
  if (!origin) return true;
  return ALLOWED_ORIGINS.includes(origin);
}

// 開発者の認証（HD-PLANNERACTIVITY-014）。'none' = Authorization なし（一般）、'ok' = 一致、'rejected' = それ以外。
// env が未設定・短すぎる時は、Authorization 付きの要求をすべて 'rejected' にする（fail-closed）。
function developerAuth(req, env) {
  const headers = (req && req.headers) || {};
  const raw = headers.authorization !== undefined ? headers.authorization : headers.Authorization;
  if (raw === undefined || raw === null) return 'none';
  const expected = String((env || process.env).PLANNER_ACTIVITY_DEVELOPER_TOKEN || '');
  if (expected.length < DEVELOPER_TOKEN_MIN_LENGTH) return 'rejected';
  const m = /^Bearer ([^\s]+)$/.exec(String(raw));
  if (!m) return 'rejected';
  const given = Buffer.from(m[1], 'utf8');
  const want = Buffer.from(expected, 'utf8');
  return given.length === want.length && crypto.timingSafeEqual(given, want) ? 'ok' : 'rejected';
}

function queryParam(req, name) {
  if (req && req.query && Object.prototype.hasOwnProperty.call(req.query, name)) {
    const v = req.query[name];
    return Array.isArray(v) ? String(v[0]) : String(v);
  }
  try {
    const url = new URL(String((req && req.url) || ''), 'https://www.sidekick-lab.com');
    return url.searchParams.has(name) ? url.searchParams.get(name) : null;
  } catch (_) {
    return null;
  }
}

// 公開集計の細粒度は k >= 5 未満を伏せる（HD-009）。totals の主要件数はそのまま。
function publicView(counts) {
  const out = {};
  for (const key of Object.keys(counts || {})) {
    const v = counts[key];
    if (typeof v !== 'number') continue;
    const fine = /_(category|transport|client|code)_/.test(key);
    if (fine && v < PUBLIC_K) continue;
    out[key] = v;
  }
  return out;
}

// --------------------------------------------------------------------
// 書き込み（1 event = 1 document。batch id は持たない。create の重複は無視 = 冪等）
// --------------------------------------------------------------------
async function storeEvents(db, normalized, developer) {
  const FieldValue = admin.firestore.FieldValue;
  let stored = 0;
  let duplicates = 0;
  for (const item of normalized) {
    const ref = db.collection('planner_activity_events').doc(item.id);
    const expireAt = new Date(item.doc.at.getTime() + RETENTION_DAYS * 86400000);
    const doc = {
      ...item.doc,
      at: admin.firestore.Timestamp.fromDate(item.doc.at),
      received_at: FieldValue.serverTimestamp(),
      expire_at: admin.firestore.Timestamp.fromDate(expireAt)
    };
    if (developer) doc.audience = AUDIENCE_DEVELOPER;
    try {
      await ref.create(doc);
    } catch (err) {
      if (err && (err.code === 6 || /already exists/i.test(String(err.message)))) { duplicates += 1; continue; }
      throw err;
    }
    // 開発者の event は daily / totals に加算しない（HD-PLANNERACTIVITY-014）。
    if (developer) { stored += 1; continue; }
    const inc = incrementsFor(item.doc);
    const incFields = {};
    for (const k of Object.keys(inc)) incFields[k] = FieldValue.increment(inc[k]);
    const daily = db.collection('planner_activity_daily').doc(item.doc.day);
    const totals = db.collection('planner_activity_totals').doc('all');
    await Promise.all([
      daily.set({ ...incFields, day: item.doc.day, updated_at: FieldValue.serverTimestamp() }, { merge: true }),
      totals.set({ ...incFields, updated_at: FieldValue.serverTimestamp() }, { merge: true })
    ]);
    stored += 1;
  }
  return { stored, duplicates };
}

async function readAggregate(db, now) {
  const totalsSnap = await db.collection('planner_activity_totals').doc('all').get();
  const since = new Date(now.getTime() - DAILY_WINDOW_DAYS * 86400000).toISOString().slice(0, 10);
  const dailySnap = await db.collection('planner_activity_daily')
    .where('day', '>=', since).orderBy('day', 'asc').get();
  const daily = {};
  dailySnap.forEach((d) => { const v = d.data(); daily[v.day || d.id] = publicView(v); });
  return {
    schema: 'planner_activity_aggregate/1',
    generated_at: now.toISOString(),
    note: 'Planner から送信された計測値。送信失敗・停止設定の分は含まない。細粒度は k >= 5 未満を伏せる。',
    totals: publicView(totalsSnap.exists ? totalsSnap.data() : {}),
    daily: daily
  };
}

// --------------------------------------------------------------------
// handler
// --------------------------------------------------------------------
// 開発者の受信確認（HD-PLANNERACTIVITY-014）。認証必須・no-store・1 件の有無だけ。
async function readDeveloperCheck(req, res, eventId) {
  res.setHeader('Cache-Control', 'no-store');
  if (developerAuth(req) !== 'ok') return res.status(401).end();
  if (!EVENT_ID_RE.test(String(eventId || ''))) return res.status(400).json({ error: 'bad_event_id' });
  const db = getFirestore();
  if (!db) return res.status(503).json({ error: 'firestore_unavailable' });
  try {
    const snap = await db.collection('planner_activity_events').doc(eventId).get();
    const data = snap.exists ? snap.data() : null;
    if (!data || data.audience !== AUDIENCE_DEVELOPER) return res.status(200).json({ found: false });
    const received = data.received_at && typeof data.received_at.toDate === 'function'
      ? data.received_at.toDate().toISOString() : null;
    return res.status(200).json({ found: true, audience: AUDIENCE_DEVELOPER, event: data.event, received_at: received });
  } catch (err) {
    console.error('planner-activity check failed:', err.message);
    return res.status(503).json({ error: 'read_failed' });
  }
}

module.exports = async function handler(req, res) {
  const now = new Date();
  if (req.method === 'GET') {
    const check = queryParam(req, 'check');
    if (check !== null) return readDeveloperCheck(req, res, check);
    const db = getFirestore();
    if (!db) return res.status(503).json({ error: 'firestore_unavailable' });
    try {
      const body = await readAggregate(db, now);
      res.setHeader('Cache-Control', 'public, max-age=300');
      return res.status(200).json(body);
    } catch (err) {
      console.error('planner-activity read failed:', err.message);
      return res.status(503).json({ error: 'read_failed' });
    }
  }
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'GET, POST');
    return res.status(405).end();
  }
  // ここから先は何があっても 204（Viewer / Planner の主処理を止めない）。
  // 例外は Authorization 付きで認証が一致しない要求だけ（401。Planner の開発者モードが backlog を保持する）。
  try {
    if (!originAllowed(req)) return res.status(204).end();
    const auth = developerAuth(req);
    if (auth === 'rejected') {
      console.log('planner-activity: developer auth rejected');
      return res.status(401).end();
    }
    const developer = auth === 'ok';
    const parsed = parseBody(req);
    const clientKind = classifyUserAgent(req.headers && req.headers['user-agent']);
    const normalized = eventsOf(parsed).map((e) => normalizeEvent(e, clientKind, now)).filter(Boolean);
    if (normalized.length === 0) return res.status(204).end();
    const db = getFirestore();
    if (!db) { console.error('planner-activity: firestore unavailable, dropped', normalized.length); return res.status(204).end(); }
    const result = await storeEvents(db, normalized, developer);
    if (result.duplicates) console.log('planner-activity: duplicates ignored', result.duplicates);
    if (developer) console.log('planner-activity: developer events stored', result.stored);
  } catch (err) {
    console.error('planner-activity write failed:', err.message);
  }
  return res.status(204).end();
};

module.exports.SCHEMA = SCHEMA;
module.exports.EVENTS = EVENTS;
module.exports.classifyUserAgent = classifyUserAgent;
module.exports.normalizeEvent = normalizeEvent;
module.exports.normalizeAt = normalizeAt;
module.exports.incrementsFor = incrementsFor;
module.exports.publicView = publicView;
module.exports.developerAuth = developerAuth;
