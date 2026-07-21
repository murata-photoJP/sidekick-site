# 開発日誌（Development Log）ビルド — 実装記録

`_DevelopmentLog`（Photoshop Presetsフォルダ配下、別git repo）が生成する公開用の
開発日誌を、このWebリポジトリで閲覧できるようにする仕組み。打ち出の小槌
（`docs/KNOWLEDGE_BUILD.md`）と同じ設計方針（Python + Jinja2 + markdown-it-py、
atomicなステージング書き込み、sitemapはマーカーコメント方式）を踏襲するが、
入力が事前正規化されたJSONではなく、Markdown＋YAML front matterを直接読む点が異なる。

「更新履歴」（`changelog.html`）とは別コンテンツとして扱う。`changelog.html`は
手書きの静的HTMLでビルド処理を持たず、今回の実装はそれに一切触れていない。

---

## 1. 全体の流れ

```
_DevelopmentLog/public/YYYY/MM/YYYY-MM-DD[a-z].md  （status: published のみ）
        ↓ sync_development_log.py
content/development-log/YYYY/MM/YYYY-MM-DD[a-z].md  （このWebリポジトリ、コミット対象）
        ↓ build_development_log.py
development-log/index.html, development-log/{slug}.html
        ↓ generate_development_log_sitemap.py
sitemap.xml（マーカー区間のみ更新）
        ↓ git commit & push
Vercelが自動ビルド・公開
```

英語版（2026-07-21追加、軽量版）は並行トラックとして以下の流れになる。

```
_DevelopmentLog/public/YYYY/MM/YYYY-MM-DD.md（ja, status: published）
        ↓ _DevelopmentLog/scripts/translate_to_english.py（1回のAI翻訳）
_DevelopmentLog/public/en/YYYY/MM/YYYY-MM-DD.md（+.txt、status: draft固定）
        ↓ 村田さんが.txtを読んで確認（Google翻訳等での逆翻訳チェックを含む）
        ↓ 確認後、statusを手動でpublishedへ変更
        ↓ sync_development_log.py（--source public/en --dest content/development-log/en）
content/development-log/en/YYYY/MM/YYYY-MM-DD.md
        ↓ build_development_log.py（--content-en / --output-en）
en/development-log/index.html, en/development-log/{slug}.html
        ↓ generate_development_log_sitemap.py（--content-en）
sitemap.xml（英語版URLも同じマーカー区間に追加）
```

英語版は`_統合KB`の英語版Knowledge Base機能（監査AI・複数ラウンド・過剰修正検知）を
持ち込まない軽量版（村田さんの明示指示、2026-07-21）。AIによる翻訳監査レポートは
生成せず、村田さんが`.txt`を読んで（必要ならGoogle翻訳等で逆翻訳して）明らかな
誤りがないかを確認する運用とする。そのため生成直後は必ず`status: draft`。

Vercel上のビルド環境からはPhotoshopのPresetsフォルダを参照できないため、
**同期（sync）は必ずローカルで実行し、結果をこのリポジトリへコミットする**。
Vercel側でローカル同期処理を実行しようとしないこと。

---

## 2. 前提

- Python（`requirements-build.txt`）：`pip install -r requirements-build.txt`
  （Jinja2・markdown-it-py・PyYAML。このマシンには既にインストール済み）
- `_DevelopmentLog`の場所（このマシン）：
  `C:\Program Files\Adobe\Adobe Photoshop (Beta)\Presets\Scripts\自作\_DevelopmentLog`
- Webリポジトリ内の保存先：`content/development-log/`（コミット対象。
  `data/knowledge/web-published.json`と同じ位置づけの「受け取ったデータの正」）

---

## 3. コマンド

すべて、このリポジトリのルート（`html/`）で実行する。PowerShellの例。

```powershell
# 1. 同期（published のみ。draft/review/private等は同期されない）
python build/development-log/sync_development_log.py `
  --source "C:\Program Files\Adobe\Adobe Photoshop (Beta)\Presets\Scripts\自作\_DevelopmentLog\public" `
  --dest content/development-log

# 書き込まず結果だけ確認したい場合
python build/development-log/sync_development_log.py `
  --source "C:\Program Files\Adobe\Adobe Photoshop (Beta)\Presets\Scripts\自作\_DevelopmentLog\public" `
  --dest content/development-log --dry-run

# 2. ビルド（ローカル確認用ディレクトリへ。本番のdevelopment-log/を直接指定しない）
python build/development-log/build_development_log.py `
  --content content/development-log --output build-output/development-log

