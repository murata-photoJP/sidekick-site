# デプロイ前チェック

サイト全体（`site` / `knowledge` / `development-log` / `story` の4系統）に共通する、
デプロイ前に確認すべき手順をまとめる。個別機能の実装記録・運用ルールは
それぞれの専用ドキュメント（`DEVELOPMENT_LOG_BUILD.md`・`KNOWLEDGE_BUILD.md`・
`KNOWLEDGE_UI_PHASE_A2.md`・`STORY_BUILD.md`・`CHANGELOG_WORKFLOW.md`・
`CODEX_CHANGELOG_PROMPT.md`・`DOWNLOAD_CONTACTS.md`）を参照すること。
このドキュメントはそれらを置き換えない。

## 背景

2026-08-30、「テンプレートを直したのに本番HTMLを作り直していない（あるいはその逆）」
という不具合が3件見つかった（`about.html`・`changelog.html`・`en/knowledge`のフッター）。
いずれも直した瞬間には何も起きず、次に誰かが再ビルドしたときに初めて症状が出るという
共通構造を持っていた。特にフッターの件は5週間気づかれなかった。

この文書は、同じ種類の見落としを繰り返さないための最低限のチェック手順を定める。

---

## 1. テンプレート↔本番HTML の差分チェック（4系統ぶん）

このリポジトリには、テンプレートから静的HTMLを生成する仕組みが**4系統**ある。
1つだけ確認して安心しないこと。

| 系統 | テンプレート | ビルドスクリプト | 本番出力 |
|---|---|---|---|
| site | `templates/site/pages/` | `build/site/build_site.py` | ルート直下・`en/`直下の各ページ |
| knowledge（打ち出の小槌） | `templates/knowledge/` | `build/knowledge/build_knowledge.py` | `knowledge/`・`en/knowledge/` |
| development-log（開発日誌） | `templates/development-log/` | `build/development-log/build_development_log.py` | `development-log/`・`en/development-log/` |
| story | `templates/story/` | `build/story/build_story.py` | `story/`・`en/story/` |

それぞれに、テンプレートのレンダリング結果と本番HTMLを比較する回帰テストがある
（2026-08-30 `d3e8902`で3系統ぶんを追加、2026-08-31にstory系統を追加）。

```bash
python -m pytest tests/site/test_build_site.py::test_production_html_matches_template_render -q
python -m pytest tests/knowledge/test_build_knowledge.py::test_production_knowledge_html_matches_template -q
python -m pytest tests/development-log/test_build_development_log.py::test_production_devlog_html_matches_template -q
python -m pytest tests/story/test_build_story.py::test_production_story_html_matches_template -q
```

**ヘッダー・フッター（`templates/knowledge/header.html`・`header_en.html`・
`footer.html`・`footer_en.html`）は4系統すべてが共用している。** ここを1行でも変えたら、
**4系統すべてを再ビルドして本番へ反映する**こと。1系統だけ再ビルドすると、残りは
次に誰かが再ビルドするまで古いヘッダーのまま配信され続ける（この文書の「背景」と
同じ構造の見落としになる）。

なお`build_knowledge.py`の英語版出力は`--output`の**兄弟**（`{output}/../en/knowledge/`）
へ書かれる。`--output build-output/knowledge`で生成した場合、英語版は
`build-output/knowledge/en/`ではなく`build-output/en/knowledge/`にある。
本番へコピーするときに見落としやすい（2026-08-31に実際に見落とし、
`test_production_knowledge_html_matches_template`が検出した）。

### 1-2. 一時ビルドは本番相当ビルドとJA/EN出力ツリーを共有してはならない（2026-09-03 KB-BUILD-2）

**原則：一時ビルド（spike・比較用ビルド・検証用ビルド）は、本番相当ビルドと
日本語版・英語版のどちらの出力ツリーも共有しない。**

`build_knowledge.py`の英語版出力先は、`--output-en`を省略すると`--output`の親から
`{output}/../en/knowledge/`として導出される。つまり**`--output`を分けても、親ディレクトリを
共有していれば英語版の出力先は同じになる**。全記事ビルドは今回のインデックスに含まれない
古い`.html`を削除するため、**一時ビルドが本番相当ビルドの英語版HTMLをstale扱いで削除する**。

2026-09-03、Gate C-1のtechnical spikeで実際に発生した。`--output build-output/spike-knowledge`
で生成したところ、英語版出力先が`build-output/en/knowledge/`と解決され、
`--output build-output/knowledge`側が生成した英語版7ページが削除された。

**一時ビルドでは`--output-en`も必ず明示する。**

```bash
python build/knowledge/build_knowledge.py \
  --index data/knowledge/web-published.json \
  --output build-output/spike/knowledge \
  --output-en build-output/spike/en/knowledge
```

本番相当ビルド（`--output build-output/knowledge`）は、既定の導出のままでよい。
`build_knowledge.py`は実行時に`[info] 英語版の出力先: ...`を必ず表示するので、
**意図しない場所へ書いていないかを毎回確認すること**。

