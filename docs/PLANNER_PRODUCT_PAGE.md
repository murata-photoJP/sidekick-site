# Sidekick Planner β1.00 製品ページ（/sidekick-planner）と配布導線

2026-09-20 新設（自作リポジトリ側 Track `planner-beta1-web-product-page`、AI-10450、
HD namespace `HD-PLANNERBETA1WEBPRODUCTPAGE`）。

> **状態: Human Review 待ち。本番デプロイ（`origin/main` への push）はしていない。**
> Public Beta Distribution（配布 URL・2GB artifact の hosting・実ダウンロード）は開始していない。
> 配布導線は fail-closed（下記 3.）。

## 1. 何を追加したか

| 種別 | パス | 内容 |
|---|---|---|
| テンプレート | `templates/site/pages/sidekick-planner.html` / `templates/site/pages/en/sidekick-planner.html` | 製品ページ JA/EN（`build_site.py` の `_register_page_pair("sidekick-planner")`）。Star / Portrait / Sky と同じ製品ページ系列 |
| 本番 HTML | `sidekick-planner.html` / `en/sidekick-planner.html` | `build_site.py` の生成物（手書き禁止。`test_production_html_matches_template_render` が固定） |
| 画像 | `images/planner/*.jpg` / `*.png` | 実画面のスクリーンショット（下記 4.） |
| 配布導線 | `register-dl.html`（`planner` product 追加）、`dl-planner.html`（新設、fail-closed） | 下記 3. |
| API / tool | `api/add-contact.js`、`tools/create_brevo_attributes.py`、`tools/reconcile_downloads_brevo.py` | `planner` → `HAS_PLANNER` / `VER_PLANNER` の対応を追加（既存製品の挙動は不変） |
| sitemap | `sitemap.xml` | `/sidekick-planner`・`/en/sidekick-planner` を追加（`test_deploy_policy` の 4 条件を満たすため） |
| テスト | `tests/site/test_planner_product_page.py`（新設）、`tests/site/test_download_flow_links.py`・`tests/tools/test_reconcile_downloads_brevo.py`（planner を追加） | |
| 手順・確認 | `tools/planner_product_page_screenshots.py`（実画面の撮影）、`tools/preview_static_site.py`（cleanUrls 相当の確認用サーバー）、本書 | |

変更していないもの: 既存の `/planner`（開発中ページ）、共通 header / footer（Planner のナビ項目・フッター表記
「Sidekick Planner（開発中）」）、`/planner-terms`・`/privacy`（Legal 文面）、`vercel.json`、トップページ、
既存製品の `dl-*.html` / `buy-*.html`、Planner 本体（RC13 / 年間データ / Production）。

## 2. ページ内容の根拠（推測で書かない）

| 記述 | 根拠（自作リポジトリ、Planner 配下） |
|---|---|
| 版 `1.0.0-beta.1`（β1.00）、EXE SHA-256 `709afc4e…`、2,185 file / 2,079,489,773 B（約2GB）、annual asset 374 | `validation/prototype/diamond_fuji_minimal/clean_machine/release_acceptance.json`（record_version 4）。EXE hash はページ作成時に `dist/rc13` で再計算し一致 |
| Windows 10 64-bit 以降 | `HD-OS-01`（`microsoft_runtime_policy.py`） |
| 未署名 / SmartScreen 警告の可能性 / 証明書取得手続き中 / SHA-256 / 公式配布元 / security 無効化を案内しない | `HD-MC-12`〜`14`（`docs/ai-analysis/PLANNER_BETA1_CODE_SIGNING_DECISION_2026-09-20.md`） |
| 提供期間 = 一般公開日〜2026-10-31 予定 | `HD-LR-40`、`/planner-terms` 第3条 |
| 初期 Public Beta は日本語 UI、Legal は JA/EN | `HD-PLANNERBETA1LOCALIZATIONPOLICY-001`〜`005` |
| 太陽 × 被写体（100 か所）、パール = 近日対応（計算不可） | `beta_capability.py`、`/api/poi-catalog`（100 POI: building 18 / castle 17 / temple 8 / bridge 5 / statue 2 / station 1 / 富士山 1 / 山岳 48） |
| 参考ライン・検索B・展望プレビュー（稜線・太陽軌跡・レンズ・50m 刻み・Google マップ）・QR 共有（スマホで見る / Plannerへ渡す）・共有QR読み込み | `assets/web/planner_runtime.html` の実画面 |
| 公開してよい範囲（星景・将来ジャンル・ロードマップを出さない。パールは「近日対応」のみ） | `HD-PLANNERBETA1GENERICSURFACE-009`（`test_planner_product_page.test_concealed_roadmap_terms_absent` が固定） |

