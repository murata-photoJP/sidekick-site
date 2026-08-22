# ダウンロード記録とメール配信リスト

更新日: 2026-08-22

ダウンロード時に取得したメールアドレスを、Firestore と Brevo の2箇所に記録する仕組みの
運用メモ。**アップデート告知メールを製品別・バージョン別に出し分けるための土台。**

---

## 1. 経路

```
register-dl.html?product=star&src=lp-star
        │  同意チェック + メールアドレス入力
        ├──→ Firestore  downloads コレクション（1DL = 1ドキュメント、履歴が全部残る）
        └──→ /api/add-contact → Brevo コンタクト（1メールアドレス = 1件、属性で状態を持つ）
```

どちらの書き込みも**失敗を握りつぶして**ダウンロード導線を優先する設計。
そのため「Firestore には居るが Brevo には居ない」人が発生しうる。
定期的に `tools/reconcile_downloads_brevo.py` で突合すること（下記4）。

**正はいつも Firestore。** Brevo は配信のための投影と考える。

---

## 2. Brevo 側で作っておく属性

`api/add-contact.js` が使う属性。**すべて「テキスト」型で作成しておく。**

```bash
set BREVO_API_KEY=xkeysib-...
py -3.10 tools/create_brevo_attributes.py --dry-run   # 確認
py -3.10 tools/create_brevo_attributes.py             # 作成
```

既存の属性はスキップするので何度実行しても安全。削除は行わない。
管理画面から手で作る場合は Contacts → Settings → Contact attributes。

| 属性 | 値 | 用途 |
|---|---|---|
| `HAS_STAR` / `HAS_PORTRAIT` / `HAS_SKY` / `HAS_AI` | `yes` | その製品をDLしたか |
| `VER_STAR` / `VER_PORTRAIT` / `VER_SKY` / `VER_AI` | 例 `3.16` | 最後にDLしたバージョン |
| `LANG` | `ja` / `en` | 配信言語（最新のDLページの言語で上書き） |
| `PRODUCT` | 例 `Sidekick_Star` | 最新のDL製品（従来からある。上書きされる） |
| `LEAD_SOURCE` | 例 `lp-star` | 最新の流入元（上書きされる） |
| `FIRSTNAME` / `INTEREST` | | 従来からある |

### なぜ製品ごとに分けるのか

Brevo の `POST /v3/contacts` は `updateEnabled: true` のとき**送った属性だけ**を上書きし、
送らなかった属性は残る。`add-contact.js` は今回DLした製品ぶんだけを送るので、
`HAS_STAR` を持っている人が Portrait をDLしても `HAS_STAR` は消えない。

2026-08-20 以前は `PRODUCT` 属性ひとつしか無く、**2製品目をDLすると1製品目の記録が消えていた。**
過去のコンタクトは `PRODUCT` に最新1件しか入っていないため、実績は Firestore 側にしかない。

### 属性を作り忘れた場合

Brevo が 400 を返す。`add-contact.js` は**従来の属性だけで自動的に再送**し、
レスポンスに `degraded: "new_attributes_missing"` を付ける。
ダウンロード導線も既存の記録も壊れないが、**製品別の記録は増えない**ので、
Vercel のログに `Brevo rejected new attributes` が出ていないか確認すること。

---

## 3. バージョンの更新

`register-dl.html` の `PRODUCT_VERSIONS` が唯一の定義箇所。リリースのたびにここを更新する。

```javascript
const PRODUCT_VERSIONS = {
  star:     '3.16',
  portrait: '3.16',
  sky:      '3.16',
  ai:       ''       // 未確定
};
```

star / portrait / sky は `Sidekickシリーズ/本体/Effects_All_In_One_Fixed3.16Oq16_jsxgin化_A5`
の同一コードベースから出しているため 3.16。
**Sidekick AI（`SideKickAI.exe`）は別系統で、実行ファイルにバージョン情報が無いため未確定。**

**値が未確定の製品は空文字のままにする。** 空文字のときは `VER_*` を Brevo に送らず、
Firestore の `version` も空文字で記録する。誤ったバージョンを記録すると、
「v3.15 の人にだけ告知する」といった絞り込みが静かに壊れるため。

2026-08-20 以前は全製品共通の `'3.16'` がハードコードされており、
Sky Effect と AI のダウンロード記録にも `3.16` が入っている。**この期間のデータは信用しない。**

---

## 3.5 言語の判定

`/en/` の各ページは `register-dl` を **`&lang=en` 付き**で呼ぶ。JA 側は付けず、
`register-dl.html` の既定値 `ja` に任せる。

`src` だけでは区別できないため必要になった。Star は `src=lp-star-en` 等で判別できるが、
**Sky と Portrait は EN も JA も `lp-sky` / `lp-portrait` で同一**だった。

```
/en/sky-effect.html → register-dl?product=sky&src=lp-sky&lang=en
/sky-effect.html    → register-dl?product=sky&src=lp-sky
```

`lang` が付いていない場合の保険として `src` の末尾 `-en` も見る（キャッシュされた旧ページ対策）。

EN ページは `templates/site/pages/en/*.html` から生成されるが、
**リンク追加はテンプレートと生成物の両方に入れてある。**
`build_site.py` の全体リビルドは行っていない（理由は下記6）。

---

## 4. 突合

Brevo 側だけ見る（Firestore 不要）:

