// Sidekick Planner Activity raw event の定期 cleanup（HD-PLANNERACTIVITY-012、2026-09-19、AI-6215）
//
// Firestore TTL は Blaze（billing）前提で β1.00 では使わない。代わりに Vercel Cron（Hobby、1 日 1 回、
// vercel.json の crons）がこの endpoint を GET し、`planner_activity_events` のうち
// `expire_at <= now` の document だけを削除する（expire_at = at + 425 日は api/planner-activity.js が書く）。
//
// 守ること:
//   - 削除するのは planner_activity_events だけ。planner_activity_daily / planner_activity_totals には触れない。
//   - 条件は expire_at <= now だけ。where 無しの delete を書かない（全消し経路を作らない）。
//   - 500 件単位（Firestore batch の上限）、1 回の実行で最大 MAX_BATCHES 回。何度走っても同じ結果（冪等）。
//   - Activity 本体（api/planner-activity.js）から独立。ここが止まっても raw が増えるだけで製品・公開 Activity に影響しない。
//   - CRON_SECRET（Vercel env）が無い／合わないときは何もしない。Vercel Cron は Authorization: Bearer <CRON_SECRET> を付ける。
//
// smoke test: Human が console で作った planner_activity_events/ttl-bootstrap（expire_at 過去）が最初の実行で消える。
// share.html（Viewer beacon）の production 配置はその確認後（HD-012 第7項）。

const admin = require('firebase-admin');

const COLLECTION = 'planner_activity_events';
const BATCH_SIZE = 500;
const MAX_BATCHES = 10;

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

// Vercel Cron の Authorization header を CRON_SECRET と照合する。secret 未設定は「実行しない」（fail-closed for cleanup）。
function authorized(req, secret) {
  if (!secret) return false;
  const header = (req.headers && (req.headers.authorization || req.headers.Authorization)) || '';
  return header === 'Bearer ' + secret;
}

// expire_at <= now の raw を 1 batch（最大 BATCH_SIZE 件）消す。消した件数を返す。
async function deleteExpiredBatch(db, now) {
  const snap = await db.collection(COLLECTION)
    .where('expire_at', '<=', now)
    .orderBy('expire_at', 'asc')
    .limit(BATCH_SIZE)
    .get();
  if (snap.empty) return 0;
  const batch = db.batch();
  let n = 0;
  snap.forEach((doc) => { batch.delete(doc.ref); n += 1; });
  await batch.commit();
  return n;
}

async function cleanupExpired(db, now) {
  let deleted = 0;
  let batches = 0;
  while (batches < MAX_BATCHES) {
    const n = await deleteExpiredBatch(db, now);
    batches += 1;
    deleted += n;
    if (n < BATCH_SIZE) break;
  }
  return { deleted, batches, exhausted: batches >= MAX_BATCHES };
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    return res.status(405).end();
  }
  const secret = process.env.CRON_SECRET || '';
  if (!secret) {
    console.error('planner-activity-cleanup: CRON_SECRET not configured; nothing done');
    return res.status(503).json({ ok: false, reason: 'cron_secret_not_configured' });
  }
  if (!authorized(req, secret)) {
    return res.status(401).json({ ok: false, reason: 'unauthorized' });
  }
  const db = getFirestore();
  if (!db) return res.status(503).json({ ok: false, reason: 'firestore_unavailable' });
  const now = admin.firestore.Timestamp.fromDate(new Date());
  try {
    const result = await cleanupExpired(db, now);
    console.log('planner-activity-cleanup:', JSON.stringify(result));
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json({ ok: true, collection: COLLECTION, ...result });
  } catch (err) {
    console.error('planner-activity-cleanup failed:', err.message);
    return res.status(500).json({ ok: false, reason: 'cleanup_failed' });
  }
};

module.exports.COLLECTION = COLLECTION;
module.exports.BATCH_SIZE = BATCH_SIZE;
module.exports.MAX_BATCHES = MAX_BATCHES;
module.exports.authorized = authorized;
module.exports.cleanupExpired = cleanupExpired;
