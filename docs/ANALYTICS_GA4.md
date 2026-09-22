# GA4（Google アナリティクス 4）の配置と計測境界

サイト全体の GA4 タグ（gtag.js）が「どのページに・どの仕組みで」入っているか、
そして **いつから何が計測されているか（計測境界）** を記録する。
記事ごとのPV・X（t.co）からの流入など、後から数字を読むときは必ずこの境界を先に確認すること。

- Measurement ID：`G-K73T3Y352W`（サイト全体で1つ。別IDを増やさない）
- 再発防止テスト：`tests/site/test_deploy_policy.py`「GA4（gtag.js）の配置ポリシー」
- 共用パーシャル：`templates/knowledge/components/ga4.html`

---

## 1. 計測境界（Measurement boundary）— 2026-09-22

### 何が起きていたか

GA4 タグは 2026-06-06（commit `a80e497`「全ページにGA4トラッキングコード追加」）に、
当時存在した **手書きHTML 20ファイル** へ個別に貼られた。その後に Jinja2 テンプレートとして
新設した以下の系統には貼られず、**本番で配信されていた 154 ページ中 98 ページが GA4 に
一切記録されていなかった**（`share.html` は設計上の除外、残り 55 ページは計測されていた）。

| 系統 | 本番パス | ページ数（2026-09-22） | 未計測だった期間 |
|---|---|---|---|
| 打ち出の小槌（knowledge） | `knowledge/`・`en/knowledge/` | 34 + 34 | 2026-07-17（`520676b`、初公開）〜 GA4 導入デプロイまで |
| 開発日誌（development-log） | `development-log/`・`en/development-log/` | 7 + 7 | 系統新設〜同上 |
| Story | `story/`・`en/story/` | 6 + 6 | 系統新設〜同上 |
| 被写界深度計算機 | `tools/dof.html`・`en/tools/dof.html` | 1 + 1 | 系統新設〜同上 |
| 著者ページ | `ichiro-murata.html`・`en/ichiro-murata.html` | 1 + 1 | 系統新設〜同上 |

2026-09-21、村田さんが「記事を開くとリアルタイムには `page_view` が出るのに、
『ページとスクリーン』30日レポートで記事URL（`is-0-03mm`）が0件」という形で発見した。
リアルタイムに出ていたのは同じセッション内の別ページ（JAトップ等、GA4 が入っているページ）の
イベントであり、記事自身からは何も送られていなかった（調査結果は同日に村田さんが承認）。

### 導入の記録

| 項目 | 値 |
|---|---|
| テンプレート修正・本番HTML再生成 commit（sidekick-site） | 2026-09-22（commit ハッシュは `git log -- docs/ANALYTICS_GA4.md` の初回 commit を参照） |
| **本番デプロイ（Vercel）日時** | **未デプロイ（デプロイ後に村田さんが JST で記入する）** |
| 計測が始まるページ | 上表の 98 ページ（JA/EN の打ち出の小槌トップ・全記事を含む） |
| 変えていないもの | 記事本文・URL・title / meta description / canonical / hreflang・sitemap・taxonomy・記事ID・言語自動判定／リダイレクト仕様・Clarity |

### 数字を読むときの規則

- **導入デプロイ以前の上記 98 ページの PV は「0」ではなく `UNKNOWN / NOT MEASURED`（欠測）として扱う。**
  GA4 の「ページとスクリーン」で該当URLが0件・空欄になっているのは「訪問が無かった」ことを意味しない。
- 導入デプロイ以後は、他ページと同じ既定動作（`gtag('config')` の自動 `page_view`）で
  `page_location`＝そのページの正規URL、`page_path`＝`/knowledge/...` 等のパス、`page_title`＝各ページ固有の `<title>`
  が記録される。SPA ではなく静的HTMLなので、ページ遷移ごとに通常のページ読み込みとして計測される。
