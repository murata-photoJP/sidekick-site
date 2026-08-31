# Story ビルド — 実装記録

> デプロイ前の全体チェック手順は`docs/DEPLOY_CHECKLIST.md`を参照。

写真家・村田一朗が、写真・技術・道具作り・メーカーとの仕事・撮影現場で考えてきたこと、
そして現在のSidekickにつながる背景を長文で読むための領域。2026-08-31新設。

打ち出の小槌（`docs/KNOWLEDGE_BUILD.md`）・開発日誌（`docs/DEVELOPMENT_LOG_BUILD.md`）と
同じ設計方針（Python + Jinja2 + markdown-it-py、atomicなステージング書き込み、
sitemapはマーカーコメント方式、slug重複で停止）を踏襲する。

---

## 1. 「開発日誌」「更新履歴」との役割分担

このリポジトリには、似ているが役割の違う3つのコンテンツ領域がある。混同しないこと。

| 領域 | URL | 役割 |
|---|---|---|
| **Story** | `/story` | なぜ、こういう道具を作ることになったのか。**過去の経験を語る読み物** |
| 開発日誌 | `/development-log` | いま何を作り、何に困り、何を判断しているか。**現在進行形の記録** |
| 更新履歴 | `/changelog` | ユーザーが知る必要のある製品・サービスの変更。**簡潔な告知** |

Storyに「今日こういうバグを直した」を書かない。開発日誌に「20年前こういう仕事をしていた」を
書かない。迷ったら、その文章が読者にとって**背景**なのか**近況**なのかで判断する。

### note連載「Sidekick 開発記」との関係（2026-08-31時点）

`_SideKick_Development/docs/HISTORY/開発記_Draft/`に、note向けの連載「Sidekick 開発記」
（#01〜#10、流星編）が別に存在する。ジャンルはStoryと近いが、**現時点では別トラック**である。

- Story：Sidekick Labが原本・canonical
- 開発記：noteが公開先（`PUBLICATION_PLAN.md`が工程を定義）

将来この2つを統合するかどうかは未決で、**村田さんの判断事項**として残っている。
AI判断で片方をもう片方へ移さないこと。

---

## 2. 全体の流れ

```
content/story/{slug}.md（日本語、status: published のみ）
content/story/en/{slug}.md（英語、source_slugで日本語版と対応付け）
        ↓ build_story.py
story/index.html, story/{slug}.html
en/story/index.html, en/story/{slug}.html
        ↓ generate_story_sitemap.py
sitemap.xml（マーカー区間のみ更新）
        ↓ git commit & push
Vercelが自動ビルド・公開
```

開発日誌と違い、**sync スクリプトは無い。** 入力Markdownはこのリポジトリで直接管理する
（元原稿は`D:\OSINT調査\`にあるWord/テキストで、そこからの取り込みは都度の手作業）。

**英語版は「後で追加」ではない。JA/ENが揃った状態を公開Gateとする**（村田さんの要件、
2026-08-31）。この条件は`tests/story/test_ja_en_parity.py`で機械的に検証される。

---

## 3. 前提

- Python（`requirements-build.txt`）：Jinja2・markdown-it-py・PyYAML
- このマシンでは`py -3.10`を使う（`py -3.14`ではテスト用の依存が入っていない）
- 出力先：`story/`・`en/story/`（本ツールが生成したファイルだけを置く場所。
  手動で無関係な`.html`を置かないこと）

---

## 4. コマンド

すべてリポジトリのルート（`html/`）で実行する。PowerShellの例。

```powershell
# 1. 生成可能か確認（何も書き込まない）
python build/story/build_story.py `
  --content content/story --output build-output/story `
  --content-en content/story/en --output-en build-output/en-story --validate-only

# 2. ローカル確認用に生成
python build/story/build_story.py `
  --content content/story --output build-output/story `
  --content-en content/story/en --output-en build-output/en-story

# 3. 確認後、本番ディレクトリへ生成
python build/story/build_story.py `
  --content content/story --output story `
  --content-en content/story/en --output-en en/story

# 4. sitemap.xmlへ反映
python build/story/generate_story_sitemap.py `
  --content content/story --content-en content/story/en --sitemap sitemap.xml

# 5. テスト
python -m pytest tests/story -q
```