```bash
py -3.10 tools/reconcile_downloads_brevo.py --brevo-only
```

Firestore 側だけ見る（**BREVO_API_KEY 不要**。件数・製品別・言語・流入元の内訳が出る）:

```bash
py -3.10 tools/reconcile_downloads_brevo.py --firestore-only
```

両方を突合する:

```bash
py -3.10 tools/reconcile_downloads_brevo.py --out E:/temp/reconcile
```

Firestore を読むには `pip install google-cloud-firestore` が必要。
サービスアカウント JSON は `SideKick販売ページ\Stripe\sidekick-6cfee-firebase-adminsdk-*.json` にある。

読み取り専用。次の3つを出す。

- **Firestore に居るが Brevo に居ない** — Brevo 登録に失敗した人。手動で追加する
- **Brevo の製品属性が実際のDL実績より少ない** — `PRODUCT` 上書きの影響を受けた人
- **Brevo に居るが Firestore に記録がない** — 別経路で登録された人

`--out` を付けると CSV を書き出す。**メールアドレスを含むので、リポジトリ内に置かない・
コミットしない。** リポジトリ内のパスを指定すると警告が出る。

必要な環境変数:

| 変数 | 用途 |
|---|---|
| `BREVO_API_KEY` | Brevo API キー |
| `GOOGLE_APPLICATION_CREDENTIALS` | サービスアカウント JSON のパス |
| `FIREBASE_SERVICE_ACCOUNT` | 上の代わりに JSON 本体（`api/*.js` と同じ運用） |

---

## 4.5 Firestore から Brevo への一括登録

2026-06-24〜2026-08-22 の間、`BREVO_API_KEY` が未設定だったため
`add-contact.js` は一度も Brevo に書き込めていない。その期間のダウンロード者は
Firestore にしか存在しないので、`tools/import_downloads_to_brevo.py` で移す。

```bash
py -3.10 tools/import_downloads_to_brevo.py                    # ドライラン（既定）
py -3.10 tools/import_downloads_to_brevo.py --apply --limit 3  # 3件だけ試す
py -3.10 tools/import_downloads_to_brevo.py --apply            # 全件
```

**`--apply` を付けない限り Brevo へは何も書き込まない。** 書き込むのは追加と属性更新のみで、
削除・配信停止の変更は行わない。`add-contact.js` が1件ずつ書くのと同じ結果になる。

| 属性 | 決め方 |
|---|---|
| `HAS_*` | DL実績のある製品すべて（**ここが旧実装との違い**） |
| `VER_*` | 判っているものだけ。不明なら送らない |
| `PRODUCT` / `LEAD_SOURCE` | **最新のDL**を採用（`add-contact.js` の上書き挙動と同じ） |
| `LANG` | `ja` / `en` に**一意に確定するときだけ**。未記録・混在なら送らない |
| `INTEREST` | 常に `photography` |

先に `create_brevo_attributes.py` を実行しておくこと。属性が無いと 400 で1件も入らない。

---

## 5. 同意の範囲

`register-dl.html` で取得している同意（`consentVersion: download-2026-06-25`）の利用目的は
次の3つ。**この範囲を超えるメールを送らない。**

- ダウンロード履歴の管理
- **製品アップデートや重要なお知らせのご案内**
- お問い合わせ・サポート対応

アップデート告知・重要なお知らせ（料金改定など）はこの範囲内。

**範囲外**：新製品の販売案内、講座やワークショップの募集、打ち出の小槌の新着通知。
これらを送る場合は `CONSENT_VERSION` を上げて再同意を取るか、別途オプトインを取ること。
`consentVersion` と `consentedAt` は Firestore の各ドキュメントに記録されているので、
「いつ・どの版の同意で入った人か」は後から追える。

---

## 6. 未対応・注意

- **2026-08-22 以前のDL者は `LANG` を持たない。** `lang` の記録開始が 2026-08-22 のため、
  一括登録しても言語が空のままになる。**最初の一斉配信の前に、この層の扱いを決めること**
  （日本語で送る／`src` から推測する／英語版を別に用意する）。
- **`VER_*` は 2026-08-22 以前のぶんが信用できない。** 全製品共通の `3.16` が
  ハードコードされていたため、Sky Effect と AI にも `3.16` が入っている。
- **API キーは90日連続の無活動で失効する。** `add-contact.js` は失敗を握りつぶすので、
  失効しても無言で止まる。**月1回 `--brevo-only` を実行すれば、
  無活動タイマーがリセットされ、同時にズレも検出できる。**
- **Brevo の SMTP & API 画面にある「Activate for API keys」（IP制限）を有効にしないこと。**
  Vercel のサーバーレス関数は送信元IPが固定されないため、有効化すると全てブロックされる。
- **`build_site.py` の全体リビルドを避けている。** 2026-08-20 時点で、
  テンプレート出力とルート直下の実ファイルに次の差分がある。

  | 対象 | 差分 |
  |---|---|
  | `en/index.html` | canonical / og:url が実ファイル `…/en`、テンプレート出力 `…/en/`。BOM の有無も違う |
  | JA 6ページ | 空行の末尾スペースのみ（無害） |

  リビルドすると `/en/` の canonical が変わる。**SEO に影響するため、
  どちらが正しいかを決めてからテンプレートを直すこと。** それまでは、
  今回のように必要な変更だけをテンプレートと生成物の両方へ入れる。
