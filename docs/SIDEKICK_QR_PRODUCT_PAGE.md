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