---

## 5. front matter

```yaml
---
title: "「比較明合成」を知らなかった私が、星をつなぐまで"
subtitle: "――始まりは、燕岳を歩く登山者のヘッドライトだった"
slug: before-i-knew-lighten-composite
order: 1
date: "2026-08-31"
status: "published"
summary: "一覧カードとmeta descriptionに使う要約。"
series: "道具を作るということ"      # 任意。前後編・連作のときだけ
series_part: 1                      # 任意
series_total: 2                     # 任意
source_slug: before-i-knew-lighten-composite  # 英語版のみ。対応する日本語版のslug
related_links:                      # 任意。記事末尾の導線
  - label: "Sidekick Star"
    url: "/sidekick-star"
---
```

必須は`title`・`date`・`status`・`order`。欠けている記事は1件ごとにスキップして
警告を出すだけで、ビルド全体は止めない。

### 開発日誌との違い（3点）

1. **並び順は`date`の降順ではなく`order`の昇順。** Storyは日付順に流れていく記録では
   なく、順番に読む読み物であるため。`order`の重複は警告ではなく**ビルド停止**にしている
   （読む順序が壊れた状態を公開しないため）
2. `subtitle`・`series`・`related_links`を持つ
3. `sync`が無いぶん、`## メモ（公開しない）`の安全網も持たない（元が
   `_DevelopmentLog`のテンプレートではないため）

### `related_links`の制約

`url`は**サイト内のルート相対パス（先頭が`/`）のみ許可**する。外部URLを書くと
その記事はスキップされる。記事末尾の導線に外部リンクを紛れ込ませないための制約で、
外部への言及は本文側の責務とする。

---

## 6. 本文の扱い

**承認済みの本文をAI判断で書き換えない。** 許可される変更は、Web用のheading level調整・
paragraph構造・frontmatter/metadata・記事末尾の導線・JA/EN切替・アクセシビリティ上
必要な構造に限る。本文内容そのものを変える必要があると判断した場合は、変更せず
Human Decisionとして村田さんへ報告する。

### 2026-08-31の初回5本で使った変換規則

元原稿（`D:\OSINT調査\*.docx`）には見出しスタイルが無く、見出しも本文中の強調も
どちらも「太字」だった。Story 1だけは村田さんがMarkdown化した`.txt`があり、それを
正解として次の規則を検証した（**16見出し・5強調すべて一致**）。

| docx上の状態 | Markdown |
|---|---|
| 最初の非空段落 | front matterの`title`（本文には出さない） |
| その直後の太字段落 | front matterの`subtitle`（本文には出さない） |
| 太字 **かつ** 直前が空段落 | `## 見出し` |
| 太字 **かつ** 直前が本文 | `**強調段落**` |
| それ以外 | そのまま段落 |

同じ規則をStory 2〜5にも適用した。`.docx`と`.txt`の本文が完全一致することは実測で
確認済み（差分はStory 1のバッククォート2箇所のみ。作品名`night noise`をコード表記に
しないため、より新しい`.docx`側＝バッククォート無しを採用した）。

今後Storyを追加するときも、**元原稿にMarkdown版があるならそちらを優先**し、
docxからの変換は上記規則で行ったうえで、見出しの切れ目を目視確認すること。

---

## 7. Markdownの書き方

- 本文冒頭の`# 見出し`はArticle HeaderのH1と重複するため自動で取り除かれる
  （`strip_leading_h1()`、打ち出の小槌・開発日誌と同じ）
- 本文中の見出しは`##`から始める。`##`の次に`####`のような階層の飛び越しは警告される
  （警告のみでビルドは止まらない）
- 本文中に`# h1`があると警告される（1ページ1h1が崩れるため）
- 画像srcはWeb上の絶対パス（`https://...`または`/...`）にすること。altが空でも警告される

---

## 8. JA/EN の対応付け

英語版のfront matterに`source_slug`（対応する日本語版のslug）を書くと、
hreflangと言語切替リンクが自動で対応付けられる。対応する翻訳が無い記事には
hreflangを出さない（存在しないURLを出力しない、打ち出の小槌・開発日誌と同じ方針）。

初回5本は**JAとENでslugを同一**にしてある（URLは`/story/{slug}`と`/en/story/{slug}`で
言語プレフィックスだけが違う）。この規則を変える必要は今のところ無い。

