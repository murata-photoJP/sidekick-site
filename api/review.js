export const config = { runtime: 'edge' };

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

export default async function handler(req) {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  try {
    const formData = await req.formData();
    const password = formData.get('password') || '';
    const comment = formData.get('comment') || '';
    const imageFile = formData.get('image');

    // パスワード検証
    const correctPassword = process.env.ACCESS_PASSWORD || '';
    if (!correctPassword || password !== correctPassword) {
      return new Response(JSON.stringify({ error: 'パスワードが違います' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const apiKey = process.env.ANTHROPIC_API_KEY || '';
    if (!apiKey) {
      return new Response(JSON.stringify({ error: 'サーバー設定エラー' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // 画像をbase64に変換
    if (!imageFile) {
      return new Response(JSON.stringify({ error: '写真をアップロードしてください' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const imageBuffer = await imageFile.arrayBuffer();
    const bytes = new Uint8Array(imageBuffer);
    let binary = '';
    const chunkSize = 8192;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
    }
    const imageBase64 = btoa(binary);
    const mediaType = imageFile.type || 'image/jpeg';

    const userText = `以下の写真を村田一朗として講評してください。

【撮影者のコメント・質問】
${comment.trim() || '（なし）'}

写真を見て、構図・露出・主題の明確さなどの観点から講評をお願いします。`;

    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-6',
        max_tokens: 800,
        system: SYSTEM_PROMPT,
        messages: [
          {
            role: 'user',
            content: [
              {
                type: 'image',
                source: { type: 'base64', media_type: mediaType, data: imageBase64 },
              },
              { type: 'text', text: userText },
            ],
          },
        ],
      }),
    });

    if (!response.ok) {
      const err = await response.text();
      return new Response(JSON.stringify({ error: `API エラー: ${err}` }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const data = await response.json();
    const text = data.content?.[0]?.text || '';

    return new Response(JSON.stringify({ result: text }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });

  } catch (e) {
    return new Response(JSON.stringify({ error: `エラー: ${e.message}` }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
