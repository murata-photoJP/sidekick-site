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
- 2026-09-29 22:19 UTC（2026-09-30 07:19 JST）: endpoint を production へ（site `16ce0d2`）。Gate A = production の curl（ja / ja-JP / mixed → JA、en-US / zh-CN / header なし / `*` → EN、
  すべて 307・正確な Location、`/card/qr/` は 308 → `/card/qr`、`/CARD/QR` は 404、incoming query は保持され同名の UTM は server の値で上書き、host は固定）＋ 実ブラウザ
  （Chromium / Firefox / WebKit、GA4 の collect は test browser 内で受け取り Google へ送らない）で PASS。

## 9. Sidekick QR 1.0.1（2026-09-30、HD-SIDEKICKQR-023）

- 新規 Card の Secondary QR = `https://www.sidekick-lab.com/card/qr`（Web 版・Portable とも）。Primary・Card の見た目は不変。
- `/sidekick-qr-app/` = Sidekick QR source `6f53361` の書き出し（core = Portable 1.0.1）。validation surface の copy は 2026-09-28 の 1.0.0 のまま（今後の review には使わない）。
- Download: 製品ページ（JA 1 か所・EN 2 か所）は **`/downloads/sidekick-qr/SidekickQR-1.0.1.zip`**（25,498 bytes、SHA-256 `0447c2e8fd69949e54ba1242835eca71623de491f7bc17c665de15722f4964e1`、
  identity は Sidekick QR repository の `docs/release_artifact_1.0.1.json`）へ。**1.0.0 の ZIP は置いたまま・上書きしない**（link はしない。削除は別の Human decision）。
- 固定テスト: `tests/site/test_sidekick_qr_product_page.py`（1.0.1 の link・SHA、1.0.0 が不変で残る）、`tests/site/test_sidekick_qr_web_validation.py`（copy ごとの版）。

## 10. Sidekick QR 1.1.0（2026-09-30、HD-SIDEKICKQR-030）

- URL mode（Card の地 = 灰、Primary = 入力した URL を direct）/ EXIF mode（地 = 白、Primary = EXIF Viewer `https://www.sidekick-lab.com/exif#v=1&…`、撮影情報は fragment だけ）、
  Secondary = `/card/qr`・「← このカードを作る」。Human Acceptance は 1.1.0-rc.2（HD-SIDEKICKQR-030）、EXIF Viewer は HD-SIDEKICKQR-028 / -029（`/exif` = site `0881f7a`、この release では変えない）。
- `/sidekick-qr-app/` = Sidekick QR source `452cc6a` の書き出し（core = Portable 1.1.0）。validation surface の copy は 2026-09-28 の 1.0.0 のまま。
- Download: 製品ページ（JA 1 か所・EN 2 か所）は **`/downloads/sidekick-qr/SidekickQR-1.1.0.zip`**（35,177 bytes、SHA-256 `67d36101f28f604918d5f70ecbfe4d9fbc26213da865bf572f55a294ed992564`、
  identity は Sidekick QR repository の `docs/release_artifact_1.1.0.json`）へ。**1.0.0 / 1.0.1 の ZIP は置いたまま・上書きしない**（link はしない）。
- 製品ページの本文は版・Download・ZIP の大きさだけを変えた。EXIF mode の紹介文は入れていない（本文の追加は別の Human decision）。
- 固定テスト: `tests/site/test_sidekick_qr_product_page.py`（1.1.0 の link・SHA、1.0.0 / 1.0.1 が不変で残る）、`tests/site/test_sidekick_qr_web_validation.py`（copy ごとの版、1.1.0 の core）。

## 11. EXIF モードの紹介（2026-09-30、Sidekick QR 1.1.0、AI-15995）

- 1.1.0 本体（CLOSED / PASS、HD-SIDEKICKQR-030）は変えず、製品ページ（JA / EN）の説明だけを今の製品に合わせた。大きな構成変更・新しい layout はしない。
- 追加・変更した箇所: hero の lead に 1 文 / 「写真 ＋ URL → QRカード」の説明に 1 文、2 枚目の card を「URL か、撮影情報か」（URLモード / EXIFモード）/ 使い方の 2・3 / privacy の callout に 1 段落 / 仕様表に 1 行。
- 事実は Sidekick QR の HD-SIDEKICKQR-026 / -028 / -030 と README・TERMS に合わせる: 撮影情報は 7 項目だけ（カメラ・レンズ・焦点距離・絞り・シャッター速度・ISO・撮影日時）、
  位置情報（GPS）・シリアル番号・撮影者名・著作権情報は入れない、QR は Sidekick Lab の撮影情報ページ（/exif）を開き撮影情報だけを表示（評価・解説なし）、撮影情報はサーバーへ送られない。
  EN は撮影情報ページが現在は日本語であることを明記。/exif の仕組み（fragment 等）は製品ページの主説明に書かない。
- 変えていないもの: title・meta description・og・Download（1.1.0）・nav・sitemap・/sidekick-qr-app/・/exif・/card/qr・ZIP。
- 固定テスト: `tests/site/test_sidekick_qr_product_page.py` の JA / EN の必須の内容に EXIF の文言を追加（JA と EN で同じ事実）。
- **Human Acceptance PASS（2026-09-30、HD-SIDEKICKQR-031）**: URL / EXIF が同じ製品の 2 つの使い方として自然・EXIF 選択時の UI・撮影情報の説明・GPS 等を含めない説明・
  「写真から、Webへつなぐ。」の性格・layout がすべて PASS。修正は上部の 1 文だけ（Primary は `/exif#…` への URL なので「撮影情報へつながる QR」が正確）:
  JA「URLだけでなく、写真の撮影情報へつながるQRコードも作れます。」/ EN「You can also create a QR code that links to the photo's shooting information.」