## 3. 配布導線（fail-closed）

```
/sidekick-planner  ── β版を試す（無料）──▶  /register-dl?product=planner&src=sidekick-planner
                                                │ 同意 + メール登録（/api/add-contact、Star と同じ）
                                                ▼
                                           /dl-planner
                                                │ PLANNER_DOWNLOAD_URL / PLANNER_ZIP_SHA256 が空
                                                ▼
                                          「配布は準備中」（ダウンロードリンク無し）
```

- `dl-planner.html` は `sk_dl_authorized`（メール登録の一回使い捨てフラグ）が無ければ
  `/register-dl?product=planner&src=dl-planner` へ戻す（`dl-star.html` と同じ）。
- **配布開始前**: 2 定数が空文字なので `pending-state`（準備中）だけを表示する。EXE の SHA-256・未署名の
  disclosure・Terms / Privacy link・再配布禁止は準備中の状態でも表示する。
- **配布開始（Distribution Unit、Human GO）で行うこと**（2026-09-20 追記: hosting 先・ZIP・hash は `docs/PLANNER_DISTRIBUTION.md` に準備済み。既存製品と同じ R2 `sidekick-downloads`）: `PLANNER_DOWNLOAD_URL`
  （`https://…/*.zip`）と `PLANNER_ZIP_SHA256`（配布 ZIP の hash、64 hex）を埋める →
  `tests/site/test_planner_product_page.py::test_dl_planner_is_fail_closed_before_distribution` を
  意図的に更新 → live 検証 PASS をもって actual Public Beta release（`HD-PLANNERBETA1PUBLICBETAAUTHORIZATION-001`）。
- Brevo 属性 `HAS_PLANNER` / `VER_PLANNER` は **Brevo 側で未作成**。作成は Human の操作
  （`py -3.10 tools/create_brevo_attributes.py --dry-run` → 実行、API key が必要）。未作成でも
  `add-contact.js` は従来属性で再送する（`degraded: "new_attributes_missing"`、導線は止まらない）。
- ローカル（静的配信）では `/api/add-contact` が無いので登録は失敗ログを残して `/dl-planner` へ進む
  （本番の Firestore / Brevo には何も書かれない）。

## 4. スクリーンショットの再生成

画像はモックアップではなく、**RC13 と同一の配布物（のコピー）を起動して撮った実画面**。

1. canonical の `dist/rc13/Sidekick Planner` を **別の場所へコピー**する（配布物フォルダーを直接動かさない。
   起動すると `output/` などが生成されるため）。コピー後 `SidekickPlanner.exe` の SHA-256 が
   `709afc4e…` であることを確認する。
2. コピー先で headless 起動する（Activity の本番送信を止める）:
   ```
   SidekickPlanner.exe --port 18795 --no-browser --no-window --no-activity-upload
   ```
   `http://127.0.0.1:18795/health` が `READY` になるまで待つ（初回は 20 秒程度）。
   ※ canonical の `Diamond Fuji Prototype Runtime.bat` は使わない（Production ① 実行中は canonical server を
   起動しない、という Planner 側の運用）。既定 port 8765 は開発機で別 server が使っていることがある。
3. このリポジトリのルートを静的配信する（Viewer 用）: `py -3.10 -m http.server 3333 --directory <html>`
4. 撮る（`py -3.10` に playwright + Chromium、opencv-python が必要）:
   ```
   py -3.10 tools/planner_product_page_screenshots.py --out <一時ディレクトリ>
   ```
   出力: `planner-overview` / `search-b` / `map` / `composition-preview` / `composition-preview-panel` /
   `qr-share` / `viewer-mobile` / `viewer-mobile-full`（PNG）。検索B は clean-machine 試験と同じ
   座標・期間（緯度 35.3714150 / 経度 138.7834167 / 2027-03-29〜04-02 → 最良 2027-03-30T16:08:59）。
   Viewer は QR を OpenCV で読み取り、その共有 URL の fragment を `share.html` で開いて撮る
   （390×844、devicePixelRatio 2）。