# 生成可能かどうかだけ確認（書き込まない）
python build/development-log/build_development_log.py `
  --content content/development-log --output build-output/development-log --validate-only

# 3. 確認後、本番ディレクトリへ反映（生成物を比較のうえ手動でコピー、または
#    直接 --output development-log を指定して再実行してもよい）

# 4. sitemap.xmlへ反映
python build/development-log/generate_development_log_sitemap.py `
  --content content/development-log --sitemap sitemap.xml

# テスト
python -m pytest tests/development-log -q
```

英語版を含める場合は、同期・ビルド・sitemap反映のそれぞれに英語版の引数を加える。

```powershell
# 英語版の同期（_DevelopmentLog側。public/enはstatus: publishedの記事のみ対象）
python build/development-log/sync_development_log.py `
  --source "C:\Program Files\Adobe\Adobe Photoshop (Beta)\Presets\Scripts\自作\_DevelopmentLog\public\en" `
  --dest content/development-log/en

# ビルド（ja+en同時、hreflang・言語切替リンクも自動で対応付けられる）
python build/development-log/build_development_log.py `
  --content content/development-log --output development-log `
  --content-en content/development-log/en --output-en en/development-log

# sitemap反映（ja+en同時）
python build/development-log/generate_development_log_sitemap.py `
  --content content/development-log --content-en content/development-log/en --sitemap sitemap.xml
```

`content/development-log/en/`は`_DevelopmentLog/public/en/`と同様に「英語版専用」の
予約ディレクトリとして扱う（`--content content/development-log`でのJA読み込み時は
自動的に除外される）。

パスに日本語・空白・括弧（`(Beta)`等）が含まれていても、上記のとおり
ダブルクォートで括れば問題なく動作する（`pathlib`ベースで実装しており、
文字列としての手動分解は行っていない）。

---

## 4. 新しい開発日誌を公開する手順（運用者向け）

1. `_DevelopmentLog`側で、公開したい記事のfront matterの`status`を
   `draft`から`published`へ変更する（この変更は`_DevelopmentLog`側の運用ルールに
   従い、明示的な承認を経てから行うこと）
2. 上記コマンドの「1. 同期」を実行する
3. 「2. ビルド」を`--validate-only`で実行し、エラー・警告が無いか確認する
4. 警告が無ければ、`--output development-log`を指定して実際にビルドする
   （または`build-output/`へ生成してから内容を見比べて`development-log/`へコピーする）
5. 「4. sitemap反映」を実行する
6. `content/development-log/`・`development-log/`・`sitemap.xml`の変更を
   git commitし、pushする
7. Vercelのビルドが完了したら、本番URLで表示を確認する

---

## 5. 公開可否の判定

`_DevelopmentLog`側の`status`（`draft`/`review`/`published`/`private`）をそのまま使う。
**`status: published`のファイルだけ**が同期・ビルドの対象になる。それ以外
（`draft`・`review`・`private`・未設定・front matter解析失敗等）は、1件ごとに
スキップして警告を表示するだけで、同期・ビルド全体は止めない。

**安全網（2026-07-21実装時に発見・追加）**：`_DevelopmentLog`のPUBLIC_LOG_TEMPLATE.mdには
「`## メモ（公開しない）`」という、公開前に手動で削除する前提のセクションがある
（コミットハッシュ・内部スクリプト名等が書かれうる）。削除し忘れたまま
`status: published`にされた場合に備え、このセクションが本文に残っているファイルは、
同期・ビルドの両方で検出し、公開対象から除外する（fail-closed）。

---

## 6. slugの決定方法

1. front matterに`slug`があれば、それを使う（英小文字・数字・ハイフンのみ）
2. 無ければ、ファイル名（拡張子を除いた部分）を使う。現行の生成規則により
   `YYYY-MM-DD`、または同日に複数回生成された場合の`YYYY-MM-DDb`/`YYYY-MM-DDc`
   （`_DevelopmentLog/docs/DEVELOPMENT_LOG_GUIDE.md`の命名規則）になっており、
   そのままURLセーフなslugとして使える

同期・ビルドのどちらも、公開対象の中でslugが重複した場合は**書き込みを一切行わず
エラー終了する**（公開URLの整合性を壊さないため）。

既存のURLを変更しないため、一度使われたslugは変えない（front matterに`slug`を
後から追加する場合も、既存のファイル名由来slugと同じ値にすること）。

---

## 7. 年・月ディレクトリの追加

`_DevelopmentLog/public/`配下を`rglob("*.md")`で再帰的に探索しているため、
`2026/08`・`2027/01`のような新しいディレクトリが増えても、コード変更は不要。

---

## 8. 画像の配置方法

現時点では開発日誌に画像は無いが、将来追加する場合は次の点に注意する。

- 画像srcはWeb上の絶対パス（`https://...`または`/...`）にすること。
  Windowsのローカル絶対パス（`C:\...`）や相対ファイルパスはビルド時に警告される
