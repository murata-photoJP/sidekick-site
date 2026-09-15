# sidekick-site — Recovery and Backup（Web 版 Sidekick DOF を含むサイト全体）

作成：2026-09-16（Phase 3F / 3F.1 READ-ONLY 監査の結果を文書化。監査記録は Windows 版 Track の Phase 3F 報告）。
目的：数年後・別 PC・会話履歴なしの状態で、この repository を **発見 → 復旧 → 修正 → test → 再 deployment** できること。
この文書は手順と所在の記録であり、secret の値・secret を含む file の内容は一切書かない。

## 1. Repository の所在（役割の異なる 3 つの copy）

| copy | 場所 | 役割 |
|---|---|---|
| **GitHub `origin`（public / canonical Git remote）** | `https://github.com/murata-photoJP/sidekick-site.git`、branch `main` | tracked source の正本。`main` への push で Vercel が自動 deploy |
| **local working copy** | `C:\Program Files\Adobe\Adobe Photoshop (Beta)\Presets\Scripts\自作\SideKick販売ページ\html\`（この repository） | 開発・ビルド・テストの場。親フォルダ `SideKick販売ページ\` は jisaku repository（`自作`）の `.gitignore` で除外されているため、**jisaku の NAS bare repository（`jisaku.git`）には含まれない** |
| **NAS file-copy backup（private disaster-recovery backup including local-only state）** | `Z:\mahoroba999\ProgramSoce\自作\SideKick販売ページ\`（この repository は同 `html\`、`.git` ごと） | 親フォルダ全体の robocopy コピー。GitHub に出さない local-only / private な材料も含む |

GitHub と NAS は目的が違う。**bare mirror 化はしない**（NAS copy は Git repository の mirror ではなく、workspace 全体の私的 backup）。

## 2. NAS backup の仕組み（`SideKick販売ページ\nas_backup.ps1`、launcher `☆☆☆nas_backup.bat`。2026-09-16 実読）

- 方式：`robocopy <SideKick販売ページ> <Z:\…\自作\SideKick販売ページ> /E /XO /R:1 /W:1 /LOG+:_nas_backup_log.txt /XF _nas_backup_log.txt`
- **手動実行**（scheduler 登録なし）。`.bat` は dry run（`/L`）で差分を表示 → `Y` で本 copy。`powershell -File nas_backup.ps1 -Auto` で無確認実行。
- 非破壊：`/MIR` なし（NAS 側の削除は起きない。local で消した file は NAS に残る）。`/XO`：NAS 側がより新しい file は上書きしない。
- 範囲：親フォルダ全体（`html/` の `.git`・untracked・ignored（`.venv`、`build-output`、`__pycache__`）を含む。2026-09-12 時点 約 8,100 file / 13.5 GB）。除外は log file のみ。
- 失敗検出：NAS 未接続なら `[ABORT]`（exit 1）。robocopy exit code `≥ 8` で `[FAILED]`。結果は `_nas_backup_log.txt`（robocopy log、**file 名が載るので公開しない**）。
- path は script 内で実行時に導出（日本語 literal なし）。NAS root `Z:\mahoroba999\ProgramSoce`。

## 3. 鮮度の確認（READ ONLY、backup を実行しない）

```powershell
py -3.10 -B tools/check_nas_backup_status.py
```
出力は LOCAL HEAD / NAS HEAD / ahead commits / last backup（log の `Ended :` 行）/ backup status（`CURRENT` / `STALE` / `UNAVAILABLE`）のみ。
file 一覧や secret 名は出さない。exit 0 = CURRENT、1 = STALE、2 = UNAVAILABLE。

**backup の実行（最新化）は Human の判断**：`☆☆☆nas_backup.bat` を本人が実行する。AI worker は実行しない。
2026-09-16 実測：local `79e8088` / NAS `50ac787`、**39 commit 遅れ**（最終 backup 2026-09-12 06:11）。

## 4. 復旧手順

### 4-1. 開発 PC を失った（GitHub と NAS は生存）
1. `git clone https://github.com/murata-photoJP/sidekick-site.git` で tracked source を復旧（DOF：`assets/js/dof/`、`templates/site/pages/dof.html`、`tools/dof.html`、`tests/tools/`、`tests/site/test_dof_page.py`、`docs/DOF_CALCULATOR_PHASE1_*.md`）。
2. 未 push の commit・未 commit の変更・local-only 材料は NAS copy にしか無い：`Z:\…\SideKick販売ページ\html\.git` から `git fetch <NAS path> main` で commit を取り込み、必要な file を個別に戻す（NAS copy の鮮度＝最終 backup 時点まで）。
3. 親フォルダの private / local-only 材料（API key 等）は NAS copy から**必要な file だけ**を戻す。GitHub へは絶対に commit しない。

### 4-2. GitHub を失った（NAS 生存）
NAS の `html\` を local へ copy（NAS→local は robocopy `/XO` の規則が無いので、既存 local を潰さない新しい場所へ）。`html\.git` はそのまま有効な repository（`git fsck` で確認）。新しい remote を作って push し直す。

### 4-3. NAS を失った（GitHub 生存）
tracked source は GitHub から復旧可。private / local-only 材料は各 account（Vercel / Firebase / Brevo / Anthropic / Stripe 等）の console から再発行・再取得する。

### 4-4. GitHub も NAS も無い
この repository の完全復旧は不可。Windows 版 Sidekick DOF の Maintenance Package（`…\Sidekickシリーズ\本体\SidekickDOF\`）には Web source は含まれない（Classic core の 1:1 port と Web golden fixtures の写しのみ）。

## 5. Security boundary

- **Private / local-only files may exist in the parent folder `SideKick販売ページ\` and must never be committed to GitHub.**（backup script の comment にも明記。値・file 名はこの文書に書かない）
- `.gitignore` / `.vercelignore` の除外を外さない。`docs/`・`templates/`・`tests/`・`tools/*.py` は Vercel に配信されない（`.vercelignore`）。
- Vercel の環境変数（`api/` の Serverless Functions が参照する名前：`ANTHROPIC_API_KEY`、`BREVO_API_KEY`、`FIREBASE_SERVICE_ACCOUNT`）は Vercel project 側にのみ存在する。値は repository にも NAS backup 文書にも置かない。DOF page はこれらに依存しない。

## 6. 再 deployment に必要なもの（repository 外の情報）

- Vercel project：`sidekick-site-tawny.vercel.app`（`vercel.json` の redirect 元）、production domain `www.sidekick-lab.com`（apex `sidekick-lab.com` は www へ 301）。
- GitHub 連携：`main` への push で自動 deploy（`docs/CHANGELOG_WORKFLOW.md`）。Vercel は build を行わず、commit 済みの静的 HTML を配信（`cleanUrls: true`、`trailingSlash: false`、`.vercelignore`）。
- 新 PC から再 deployment する場合、Vercel account へのログイン・project と repository の再連携・domain・環境変数の再登録は **account 側の作業**（repository には無い）。

## 7. 将来候補（今回は行わない）

- NAS への git bare mirror（`git push --mirror`）：tracked source の 3 重化。private 材料の混入を避けるため、行う場合は `html/.git` のみを対象にする。
- backup の定期実行（Task Scheduler で `nas_backup.ps1 -Auto`）と、`check_nas_backup_status.py` の定期確認。