- **Sidekick Lab X Phase 2 prospective observation**（`D:\OSINT調査\04_発信分析\research-content-title-hook\phase2_design\`）
  の `article_pv` は、この境界より前の観測窓では `missing_reason` に「GA4 tag absent on /knowledge/ until <デプロイ日時>」を
  書いて `UNKNOWN` とする（事前登録 `01_phase2_preregistration.md`「欠測は0ではなく missing reason つき UNKNOWN」に従う）。
  P2-C07（`/knowledge/photography/is-0-03mm-blur-visible-in-print`、X 投稿予定 2026-09-20 20:00 JST）は
  この境界をまたぐ最初の候補なので、投稿〜デプロイ間の PV は欠測、デプロイ後の窓から計測値になる。
  `article_analytics_source` には `GA4 G-K73T3Y352W (tag deployed <デプロイ日時>)` を書く。
- X（t.co）からの流入は、導入後は GA4 の既定の参照元判定（`t.co / referral`）で記録される。
  ただし下記「3. 既知の制約」の言語リダイレクトにより、非日本語ブラウザからの流入は記事URLに残らない。

---

## 2. 仕組み（どこに何があるか）

### 共用パーシャル

`templates/knowledge/components/ga4.html` が gtag.js スニペットの唯一の置き場。内容は手書きページに
貼られている既存スニペットと同一（Clarity は含まない）。`templates/knowledge/` に置いてあるのは、
development-log・story・site の各ビルドが Jinja2 の検索パスに `templates/knowledge/` を含んでおり
（header / footer と同じ仕組み）、どの系統からも `{% include "components/ga4.html" %}` で参照できるため。

### 系統ごとの置き場

| 系統 | GA4 の置き場 |
|---|---|
| knowledge | `templates/knowledge/base.html` の `<head>` 末尾で include |
| development-log | `templates/development-log/base.html` の `<head>` 末尾で include |
| story | `templates/story/base.html` の `<head>` 末尾で include |
| site（手書きから移行した各ページ） | 各ページテンプレートの `{% block extra_head %}` にスニペット直書き（2026-06-06 の貼付をそのまま移行したもの） |
| site（`dof` / `en/dof` / `ichiro-murata` / `en/ichiro-murata`） | 各ページテンプレートの `{% block extra_head %}` 末尾で include |
| `share.html`（Snapshot Viewer） | **入れない**（設計上 analytics なし。正本は Planner リポジトリ側、`DEPLOY_CHECKLIST.md`「Snapshot Viewer（/share）の扱い」） |

`templates/site/base.html` には置いていない。手書き移行ページが各自 `extra_head` に持っているため、
base に置くと二重に送信される。site 系に新しいページテンプレートを追加するときは、
`{% block extra_head %}` に `{% include "components/ga4.html" %}` を1回入れること
（入れ忘れ・二重は `test_every_site_page_template_carries_ga4` が検出する）。

### 再発防止テスト（`tests/site/test_deploy_policy.py`）

| テスト | 固定していること |
|---|---|
| `test_ga4_partial_defines_the_measurement_id_exactly_once` | パーシャルがローダーと config で `G-K73T3Y352W` をちょうど1回ずつ持つ |
| `test_every_production_page_has_exactly_one_ga4_tag` | `share.html` を除く全本番HTMLが gtag.js をちょうど1回持つ（0回＝未計測、2回＝二重送信） |
| `test_production_pages_use_only_the_intended_measurement_id` | 本番HTMLに現れる Measurement ID が `G-K73T3Y352W` だけ |
| `test_no_analytics_by_design_pages_stay_free_of_analytics` | `share.html` に GA4 / Clarity が混入しない（逆向きの固定） |
| `test_template_family_base_includes_ga4` | knowledge / development-log / story の base.html が include を持つ |
| `test_every_site_page_template_carries_ga4` | site 系の全ページテンプレートが GA4 を1回持つ |

`firebase-init.js` の `measurementId: "G-SBJEMRYFZQ"` は Firebase 設定の一部で、`getAnalytics` を
呼んでいないため計測には使われていない（HTML にも現れない）。HTML に現れたら混入として上のテストが検出する。

### デプロイ後の確認手順（村田さん）

1. GA4 → リアルタイム → 記事URL（例 `/knowledge/photography/is-0-03mm-blur-visible-in-print`）を開き、
   `page_view` の **ページタイトル** がその記事の `<title>` になっていること（共通タイトルではない）。
2. 翌日以降、「ページとスクリーン」で `/knowledge/` を検索して記事パスが並ぶこと。
3. 本文書「1. 導入の記録」の **本番デプロイ日時** を JST で記入する。

---

## 3. 既知の制約・Future Work（今回は変更していない）

### 言語自動判定リダイレクトが記事URLの計測を落とす — 別 issue

`templates/knowledge/base.html`（development-log・story の base.html も同じ）の先頭スクリプトは、
`localStorage.sk_lang_pref === 'en'` またはブラウザ言語が非日本語のとき、記事ページから
`location.replace('/en/')`（**英語トップ**、EN版記事ではない）へ飛ばす。この場合：

- GA4 には `/en/` の `page_view` だけが残り、記事URLは残らない
- 参照元は t.co ではなく自サイト（自己参照として除外）になり、X からの流入として数えられない
- 訪問者は EN 版記事（hreflang で対応づけ済み）ではなくトップに着地する

2026-07-20 に「既存動作を変えない」方針で `/en/` 固定にしたもの（base.html のコメント参照）。
遷移先を hreflang 対応URL（EN 版記事）へ変えるかどうかは、UX と計測の両面から
**別途村田さんの判断**とし、今回の GA4 導入 Unit では変更していない。
Phase 2 の数字を読むときは、非日本語ブラウザからの流入がこの経路で欠けることを前提に置く。

### Clarity

Microsoft Clarity は手書き移行ページだけが持っている。テンプレート系統への展開は今回の scope 外。

### 記事ごとの閲覧数の利用

`KNOWLEDGE_UI_PHASE_A2.md`「おすすめ記事（PICK UP）」は「閲覧数を安全に取得できる仕組みが無い」前提で
手動選定にしている。GA4 導入後もこの方針は変えない（Data API 連携・資格情報の扱いは別課題）。
