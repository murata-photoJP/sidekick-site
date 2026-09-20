# Sidekick Planner β1.00 — 配布（Distribution）手順書

2026-09-20 新設（自作リポジトリ Track `planner-beta1-distribution-preparation`、AI-10650）。
製品ページ・登録導線は `docs/PLANNER_PRODUCT_PAGE.md`。本書は **ZIP を置く場所と、Human GO 後に配布を開始する最短手順**。

> **状態（2026-09-20 AI-10850、Distribution Unit）: R2 upload 済み・検証 PASS・`dl-planner` の有効化は local commit のみ。**
> site の push（本番デプロイ）は未実施 = 一般ユーザーは `/sidekick-planner` にも `/dl-planner` にも到達できず、Public Beta は未開始。
> object `Sidekick_Planner_1.0.0-beta.1_bea1697.zip` は public bucket に存在する（URL を知っていれば取得可能な状態）。
> 配布停止が必要なら Cloudflare Dashboard で object を削除する（Human 操作）。

## 1. 配布基盤（fresh verify、2026-09-20）

Sidekick Star / Portrait / SkyEffect / AI は **すべて同じ基盤** で ZIP を配布している。Planner も同じ基盤を使う（Planner 専用の配布サービスは作らない）。

| 項目 | 実測値（正本） |
|---|---|
| ストレージ | Cloudflare R2、バケット `sidekick-downloads`（`_SideKick_Development/PROJECT_STATUS.md`「販売サイト構成」、`README_AI.md`「ZIPファイルのR2アップロード手順」） |
| 公開 URL | r2.dev public development URL `https://pub-123781c638d64762ac2e397ce0e98259.r2.dev/<object>`（`dl-star.html` 等 4 ページの `R2_URL`、`アップロード先/R2関係/R2_公共開発URL.txt`） |
| 現在の object（`rclone lsl`） | `Sidekick_Star.zip` 3,479,181,062 B ／ `Sidekick_Star_Core.zip` 429,493,673 B ／ `Sidekick_Portrait.zip` 1,794,444 B ／ `Sidekick_SkyEffect.zip` 1,141,612 B ／ `Sidekick_AI.zip` 9,653,529 B ／ マニュアル PDF 2 件 = 7 object、3.653 GiB |
| upload 方法 | rclone v1.74.2（`SideKick販売ページ/アップロード先/rclone-v1.74.2-windows-amd64/rclone.exe`）、remote `r2`（type s3 / provider Cloudflare / endpoint `https://<account>.r2.cloudflarestorage.com`、credential は `%APPDATA%\rclone\rclone.conf`）。`rclone copy <zip> r2:sidekick-downloads`（Star 3.48 GB の再 upload 実績 2026-09-03） |
| 命名 | 既存製品は無 version 名（上書き運用）。**Planner は versioned 名** `Sidekick_Planner_1.0.0-beta.1_bea1697.zip`（product_version ＋ source commit）。既存 object と衝突しない・上書きしない |
| 接続 | `/sidekick-planner` → `/register-dl?product=planner&src=sidekick-planner`（メール登録）→ `/dl-planner`（`sk_dl_authorized` gate）→ `PLANNER_DOWNLOAD_URL` の `<a download>`（Star は同じ構造で `R2_URL` 直リンク） |
| HEAD 実測（Star） | `200`, `Content-Type: application/zip`, `Accept-Ranges: bytes`, `Server: cloudflare`（range 対応 = ブラウザのレジューム可） |

### R2 の制約（Cloudflare 公式 docs、2026-09-20 参照）

| 項目 | 値 | Planner ZIP（1.80 GiB）への影響 |
|---|---|---|
| object 最大 | 5 TiB（実効 4.995 TiB） | 問題なし |
| 単一 PUT 最大 | 5 GiB（実効 4.995 GiB） | 問題なし（rclone は 200 MiB 超で multipart、part 上限 10,000） |
| 料金（Standard） | storage $0.015/GB-月、Class A（PutObject / UploadPart 等）$4.50/百万、Class B（GetObject / HeadObject）$0.36/百万、**egress 無料** | 無料枠 10 GB-月・Class A 100万・Class B 1,000万。bucket は 3.65 → 5.45 GiB で無料枠内。DL 1 回 = Class B 1（range 分割でも数回）。1 upload の Class A は数百 |
| r2.dev URL | 「non-production traffic 向け」「rate-limited」、Cache / WAF / access control なし | **既存 4 製品と同じ条件**（Star 3.48 GB がこの URL で配布中）。β配布はこの条件を承知で使う。将来 custom domain（例 `dl.sidekick-lab.com`）にすれば Cache・WAF が使える（Human Decision、全製品共通） |
| 同一 object への書き込み | 1 回/秒 | 問題なし |

