// Brevo コンタクト追加 API
// register-dl.html から非同期で呼ばれる（失敗許容）
//
// 製品別属性について:
//   Brevo の POST /v3/contacts は updateEnabled:true のとき「送った属性だけ」を
//   上書きし、送らなかった属性はそのまま残る。この性質を利用して、
//   ダウンロードした製品を HAS_STAR / HAS_PORTRAIT / HAS_SKY / HAS_AI に
//   分けて記録する（今回の製品ぶんだけ送る）。
//   従来の PRODUCT 属性は1つしか持てず、2製品目をDLすると1製品目が消えていた。
//   PRODUCT / LEAD_SOURCE は「最新のDL製品・最新の流入元」として互換のため残す。
//
// Brevo 側の事前設定（未作成だと 400 になる）:
//   コンタクト属性を「テキスト」型で作成しておくこと。
//     HAS_STAR / HAS_PORTRAIT / HAS_SKY / HAS_AI
//     VER_STAR / VER_PORTRAIT / VER_SKY / VER_AI
//     LANG
//   tools/create_brevo_attributes.py で一括作成できる。
//   未作成の場合は従来の属性のみで自動リトライするため、DL導線は止まらない。

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

async function postToBrevo(apiKey, payload) {
  const res = await fetch('https://api.brevo.com/v3/contacts', {
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

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { email, firstName, product, productKey, version, lang, leadSource, interest } = req.body || {};
  if (!email) return res.status(400).json({ error: 'email required' });

  const apiKey = process.env.BREVO_API_KEY || '';
  if (!apiKey) {
    console.error('BREVO_API_KEY not set');
    return res.status(200).json({ ok: false, reason: 'no_api_key' });
  }

  // 2026-08-20 以前から Brevo 側に存在する属性。フォールバック時はこれだけを送る。
  const legacyAttributes = {
    FIRSTNAME:   firstName  || '',
    INTEREST:    interest   || 'photography',
    PRODUCT:     product    || '',
    LEAD_SOURCE: leadSource || ''
  };

  // 2026-08-20 に追加した属性。Brevo 側で未作成だと 400 になるため、まとめて扱う。
  const newAttributes = {};

  // 言語は「最後にDLしたページの言語」で上書きしてよい（配信言語の判定に使う）。
  // 不明な値が来た場合は書かない（既存の LANG を壊さないため）。
  if (lang === 'ja' || lang === 'en') newAttributes.LANG = lang;

  // 今回DLした製品ぶんだけを追加する（他製品の HAS_* / VER_* は送らないので残る）
  const suffix = resolveSuffix(productKey, product);
  if (suffix) {
    newAttributes['HAS_' + suffix] = 'yes';
    // バージョン未確定（空文字）のときは書かない。誤った値を残さないため。
    if (version) newAttributes['VER_' + suffix] = String(version);
  } else {
    console.warn('add-contact: unknown product', { product, productKey });
  }

  try {
    let result = await postToBrevo(apiKey, {
      email,
      attributes: Object.assign({}, legacyAttributes, newAttributes),
      updateEnabled: true   // 既存コンタクトは属性を上書き（重複登録しない）
    });

    // 新設属性が Brevo 側に未作成だと 400 になる。
    // その場合は従来の属性だけで再送し、DL導線と既存の記録を守る。
    if (!result.ok && result.status === 400 && Object.keys(newAttributes).length > 0) {
      console.error('Brevo rejected new attributes (要 Brevo 側で属性作成):',
        Object.keys(newAttributes).join(', '), result.body);
      result = await postToBrevo(apiKey, {
        email,
        attributes: legacyAttributes,
        updateEnabled: true
      });
      if (result.ok) {
        return res.status(200).json({ ok: true, degraded: 'new_attributes_missing' });
      }
    }

    if (result.ok) return res.status(200).json({ ok: true });

    console.error('Brevo error:', result.status, result.body);
    // Brevo 失敗でも DL 導線を止めないため 200 を返す
    return res.status(200).json({ ok: false, reason: result.body });

  } catch (err) {
    console.error('add-contact exception:', err.message);
    return res.status(200).json({ ok: false, reason: err.message });
  }
};
