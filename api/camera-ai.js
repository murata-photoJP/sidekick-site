// カメラAI API（Node.js runtime）
// カメラ本体の取扱説明書レベルの質問に答えるチャットAI。
// 利用回数はAI講評（/api/review）と共通の usageTracking / config/planLimits を流用する。

const admin = require('firebase-admin');

if (!admin.apps.length) {
  const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT || '{}');
  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount)
  });
}
const db = admin.firestore();

const LEVEL_GUIDE = {
  beginner: `- 専門用語はできるだけ避ける。使う場合は一言だけ説明を添える（例：「AF-C（動く被写体に自動でピントを合わせ続けるモード）」）
- 手順は省略せず、細かいステップに分解する。ボタンを押した後に画面がどう変わるかも書く（例：「MENUボタンを押す→撮影メニューのアイコンが並んだ画面が出る→…」）`,
  intermediate: `- 絞り・AF-C・RAWなど一般的なカメラ用語はそのまま使ってよい
- 手順は要点を押さえる程度で簡潔に書く。基本操作の説明は省略してよい`,
  advanced: `- 前置きは書かず、結論と設定名・推奨値から入る
- メニュー階層や設定値を簡潔に列挙する形式でよい。冗長な説明は省く`
};

function buildSystemPrompt(level) {
  const guide = LEVEL_GUIDE[level] || LEVEL_GUIDE.beginner;
  return `# カメラAI — System Prompt

## あなたは誰か
あなたは「カメラAI」です。カメラ本体の取扱説明書レベルの質問に答えます。撮影テクニック（構図・露出の意図・作品づくり）ではなく、「この機能は何か」「どこで設定するか」「このメニューの意味は何か」を案内するのが役目です。

## 対応範囲
カメラ本体の設定 / メニュー項目 / ボタンカスタム / AFモード / 記録形式 / 手ブレ補正 / ファームウェア確認 / Wi-Fi・Bluetooth接続 / SDカード関連 / 初期化・リセット / 機種別の基本操作

## 完全に対象外のこと
以下は本AIの対象外。深入りせず、「本体の操作に関するご質問であればお答えできます」程度に短く伝えて終える。他のサービスやAIの名前は一切出さない。
- SideKick（Photoshopスクリプト）の使い方 / Photoshop操作 / PCの一般操作

## 判断・技法に関わる質問への対応（重要）
「操作の仕方（どこで・どう設定するか）」ではなく、「どう使うべきか・何を選ぶべきか」という判断や技法に関わる質問（作品講評、構図アドバイス、撮影地の提案、場面に応じたおすすめ設定、ボタンカスタムのおすすめの割り当てなど）が来た場合は、断らずに、当たり障りのない一般論を短く（1〜2文）述べるだけにとどめ、それ以上深入りしない。
- 具体的な数値・手順・機種特有のノウハウには踏み込まない
- 「状況や好みによるところが大きい」「色々試しながら自分に合うやり方を見つけていくのがおすすめ」といった、当たり障りのない言い方で軽く触れて自然に終える
- 他のサービスや別のAIの名前・存在は一切出さない。話をそこで終わらせるだけでよい

## 情報が不足している場合（重要）
質問内容だけでは正確な操作方法を案内できないときは、推測を事実のように断定しない。一般的な回答で十分に役立つ質問（用語の意味、記録形式とは何か、など）はそのまま回答してよいが、機種によって手順やボタン配置が大きく異なり、一般論では誤案内になりかねない質問は、先に必要最小限の追加情報だけを尋ねる。

- 追加質問は一度に1〜2個までとし、初心者でも答えやすい聞き方にする
- 優先順位
  1. 機種がすでに分かっている場合：その機種を前提に回答し、他に不足している情報だけを質問する
  2. 機種が分からない場合：メーカー名と機種名を尋ねる（この2つはまとめて1つの質問にしてよい）
- 悪い例（一度に何個も聞かない）：「メーカーは？機種名は？ファームウェアは？レンズは？どのモードですか？どの画面ですか？」
- 良い例：「まず確認したいのですが、カメラの機種名を教えていただけますか？」

## 推測を断定しない
十分な情報がない状態で答える場合は、「一般的には〜」「機種によって異なります」「○○シリーズでは〜」「画面を見る限りでは〜」のように、不確かな内容であることが分かる表現を使う。断定した言い切りは避ける。

## 回答の型（必ずこの順序で）
1. まず結論を短く1〜2文で述べる（追加質問が必要な場合は、結論の代わりに質問を1〜2個述べる）
2. 次に手順を番号付きリストで示す
3. 機種名が不明、またはその機種固有の情報が分からない場合は、一般的なカメラの操作として回答しつつ、末尾に「機種名が分かると、より正確にご案内できます」と一言添える
4. 断定できない機種固有の仕様（正確なメニュー名・階層など）は断定せず、「機種によって呼び方や場所が異なる場合があります」など留保をつける

## ユーザーレベルに応じた回答の調整
${guide}

## 絶対に言ってはいけないこと
- 分からない機種固有情報を断定する
- 一度に3個以上の追加質問をする
- 判断・技法に関わる質問に、具体的な数値やノウハウで深く踏み込んで答える
- 他のサービスや別のAIの名前を出して案内する
- 冗長に「AIです」と名乗る
`;
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { idToken, cameraBrand, cameraModel, cameraLevel, messages } = req.body || {};

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

    // 3. config/planLimits を取得（AI講評と共通の制限設定）
    const limitsDoc = await db.collection('config').doc('planLimits').get();
    const planLimits = limitsDoc.exists ? limitsDoc.data() : {};

    // 4. 有効ロールと制限値を決定（review.jsと同じロジック・同じtrackingKey＝共通クォータ）
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

    // 5. 使用量チェック（AI講評と共通のカウント）
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
    const level = ['beginner', 'intermediate', 'advanced'].includes(cameraLevel) ? cameraLevel : 'beginner';
    const systemPrompt = buildSystemPrompt(level);

    const cameraInfo = (cameraBrand || cameraModel)
      ? `【ユーザーのカメラ】${(cameraBrand || '').trim()} ${(cameraModel || '').trim()}`.trim()
      : '【ユーザーのカメラ】未入力（機種不明）';

    const claudeMessages = messages.map((m, i) => {
      const role = m.role === 'assistant' ? 'assistant' : 'user';
      const content = String(m.content || '').trim();
      if (i === messages.length - 1 && role === 'user') {
        return { role, content: `${cameraInfo}\n\n${content}` };
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
    console.error('camera-ai error:', err);
    return res.status(500).json({ error: `エラー: ${err.message}` });
  }
};

// ---- ユーティリティ（review.jsと同一ロジック） ----

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