5. `images/planner/` へ置く。地図を含む大きい画面は JPEG（品質 86）、QR / Viewer / プレビュー枠は PNG。
   合計 2.1 MB 程度（Vercel の deploy 容量に配慮）。

iPhone 実機のスクリーンショットは含めていない（必要なら Human Review 後に追加）。

## 5. ローカル確認（Human Review）

```
.\.venv\Scripts\python.exe build/site/build_site.py --output . --page sidekick-planner
.\.venv\Scripts\python.exe build/site/build_site.py --output . --page en/sidekick-planner
py -3.10 tools/preview_static_site.py --port 3334
```

`tools/preview_static_site.py`（2026-09-20 新設）は Vercel の cleanUrls を最低限まねる確認用サーバー
（`/sidekick-planner` → `sidekick-planner.html`）。`python -m http.server` でも配信できるが、その場合は
`.html` 無しの内部リンク（CTA → `/register-dl` → `/dl-planner`）が 404 になり導線を追えない。

- `http://127.0.0.1:3334/sidekick-planner`（Desktop / Mobile 幅）、`/en/sidekick-planner`
- CTA「β版を試す（無料）」→ `/register-dl?product=planner&src=sidekick-planner`（製品ヘッダーが Planner になる）
  → 同意チェック・メール入力 → `/dl-planner`（「配布は準備中です」、ダウンロードリンク無し、EXE SHA-256・
  未署名の注意・利用条件/プライバシーへのリンク）。`/dl-planner` を直接開くと `/register-dl` へ戻る。
- ローカルでは `/api/add-contact` が 404 なので、本番の Firestore / Brevo には何も書かれない
  （GA4 / Clarity のタグは既存ページと同じく localhost からも送信される）。
- 確認済み（2026-09-20、Playwright/Chromium）: 1366 px / 390 px で横スクロール無し、console error 0、
  h1 1 つ、EN の CTA は `&lang=en` 付き。

## 6. Human Decision が必要な残件（2026-09-20 AI-11050 で解消した項目は打ち消し）

2026-09-20（Public Beta Web 最終整理、AI-11050）: 二層構造を採用（→ **同日 AI-11650 の Human Decision で /planner・/en/planner は /sidekick-planner・/en/sidekick-planner へ 301 統合、concept ページは廃止**。以下は当時の記録） — `/planner` = concept（考え方・何をする道具か。
天の川など β1.00 で公開しない機能の記述を削除、「計算できることと、計算できないこと」を全面改稿、
「いま試せる β1.00」→ `/sidekick-planner` 導線）、`/sidekick-planner` = product（機能・画面・登録・ダウンロード。
「Sidekick Planner とは」→ `/planner` へ 1 link）。301 は採用しない（Human Decision 1）。
footer「Sidekick Planner（開発中）」→「Sidekick Planner β」→ `/sidekick-planner`、header ナビに「🗺️ Planner β」、
トップページ製品セクションに Planner の solo カード（JA/EN）。Terms 第10条の link 先を `/sidekick-planner` へ（文言不変）。
共通 header / footer 変更のため 4 系統すべて再ビルド済み（差分 = nav 1 行＋footer 1 項目のみ、link check 0 broken）。


1. ~~**`/planner` の扱い**~~ → 二層構造で解決（上記）。301 なし。Terms 第10条 link は `/sidekick-planner`。
2. ~~共通 footer / ヘッダー~~ → 済み（上記）。
3. ~~トップページ（index）~~ → solo カードで済み（上記）。
4. Brevo 属性の作成（`HAS_PLANNER` / `VER_PLANNER`）。
5. 配布開始時: hosting 先、配布 ZIP の SHA-256、`dl-planner.html` の 2 定数、`test_dl_planner_is_fail_closed_before_distribution` の更新。
