// 写真講評 API（Node.js runtime）
// Firebase Admin でトークン検証・Firestore でロール確認・使用量管理・imageCache

const admin = require('firebase-admin');

if (!admin.apps.length) {
  const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT || '{}');
  admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
}
const db = admin.firestore();

const SYSTEM_PROMPT = `# 村田一朗AI — System Prompt（v2.0）

## あなたは誰か
あなたは写真家・村田一朗です。PHOTODAYSというオンライン写真講座で、構図・星景・波・ポートレートを中心に、数百名の受講生に写真指導を行ってきました。
フレンドリーで率直、時に厳しく、しかし受講生を見捨てない。「頑張ってやってみてください。きっと出来ます。」という姿勢が根底にあります。

## 画面座標の定義（最重要）
写真画面を3×3のグリッドで9分割し、以下の記号で位置を指定する。

- A〜I：画面の9つの領域（Aが左上、Iが右下）
- ①〜④：三分割線の4つの交点
  - ①：左上の交点、②：右上の交点、③：左下の交点、④：右下の交点

## 指導の絶対原則
1. 第三者の目線が全て。「撮った本人しか判らない写真はダメ」
2. 引き算の哲学。不要なものは徹底的に排除する
3. 主題と副題。主題は必ず三分割の交点（①〜④）に置く
4. 三分割構図。強い線は三分割線に乗せる。画面が割れるのは初歩的なミス
5. 露出と構図は不可分。黒潰れ・白飛びに気を配る
6. レタッチは「失敗を救うため」ではなく「撮れないことをやる」ため

## よくあるNGとその指摘
| 問題 | 村田の言い方 |
|------|------------|
| 画面が上下に割れている | 「画面が上下に割れてしまって、何を見たらいいか判らない写真になっています」 |
| 黒潰れが大きい | 「これだけ大きな黒潰れは、情報が皆無なのに面積だけ大きく、目を引いてしまいます」 |
| 不要なものが写っている | 「この○○は必要ですか？どこが魅力的ですか？無意味なら引き算すべきです」 |
| 主題が弱い | 「第三者は○○の方に目が行ってしまい、本来の主題が見えなくなっています」 |

## 写真を見て添削する場合の手順
1. まず全体を見る：何が一番目立つか？
2. 割れていないか確認：画面が上下または左右に二分割されていないか
3. 主題を確認：何が主題か？それは交点に置かれているか？
4. 引き算できているか：不要なもの、中途半端に入っているものはないか
5. 露出は適切か：潰れている部分が無意味な空間になっていないか
6. 良い点を先に言う（または「もったいない」から入る）
7. 最重要の問題点を1〜2点に絞って指摘（全部言わない）
8. 「この調子で頑張ってください」「引き続き頑張ってくださいね」で締める

## 口調・スタイル
- 丁寧語だが親しみやすい。「ですよ」「ですね」「ますよ」調
- 問いかけ形式を多用：「なぜこれが必要なのか？」「どこが魅力的ですか？」
- 否定より「惜しい」「もったいない」で入ることが多い
- 「・・・」を多用（考えながら話すニュアンス）
- 写真の領域（A〜I）を使って具体的に指摘する
- 絵文字は使わない

## 出力について
- **文字数は200〜400字**
- コメント文のみを出力する。前置き不要
- 受講生（または一般ユーザー）が読む文章として書く
- 「AIです」と名乗らない
- 「完璧です」「文句なしです」と言い切らない

## 絶対に言ってはいけないこと
- 「AIです」と名乗らない
- 「完璧です」「文句なしです」と言い切らない
- 受講生の思い入れを否定しない（ただし「第三者には伝わらない」と伝える）
`;

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { idToken, imageBase64, imageHash, mediaType, comment, marketingConsent, creditConsent } = req.body || {};

    // boolean 正規化（フロントから truthy 値が来ても安全に処理）
    const normalizedMarketingConsent = marketingConsent === true;
    const normalizedCreditConsent = normalizedMarketingConsent && creditConsent === true;

    if (!idToken || !imageBase64) {
      return res.status(400).json({ error: 'idToken と imageBase64 は必須です' });
    }

    // 1. Firebase ID トークン検証
    let uid;
    try {
      const decoded = await admin.auth().verifyIdToken(idToken);
      uid = decoded.uid;
    } catch {
      return res.status(401).json({ error: '認証エラー。再ログインしてください。' });
    }

    // 2. ユーザーの roles を取得
    const userDoc = await db.collection('users').doc(uid).get();
    const roles = (userDoc.exists && userDoc.data().roles) || ['free'];

    // 3. config/planLimits を取得
    const limitsDoc = await db.collection('config').doc('planLimits').get();
    const planLimits = limitsDoc.exists ? limitsDoc.data() : {};

    // 4. 有効ロールと制限値を決定
    const effectiveRole = getHighestRole(roles);
    const now = new Date();
    const campaignEnd = planLimits.campaignEndDate
      ? new Date(planLimits.campaignEndDate)
      : new Date('2026-08-31');

    let limit, trackingKey;
    if (now < campaignEnd) {
      const weekKey = getWeekKey(now);
      trackingKey = `${uid}_${weekKey}`;
      const val = planLimits[effectiveRole]?.weeklyReviews;
      limit = (val && val !== 'TBD') ? val : (planLimits.free_campaign?.weeklyReviews ?? 5);
    } else if (effectiveRole === 'free') {
      const monthKey = getMonthKey(now);
      trackingKey = `${uid}_${monthKey}`;
      limit = planLimits.free_after?.monthlyReviews ?? 5;
    } else {
      const weekKey = getWeekKey(now);
      trackingKey = `${uid}_${weekKey}`;
      const val = planLimits[effectiveRole]?.weeklyReviews;
      limit = (val && val !== 'TBD') ? val : (planLimits.free_after?.monthlyReviews ?? 5);
    }

    // 5. 使用量チェック
    const usageRef = db.collection('usageTracking').doc(trackingKey);
    const usageDoc = await usageRef.get();
    const usedCount = usageDoc.exists ? (usageDoc.data().count || 0) : 0;

    if (usedCount >= limit) {
      const isWeekly = trackingKey.includes('-W');
      return res.status(429).json({
        error: `今${isWeekly ? '週' : '月'}の講評枚数上限（${limit}枚）に達しました。${isWeekly ? '月曜日' : '翌月1日'}にリセットされます。`,
        limit,
        count: usedCount
      });
    }

    // 6. imageCache チェック（同一画像は Claude を呼ばない）
    if (imageHash) {
      const cacheDoc = await db.collection('imageCache').doc(imageHash).get();
      if (cacheDoc.exists) {
        // キャッシュヒット：使用量だけカウントして返す
        // NOTE: キャッシュヒット時は新しい review ドキュメントを作成しないため、
        // marketingConsent / creditConsent は記録されない。
        // 同意履歴を厳密に残す必要が生じた場合は、ここでも reviewRef.set() を呼ぶこと。
        await Promise.all([
          db.collection('imageCache').doc(imageHash).update({
            hitCount: admin.firestore.FieldValue.increment(1)
          }),
          usageRef.set({
            userId: uid,
            count: admin.firestore.FieldValue.increment(1),
            updatedAt: admin.firestore.FieldValue.serverTimestamp()
          }, { merge: true })
        ]);
        return res.status(200).json({ result: cacheDoc.data().aiReview, cached: true });
      }
    }

    // 7. Claude Haiku Vision API 呼び出し
    const apiKey = process.env.ANTHROPIC_API_KEY || '';
    if (!apiKey) return res.status(500).json({ error: 'サーバー設定エラー' });

    const userText = `以下の写真を村田一朗として講評してください。

【撮影者のコメント・質問】
${(comment || '').trim() || '（なし）'}

写真を見て、構図・露出・主題の明確さなどの観点から講評をお願いします。`;

    const claudeRes = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 800,
        system: SYSTEM_PROMPT,
        messages: [{
          role: 'user',
          content: [
            {
              type: 'image',
              source: { type: 'base64', media_type: mediaType || 'image/jpeg', data: imageBase64 }
            },
            { type: 'text', text: userText }
          ]
        }]
      })
    });

    if (!claudeRes.ok) {
      const errText = await claudeRes.text();
      return res.status(500).json({ error: `APIエラー: ${errText}` });
    }

    const claudeData = await claudeRes.json();
    const reviewText = claudeData.content?.[0]?.text || '';

    // 8. Firestore に保存（review + imageCache + usageTracking）
    const reviewRef = db.collection('reviews').doc();
    const serverTs = admin.firestore.FieldValue.serverTimestamp();

    await Promise.all([
      reviewRef.set({
        userId: uid,
        imageHash: imageHash || null,
        thumbnailUrl: null,
        aiReview: reviewText,
        murataNote: null,
        murataReviewedAt: null,
        tags: [],
        genre: 'other',
        userComment: comment || '',
        marketingConsent: normalizedMarketingConsent,
        creditConsent: normalizedCreditConsent,
        consentVersion: '2026-06-25',
        createdAt: serverTs
      }),
      imageHash
        ? db.collection('imageCache').doc(imageHash).set({
            reviewId: reviewRef.id,
            aiReview: reviewText,
            createdAt: serverTs,
            hitCount: 0
          })
        : Promise.resolve(),
      usageRef.set({
        userId: uid,
        count: admin.firestore.FieldValue.increment(1),
        updatedAt: serverTs
      }, { merge: true })
    ]);

    return res.status(200).json({ result: reviewText, reviewId: reviewRef.id });

  } catch (err) {
    console.error('review error:', err);
    return res.status(500).json({ error: `エラー: ${err.message}` });
  }
};

// ---- ユーティリティ ----

function getHighestRole(roles) {
  const PRIORITY = ['admin', 'paid_member', 'salon_member', 'sidekick_user', 'workshop_user', 'free'];
  for (const r of PRIORITY) {
    if (roles.includes(r)) return r;
  }
  return 'free';
}

function getWeekKey(date) {
  // ISO週番号（月曜始まり）
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(weekNo).padStart(2, '0')}`;
}

function getMonthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}
