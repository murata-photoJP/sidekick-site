# プランナーQRマップ G-5.1: Production Safety Infrastructure

- 自作 AI-ID: AI-17211 ／ Human Decision: `HD-PLANNERQRMAP-044`（G5-HQ-10、実装承認）・`-035` / `-036`（専用 project・id 候補）・`-038`（WAF 初期値）・`-041`（公開の有効化は Production Gate 後）
- 日付: 2026-10-06 ／ branch: `qr-map/g5-1-production-safety`（`qr-map/g3-map-viewer` `1a88659` から）
- 状態: **Production 接続 0**（Firebase project は未作成、credential なし、deploy なし、Vercel 設定の変更なし）

目的は「Production へまだ一度もつながずに、将来 Production 設定を入れたときの安全装置を完成させる」こと。

## 1. 本番接続の positive allow（`api/_qr_map/firestore.js` `resolveConnection`）

production を返すのは、次が **すべて** 揃ったときだけ。1 つでも欠ければ `QrMapConfigError`（API は 503 `QR_MAP_UNAVAILABLE`）。

1. `VERCEL_ENV === "production"`（Preview / Development / Vercel 外では、credential が入っていても接続しない）
2. `QR_MAP_PRODUCTION_FIRESTORE === "enabled"`（本番接続そのものの明示 switch。公開の switch とは別）
3. `QR_MAP_FIREBASE_PROJECT_ID` が `CONSTANTS.PRODUCTION_PROJECT_IDS`（= `["sidekick-map-prod"]`）に含まれる
4. `QR_MAP_FIREBASE_SERVICE_ACCOUNT` の `project_id` が 3 と一致
5. emulator 設定（`FIRESTORE_EMULATOR_HOST` / `QR_MAP_REQUIRE_EMULATOR=1`）・`NODE_ENV=test`・`demo-` project が無い

従来の守り（`sidekick-6cfee` 拒否・emulator は `demo-` だけ・名前付き app `qr-map`）は維持。追加で、Vercel の `production` / `preview` に emulator 設定が紛れ込んだ場合も拒否し、local 確認用 Origin（`QR_MAP_DEV_ALLOWED_ORIGINS`）は Vercel の `production` / `preview` では常に無視する。

## 2. Local / Preview / Production

| | LOCAL / TEST | PREVIEW | PRODUCTION |
|---|---|---|---|
| 接続 | Emulator（`demo-sidekick-qr-map`） | **無し**（条件 1 で必ず 503） | 専用 project（`sidekick-map-prod`、未作成） |
| Vercel env | — | `QR_MAP_*` を登録しない（登録しても条件 1 で拒否） | `QR_MAP_FIREBASE_PROJECT_ID` / `QR_MAP_FIREBASE_SERVICE_ACCOUNT` / `QR_MAP_PRODUCTION_FIRESTORE=enabled` / `QR_MAP_PUBLISH_ENABLED`（初回は未設定）/ `QR_MAP_DAILY_PUBLISH_LIMIT` / `QR_MAP_CLEANUP_ENABLED`（初回は未設定）/ `CRON_SECRET`（既存） |
| 書き込み先 | Emulator だけ | 無し | Production Firestore だけ |

## 3. Circuit breaker（運用で即時に止める）

| switch（文字列の完全一致だけ ON） | 止まるもの | 止まらないもの |
|---|---|---|
| `QR_MAP_PUBLISH_ENABLED` ≠ `"true"` | 新しい公開（publish、503 `PUBLISH_DISABLED`） | Map の tile・詳細（open）と activity 更新・**取り消し（unpublish）**・既存 QR・既存 Viewer |
| `QR_MAP_DAILY_PUBLISH_LIMIT`（既定 200） | その日の上限を超えた公開（503 `PUBLISH_LIMIT_REACHED`） | 同上 |
| `QR_MAP_CLEANUP_ENABLED` ≠ `"true"` | 物理削除（503 `CLEANUP_DISABLED`、何も読まない） | それ以外すべて |
| `QR_MAP_PRODUCTION_FIRESTORE` ≠ `"enabled"` | QR Map の API 全体（503） | 既存 QR・既存 Viewer（Firestore を見ない） |

取り消しは公開停止中でも動かす（利用者が掲載を消せる方を優先。G-2 から既存の挙動で、G-5.1 で test に固定）。

## 4. 物理削除（cleanup）

- Firestore TTL は使わない（billing = Blaze 必須。Spark で MVP を始めるため）。
- `api/qr-map-cleanup.js`（新 function、GET、Vercel Cron が `Authorization: Bearer <CRON_SECRET>` を付けて 1 日 1 回）→ `store.cleanupEligible()`。
- 判定（`lifecycle.planCleanupVerdict`）: active（published かつ now < expires_at）は delete_after が何であっても残す ／ 削除は「state から導いた削除可能時刻（期限切れ・取り消し・運営停止 ＋ 30 日）」と「保存された delete_after」の両方が now 以前のときだけ ／ state 不明・時刻欠落 / 非 Timestamp は malformed として数えるだけ。
- bounded: collection ごとに最大 `CLEANUP_BATCH_LIMIT`（200）件、超えれば `more: true` で次回へ。limit 引数も 200 に丸める。
- 読んだ後に更新された document は消さない（`lastUpdateTime` 前提条件。例: 詳細を開いて期限が延びた）。
- idempotent: 再実行で消えるのは削除可能なものだけ。応答は件数だけ（plan_id・座標・fragment を返さない）。
- 補助 document（`qr_map_idempotency`・`qr_map_counters`）は delete_after 以降に削除。
- Map の可視性は従来どおり query 時の即時判定（`state == published AND expires_at > now`）。activity は詳細を明示的に開いたときだけ・24 時間に 1 回まで・180 日。

## 5. Cron

`vercel.json` の `crons` に `{ "path": "/api/qr-map-cleanup", "schedule": "50 18 * * *" }`（UTC 18:50 = JST 03:50、既存の Activity cleanup 18:30 とずらす。Hobby の 1 日 1 回に収まる）。**deploy していない**。Production で `QR_MAP_CLEANUP_ENABLED` を入れるまで、Cron が呼ばれても 503 で何もしない。

Function 数: 既存 7 ＋ `qr-map` ＋ `qr-map-cleanup` = 9（Hobby の上限 12 以内）。cleanup を別 function にしたのは、Cron の path に query を使わない・POST 用 WAF rate limit（`-038`）の対象から外すため。

## 6. tests

- unit（`tests/qr_map/unit/test_production_safety.mjs`、15 件）: positive allow・Preview / Development / Vercel 外・明示 switch・許可外 project・credential 欠落 / 不一致・矛盾した組み合わせ・LOCAL / TEST の emulator・Origin・switch の完全一致・cleanup 判定（active / 猶予 / 取り消し / malformed）・Cron endpoint（405 / 503 / 401 / 200、接続不可は 503、内部 error の詳細を出さない）。`test_core_pure.mjs` の本番接続 case を新条件に更新。
- emulator（`tests/qr_map/emulator/test_store_emulator.mjs` に 5 件追加）: cleanup の境界と再実行・malformed の skip・上限と more・補助 document・circuit breaker（公開だけ止まる）・HTTP 経由の Cron endpoint live smoke。

## 7. やっていないこと

Production Firebase project の作成・credential・接続・書き込み・deploy・Vercel の設定 / plan / WAF / Cron の登録・DNS・billing・Privacy / Terms の反映。Planner の code は変更していない（G-4 凍結）。
