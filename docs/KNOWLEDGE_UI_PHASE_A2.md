# 打ち出の小槌 画面実装 — Phase A2

Phase A1（公開基盤）の上に、打ち出の小槌トップ・複数記事ページ・共通Header/Footer・
モバイルナビ・記事カード・関連記事・製品導線をローカルで確認できる状態まで実装した。
本番記事の公開・Vercelへのデプロイは行っていない。

---

## 生成ページ

`build_knowledge.py`を引数無しで実行すると、公開インデックス内の全記事＋トップページを生成する。

```
build-output/knowledge/
├── index.html                        ← 打ち出の小槌トップ
├── photoshop/{slug}.html
├── photography/{slug}.html
└── marketing/{slug}.html
```

`--article-id`を指定すると、その1記事だけを生成する（トップページは生成されない）。

## テンプレート構成

```
templates/knowledge/
├── base.html                  ← <head>・header/footerのinclude・contentブロック
├── header.html                ← 共通ヘッダー（Products/打ち出の小槌/AI Lab/Workshop/About）
├── footer.html                ← 共通フッター
├── index.html                 ← 打ち出の小槌トップ（Hero + カテゴリnav + 新着記事 + おすすめ記事 + カテゴリ別一覧）
├── article.html               ← 記事ページ
└── components/
    ├── article-card.html      ← Article Card部品（カテゴリ別一覧から include）
    ├── mini-card.html          ← 小型カード部品（新着記事・おすすめ記事から include。2026-07-21追加）
    └── category-nav.html       ← カテゴリnav（チップ型リンク）部品（2026-07-21追加）
```

Jinja2の`extends`/`include`で分離しており、部品を増やしすぎないよう
「トップページと記事ページで共通のカード部品」だけを独立ファイルにした。

## CSS

`assets/css/knowledge.css`（既存ページのCSSは変更していない、新規追加のみ）。
既存`index.html`のダークテーマ配色（`--bg:#09090c`、`--accent:#ff8a00`等）に合わせた値を
このファイル内で独自の変数として再定義している（既存の`:root`定義を上書き・依存しない、
完全に独立したファイル）。Header/Nav/Footer/Hero/Article List/Card/Breadcrumb/
Article Header/Body/Author Short/Author Block/Related Articles/Product Context/CTA/
表・引用・コードブロック・レスポンシブ・フォーカス表示をカバーしている。

## モバイルナビ

Progressive enhancementで実装した。

- JSが読み込まれない/失敗した場合: `.kzc-nav-menu`はCSSの既定値で常に表示（`display:flex`）。
  トグルボタンは`display:none`（動作しないボタンを見せない）。5項目のリンクはHTML上に
  常に存在する
- JSが有効な場合: `body`に`kzc-js-nav`クラスが付き、トグルボタンが表示される。
  クリック/Enter/Spaceで開閉、`aria-expanded`・`data-open`を同期、Escapeキーで閉じる、
  メニュー外クリックで閉じる、フォーカス表示を維持
- 実機ブラウザ（Chromium、ローカルプレビュー環境）で、開閉・Escape・外側クリックの
  各挙動をJS実行結果として確認済み

## 非公開になった記事の古いHTML削除（2026-07-17追加）

全記事一括生成（`--article-id`を省略した実行）のときだけ、`--output`配下の既存`.html`のうち
今回生成した集合に含まれないものを、新しい内容の書き込みが**すべて成功した後**に削除する。

- `--article-id`で1記事だけ生成する場合は削除しない（全体像が分からないため）
- 新しい内容の確定コピーより前には絶対に削除しない（2回目のビルドが失敗した場合、
  1回目の生成物は一切削除されないことをテストで確認済み）
- `--output`はこのツールが生成したファイルだけを置く場所という前提。手動で置いた
  無関係な`.html`も削除対象になるため、`--output`を他の用途と共有しない

## 見出し階層・画像altの検証（2026-07-17追加）

記事本文（Markdown）から、次の2点を警告としてビルド時に出力する（生成は止めない）。

- **見出し階層の飛び越し**：直前の見出しレベルより2段階以上深い見出しが出てきた場合
  （例：h2の次にいきなりh4）。本文の見出しはh2から始まる想定（h1はページタイトル用）
- **画像alt未指定**：`![](path)`のようにalt文字列が空/空白のみの画像

意味の無いダミーalt（「image」等）を自動で埋めることはしていない。警告を見て、
記事の書き手（村田さん）が意味のある代替テキストを追加する運用とする。

## UIレビューによる改善（2026-07-17）

村田さんのレビュー依頼を受け、以下を改善した（詳細な検討理由はレビュー時のやり取りを参照）。

