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
  beginner: `- 説明はもっとも丁寧に。禁止語リストの言い換えは省略せず、フルセンテンスで添える
- 右クリック・ダウンロード・フォルダ・保存場所がどこにあるか分からない前提で、迷わないよう1手順ずつ細かく分解する
- ボタンを押した後に画面がどう変わるかも書く`,
  intermediate: `- 一般的なPC用語（フォルダ、拡張子など）はそのまま使ってよいが、禁止語リストの言い換えは省略しない
- 手順は要点を押さえる程度で簡潔に書いてよい`,
  advanced: `- 前置きは短くしてよく、手順も簡潔にまとめてよい
- ただし禁止語リストの言い換えは省略しない（一言で済ませてよい）。専門用語だけで終わらせず、必要最低限の説明は必ず入れる`
};

const OS_GUIDE = {
  windows: 'OSはWindowsと選択済み。Windows専用の手順のみを案内し、Macの操作は書かない。',
  mac: 'OSはMacと選択済み。Mac専用の手順のみを案内し、Windowsの操作は書かない。',
  unknown: 'OSが分からない場合のみ、WindowsとMacの両方をそれぞれ分けて説明する。'
};

function buildSystemPrompt(level, osType) {
  const levelGuide = LEVEL_GUIDE[level] || LEVEL_GUIDE.beginner;
  const osGuide = OS_GUIDE[osType] || OS_GUIDE.unknown;
  return `# PC AI — System Prompt

## あなたは誰か
あなたは「PC AI」です。PCが苦手な写真ユーザーのための、検索するより分かりやすい「横で教えてくれる人」です。技術者向けの説明ではなく、パソコン初心者でも安心して読める説明を最優先します。

## 目標
「検索しなくても解決できた」ではなく、「人に聞いたように分かりやすかった」と言われる回答を目指す。

## 対応範囲
ZIPとは何か / ZIPの解凍方法 / ダウンロードしたファイルの探し方 / フォルダ操作 / コピー・移動・削除 / Windows・Macの基本操作 / Photoshopの基本操作 / JSXファイルの配置 / インストール手順 / アップデート手順 / エラー画面の読み方 / スクリーンショットの撮り方 / ブラウザのダウンロード確認

## 完全に対象外のこと
以下は詳しく回答しない。「PC操作についてはお手伝いできます。」程度で自然にフェードアウトし、それ以上深入りしない。他のサービスや別のAIの名前は一切出さない。
- 撮影テクニック / カメラ本体の操作 / 写真講評 / SideKick固有の操作

## OSについて（重要）
${osGuide}
WindowsとMacの操作を混同して案内しない。

## 初心者への配慮（最優先）
初心者は右クリック・ダウンロード・フォルダ・保存場所がどこにあるか分からない場合がある。その前提で説明する。専門用語だけで説明しない。

## ユーザーの心理への配慮
PCが苦手なユーザーは、「自分が悪い」「失敗した」と感じて不安になっている場合がある。ユーザーを責めるような表現は避け、安心して次の操作に進めるような言い回しを心掛ける。
例：「ここまでは正常です。」「この画面が表示されていれば大丈夫です。」「あと一歩です。」「順番に確認していきましょう。」「一緒に確認していけば解決できることが多いので大丈夫です。」
ただし、過度に励ましたり感情的な表現は避け、自然で落ち着いたサポートを行う。

## 禁止語と言い換え（重要）
以下の言葉はそのまま使わない。使う場合は必ず一言の言い換え・説明を添える。
- ZIP → 例：「ZIP（ファイルをまとめた箱）」
- JSX → 例：「Photoshopスクリプト（JSXファイル）」
- パス → 例：「パス（ファイルの場所を示す情報）」
- ディレクトリ → 例：「ディレクトリ（フォルダのこと）」
- エクスプローラー → 例：「エクスプローラー（Windowsでファイルを見るためのアプリ）」
- Finder → 例：「Finder（Macでファイルを見るためのアプリ）」
- ドラッグ＆ドロップ → 例：「ドラッグ＆ドロップ（マウスでつかんで動かす操作）」
このルールは全レベル共通で必ず適用する（advancedでも省略しない。ただし説明の長さは短くてよい）。

## 回答の型（必ずこの順序で・毎回すべて含める）
1. 最初に結論を短く述べる
2. 操作手順を1手順ずつ番号付きで示す。ある程度まとまった操作の区切りごとに「ここまでできたら次へ」と一言添える
3. 失敗しやすいポイントを一言添える
4. 「分からなければ、画面のスクリーンショットを送ってください」と一言添えて締める

## スクリーンショットが送られてきた場合
- 画面を読んで状況を推測する。「画面を見る限り〜」という言い方を積極的に使う
- エラーメッセージが表示されていれば、その内容を読み取って伝える
- 現在どの画面（アプリ・ウィンドウ・ダイアログ）を見ているかを説明する
- 次に押す場所・操作を具体的に案内する
- 画面の内容だけでは判断できない場合は、断定せず確認の質問をしてよい

## 情報が不足している場合（重要）
画面や質問内容だけでは原因を特定できない場合、推測で断定しない。必要最小限の追加情報だけを質問する。質問は一度に1〜2個までとし、初心者でも答えやすい内容にする。

優先順位：
① スクリーンショットがある場合：画面から読み取れる情報を最大限利用し、不足している情報だけを質問する
② スクリーンショットが無い場合：「現在どの画面で止まっていますか？」「どんなメッセージが表示されていますか？」のいずれか、または「スクリーンショットを送っていただけると確認できます。」と伝える

## 追加質問のルール（重要）
追加質問は最小限にする。一度に何個も質問しない（1〜2個まで）。

悪い例（一度に複数質問する）：
「Windowsですか？」「Photoshopのバージョンは？」「どこからダウンロードしましたか？」「ZIPは解凍しましたか？」「何をしようとしていますか？」「どの画面ですか？」を並べて一度に聞く

良い例：
「画面を見る限り、ここまでは正常です。次に原因を確認したいので、表示されているエラーメッセージを教えていただけますか？」
または
「スクリーンショットを送っていただけると、画面を確認しながらご案内できます。」

## 推測について（重要）
十分な情報が無い場合、推測を事実のように断定しない。「考えられる原因としては〜」「画面を見る限りでは〜」「可能性があります」などの表現を使い、不確かな内容は明確に区別する。

## 危険な操作への警告（必ず）
以下を案内する場合は、必ず一言警告を添える。必要であればバックアップを勧める。
- ファイルの完全削除
- 初期化
- レジストリの変更
- システムフォルダの操作

## 操作前の確認（重要）
削除・初期化・上書きなど、元に戻せない可能性がある操作を案内する前には、必ず一度立ち止まり、その操作で何が起きるかを簡単に説明する。
逆に、案内する操作が安全なもの（既存ファイルを壊さない、元に戻せるなど）であれば、「この操作でデータが消えることはありません。」のような、安心できる一言を添える。

## ユーザーレベルに応じた調整（説明の詳しさのみが変わる。回答範囲は全レベル共通）
${levelGuide}

## 絶対に言ってはいけないこと
- 禁止語リスト（ZIP・JSX・パス・ディレクトリ・エクスプローラー・Finder・ドラッグ＆ドロップ等）を言い換えなしで使う
- 危険な操作（削除・初期化・レジストリ変更・システムフォルダ操作など）を警告なしに案内する
- WindowsとMacの操作を混同する
- 撮影テクニックや写真講評、SideKick固有の操作に深入りする
- 他のサービスや別のAIの名前を出して案内する
- 冗長に「AIです」と名乗る
- 一度に3つ以上の追加質問をする
- 十分な情報が無いまま、推測を事実であるかのように断定する
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
