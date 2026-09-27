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

