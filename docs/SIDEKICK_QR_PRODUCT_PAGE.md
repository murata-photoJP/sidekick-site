# Sidekick QR 製品ページ（/sidekick-qr, /en/sidekick-qr）

2026-09-27 新設。製品の正本は自作 repository 内の独立 repository `Sidekickシリーズ/本体/Sidekick QR`
（nas `Z:\mahoroba999\ProgramSoce\自作\sidekickQR.git`、Human Decision は同 repository の `docs/DECISIONS.md`、`HD-SIDEKICKQR-*`）。

## 1. URL は恒久

`https://www.sidekick-lab.com/sidekick-qr` は、Sidekick QR が作る Card に載せる **Secondary QR（「このカードを作る」）の行き先**になる。
印刷・配布された Card から読まれ続けるので、**URL を変えない・消さない**（変えるなら 301 を残す判断を Human が行う）。
Secondary QR の実装は、この URL が本番で 200 を返すことを確認してから行う。

## 2. 追加したもの

| 種別 | パス |
|---|---|
| テンプレート | `templates/site/pages/sidekick-qr.html` / `templates/site/pages/en/sidekick-qr.html`（`build_site.py` の `_register_page_pair("sidekick-qr")`） |
| 本番 HTML（生成物、手書き禁止） | `sidekick-qr.html` / `en/sidekick-qr.html` |
| sitemap | `sitemap.xml` に 2 URL（`DEPLOY_CHECKLIST.md` 2-2 の 4 条件を満たす） |
| テスト | `tests/site/test_sidekick_qr_product_page.py` |

変更していないもの: 共通 header / footer（グローバルナビに Sidekick QR は足していない。足すと 4 系統の全ページ再生成になるため別判断）、
`vercel.json`（`cleanUrls` で `/sidekick-qr` → `sidekick-qr.html`）、既存ページ。

## 3. 書いてよいこと・書かないこと（テストで固定）

- 書く: Sidekick QR / by Sidekick Lab / 「写真から、Webへつなぐ。」（暫定コピー、`HD-SIDEKICKQR-003`）、写真 ＋ URL → QR カード、
  写真・URL・カードを送信しない（アプリの CSP `connect-src 'none'`）、JPEG / PNG、プレビュー、PNG 保存。
- ダウンロードは **「ダウンロード 準備中」/「Download Coming Soon」の表示だけ**。installer / ZIP / EXE へのリンク、登録導線、404 になる偽リンク、
  押せそうな button は置かない（配布物が存在しない、`HD-SIDEKICKQR-004`）。
- 書かない: まだ無い機能（Overlay・SNS 向けの型・一括処理・EXE・シェアウェア・ライセンス・価格）、色が正確に保たれるという claim
  （`HD-SIDEKICKQR-005` / Validation Backlog VB-01。ページには「色の再現は検証中」と明記している）。
- 製品のスクリーンショットはまだ載せていない（Secondary QR の実装後の Card で撮る）。og:image は base.html の既定画像。

## 4. 確認

```
.\.venv\Scripts\python.exe build/site/build_site.py --output . --page sidekick-qr
.\.venv\Scripts\python.exe build/site/build_site.py --output . --page en/sidekick-qr
.\.venv\Scripts\python.exe -m pytest tests/site/test_sidekick_qr_product_page.py -q
py -3.10 tools/preview_static_site.py --port 3334    # http://127.0.0.1:3334/sidekick-qr
```

本番反映は `origin/main` への push（= production deploy）で、**Human decision が必要**（`START_HERE_FOR_DEVELOPMENT.md` §6）。

## 5. 正式版 1.0.0 の Download（2026-09-28、HD-SIDEKICKQR-016）

- 正式 artifact: **`/downloads/sidekick-qr/SidekickQR-1.0.0.zip`**（25,381 bytes、SHA-256 `6bdaac3bd617b523195a07448d198ae013869a7ccd0d8c719f8862e666cbf405`、
  Sidekick QR repository の `tools/build_portable_zip.py` で source `e9b3900` から build。identity と release record は同 repository の `docs/RELEASE_1.0.0.md`）。
  この file を差し替えない（新しい版は新しい file 名で置き、ページの link を変える）。sitemap には載せない（ZIP は検索の対象にしない）。
- 製品ページ: 「準備中」をやめ、hero と Download 節の 2 か所から上の ZIP へ直接 link（登録導線なし）。Download 節に「すべて展開」→「Sidekick QR.html」の 3 行。
  仕様表に版・動作環境（Windows、Edge / Chrome）・形式（ZIP、インストール不要、Python 等も不要）・写真（JPEG / PNG）・色（sRGB 基準）・利用条件（ZIP 内の TERMS.txt）・更新（手動）。
  privacy の表記は「Sidekick QR の処理のために外部のサーバーへ送信されません」と、QR を読んだ端末がその Web ページへアクセスすることの両方を書く。