**結論: YES — Star 等と同じ配布基盤（R2 `sidekick-downloads` + r2.dev 公開 URL + rclone）に Planner 約2GB ZIP を置ける。** 根拠 = 既に 3.48 GB の Star ZIP が同じ経路で配布されている／size・料金・egress に制約なし／無料枠内／`rclone copy --dry-run` が Planner ZIP を 1 file・1.801 GiB として認識（2026-09-20、upload はしていない）。

## 2. 配布 package（作成済み・未 upload）

| 項目 | 値 |
|---|---|
| ZIP | `SideKick販売ページ/zip/Sidekick_Planner_1.0.0-beta.1_bea1697.zip`（identity: 同名 `.identity.json`） |
| ZIP bytes | **1,934,309,563**（1.80 GiB） |
| ZIP SHA-256 | **`93c27bf1f37641cfc05109d8c0f5876b402bd975b2a01fd59333ed0d3bca83e1`** |
| entries | 2,185（top-level `Sidekick Planner/` 1 folder、deflate、path 順、mtime 保持） |
| 内部 RC13 | build `1.0.0-beta.1+20260920T004212Z.gbea1697` / `bea1697` / EXE SHA-256 `709afc4e8a7b3ecd0073fc3926566b570a8c0fc8519080231ba598f18c720af7` / 2,185 file / 2,079,489,773 B |
| 検証 | 入力 `dist/rc13` = `expected_manifest_rc13.json` 全 file 一致 → ZIP → 一時展開 = manifest 全 file 一致（Python）。独立検証: PowerShell `Get-FileHash` = 同 sha256、`Expand-Archive` 2,185 file・EXE sha256 一致・top-level 1 folder |
| 作成ツール | `Sidekick Planner/validation/prototype/diamond_fuji_minimal/build_distribution_zip.py`（fail-closed: 入力が manifest と 1 件でも違えば作らない、既存出力を上書きしない、入力を変更しない） |

ZIP の identity（sha256 `93c27bf1…`）は **distribution package identity**。RC13 の EXE identity（`709afc4e…`）とは別物で、`dl-planner` には両方を表示する。

## 2-2. upload と検証の記録（2026-09-20、AI-10850、Human GO）

| 検証 | 結果 |
|---|---|
| upload | `rclone copy zip\Sidekick_Planner_1.0.0-beta.1_bea1697.zip r2:sidekick-downloads`（dry-run で 1/1 を確認後に実行、2m56s、Multi-thread Copied (new)） |
| bucket | `rclone lsl` = 8 object。既存 7 object の bytes 不変（Star 3,479,181,062 / Star_Core 429,493,673 / Portrait 1,794,444 / SkyEffect 1,141,612 / AI 9,653,529 / PDF 2 件） |
| HEAD | `200`、`Content-Type: application/zip`、`Content-Length: 1934309563`、`Accept-Ranges: bytes`、`Last-Modified: Sun, 20 Sep 2026 09:40:38 GMT` |
| Range | `curl -r 0-1023` → `206`（レジューム可） |
| 実 download | `200`、1,934,309,563 B、sha256 `93c27bf1f37641cfc05109d8c0f5876b402bd975b2a01fd59333ed0d3bca83e1`（= canonical identity record） |
| 展開 | 2,185 entry、top-level `Sidekick Planner/` のみ、zip64 なし → `expected_manifest_rc13.json` と全 file（path/bytes/sha256）一致、2,079,489,773 B、EXE sha256 `709afc4e…` 一致 |
| site 側 | `dl-planner.html` の 2 定数を埋めた（local commit、未 push）。`tests/site` 224 PASS（fail-closed test は「検証済み object 1 つだけを指す」形へ意図的に更新） |

## 3. Human GO 後の最短手順（Public Beta 開始）

前提: Human が「配布 GO」を出す。順番を変えない（URL 有効化は upload と live 検証の後）。

