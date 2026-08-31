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

**`python -m pytest tests -q` は318件**（`tests/site` 46件・`tests/knowledge` 87件・
`tests/development-log` 71件・`tests/tools` 50件・`tests/story` 64件の全5スイート）。
2026-08-31にStory領域の新設で254件→318件になった（`tests/story`の64件が増分）。

`tests/`配下の一部だけを指定すると、当然それより少ない件数になる。
例えば`tests/tools`を含めない4スイートだけの実行では268件になる。
2026-08-30、この取り違えが実際に報告に混ざった。

デプロイ前・作業報告で件数を出すときは、**実行したコマンドと対象を件数に併記する**
こと。「318 passed」とだけ書かず、「`pytest tests -q` で318 passed」のように書く。

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