### 公開漏れGate（`tests/story/test_ja_en_parity.py`）

Storyが増えても追加作業なしで効くよう、記事の一覧は`content/story/`から動的に読む。
検証しているのは次の10項目。

1. JA/ENペアの欠落 = 0（両方向）
2. `order`・`series`がJA/ENで一致している
3. 生成HTMLが両言語に存在する
4. canonicalが自己参照かつ言語ごとに正しい
5. hreflangが相互参照になっている／言語切替リンクが相手言語を指している
6. title・meta descriptionが空でなく、ページ間で重複していない
7. sitemapに両言語が載っている
8. Storyページから出るサイト内リンクが実ファイルに解決する（`cleanUrls: true`前提）
9. Story以外のJA/EN対ページ（`PAGE_PAIRS`。現在はPlanner）も1〜3・7と同じ検証
10. Story 5 ⇄ Plannerの相互リンク、Plannerページの「開発中」表示、
    グローバルナビへのStory掲載

**JA/EN対のページを新設したときは、`PAGE_PAIRS`へ1行足せば同じ検証が効く。**

---

## 9. URL・ディレクトリ構成

- 一覧：`/story` （`story/index.html`）
- 個別：`/story/{slug}` （`story/{slug}.html`、フラットファイル。
  `vercel.json`の`trailingSlash: false`との整合、打ち出の小槌・開発日誌と同じ理由）
- 英語版：`/en/story`・`/en/story/{slug}`
- テンプレート：`templates/story/`（`header.html`/`footer.html`/`header_en.html`/
  `footer_en.html`は`templates/knowledge/`のものをJinja2の検索パス経由で再利用）
- CSS：`/assets/css/knowledge.css` ＋ `/assets/css/story.css`

### Story専用CSSを足した理由

打ち出の小槌・開発日誌はknowledge.cssだけで足りていたが、Storyは
(1) 1本が1万5千〜2万字と長い、(2) 一文一段落が続く文体、(3) サブタイトル・前後編・
記事間の順序というStoryにしか無いUI要素、の3点があるため、その分だけを
`assets/css/story.css`へ足した。**knowledge.css自体は変更していない**
（打ち出の小槌・開発日誌の既存表示に影響を出さないため）。

本文の幅は`38em`に絞ってある。デスクトップで全角約38文字／1行、モバイル（375px）で
約21文字／1行（2026-08-31にブラウザ実機で実測）。

---

## 10. グローバルナビゲーション

`templates/knowledge/header.html`・`header_en.html`のAboutと開発日誌の間に
`Story`を追加した（JA 14項目、EN 13項目）。`.nav`は`flex-wrap`のため折り返しで
破綻しない。モバイルはトグルメニューに入る（実機確認済み）。

`_SideKick_Development/docs/UX/04_NAVIGATION.md`（`status: draft`）は
「グローバルナビは4本柱+Aboutで一定」としているが、実装は以前から13項目で運用されており、
既存の開発日誌がナビにある以上Storyだけ導線が無いのは不整合になるため、
実装側の現状に合わせた。**この差異は村田さんへ報告済み（2026-08-31）。**

---

## 11. Developer Evidence と Product Evidence を混同しない

Storyには PENTAX / RICOH・Nikon・『デジタルフォト』・CP+・O-GPS1・大学研究・LSI開発・
Vectorソフトなどが登場する。これらは**村田一朗がどのような経験をしてきたか**
（Developer Evidence）を示すものであり、**現在のSidekick製品の性能・精度・メーカー公認**
（Product Evidence）ではない。

次のような含意を、本文にも導線にも作らないこと。

- 「PENTAX公認Sidekick」「RICOHが認めたSidekick」
- 「メーカーとの仕事があるからPlannerは正確」
- 「過去ソフト（Comet・燕・北燕）が現在のSidekickへ直接進化した」

記事テンプレートのAuthor Blockに、この趣旨の但し書きを常時表示している
（`templates/story/article.html`）。Plannerページ末尾にも同じ但し書きがある。