- **Knowledge Topの構成変更**：Hero→記事一覧→「打ち出の小槌とは」の順だったが、
  Hero→「打ち出の小槌とは」→記事一覧に変更。Heroの説明文と「打ち出の小槌とは」の
  内容が重複していたため、Hero側の説明文は削除しタグラインのみにした
- **H1のメイン/サブタイトル分離**：全記事のtitleが「メイン｜サブ」形式であることを
  利用し、`split_title()`でH1の表示だけをメイン+サブに分離（`<span class="kzc-title-sub">`）。
  `<title>`タグ・meta description・canonical等のSEO関連は一切変更していない。
  「｜」が無いタイトルは従来通り1本のまま表示（後方互換）
- **パンくずを控えめに**：現在ページの項目（記事タイトル）が本文と同じ明るい色で
  H1と視覚的に重複していたため、他のパンくず項目と同じ色に統一。表示テキストも
  メインタイトルのみ（サブタイトル部分は省略）に変更
- **Product Contextの橋渡し文を廃止**：自動生成の「この工程を繰り返しているなら
  SideKickで自動化できます」的な文言が、本文側の自然な製品言及と重複していた
  （実記事で発覚）。中立的なラベル「関連するSideKick製品」＋製品名・説明・リンクのみの
  参照ブロックに変更した

**見送った項目**：記事カードの多カラム化（現時点では記事数が少ないため、カテゴリ・検索・
サムネイル等の設計が固まった段階で改めて検討）。更新日のみの表示・読了時間非表示は
現状維持。

## カテゴリnav・新着記事・おすすめ記事・カテゴリ別一覧（2026-07-21追加）

記事数が増えるにつれ、Article Cardをpublish順に並べただけの一覧では見つけにくくなる
という村田さんの指摘を受けて改修した。トップページの構成は次の順になった。

```
Hero → 打ち出の小槌とは → カテゴリnav → 新着記事(NEW) → おすすめ記事(PICK UP) → カテゴリ別一覧(記事一覧)
```

### カテゴリnav

`web-published.json`の`categories`（`_統合KB`側が記事データから自動集計したもの）を
そのまま使い、`build_category_groups()`（`build_knowledge.py`）でカテゴリ別に
グループ化・件数集計する。カテゴリの追加・削除は記事データ側（`_統合KB`）に追随する
だけで、Web側のコード変更は不要（新しいカテゴリの記事が公開されれば自動的にnavと
一覧セクションが増える）。

- 表示順は`web-published.json`の`categories`の並び順（slugのアルファベット順、
  `generate_web_published_index.py`が`sorted()`で生成）にそのまま従う。村田さんの
  例示（写真→Photoshop→マーケティング）とは順序が異なる場合があるが、これは
  taxonomyの表示用`id`のような優先順位データが現状`web-published.json`に無いための
  実装判断（優先順位を付けたい場合は`_統合KB`側にその情報を追加する必要がある）
- リンクは`<a href="#kzc-cat-{slug}">`のハッシュリンクで、JavaScriptが無くても
  クリックでその場へ移動できる（スムーズスクロールは`html{scroll-behavior:smooth}`
  というCSSのみで実現、JS不要）
- 現在位置のハイライト（`aria-current="true"`）だけはJS（`IntersectionObserver`による
  scroll-spy、progressive enhancement）で行う。JSが動かない環境でもnav自体の
  クリック機能には影響しない

### 新着記事（NEW）

`_recency_sort_key()`で`published_at`の新しい順に並べ、上位3件（`NEW_ARRIVALS_LIMIT`）を
表示する。`published_at`が完全に同一の記事が複数あっても、記事IDの降順を
タイブレークにして、ビルドのたびに順序が変わらないようにしている。

### おすすめ記事（PICK UP）

アクセス解析による実際の閲覧数を安全に取得できる仕組みが現状無いため
（GA4等のAPI連携・サービスアカウント資格情報がリポジトリに存在しないことを確認済み）、
架空の閲覧数・人気順位は作らない方針とした。見出しは常に「PICK UP／おすすめ記事」
（「人気記事」ではない）。

- **手動選定**：`data/knowledge/pickup.json`（サイト側だけで完結する設定ファイル。
  `_統合KB`のパイプライン・記事frontmatterには一切触れない）に、言語ごとに
  記事IDを配列で並べる。
  ```json
  { "ja": ["SKB-ART-000003", "SKB-ART-000005"], "en": [] }
  ```
  先頭から順に採用され、存在しないIDは無視される（fail-closed）。