デプロイ前は、この4つを個別に意識するか、後述の「2. pytestの実行範囲」で
まとめて実行すること。

**期待される出力**：上記4テストはいずれも比較前にBOM・CRLFを正規化する
（`_normalize_html`系関数、「内容の差ではない」という理由で意図的に無視している）。
そのため、**BOMの有無だけの食い違いはこのテストでは検出できない**。2026-08-30時点で
テンプレート6本（`index.html`・`ai-lab.html`・`ai-review.html`・`camera-ai.html`・
`pc-ai.html`・`shooting-ai.html`）にBOMがあり本番にBOMが無い状態だったが、
これは上記テストでは常に検出されず「差分ゼロ」のまま通っていた。BOMの有無自体は
本文書「4. BOMの有無を確認する」のバイト単位チェックで別途確認すること。
上記4テストが期待するのは、あくまで**BOM・CRLF以外の内容が完全に一致していること**であり、
これは常に差分ゼロが期待値になる（例外は無い）。

テストに頼らず手動で確認する場合は、各ビルドスクリプトを`build-output/`配下の
一時ディレクトリへ出力し、本番ディレクトリと`diff -rq`で比較してから、
変更のあったファイルだけを本番へコピーする（本番ディレクトリを直接
`--output`に指定しない）。各`build/*/*.py --help`に手順がある。

---

## 2. pytest の実行範囲

全体を通すコマンドは常にこれ。

```powershell
python -m pytest tests -q
```

**PASS条件は「全件PASSし、次の5スイートがすべて収集されていること」。**

- `tests/site`
- `tests/knowledge`
- `tests/development-log`
- `tests/tools`
- `tests/story`

`tests/`配下の一部だけを指定すると、当然それより少ない件数になる。とくに
`tests/tools`は忘れやすく、これを含めない4スイートだけの実行は全体より少なくなる。
2026-08-30、この取り違えが実際に報告に混ざった。

デプロイ前・作業報告で件数を出すときは、**実行したコマンドと対象を件数に併記する**
こと。「399 passed」とだけ書かず、「`pytest tests -q` で399 passed」のように書く。

**合計件数はこの文書に確定値として書かない。** 件数はUnitごとに増えるため、書けば
必ず陳腐化する。実際、318件と書かれたまま実測399件まで放置され、この文書自身が
「件数を併記せよ」と定めているのに文書側の数字が最も古い、という状態になっていた
（2026-09-01に是正）。報告に出す件数は、そのつど上のコマンドを実行して得ること。

参考値（2026-09-01時点、確定値ではない）：`pytest tests -q`で399件
（`tests/site` 127・`tests/knowledge` 87・`tests/development-log` 71・
`tests/tools` 50・`tests/story` 64）。

スイートを追加・改名したときは上の一覧も更新すること。一覧と実体の一致は
`tests/site/test_deploy_policy.py`が検査する。

---

## 2-2. sitemap.xml へ載せるかどうかの判断

`sitemap.xml`は**前半（site系ページ）が手書き、後半3ブロックが自動生成**という
混成ファイルである。

| 範囲 | 生成 |
|---|---|
| 先頭〜`BEGIN AUTO-GENERATED KNOWLEDGE URLS`の直前 | **手書き**（site系の全ページ） |
| KNOWLEDGE / DEVELOPMENT LOG / STORY の各マーカーブロック | 各`generate_*_sitemap.py`が置換 |

site系にはジェネレータが無いため、**ページを新設しても誰も自動では追加しない**。
実際に`/en/legal`・`/en/privacy`は2026-07-25に公開されながら、2026-09-01までの
38日間sitemapへ入っていなかった。原因は、EN全ページを一括登録した
コミット（2026-07-14）の時点でこの2ページがまだ存在せず、後から追加したコミットが
sitemapに触れなかったこと。悪意も設計判断も無い、単なる追随漏れである。

**判断基準**：ページが次を*すべて*満たすなら、sitemapへ載せる。

1. self-canonical を持つ（自分自身が正規URL）
2. `<meta name="robots">` で noindex にしていない
3. 対になる言語版があり、hreflang が相互参照になっている
4. その対の片方が既にsitemapへ載っている

購入・ダウンロード・完了などの導線ページ（`buy-*`・`dl-*`・`thanks*`・
`register-dl`）は3を満たさない単独の機能ページで、意図的に非掲載にしている。
`workshop`は日本語限定（英語版を作らない、`build_site.py`に明記）なので
対称性の問題ではない。

この4条件の破れは`tests/site/test_deploy_policy.py`が検出する。

### 単独LP（star-lp / kouzu-lp）の扱い — 2026-09-01 村田さん決定

