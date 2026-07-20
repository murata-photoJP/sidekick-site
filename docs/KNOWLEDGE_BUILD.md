# 打ち出の小槌（Knowledge）ビルド — Phase A1

`_統合KB`が生成した`web-published.json`を読み、Markdown本文をHTML化し、
Jinja2テンプレートへ流し込んで静的HTMLを生成する仕組み。Phase A1の範囲は
「記事1本のHTML生成が動くこと」まで。一覧ページ・複数記事の一括生成・
既存サイトへの実配置は行っていない（Phase A2以降）。

責任分界・技術方針の正は
`_SideKick_Development/docs/COMPONENTS/10_PHASE0_DECISIONS.md`。

> **2026-07-17追記**：Phase A2でトップページ・複数記事一括生成・共通Header/Footer・
> モバイルナビ・CSS・Related Articles/Product Context/CTAを実装した。詳細は
> `docs/KNOWLEDGE_UI_PHASE_A2.md`を参照。このドキュメント（KNOWLEDGE_BUILD.md）は
> Phase A1時点の1記事生成の仕組みの記録として残す。

---

## ビルド環境

Next.js・React・Vue・Astro・CMS・データベースは導入していない。
既存の静的HTMLサイト（Vercelでcleanurlsとして配信）はそのまま維持し、
Pythonのビルド時スクリプトで静的HTMLファイルを生成する方式を採用した。

```
sidekick-site/
├── build/
│   └── knowledge/
│       └── build_knowledge.py   ← ビルドCLI本体
├── templates/
│   └── knowledge/
│       ├── base.html            ← 共通レイアウト（head/header/footer include）
│       ├── header.html          ← Phase A1: 最小限のプレースホルダー
│       ├── footer.html          ← Phase A1: 最小限のプレースホルダー
│       └── article.html         ← 記事ページ（base.htmlを継承）
├── data/
│   └── knowledge/
│       └── web-published.json   ← _統合KB側から受け取る公開インデックス
├── build-output/                ← ビルド生成物（.gitignore対象。本番デプロイ対象外）
├── tests/
│   └── knowledge/
│       └── test_build_knowledge.py
├── requirements-build.txt
└── docs/
    └── KNOWLEDGE_BUILD.md（このファイル）
```

既存の`html/*.html`・`api/`・`images/`・`vercel.json`・`package.json`とは
独立しており、衝突しない場所に配置した。

## requirements-build.txt

```
Jinja2==3.1.6
markdown-it-py==4.0.0
```

両方とも、このマシンのPython環境に**既にインストール済み**であることを確認済み
（新規依存の追加ではない）。PyYAMLはWeb側では使わない（`web-published.json`は
JSONであり、YAMLパースが不要なため）。既存の`package.json`（Node/Vercel
Serverless Functions用）には触れていない。

インストール：

```bash
pip install -r requirements-build.txt
```

---

## JSON仕様（web-published.json）

`_統合KB/docs/SKB_WEB_PUBLISH_INDEX.md`を正とする。このビルドスクリプトは
`schema_version`を確認し、対応バージョン（現在は`1`のみ）でなければ
明確なエラーで停止する（未対応バージョンのまま誤って古い/新しい形式を
読み込んでしまう事故を防ぐ）。

---

## Markdown変換

`markdown-it-py`の`commonmark`プリセットをベースに、`html: False`
（本文中の生HTMLはそのまま出力せずエスケープする＝安全側のデフォルト）と
`table`ルールの有効化（GFM形式の表に対応するため）だけを追加している。
追加のプラグインパッケージ（`mdit-py-plugins`等）は不要だった
（`table`ルール自体はmarkdown-it-pyのコアに含まれており、`commonmark`
プリセットで無効化されているだけだったため、`.enable(["table"])`で
有効化するだけで済む）。

対応済み：見出し・段落・箇条書き・番号付きリスト・リンク・引用・コードブロック・表。
Before/After・画像・注意書き等のWeb独自記法はPhase A1では未対応（Phase A2）。

---

## テンプレート構成

Jinja2の継承・includeで、base / header / footer / article を分離した。

- `base.html`：`<!doctype html>`・`lang`・charset・viewport・title/meta description/canonicalの
  ブロック定義・`header.html`と`footer.html`のinclude
- `header.html` / `footer.html`：Phase A1では最小限のプレースホルダー
  （実際のグローバルヘッダー/フッターは`docs/COMPONENTS/01_GLOBAL_COMPONENTS.md`
  に沿ってPhase A2以降で作り込む）
