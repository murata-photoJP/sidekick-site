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
├── index.html                 ← 打ち出の小槌トップ（Hero + Article List + About）
├── article.html               ← 記事ページ
└── components/
    └── article-card.html      ← Article Card部品（トップページのArticle Listから include）
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

Phase A1の16件 + Phase A2で追加した96件（古いHTML削除15件、見出し階層・画像alt検証7件を含む） = 計112件。HTMLの検証は正規表現・文字列検索
（既存のPhase A1テストと同じ方式）で行っており、新しいHTMLパーサーライブラリは追加していない。

カバーしている内容：複数記事の一括生成／1記事指定／validate-only／重複出力パス検知／
atomicなバッチ確定（失敗時に既存出力を壊さない）／article_cards・categoriesとの整合確認／
トップページのカード件数・並び順・空表示／記事ページのbreadcrumb非リンク・著者情報重複無し・
Related Articles/Product Context/CTAの条件表示／canonical・meta description・h1が1つ／
Header主要5項目・aria-current・モバイルナビのaria属性・JS無しでもリンクが存在すること／
Footerに空リンク・存在しない英語記事リンクが無いこと。

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
