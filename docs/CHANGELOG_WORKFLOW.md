# 更新履歴（Changelog）— Codex運用ルール

> デプロイ前の全体チェック手順は`docs/DEPLOY_CHECKLIST.md`を参照。

## 1. 目的

この文書は、SideKick Labのユーザー向け更新履歴をCodexで安全に更新するための手順を定める。

更新履歴はDevelopment Logとは別物である。

- **Development Log**：開発過程、判断、失敗、学びを記録する
- **更新履歴**：ユーザーが知る必要のある製品・サービスの変更を簡潔に知らせる

内部整理、テスト追加、リファクタリング、ドキュメント整理を機械的にすべて掲載しない。

## 2. 対象ファイル

正本となるテンプレート：

```text
templates/site/pages/changelog.html
templates/site/pages/en/changelog.html
```

生成物：

```text
changelog.html
en/changelog.html
```

ビルド登録：

```text
build/site/build_site.py
```

生成済みHTMLだけを直接編集しない。原則として日英テンプレートを更新し、
`build_site.py`で日英の生成物を再生成する。

## 3. 更新候補の調査

次の情報を確認する。

1. 各対象リポジトリの`CHANGELOG_AI.md`
2. `PROJECT_STATUS.md`と`CURRENT_WORK.md`
3. Gitコミット履歴と差分
4. `_DevelopmentLog/private/`のRelease Note候補
5. 公開済みDevelopment Log
6. 実際の本番状態とテスト結果

確認できない内容を推測で掲載しない。日付、バージョン、価格、提供条件、
対応環境、公開状態が不明な場合はユーザーへ確認する。

## 4. 掲載する内容

次のような、ユーザーに意味がある変更を掲載する。

- 新製品・新機能の正式公開
- 既存機能の追加・変更
- 利用者に影響する不具合修正
- 対応環境・インストール・配布方法の変更
- 価格・試用期間・利用条件の変更
- Webサイトの主要な導線やサービス構成の変更
- Privacy、Terms、Legal等の重要ページ追加

次は原則として掲載しない。

- 内部だけのリファクタリング
- テストコードだけの変更
- AI作業ルールや引き継ぎ資料だけの変更
- 未公開機能
- 検証中で効果が確定していない変更
- ユーザーへの影響がない軽微な内部修正

迷う場合は追加せず、候補としてユーザーへ提示する。

## 5. 文体と内容

- 新しい項目をタイムラインの先頭へ追加する
- 日付は実際にユーザーへ提供・公開された日を使う
- タイトルだけで変更の意味が分かるようにする
- 箇条書きは、利用者に何が変わるかを中心にする
- 内部ファイル名・関数名・コミットIDを掲載しない
- 誇張、未確認の性能表現、販売を急かす表現を使わない
- 日本語版と英語版で、日付・項目数・事実関係を一致させる
- 英語は直訳調を避けるが、日本語版に無い主張を追加しない

既存の分類を使う。

- `data-type="sidekick"`：製品・ツールの変更
- `data-type="site"`：Webサイト・AI Lab・公開基盤等の変更

既存のタグ表記とCSSクラスを流用し、新しい分類やデザインを勝手に追加しない。

## 6. 作業手順

1. 対象リポジトリの未コミット変更を確認する
2. 更新候補と根拠を整理する
3. 掲載候補をユーザーに提示し、内容と日付を確認する
4. 日本語テンプレートへ追加する
5. 同じ内容を英語テンプレートへ追加する
6. 日英ページを一時出力または`--validate-only`で検証する
7. 日英の生成済みHTMLを更新する
8. 日英の項目対応、H1、リンク、Desktop／Mobile表示を確認する
9. 関係する全テストを実行する
10. 意図しない差分がないことを確認する

ビルド例：

```powershell
python build/site/build_site.py --output build-output/site --page changelog --validate-only
python build/site/build_site.py --output build-output/site --page en/changelog --validate-only

python build/site/build_site.py --output . --page changelog
python build/site/build_site.py --output . --page en/changelog
```

テスト：

```powershell
python -m pytest tests/site -q
python -m pytest tests -q
```

プロジェクト固有Pythonが無い場合は、ルート`AGENTS.md`の実行環境ルールに従う。
依存関係を勝手にグローバルインストールしない。

## 7. 公開

更新履歴の編集と本番公開は別工程として扱う。

- ユーザーの確認前にコミット・プッシュ・デプロイしない
- 公開指示があれば、今回の対象ファイルだけを明示的にステージする
- `main`へのプッシュでVercelが自動デプロイされる
- Vercel完了後、次を本番で確認する

```text
https://www.sidekick-lab.com/changelog
https://www.sidekick-lab.com/en/changelog
```

本番確認では、HTTP 200、最新項目、日英内容、言語切替、既存項目が残っていることを確認する。

## 8. Development Logとの連携

Privateログの`Release Note候補`は更新履歴の入力候補として使えるが、
自動的に掲載対象とは扱わない。

Public Development Logを公開したこと自体も、常に更新履歴へ載せる必要はない。
ユーザーにとって重要な新機能・変更である場合だけ掲載する。