- altテキストが空の場合も警告される（生成は止めない）
- 実際の画像ファイルは、打ち出の小槌の`assets/`と同様、Webリポジトリの
  `assets/`配下へ別途配置する運用を想定（今回は画像自体の配置場所の新設は行っていない）

---

## 9. エラー・警告が出たときの確認箇所

| 症状 | 確認箇所 |
|---|---|
| 同期で「対象外」と出る | front matterの`status`が`published`になっているか |
| 同期・ビルドで「必須項目がありません」 | `title`・`date`・`status`が揃っているか |
| 「dateがYYYY-MM-DD形式ではありません」 | front matterの`date`の書式 |
| 「slugが重複しています」 | 同期・ビルドとも書き込みを行わず停止する。該当ファイルのファイル名またはfront matterの`slug`を確認する |
| 「メモ（公開しない）セクションが本文に残ったまま」 | `_DevelopmentLog`側の元ファイルからそのセクションを削除し、再同期する |
| 「画像srcがWeb上の絶対パスではありません」 | 本文中の`![alt](src)`のsrcを確認する（警告のみ、ビルドは止まらない） |
| ビルド後に古い記事のHTMLが消えない／消えてほしくないのに消えた | `development-log/`配下は本ツールが生成したファイルだけを置く場所という前提。手動で無関係な`.html`を置かないこと |

---

## 10. Vercel公開までの流れ

既存の打ち出の小槌と同じ。`vercel.json`（`cleanUrls: true`, `trailingSlash: false`）
により、`development-log/{slug}.html`は`/development-log/{slug}`として、
`development-log/index.html`は`/development-log`としてそのまま配信される。
git push後はVercelが自動でビルド・公開する（本仕組み自体はビルド時にPythonを
一切必要としない静的HTMLを生成するだけであり、Vercel側の追加設定は不要）。

---

## 11. 今回の実装で採用したURL・ディレクトリ構成

- 一覧ページ：`/development-log` （`development-log/index.html`）
- 個別記事：`/development-log/{slug}` （`development-log/{slug}.html`、フラットファイル。
  打ち出の小槌と同じ理由＝`vercel.json`の`trailingSlash: false`との整合）
- 英語版：`/en/development-log`・`/en/development-log/{slug}`
  （`en/development-log/index.html`・`en/development-log/{slug}.html`、
  打ち出の小槌の`en/knowledge/`と同じ配置方針）
- hreflang・言語切替リンク：英語記事front matterの`source_slug`で日本語版と対応付け、
  対応する翻訳が無い記事にはhreflangを出さない（存在しないURLを出力しない）
- テンプレート：`templates/development-log/`（`header.html`/`footer.html`/
  `header_en.html`/`footer_en.html`は`templates/knowledge/`のものをJinja2の
  検索パス経由でそのまま再利用）
- CSS：新規追加なし。既存の`/assets/css/knowledge.css`とkzc-*クラスをそのまま利用

---

## 12. テスト

```powershell
python -m pytest tests/development-log -q
```

同期・ビルド・sitemap反映のそれぞれについて、tempfile上の独立した
ディレクトリで完結するテストを用意した（本番の`_DevelopmentLog`・
`content/development-log`・`sitemap.xml`には一切触れない）。日本語・空白・
括弧を含むWindowsパスでの動作も確認済み（`test_sync_development_log.py::
test_handles_japanese_space_and_parenthesis_in_path`）。

既存の打ち出の小槌テスト（`tests/knowledge/`）と合わせて
`python -m pytest tests -q`で全件実行できる。

---

## 13. 残課題（今回見送った項目）

- トップページ（`index.html`）への「最新の開発日誌」導線は追加していない
  （`index.html`は手書きの静的HTMLでテンプレート化されておらず、今回の
  スコープでは一覧ページとナビゲーション導線のみとした）
- RSS（開発日誌専用・既存サイト共通とも）は追加していない（既存サイトに
  RSSの仕組みが無いため、今回は必須要件ではないと判断した）
- 記事別OGP画像・構造化データ（JSON-LD）は追加していない（打ち出の小槌の
  記事ページ自体がこれらを実装していないため、対象範囲を揃えた）
- 英語版の翻訳品質チェックは軽量版（村田さんが`.txt`を読んで確認、AIによる
  監査レポートは無し）。`_統合KB`のような複数ラウンド監査・過剰修正検知は
  意図的に持ち込んでいない

## 14. 公開実績（2026-07-21時点）

- 日本語：2026-07-18分・2026-07-20分を`/development-log`へ本番公開済み
- 英語：上記2本を`_DevelopmentLog/scripts/translate_to_english.py`で翻訳し、
  村田さんの確認後`/en/development-log`へ本番公開済み