- `article.html`：`base.html`を継承し、Breadcrumb・Article Header・
  短い著者情報（記事冒頭）・Article Body・詳細Author Block（記事末尾）を実装

Phase A2でそのまま拡張できるよう、部品を増やしすぎず、
必要な差し込み口（`{% block %}`、`{% include %}`）だけを用意した。

---

## 採用した静的HTML出力形式とURLとの整合性

出力形式は **`html/knowledge/{category}/{slug}.html`**（フラットファイル）を採用した。
`html/knowledge/{category}/{slug}/index.html`（フォルダ+index.html形式）は不採用。

判断根拠：

- `vercel.json`は`"trailingSlash": false`を設定済みで、正規URLは末尾スラッシュ無し
  （`/knowledge/{category}/{slug}`）である
- 現行サイトの全ページ（`about.html`, `ai-lab.html`等）は例外なくフラットな
  `.html`ファイルであり、`index.html`をフォルダに入れる形式は1件も存在しない
- `cleanUrls: true`により、`{slug}.html`は`/knowledge/{category}/{slug}`として
  そのままアクセス可能になる。フラット形式の方が既存サイトの慣習と一致し、
  `trailingSlash: false`とも矛盾しない

推測ではなく、既存の`vercel.json`と実際のファイル構成を確認した上でこの形式を選んだ。

---

## テスト用記事の生成結果（Phase A1動作確認）

`_統合KB`側にテスト専用フィクスチャ記事（本番の10記事とは別、`SKB-TEST-PHASEA1-001`）を
一時ディレクトリに作成し、`generate_web_published_index.py`で
`data/knowledge/web-published.json`へ実際に書き出した上で、このビルドスクリプトで
`build-output/knowledge/photoshop/test-article.html`を生成した。

確認済み項目：日本語UTF-8が文字化けしないこと、meta descriptionとcanonicalが
正しく出力されること、短い著者情報と詳細Author Blockの両方が出ること、
見出し・箇条書き・番号付きリスト・引用・コードブロック・表がすべて正しくHTML化
されること、本文中の生HTML（`<script>`タグ）がエスケープされ実行可能な形で
出力されないこと。

このテスト記事は`build-output/`（`.gitignore`対象）に生成されており、
本番の`html/knowledge/`には一切配置していない。

---

## テスト

```bash
python tests/knowledge/test_build_knowledge.py
```

29件のテストがすべてパスすることを確認済み（JSON読込・schema_version確認・
記事取得・Markdown→HTML・UTF-8・meta description・canonical・著者情報・
内部情報の非露出・出力URL・テンプレート継承・エラー時に壊れた出力を残さないこと）。

`_統合KB`側のテスト（`_統合KB/scripts/test_web_published_index.py`、24件）と
合わせて、Phase A1のパイプライン全体が自動テストで検証されている。

---

## Phase A2で拡張する箇所

- `header.html`/`footer.html`を、`docs/COMPONENTS/01_GLOBAL_COMPONENTS.md`の
  5項目ナビ・モバイルメニュー・言語切替を備えた実装に差し替える
- 複数記事の一括ビルド、打ち出の小槌トップページ・カテゴリページのテンプレート追加
- Related Articles・Product Context Block・Contextual CTAの画面実装
  （データ自体は`web-published.json`に既に含まれている）
- Before/After・注意書き等のWeb独自Markdown記法への対応
- 実際に`html/knowledge/`へ生成物を配置し、Vercelへデプロイする運用手順の確立

> **2026-07-20追記（sitemap.xml自動反映）**：`sitemap.xml`はKnowledge記事の
> URLを反映する工程が無く、最初の記事公開以降ずっと未反映のままだったことが
> 判明した。`build/knowledge/generate_knowledge_sitemap.py`を新設し、
> `web-published.json`からKnowledge記事のURLを機械的に導出して
> `sitemap.xml`内のマーカーコメント区間だけを更新するようにした（それ以外の
> 手動管理項目には触れない）。
>
> ```
> python build/knowledge/generate_knowledge_sitemap.py \
>   --index data/knowledge/web-published.json --sitemap sitemap.xml
> ```
>
> Knowledge記事を公開・更新するたびに、`generate_web_published_index.py`→
> `build_knowledge.py`→`generate_knowledge_sitemap.py`の順で実行する運用とする
> （テスト: `tests/knowledge/test_generate_knowledge_sitemap.py`）。