- 内部の検証事項（Validation Backlog）・色管理の技術説明（Adobe RGB / ICC 等）はページに載せない（`tests/site/test_sidekick_qr_product_page.py` が固定）。
- validation 専用 ZIP（`/validation/sidekick-qr/…`、HD-SIDEKICKQR-014 A）は production smoke の PASS 後に削除する。

## 6. Web 版の validation surface（2026-09-28、HD-SIDEKICKQR-018 → Human Review PASS、HD-SIDEKICKQR-021）

- production の `/sidekick-qr`・`/en/sidekick-qr`・global navigation は**変えていない**（Human Review PASS 後に Human が Production Replacement を GO）。
- validation: `/validation/sidekick-qr-web/<id>`（id は `build_site.py` の `SIDEKICK_QR_WEB_VALIDATION_ID`）= shell（テンプレート `templates/site/pages/validation/sidekick-qr-web.html`、
  今の製品ページの CSS、analytics なし・noindex）＋ iframe の app（同じ folder の `sidekick-qr-app/app`、Sidekick QR の `tools/export_web_app.py` の書き出し、
  Portable 1.0.0 と byte 一致・analytics なし・自前 CSP）。入口を `app.html` にするのは、cleanUrls ＋ trailingSlash:false で folder の index.html だと
  相対 `js/…` が 1 つ上を指すため。
- 設計の正本: Sidekick QR repository の `docs/WEB_VERSION_ARCHITECTURE.md`。

## 7. Production Replacement（2026-09-28、HD-SIDEKICKQR-021、site 76b63d7）

- 日本語 `/sidekick-qr` = 説明 ＋ **Primary: その場で使える Web 版**（iframe `/sidekick-qr-app/app`、`allow="web-share"`）＋ **Secondary: オフラインで使う**
  （Portable 1.0.0 の ZIP、URL・bytes・SHA-256 そのまま、`id="download-link"`）。コピーの中心は「Sidekick QR / 写真から、Webへつなぐ。」。
  shell は GA4 の page_view だけ（写真・ファイル名・URL・タイトル・説明・Card・QR の内容・共有先は analytics に送らない）。
- `/sidekick-qr-app/`: validation で Human PASS した app と byte 一致（manifest の source `7be38fd`、core = Portable 1.0.0）。analytics なし・noindex（X-Robots-Tag）・sitemap なし。
- global navigation: 「🔗 Sidekick QR」—— JA は「📐 DOF計算」の直後・「📷 Workshop」の直前、EN は「📐 DOF Calculator」の直後（共通 header、4 系統の全ページを再生成）。
- 英語 `/en/sidekick-qr` は Portable の製品ページのまま（D-4 = E2、本文不変、nav の 1 行だけ変わる）。
- validation surface `/validation/sidekick-qr-web/36429dd1d469d9cb` は**残す**（noindex・analytics なし・link なし。削除は別の Human decision）。
- 確認: Sidekick QR repository の `validation/web/production_gate_web.py`（deploy 前 `--site-root`、deploy 後 `--url https://www.sidekick-lab.com/sidekick-qr`）。
  GA4 の collect は route で受け取って Google へ送らない。2026-09-28: local 20 / production smoke 20 checks PASS。

## 8. Secondary return endpoint `/card/qr`（2026-09-30、HD-SIDEKICKQR-023）

- `vercel.json` の redirect 2 件（host → www の規則の後、評価順）: `Accept-Language` に `ja` の言語タグを含む → `/sidekick-qr?utm_source=sidekick-qr&utm_medium=qr-card&utm_campaign=secondary-qr`、
  それ以外（header なしを含む）→ `/en/sidekick-qr?…`（同じ UTM）。どちらも **307**（`permanent: false`）。
- regex `(^|.*[, ])[jJ][aA]($|[-;, ].*)` は、Vercel の `has` の string 値が完全一致・部分一致のどちらで評価されても同じ結果になる形（docs からは確定できないため）。
- `/card/<product>` は入口専用: content を置かない・link しない・sitemap に載せない。**`/card/qr` は Card に刻まれたら永久に維持**、行き先・UTM の変更は `vercel.json` だけで行う。
  `/sidekick-qr`（1.0.0 の Card の Secondary）は redirect しない・変えない。
- 固定テスト: `tests/site/test_sidekick_qr_card_return.py`。production の実測と Card 側（1.0.1）の記録は Sidekick QR repository の release 記録。