1. **upload（済み、上記 2-2）**
   ```powershell
   $rclone = "C:\Program Files\Adobe\Adobe Photoshop (Beta)\Presets\Scripts\自作\SideKick販売ページ\アップロード先\rclone-v1.74.2-windows-amd64\rclone.exe"
   $zip    = "C:\Program Files\Adobe\Adobe Photoshop (Beta)\Presets\Scripts\自作\SideKick販売ページ\zip\Sidekick_Planner_1.0.0-beta.1_bea1697.zip"
   & $rclone copy $zip r2:sidekick-downloads --progress
   ```
   `copy` は名指しの 1 file だけを転送する（`sync` は使わない = 既存 object を消さない）。
2. **object 検証（upload 直後）**
   ```powershell
   & $rclone lsl r2:sidekick-downloads          # Sidekick_Planner_1.0.0-beta.1_bea1697.zip 1934309563 が増えているだけ
   curl.exe -sI https://pub-123781c638d64762ac2e397ce0e98259.r2.dev/Sidekick_Planner_1.0.0-beta.1_bea1697.zip   # 200 / Content-Length 1934309563
   ```
   さらに一度ダウンロードして `Get-FileHash` が `93c27bf1…` であること（egress 無料）。
3. **dl-planner 有効化（済み、local commit）** — `dl-planner.html` の 2 定数:
   ```js
   const PLANNER_DOWNLOAD_URL = 'https://pub-123781c638d64762ac2e397ce0e98259.r2.dev/Sidekick_Planner_1.0.0-beta.1_bea1697.zip';
   const PLANNER_ZIP_SHA256 = '93c27bf1f37641cfc05109d8c0f5876b402bd975b2a01fd59333ed0d3bca83e1';
   ```
   `tests/site/test_planner_product_page.py::test_dl_planner_is_fail_closed_before_distribution` を「配布開始後」の形へ意図的に更新（URL・hash が上の値であること／`.zip` link が 1 つで R2 の Planner object を指すこと）。`pytest tests -q` PASS。
4. **deploy** — `git push origin main`（= Vercel 本番。`docs/DEPLOY_CHECKLIST.md`）。Human Decision 残件（`/planner` の 301／footer・nav・index）は同時でも別でもよいが、少なくとも `/sidekick-planner` が本番に出ていること。
5. **live 検証** — 本番で `/sidekick-planner` → 登録 → `/dl-planner` にボタンが出て R2 から DL できる、DL 後の `Get-FileHash` = `93c27bf1…`、展開後 EXE = `709afc4e…`。**この PASS 時点 = actual Public Beta release 日**（`HD-LR-40` の一般公開日。捏造しない）。
6. **記録** — Planner 側 `release_acceptance.json` に `HD-RA-*` に従って release 記録（配布 package identity・URL・release 日）、CHANGELOG、`/changelog` ページ。Brevo 属性 `HAS_PLANNER`/`VER_PLANNER` は **2026-09-20 作成済み**（Human confirmation → `tools/create_brevo_attributes.py --dry-run`（既存 normal 22、作成対象 2 のみ）→ 実行 → API 再確認: 両属性 category `normal` / type `text`、normal 22 → 24、既存 HAS_*/VER_* 10 属性不変・削除 0）。

## 4. rollback / replacement / versioning

- **rollback（配布停止）**: `dl-planner.html` の 2 定数を空文字に戻して push → fail-closed「準備中」に戻る（object は残してよい。既に DL した人には影響しない）。急ぐ場合は Cloudflare Dashboard で object を削除しても同じ（URL が 404）。
- **replacement（β1.01 等）**: 新しい RC で `build_distribution_zip.py` → **新しい versioned object 名**（例 `Sidekick_Planner_1.0.0-beta.2_<commit>.zip`）を upload → 2 定数を差し替え → push。既存 object は上書きしない。古い object の削除は Human 判断（配布終了後、`HD-LR-40` の期間終了時など）。
- **versioning の原則**: object 名 = `Sidekick_Planner_<product_version>_<source short commit>.zip`。同名 object を再 upload しない（内容が変わるなら名前も変わる）。identity.json を ZIP と一緒に保管する。

## 5. Claude Code から upload する場合の安全条件

- `rclone copy <単一 zip> r2:sidekick-downloads` のみ（`sync` / `delete` / `purge` / 既存 object 名を使わない）。
- 実行前に `--dry-run` で「Transferred 1 / 1」と対象 file 名を確認する。
- 実行後に `lsl` で既存 7 object の bytes が不変であることを確認する。
- credential（`rclone.conf`、`アップロード先/R2関係/アカウントAPIトークン.txt`）は表示・コピーしない。