`star-lp.html`・`kouzu-lp.html`は、Sidekick製品ではなく**写真実践塾**
（`photo-kouza.com`）の講座を紹介する単独LP。共通ヘッダー／フッターを使わず
（「村田一朗 写真の学び場」という別ブランディング）、テンプレート生成でもなく、
サイト内の被リンクは互いのみ。それでいて本文は長文・作例写真つきで、
title / description / keywords も明確に検索流入を狙う作りになっている。

**方針：独立した検索Landingとしてindexさせる（C-1）。**

- self canonical を持たせる（`https://www.sidekick-lab.com/{slug}`）
- `og:url` は canonical と同じ値にする
- sitemapへ載せる（priority 0.6、`workshop`と同じ「学び」系の扱い）
- **noindexにはしない。他ページへのcanonical統合もしない**

他ページへ統合しない理由は、統合先となる重複ページがサイト内に存在しないため。
これらは外部講座の紹介であり、`/lp-star`（SideKick Star の製品LP）とは
検索意図も内容も別物である。

上の4条件は対になる言語版を前提にしているが、この2ページは日本語限定で
条件3を満たさない。そのため掲載可否は4条件では決まらず、この節の決定が根拠になる。
`tests/site/test_deploy_policy.py`が、canonical・og:url・sitemap掲載・
noindexでないことを名指しで固定している。

---

## 3. 一括置換をするときのGUARD手順

複数ファイルにまたがる機械的な一括置換（表記統一・リンク修正・BOM除去等）を行う際は、
次を必ず行う。2026-08-24、後処理の正規表現置換がJavaScript 90ファイルを壊した実例
（`s.replace(" ()", "")`が`function () {`を`function {`に変え構文エラーにした）があり、
このときスクリプト自身は「完了・保護対象も無傷」と表示していた。**スクリプトの自己申告は
信用せず、`git diff`を実際に見て確認する。**

- [ ] **明示的な文字列ペアだけを置換する。** 素の記号（`×`・`()`・数字単体等）を
      正規表現で置換しない。このリポジトリで壊れやすい実例：
      `512×512`（`about.html`等に登場する画像処理装置のスペック）、
      `4×5大判カメラ`（`workshop.html`等のワークショップ告知）。
- [ ] **「掃除」のための後処理を追加しない。** 空白・空カッコの整形は、
      置換ペア側に含めて一度で済ませるか、別途目視で確認する。
- [ ] **保護対象リスト（GUARD）を作り、処理前後で件数が一致することを確認する。**

  ```python
  GUARD = ["512×512", "4×5大判カメラ"]  # 絶対に壊してはいけない文字列（このリポジトリの例）
  # 対象ファイル群での出現回数を処理前後で数え、一致しなければ異常とみなす
  ```

- [ ] **JS/CSSの破損チェックを明示的に走らせる。**

  ```bash
  for k in "function {" "( =>" ", =>"; do
    grep -rF "$k" --include="*.html" . | wc -l   # いずれも0であること
  done
  ```

- [ ] **`git diff`を「意図した表現以外」で絞って確認する。** 最後の砦。

  ```bash
  git diff -U0 | grep -E "^[+-]" | grep -vE "^[+-]{3}" | grep -viE "意図した語1|意図した語2"
  # ↑ ここが空でなければ、意図しない変更が混ざっている
  ```

- [ ] **テンプレートと本番出力の両方を直したか確認する。** 片方だけだと
      次の再ビルドで巻き戻る（本文書の背景を参照）。上記「1.」の差分チェックで検出できる。
- [ ] **作業前に`git status`が空であることを確認する。** 途中で問題が起きても
      `git checkout -- .`で完全に戻せる状態から始める。

より詳しい調査時の一般的なチェックリストは`D:\OSINT調査\99_作業用\調査チェックリスト.md`
§4.5にあるが、そちらは調査プロジェクト側の運用文書であり、このリポジトリの正本ではない。
上記はこのリポジトリ向けに必要な部分だけを移した内容である。

---

## 4. BOMの有無を確認する

「1.」のテンプレート↔本番HTML差分チェックはBOM・CRLFを意図的に無視するため、
**BOMの有無だけが食い違っていても検出できない。** BOMは不可視文字であり、
`git diff`の見た目でも分かりにくい。2026-08-30、まさにこの「不可視文字が差分の
要約に紛れて見えなくなる」件が実際に起きている。BOMの有無を確認するときは、
バイト単位で見る。

```bash
# 各ファイルの先頭3バイトを見る。EF BB BF ならBOMあり
for f in index.html ai-lab.html ai-review.html camera-ai.html pc-ai.html shooting-ai.html; do
  printf "%s: " "$f"; head -c 3 "$f" | od -An -tx1
done
```

```python
# Pythonで確認する場合
data = open("index.html", "rb").read()
has_bom = data[:3] == b"\xef\xbb\xbf"
```

テンプレート側と本番側は常に同じBOM状態（両方あり／両方無し）で揃っていること。
どちらかにだけBOMがある状態は、次の全ページ再ビルドでBOMが消える・増えるという
形で本番へ意図せず影響する。