- **自動補完**：手動選定が無い/不足する場合、新着記事と重複しない範囲で
  `published_at`の新しい記事から自動的に埋める（最大`PICKUP_LIMIT=3`件）。
  補完後も0件なら、おすすめ記事セクション自体が非表示になる（空枠を出さない）。
- ファイルが存在しない・壊れている・該当言語のキーが無い場合は空リスト扱いになり、
  ビルド自体は失敗しない。

**今後記事が増えたときの運用**：村田さんが`pickup.json`を直接編集し、見せたい記事の
IDを並べるだけでよい（ビルドの再実行が必要）。ビルドスクリプトや`_統合KB`側の
変更は不要。

### カテゴリ別一覧（記事一覧）

`build_category_groups()`でカテゴリごとに`article-card.html`を並べる。各カテゴリ内は
新着記事と同じ`_recency_sort_key()`で新しい順。新着記事・おすすめ記事に載った記事も、
このカテゴリ別一覧からは除外しない（セクション間で重複除外はしない、村田さんの
明示要件）。

### テスト分離のための`--pickup-config`引数

`tests/knowledge/test_build_knowledge.py`が本番の`data/knowledge/pickup.json`に
触れずに検証できるよう、`build_knowledge.py`に`--pickup-config <path>`を追加した
（省略時は本番の`data/knowledge/pickup.json`を使う）。

### 本番デプロイ後に発見・修正した不具合2件（2026-07-21）

**1. EN側のカテゴリ表示順バグ**

`_統合KB`の`generate_web_published_index.py`の`build_categories()`が、
言語に関わらず`categories`配列の`name`フィールドに常に`name_ja`（日本語名）を
入れていた（`build_article_card()`は元々言語別に出し分けていたが、こちらだけ
取り残されていた既存バグ）。今回追加した`build_category_groups()`（本ファイル）が
この`name`でslugを逆引きする実装だったため、EN記事だけ誤ったフォールバックslug
（大文字化けした疑似slug、例：`Marketing`）が使われ、taxonomy順ソートが機能せず
アルファベット順もどきの誤った順になっていた。`_統合KB`側で`e["language"] == "en"`
のときは`category.name`（英語名）を使うよう修正。合わせて、本ファイルのテスト
フィクスチャ（`card_from_article()`・`categories_from_articles()`）にも同じ
言語分岐の抜けがあり、本番と異なる前提でテストが通っていたことが判明したため、
本番コードと同じ前提に揃えた。

**教訓**：Web側で言語別データ（EN/JA）を扱うロジックを追加する際は、上流
（`_統合KB`側の集計・変換関数）が言語別に正しく出し分けているか確認すること。
テストフィクスチャがそのズレを隠してしまうと、本番デプロイまで気づけない。

**2. カテゴリnavの選択状態がスクロールで意図せず変わるバグ**

初期実装では、カテゴリnavの現在位置ハイライトを`IntersectionObserver`による
scroll-spy（画面に見えているセクションを自動でハイライト）で実装していた。
しかし「Photoshop」等をクリックした直後でも、上部（先頭セクション）へ
スクロールして戻ると、scroll-spyが「今見えているのは先頭のカテゴリ」と判定し、
クリックした選択状態を無条件に上書きしてしまう不具合があった（本番で報告）。

scroll-spyを完全に削除し、`hashchange`イベント1本で選択状態を管理する方式に
変更した。クリック・ページ初期表示・ブラウザの戻る/進むのいずれも`hashchange`
イベント経由で同じ関数（`slugFromHash()` → `setActive()`）に集約され、
スクロールでは選択状態を一切変更しない。`aria-current`の値も`true`から、
ARIA的により正確な`location`へ変更した（CSS側のセレクタも追随）。
スムーズスクロール自体（CSSの`scroll-behavior:smooth`のみで実現、JS不要）は
変更していない。

再発防止として、`test_category_nav_active_state_is_hash_based_not_scrollspy`を
追加し、生成HTMLに`new IntersectionObserver`が含まれないこと・`hashchange`が
含まれることを静的に検証している。

## 複数記事一括生成

```bash
# 全記事 + トップページ
python build/knowledge/build_knowledge.py --index data/knowledge/web-published.json --output build-output/knowledge

# 1記事だけ
python build/knowledge/build_knowledge.py --index data/knowledge/web-published.json --output build-output/knowledge --article-id SKB-ART-000001

# 検証のみ（何も書き込まない）
python build/knowledge/build_knowledge.py --index data/knowledge/web-published.json --output build-output/knowledge --validate-only
```

