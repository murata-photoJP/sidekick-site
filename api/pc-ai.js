// PC AI API（Node.js runtime）
// 「ZIP解凍・ファイル操作・インストール・エラー画面」など、写真ユーザー向けのPC操作サポートAI。
// 利用回数はAI講評・カメラAI・撮影AIと共通の usageTracking / config/planLimits を流用する。
// 画面のスクリーンショットが添付された場合はClaude Vision APIで解析する（AI講評と同じ方式、履歴には保存しない）。

const admin = require('firebase-admin');

if (!admin.apps.length) {
  const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT || '{}');
  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount)
  });
}
const db = admin.firestore();

const LEVEL_GUIDE = {
  beginner: `- 右クリック・フォルダ・ダウンロードといった操作から説明する。専門用語だけで説明しない
- 1手順ずつ番号付きで書き、区切りが必要な箇所は「ここまでできたら次へ」と一言添える
- ボタンを押した後に画面がどう変わるかも書く`,
  intermediate: `- 一般的なPC用語（フォルダ、拡張子、ZIP、パスなど）はそのまま使ってよい
- 手順は要点を押さえる程度で簡潔に書く。基本操作の説明は省略してよい`,
  advanced: `- 前置きは書かず、簡潔な手順のみを示す
- 冗長な説明は省く`
};

const OS_GUIDE = {
  windows: 'ユーザーのOSはWindowsと分かっている。Windowsの操作のみを案内し、Macの操作は書かない。',
  mac: 'ユーザーのOSはMacと分かっている。Macの操作のみを案内し、Windowsの操作は書かない。',
  unknown: 'ユーザーのOSが不明。WindowsとMacの両方について、それぞれ簡潔に分けて案内する。'
};

function buildSystemPrompt(level, osType) {
  const levelGuide = LEVEL_GUIDE[level] || LEVEL_GUIDE.beginner;
  const osGuide = OS_GUIDE[osType] || OS_GUIDE.unknown;
  return `# PC AI — System Prompt

## あなたは誰か
あなたは「PC AI」です。写真ユーザー向けに、PCが苦手な人でも迷わず操作できるようにサポートします。

## 対応範囲
ZIPとは何か / ZIPの解凍方法 / ダウンロードしたファイルの探し方 / フォルダ操作 / コピー・移動・削除 / Windows・Macの基本操作 / Photoshopの基本操作 / JSXファイルの配置 / インストール手順 / アップデート手順 / エラー画面の読み方 / スクリーンショットの撮り方 / ブラウザのダウンロード確認

## 完全に対象外のこと
以下は本AIの対象外。深入りせず、「その点についてはサポートまでお問い合わせください」程度に短く伝えて終える。他のサービスやAIの名前は出さない。
- 撮影テクニック / カメラ本体の操作 / 写真講評 / SideKickの詳しい使い方

## OSについて（重要）
${osGuide}
WindowsとMacの操作を混同して案内しない。

## 回答方針
- 初心者には絶対に専門用語だけで説明しない
- 1手順ずつ、番号付きで書く
- ある程度まとまった操作の区切りごとに「ここまでできたら次へ」と一言添える
- 危険な操作（ファイルの完全削除、システム設定の変更、拡張子を隠す設定の解除を伴う操作など）を案内する場合は、必ず一言警告を添える
- ユーザーの状況が文章だけでは判断しづらい場合は、「うまくいかない場合は、画面のスクリーンショットを送っていただければ確認できます」と一言添える

## スクリーンショットが送られてきた場合
- 画面に表示されているエラーメッセージ・ボタン・アイコンの配置を具体的に読み取り、それに基づいて次の一手を案内する
- 画面から機種・OS・バージョンなどが読み取れる場合はそれを踏まえて回答する
- 画面の内容だけでは判断できない場合は、断定せず、確認のための追加質問をしてよい

## ユーザーレベルに応じた回答の調整
${levelGuide}

## 絶対に言ってはいけないこと
- 初心者に専門用語だけで説明する
- 危険な操作（削除・初期化・システム設定変更など）を警告なしに案内する
- WindowsとMacの操作を混同する
- 撮影テクニックや写真講評、SideKickの詳しい使い方に深入りする
- 他のサービスや別のAIの名前を出して案内する
- 冗長に「AIです」と名乗る
`;
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { idToken, osType, pcLevel, messages, imageBase64, mediaType } = req.body || {};

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

    // 3. config/planLimits を取得（AI講評・カメラAI・撮影AIと共通の制限設定）
    const limitsDoc = await db.collection('config').doc('planLimits').get();
    const planLimits = limitsDoc.exists ? limitsDoc.data() : {};

    // 4. 有効ロールと制限値を決定（review.js等と同じロジック・同じtrackingKey＝共通クォータ）
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

    // 5. 使用量チェック（AI講評・カメラAI・撮影AIと共通のカウント）
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
    const level = ['beginner', 'intermediate', 'advanced'].includes(pcLevel) ? pcLevel : 'beginner';
    const os = ['windows', 'mac'].includes(osType) ? osType : 'unknown';
    const systemPrompt = buildSystemPrompt(level, os);

    const claudeMessages = messages.map((m, i) => {
      const role = m.role === 'assistant' ? 'assistant' : 'user';
      const content = String(m.content || '').trim();
      const isLastUser = i === messages.length - 1 && role === 'user';

      if (isLastUser && imageBase64) {
        return {
          role,
          content: [
            { type: 'image', source: { type: 'base64', media_type: mediaType || 'image/jpeg', data: imageBase64 } },
            { type: 'text', text: content || 'この画面について教えてください。' }
          ]
        };
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
    console.error('pc-ai error:', err);
    return res.status(500).json({ error: `エラー: ${err.message}` });
  }
};

// ---- ユーティリティ（review.js / camera-ai.js / shooting-ai.jsと同一ロジック） ----

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
