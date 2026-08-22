// ダウンロード登録 API（Firestore への記録 + Brevo へのコンタクト登録）
// register-dl.html から呼ばれる。
//
// 2026-08-22 の変更:
//   以前は register-dl.html がブラウザから直接 Firestore に書いていたが、
//   その方式は「匿名認証 → セキュリティルールの request.auth != null」に依存していた。
//   Firebase の匿名認証プロバイダが有効になっておらず（Google のみ登録）、
//   signInAnonymously() が auth/admin-restricted-operation で失敗し続けた結果、
//   書き込みが permission-denied で拒否されていた。
//   クライアント側は失敗を握りつぶす作りだったため、誰も気づけなかった。
//
//   そこで Firestore への書き込みをサーバー側（Admin SDK）へ移した。
//   Admin SDK はセキュリティルールを通らないため、匿名認証もルールも不要になる。
//   ブラウザに Firestore の書き込み権限を持たせる必要そのものが無くなった。
//
// 失敗時もレスポンスは 200 を返す（DL 導線を止めないため）が、
// **どちらが失敗したかを必ずレスポンスとログに残す**。
// 以前のように無言で消えることはない。
//
// Brevo 側の事前設定（未作成だと 400 になる）:
//   コンタクト属性を「テキスト」型で作成しておくこと。
//     HAS_STAR / HAS_PORTRAIT / HAS_SKY / HAS_AI
//     VER_STAR / VER_PORTRAIT / VER_SKY / VER_AI
//     LANG / INTEREST / PRODUCT / LEAD_SOURCE
//   tools/create_brevo_attributes.py で一括作成できる。
//   未作成の場合は従来の属性のみで自動リトライするため、DL導線は止まらない。

const admin = require('firebase-admin');

const BREVO_API = 'https://api.brevo.com/v3/contacts';

// productKey（star / portrait / sky / ai）→ Brevo 属性のサフィックス
const PRODUCT_SUFFIX = {
  star:     'STAR',
  portrait: 'PORTRAIT',
  sky:      'SKY',
  ai:       'AI'
};

// productKey が来なかった場合（キャッシュされた旧 register-dl.html 等）の保険
const PRODUCT_NAME_TO_KEY = {
  'Sidekick_Star':     'star',
  'Sidekick_Portrait': 'portrait',
  'Sidekick_SkyEffect':'sky',
  'Sidekick_AI':       'ai'
};

function resolveSuffix(productKey, product) {
  const key = productKey || PRODUCT_NAME_TO_KEY[product] || '';
  return PRODUCT_SUFFIX[key] || '';
}

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

async function recordDownload(body) {
  const db = getFirestore();
  if (!db) return { ok: false, reason: 'firestore_unavailable' };

  const lang = (body.lang === 'ja' || body.lang === 'en') ? body.lang : '';
  const source = body.leadSource || 'direct';

  try {
    const ref = await db.collection('downloads').add({
      // 匿名認証をやめたため uid は無い。既存レコードと同じ形を保つ。
      userId: 'email-' + Date.now(),
      email: body.email,
      productName: body.product || '',
      downloadedAt: admin.firestore.FieldValue.serverTimestamp(),
      version: body.version || '',
      lang: lang,
      sourcePage: source,
      leadSource: source,
      consentVersion: body.consentVersion || '',
      consentedAt: body.consentedAt || new Date().toISOString(),
      authMethod: 'email-only'
    });
    return { ok: true, id: ref.id };
  } catch (err) {
    console.error('Firestore write failed:', err.message);
    return { ok: false, reason: err.message };
  }
}

// --------------------------------------------------------------------
// Brevo
// --------------------------------------------------------------------
async function postToBrevo(apiKey, payload) {
  const res = await fetch(BREVO_API, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'api-key': apiKey
    },
    body: JSON.stringify(payload)
  });
  // 201 Created または 204 No Content（既存更新）が成功
  const ok = res.status === 201 || res.status === 204;
  const body = ok ? '' : await res.text();
  return { ok, status: res.status, body };
}

async function upsertContact(body) {
  const apiKey = process.env.BREVO_API_KEY || '';
  if (!apiKey) {
    console.error('BREVO_API_KEY not set');
    return { ok: false, reason: 'no_api_key' };
  }

  // 2026-08-20 以前から Brevo 側に存在する属性。フォールバック時はこれだけを送る。
  const legacyAttributes = {
    FIRSTNAME:   body.firstName  || '',
    INTEREST:    body.interest   || 'photography',
    PRODUCT:     body.product    || '',
    LEAD_SOURCE: body.leadSource || ''
  };

  // 2026-08-20 に追加した属性。Brevo 側で未作成だと 400 になるため、まとめて扱う。
  const newAttributes = {};

  // 言語は「最後にDLしたページの言語」で上書きしてよい（配信言語の判定に使う）。
  // 不明な値が来た場合は書かない（既存の LANG を壊さないため）。
  if (body.lang === 'ja' || body.lang === 'en') newAttributes.LANG = body.lang;

  // 今回DLした製品ぶんだけを追加する（他製品の HAS_* / VER_* は送らないので残る）
  const suffix = resolveSuffix(body.productKey, body.product);
  if (suffix) {
    newAttributes['HAS_' + suffix] = 'yes';
    // バージョン未確定（空文字）のときは書かない。誤った値を残さないため。
    if (body.version) newAttributes['VER_' + suffix] = String(body.version);
  } else {
    console.warn('add-contact: unknown product', {
      product: body.product, productKey: body.productKey });
  }

  try {
    let result = await postToBrevo(apiKey, {
      email: body.email,
      attributes: Object.assign({}, legacyAttributes, newAttributes),
      updateEnabled: true   // 既存コンタクトは属性を上書き（重複登録しない）
    });

    // 新設属性が Brevo 側に未作成だと 400 になる。
    // その場合は従来の属性だけで再送し、DL導線と既存の記録を守る。
    if (!result.ok && result.status === 400 && Object.keys(newAttributes).length > 0) {
      console.error('Brevo rejected new attributes (要 Brevo 側で属性作成):',
        Object.keys(newAttributes).join(', '), result.body);
      result = await postToBrevo(apiKey, {
        email: body.email,
        attributes: legacyAttributes,
        updateEnabled: true
      });
      if (result.ok) return { ok: true, degraded: 'new_attributes_missing' };
    }

    if (result.ok) return { ok: true };

    console.error('Brevo error:', result.status, result.body);
    return { ok: false, reason: result.body };

  } catch (err) {
    console.error('Brevo exception:', err.message);
    return { ok: false, reason: err.message };
  }
}

// --------------------------------------------------------------------
module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const body = req.body || {};
  if (!body.email) return res.status(400).json({ error: 'email required' });

  // Firestore が正、Brevo は配信のための投影。
  // 片方が落ちてももう片方は実行する。どちらもDL導線は止めない。
  const [firestore, brevo] = await Promise.all([
    recordDownload(body),
    upsertContact(body)
  ]);

  if (!firestore.ok || !brevo.ok) {
    console.error('add-contact partial failure:', {
      firestore: firestore.ok ? 'ok' : firestore.reason,
      brevo: brevo.ok ? 'ok' : brevo.reason
    });
  }

  // DL 導線を止めないため常に 200。ただし内訳は必ず返す。
  return res.status(200).json({
    ok: firestore.ok && brevo.ok,
    firestore: firestore.ok ? 'ok' : 'failed',
    brevo: brevo.ok ? (brevo.degraded ? brevo.degraded : 'ok') : 'failed'
  });
};
