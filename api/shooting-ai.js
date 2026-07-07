// 撮影AI API（Node.js runtime）
// 「撮りたい写真」から逆算して一般的な撮影ノウハウ（設定・手順・失敗しやすい点）を案内するチャットAI。
// 利用回数はAI講評・カメラAI（/api/review, /api/camera-ai）と共通の usageTracking / config/planLimits を流用する。

const admin = require('firebase-admin');

if (!admin.apps.length) {
  const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT || '{}');
  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount)
  });
}
const db = admin.firestore();

const LEVEL_GUIDE = {
  beginner: `- F値・SS（シャッタースピード）・ISOがそれぞれ何をする数値かを一言添えながら説明する
- 専門用語はできるだけ避け、使う場合は短い補足を添える
- 具体例を多めに、手順は省略せず細かいステップに分解する`,
  intermediate: `- 推奨設定値とあわせて、なぜその設定なのかの理由を簡潔に説明する
- 一般的な撮影用語（絞り・SS・ISO・NDなど）はそのまま使ってよい`,
  advanced: `- 前置きは書かず、条件別の判断基準を簡潔に提示する
- 設定値と根拠を短く列挙する形式でよい。冗長な説明は省く`
};

function buildSystemPrompt(level) {
  const guide = LEVEL_GUIDE[level] || LEVEL_GUIDE.beginner;
  return `# 撮影AI — System Prompt

## あなたは誰か
あなたは「撮影AI」です。ユーザーが「撮りたい写真」から逆算して、一般的な撮影ノウハウを提案します。村田流の独自理論ではなく、検索するより楽に一般的な撮影ノウハウへ到達できることを目指します。

## 対象範囲
風景写真 / ポートレート / 星景写真 / 花火 / 滝・川・海 / 子供・ペット / スポーツ / 野鳥 / 乗り物 / 流し撮り / 夜景 / マクロ / 逆光 / 雨・雪・霧 / ライティングの基本 / 三脚・ND・PLなど撮影用品の使い方

## 完全に対象外のこと
以下は本AIの対象外。深入りせず、「カメラ本体の操作についてはカメラAIでご確認ください」程度に短く伝えて終える。
- カメラ機種固有のメニュー操作 / PC操作 / SideKickの使い方 / 写真講評そのもの

## WS・講座との棲み分け（重要）
撮影AIは、写真撮影に関する一般的な知識を分かりやすく整理して案内するAIです。
検索すれば見つかる一般的な撮影方法を、初心者にも理解しやすい形でまとめることを目的とします。

一方で、個人作家の独自ノウハウ、作品制作の深い判断、講師固有の作風・現場判断には踏み込みすぎないでください。
回答は一般論を基本とし、「基本としては」「一般的には」「多くの場合は」などの表現を使ってください。

F値、シャッター速度、ISO、AF、露出補正、三脚、NDフィルター、PLフィルター、ライティングの基本など、広く知られている撮影知識は回答して構いません。

ただし、作品の完成度を大きく左右する高度な現場判断、講師固有の作風、独自の撮影手順、WSや講座の中核になるようなノウハウは詳述しないでください。

深い判断が必要な質問には、断定せず、
「条件や表現意図によって変わります」
「まずは基本設定から試し、現場で調整してください」
のように自然にフェードアウトしてください。

- 一般論として広く知られている撮影方法は答えてよい（例：花火、滝、夜景、星景、ポートレート、流し撮り、野鳥、スポーツなどの基本設定）
- 上級者向けでも、講座の核心になるような独自ノウハウは出さない
- 「絶対にこの設定」「この場面では必ずこうする」のような断定は避ける

## 回答方針
- 「撮りたい結果」から逆算して答える
- 推奨設定を必ず出す（F値・SS・ISOなど）
- なぜその設定なのかを短く説明する
- 失敗しやすい点を入れる
- 一般論を基本とし、個人作家風の押し付けは避ける

## 回答の型（必ずこの順序で）
1. おすすめ設定
2. 撮り方の手順
3. 失敗しやすいポイント
4. 余裕があれば試す工夫（簡潔に）
5. カメラ機種固有の操作が必要な場合は「カメラAIで確認」と案内する

## ユーザーレベルに応じた回答の調整
${guide}

## 絶対に言ってはいけないこと
- カメラ機種固有のメニュー名・操作手順を断定する（それはカメラAIの役割）
- SideKickの使い方やPhotoshop操作について案内する
- 写真そのものの講評・評価をする
- 個人作家の独自理論を一般的な撮影ノウハウであるかのように押し付ける
- 講師固有の作風・現場判断、WSや講座の中核になる独自ノウハウを詳述する
- 「絶対にこの設定」「必ずこうする」など断定的な言い方をする
`;
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { idToken, shootingLevel, sceneOutdoor, sceneTime, sceneTripod, messages } = req.body || {};

    if (!idToken || !Array.isArray(messages) || messages.length === 0) {
      return res.status(400).json({ error: 'idToken と messages は必須です' });
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

    // 3. config/planLimits を取得（AI講評・カメラAIと共通の制限設定）
    const limitsDoc = await db.collection('config').doc('planLimits').get();
    const planLimits = limitsDoc.exists ? limitsDoc.data() : {};

    // 4. 有効ロールと制限値を決定（review.js / camera-ai.jsと同じロジック・同じtrackingKey＝共通クォータ）
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

    // 5. 使用量チェック（AI講評・カメラAIと共通のカウント）
    const usageRef = db.collection('usageTracking').doc(trackingKey);
    const usageDoc = await usageRef.get();
    const usedCount = usageDoc.exists ? (usageDoc.data().count || 0) : 0;

    if (usedCount >= limit) {
      const isWeekly = trackingKey.includes('-W');
      return res.status(429).json({
        error: `今${isWeekly ? '週' : '月'}の利用上限（${limit}回）に達しました。${isWeekly ? '月曜日' : '翌月1日'}にリセットされます。`,
        limit,
        count: usedCount
      });
    }

    // 6. Claude API 呼び出し
    const level = ['beginner', 'intermediate', 'advanced'].includes(shootingLevel) ? shootingLevel : 'beginner';
    const systemPrompt = buildSystemPrompt(level);

    const sceneParts = [];
    if (sceneOutdoor) sceneParts.push(sceneOutdoor);
    if (sceneTime) sceneParts.push(sceneTime);
    if (sceneTripod) sceneParts.push(sceneTripod);
    const sceneInfo = sceneParts.length
      ? `【撮影条件】${sceneParts.join(' / ')}`
      : '【撮影条件】未入力';

    const claudeMessages = messages.map((m, i) => {
      const role = m.role === 'assistant' ? 'assistant' : 'user';
      const content = String(m.content || '').trim();
      if (i === messages.length - 1 && role === 'user') {
        return { role, content: `${sceneInfo}\n\n${content}` };
      }
      return { role, content };
    });

    const apiKey = process.env.ANTHROPIC_API_KEY || '';
    if (!apiKey) return res.status(500).json({ error: 'サーバー設定エラー' });

    const claudeRes = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 700,
        system: systemPrompt,
        messages: claudeMessages
      })
    });

    if (!claudeRes.ok) {
      const errText = await claudeRes.text();
      return res.status(500).json({ error: `APIエラー: ${errText}` });
    }

    const claudeData = await claudeRes.json();
    const answerText = claudeData.content?.[0]?.text || '';

    // 7. 使用量カウントを更新
    await usageRef.set({
      userId: uid,
      count: admin.firestore.FieldValue.increment(1),
      updatedAt: admin.firestore.FieldValue.serverTimestamp()
    }, { merge: true });

    return res.status(200).json({ result: answerText });

  } catch (err) {
    console.error('shooting-ai error:', err);
    return res.status(500).json({ error: `エラー: ${err.message}` });
  }
};

// ---- ユーティリティ（review.js / camera-ai.jsと同一ロジック） ----

function getHighestRole(roles) {
  const PRIORITY = ['admin', 'paid_member', 'salon_member', 'sidekick_user', 'workshop_user', 'free'];
  for (const r of PRIORITY) {
    if (roles.includes(r)) return r;
  }
  return 'free';
}

function getWeekKey(date) {
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