歴史表現についても同じ。**村田が比較明合成を発明したとは書かない。** 本文（Story 1）は
「一般写真の世界ではまだ広く知られていなかった／天文写真の一部ではすでに使われていた／
村田自身はその言葉を知らない状態でPhotoshopの合成方法へ独立に到達した」という位置づけを
取っており、この表現を弱めないこと。

---

## 12. PII / 公開禁止事項

Storyに次を書かない。

- 旧Waybackに残る電話番号、メールアドレス等の個人連絡先
- street-levelの位置情報
- 顧客データ、Photo Advice / PHODAYS の内部情報、受講生のPII、講評記録
- 比較対象の私的な氏名・数値
- 旧`murata-photo.com`への外部リンク（ドメインが失効し第三者のSEOスパムに転用されている。
  歴史資料として本文に出す必要がある場合も、現在の外部リンク先として使わない）

---

## 13. Sidekick Planner ページ

`/planner`・`/en/planner`（`build/site/build_site.py`のPAGESに登録、
テンプレートは`templates/site/pages/planner.html`・`en/planner.html`）。

Story 5を読んだ人が「Sidekick Plannerとは何か」を探したときの受け皿であり、
**完成製品ページではない。** 次を守ること。

- ページ上部に「現在開発中 / In development」を明示する
  （`tests/story/test_ja_en_parity.py::test_planner_page_states_it_is_in_development`で検証）
- 「実際に動いているもの」「Version 1で予定している範囲」「まだ決まっていないこと」
  「Version 1では対象にしないこと」を**見出しで分ける**。検討中を製品仕様の約束として
  書かない
- 記載内容の根拠は`Sidekickシリーズ/本体/Sidekick Planner/`の`README.md`・
  `CURRENT_WORK.md`・`docs/OPEN_QUESTIONS.md`を**実測して確認したものだけ**。
  会話の記憶から機能を列挙しない

2026-08-31時点で意図的に載せていないもの（すべて未決・対象外）：価格、提供時期、
提供形態、認証方式、年間データの配布方式、自動アップデート、コード署名、Web版・
スマートフォン版、アーチ構図・精密な構図検索、雲量予報オーバーレイ。

---

## 14. テスト

```powershell
python -m pytest tests/story -q
```

2026-08-31時点で64件（`test_build_story.py` 36件、`test_ja_en_parity.py` 17件、
`test_generate_story_sitemap.py` 11件）。

`test_build_story.py`と`test_generate_story_sitemap.py`はtempfile上で完結し、本番に
触れない。`test_production_story_html_matches_template`と`test_ja_en_parity.py`だけは
本番の生成物を**読む**が、書き込みは一切しない。

リポジトリ全体は`python -m pytest tests -q`で318件（`tests/site` 46件・
`tests/knowledge` 87件・`tests/development-log` 71件・`tests/tools` 50件・
`tests/story` 64件）。

---

## 15. 公開実績（2026-08-31時点）

日本語・英語とも、次の5本を`/story`・`/en/story`へ生成済み。

| order | slug | 備考 |
|---|---|---|
| 1 | `before-i-knew-lighten-composite` | 「比較明合成」を知らなかった私が、星をつなぐまで |
| 2 | `make-your-own-tools` | 撮るための道具は、自分で作ればいい（前編） |
| 3 | `good-tools-get-simpler` | いい道具は、だんだん簡単になる（後編） |
| 4 | `the-earth-keeps-turning` | 地球の自転は止められない |
| 5 | `when-and-where-should-i-go` | 「いつ、どこへ行けばいい？」から始まった |

あわせて`/planner`・`/en/planner`（開発中ページ）を新設した。

---

## 16. 残課題（今回見送った項目）

- **画像が1枚も無い。** 記事内の作例写真・記事別OGP画像は未対応
  （打ち出の小槌・開発日誌も同様のため、対象範囲を揃えた）
- **トップページ（`/`・`/en`）本文へのStory導線は追加していない。** グローバルナビと
  フッターからは辿れる。製品ハブとしてのHomepageの役割を壊さないため、本文への追加は
  村田さんの判断待ち
- **noteへの転載は未実装**（今回のUnitの対象外。Sidekick Labを原本・canonicalとする）
- **共通フッターの`<h4>`による見出し階層の飛び越し**（h2 → h4）は、Storyに限らず
  サイト全ページに以前から存在する。今回は共通フッターに手を入れていない
