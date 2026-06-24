// Brevo コンタクト追加 API
// register-dl.html から非同期で呼ばれる（失敗許容）

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { email, firstName, product, leadSource, interest } = req.body || {};
  if (!email) return res.status(400).json({ error: 'email required' });

  const apiKey = process.env.BREVO_API_KEY || '';
  if (!apiKey) {
    console.error('BREVO_API_KEY not set');
    return res.status(200).json({ ok: false, reason: 'no_api_key' });
  }

  try {
    const payload = {
      email,
      attributes: {
        FIRSTNAME:   firstName  || '',
        INTEREST:    interest   || 'photography',
        PRODUCT:     product    || '',
        LEAD_SOURCE: leadSource || ''
      },
      updateEnabled: true   // 既存コンタクトは属性を上書き（重複登録しない）
    };

    const brevoRes = await fetch('https://api.brevo.com/v3/contacts', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'api-key': apiKey
      },
      body: JSON.stringify(payload)
    });

    // 201 Created または 204 No Content（既存更新）が成功
    if (brevoRes.status === 201 || brevoRes.status === 204) {
      return res.status(200).json({ ok: true });
    }

    const body = await brevoRes.text();
    console.error('Brevo error:', brevoRes.status, body);
    // Brevo 失敗でも DL 導線を止めないため 200 を返す
    return res.status(200).json({ ok: false, reason: body });

  } catch (err) {
    console.error('add-contact exception:', err.message);
    return res.status(200).json({ ok: false, reason: err.message });
  }
};