生成は「全記事を一時ディレクトリ（`--output`の親ディレクトリ内の`.build-staging-<uuid>`）へ
書き出し、1件でも失敗すれば何も確定しない」方式。成功時のみ、一時ファイル経由の
`os.replace`で`--output`側へ確定する。重複する出力パス（同じcategory/slugの組み合わせ）は
生成前に検知してエラーにする。`article_cards`に存在しない記事があれば致命的エラー、
`categories`の集計に無いカテゴリ組み合わせがあれば警告にとどめて生成は継続する。

## ローカルプレビュー

```bash
# sidekick-siteリポジトリのルート（html/）で実行する
python -m http.server 3333 --directory .
```

```
http://localhost:3333/build-output/knowledge/index.html
http://localhost:3333/build-output/knowledge/photoshop/{slug}.html
```

**注意（ローカルURLと本番URLの違い）**：
- ローカルでは`/build-output/knowledge/...`というパスになるが、本番では
  `/knowledge/...`になる（`build-output/`は本番配置先ではなく確認用の一時出力先のため）
- ローカルの`python -m http.server`は`vercel.json`の`cleanUrls`（拡張子無しURL）を
  再現しない。本番の実際のURL（`/knowledge/{category}/{slug}`、末尾スラッシュ無し）は
  Vercelへ実配置して初めて確認できる
- リポジトリのルート（`html/`）で起動することで、`/assets/css/knowledge.css`や
  `/ai-lab`・`/about`等の既存ページへのリンクも同時に確認できる（実際に確認した際は
  Header/Footerの実リンクが実在の既存ページへ正しく遷移することを確認済み）

大規模な開発サーバー（Node製のライブサーバー等）は導入していない。

## テスト

```bash
python tests/knowledge/test_build_knowledge.py
```

計180件（チェック単位、2026-07-21時点）。HTMLの検証は正規表現・文字列検索
（既存のPhase A1テストと同じ方式）で行っており、新しいHTMLパーサーライブラリは追加していない。

カバーしている内容：複数記事の一括生成／1記事指定／validate-only／重複出力パス検知／
atomicなバッチ確定（失敗時に既存出力を壊さない）／article_cards・categoriesとの整合確認／
トップページのカード件数・並び順・空表示／記事ページのbreadcrumb非リンク・著者情報重複無し・
Related Articles/Product Context/CTAの条件表示／canonical・meta description・h1が1つ／
Header主要5項目・aria-current・モバイルナビのaria属性・JS無しでもリンクが存在すること／
Footerに空リンク・存在しない英語記事リンクが無いこと／
**（2026-07-21追加）** カテゴリnavの件数表示・カテゴリ別一覧の並び順／新着記事top3と
同日タイブレーク／おすすめ記事の手動選定反映・自動補完フォールバック・見出しが常に
「おすすめ記事」であること／新着記事・おすすめ記事に載った記事もカテゴリ別一覧に
残ること。

## 本番配置前の確認事項

- `build-output/`は`.gitignore`対象。本番の`html/knowledge/`へは今回コピーしていない
- 本番投入前に、`--output`を実際の`html/knowledge/`に向けて再実行する運用手順を
  別途決める必要がある（今回は意図的に行っていない）
- **（2026-07-17改訂）Header/Footerは既存サイト（index.html）の実ヘッダー・実フッターをそのまま流用している。**
  当初は打ち出の小槌専用の簡略化した5項目ナビを設計したが、実際にライブで確認したところ
  サイト全体としての一貫性を欠くと判断し、方針転換した。既存の12項目ナビ・ロゴバッジ・
  ブランド名・言語バナーをそのまま使い、「打ち出の小槌」を新規ナビ項目として追加している。
  リンクは打ち出の小槌ページが`/knowledge/`配下（1〜2階層下）にあるため、すべてルート相対
  パス（`/sidekick-star.html`等）に変換済み。モバイル時の「display:noneで隠すだけ」という
  既存サイトの実装は踏襲せず、キーボード操作・aria-expanded対応のトグルボタンを追加している
- 本文Markdownが`# タイトル`から始まる記事（実際の10記事すべてがこの形式）で、Article Header
  のH1と重複してh1が2つできるバグを発見・修正した（`strip_leading_h1()`で本文冒頭の単一
  `#`見出しのみ除去。`##`以降は対象外）

## Phase Bへ持ち越す内容

- カテゴリページ（現状Breadcrumbのカテゴリ名は非リンクのまま）
- Search・Category Summaryの本格実装
- Table of Contents・Series Navigation
- Workshop Context Block・Newsletter CTA
- サムネイル画像の実データ対応（`thumbnail_url`を実際に埋める仕組みが`_統合KB`側に無い）
- 英語版打ち出の小槌・翻訳ペア管理
- 本番`html/knowledge/`への実配置・Vercelへのデプロイ・自動化
