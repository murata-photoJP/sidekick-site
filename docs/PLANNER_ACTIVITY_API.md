# Sidekick Planner Activity API（`/api/planner-activity`）

2026-09-19 新設（AI-6205、Phase 1）。Sidekick Planner β1.00 の **B2+ anonymous aggregate Activity** の受け口。
正本の決定は `自作` repo `Sidekickシリーズ/本体/Sidekick Planner/docs/OPEN_QUESTIONS.md` の
`HD-PLANNERACTIVITY-001`〜`-011`（2026-09-19）。設計は同 repo `docs/ai-analysis/PLANNER_BETA1_ACTIVITY_*.md`。

## 目的

「誰が何をしたか」ではなく **「Sidekick Planner というシステム全体がどれだけ動いているか」**（QR がどれだけ発行され、
どれだけ参照されているか）を数える。個々のユーザー・個々の撮影計画は追跡しない。

## 受けるもの（POST、allow-list）

| field | 値 | 必須 | 誰が送るか |
|---|---|---|---|
| `schema` | `planner_activity/1` | ○ | 全員 |
| `event` | `share_created` / `share_viewed` / `share_view_failed` | ○ | Planner / Viewer / Viewer |
| `event_id` | 32 hex（random 128 bit。冪等キー） | ○ | 全員 |
| `at` | `YYYY-MM-DDTHH:00Z`（client 時刻、**1 時間粒度**） | 任意（不正なら server 時刻を 1 時間に丸める） | 全員 |
| `category` | `mountain` / `structure` | 任意（`share_created` のみ、他は `unknown`） | Planner |
| `transport` | `viewer` / `planner` | 任意（`share_created` のみ） | Planner |
| `repeat` | `true` / `false` | 任意（`share_viewed` のみ） | Viewer |
| `code` | contract の error code（`[A-Z_]{1,40}`） | 任意（`share_view_failed` のみ） | Viewer |

body は 1 event の object、または `{"events": [...]}`（最大 50 件。offline backlog 用）。8 KB まで。
**これ以外の key（`plan_ref` / `poi_id` / `installation_id` / `country` / 緯度経度 / 撮影日時 / payload / fragment）は捨てる。**

## 保存しないもの

IP（`x-forwarded-for` 等を読まない）／ IP 由来の地理情報（`x-vercel-ip-*` を読まない）／ User-Agent の生文字列
（`client_kind` = `mobile` / `desktop` / `preview_fetch` / `bot` / `planner` / `unknown` に分類してから捨てる）／ batch id。
⚠️ IP と UA は **Vercel の request log には到達する**（短時間保持）。「保存しない」であって「到達しない」ではない。Privacy 文面に明記する。

## 応答

- `POST` → **常に 204**（body が壊れていても、Firestore が落ちていても）。Viewer の表示・Planner の QR 発行を止めない。
  browser からの request（`Origin` あり）は `https://www.sidekick-lab.com` 以外を無視する。Planner（`Origin` 無し）は通す。
- `GET` → 集計 JSON（`Cache-Control: public, max-age=300`）:

```json
{
  "schema": "planner_activity_aggregate/1",
  "generated_at": "2026-09-19T08:00:00.000Z",
  "note": "Planner から送信された計測値。送信失敗・停止設定の分は含まない。細粒度は k >= 5 未満を伏せる。",
  "totals": { "share_created": 42, "share_viewed": 317, "share_viewed_unique": 240, "share_created_category_mountain": 30, "...": 0 },
  "daily": { "2026-09-19": { "share_created": 3, "share_viewed": 12 } }
}
```

細粒度（`*_category_*` / `*_transport_*` / `*_client_*` / `*_code_*`）は **k ≥ 5 未満を伏せる**（`HD-PLANNERACTIVITY-009`）。
公開ページで表示する項目名は **「計測された QR 発行数」**（実数ではなく計測値であることを脚注に書く）。

## 保存先（Firestore、project `sidekick-6cfee`、Admin SDK）

| collection / document | 内容 | 保持 |
|---|---|---|
| `planner_activity_events/{event_id}` | raw event（`schema` `event` `at` `day` `client_kind` ＋ event 種別の field、`received_at`、`expire_at`） | **`expire_at` = `at` ＋ 425 日**（`HD-007`: β ＋ 12 か月）。**`expire_at <= now` になった doc は `/api/planner-activity-cleanup`（Vercel Cron、1 日 1 回）が削除する**（`HD-PLANNERACTIVITY-012`。Firestore TTL は Blaze 前提のため β1.00 では使わない） |
| `planner_activity_daily/{YYYY-MM-DD}` | 日次 increment（`share_created` `share_created_category_*` `share_created_transport_*` `share_viewed` `share_viewed_unique` `share_viewed_client_*` `share_view_failed` `share_view_failed_code_*`） | 永久（成長推移） |
| `planner_activity_totals/all` | 累計 increment（同じ field） | 永久 |

冪等: `event_id` を document id にして `create()`。重複は無視し、集計は **create 成功時だけ** 増やす（再送しても二重計上しない）。

## raw event の cleanup（`/api/planner-activity-cleanup`、`HD-PLANNERACTIVITY-012`）

- `vercel.json` の `crons` により **Vercel Hobby Cron が 1 日 1 回（UTC 18:30 = JST 03:30）GET** する。Vercel は `Authorization: Bearer <CRON_SECRET>` を付ける。
- 動作: `planner_activity_events` を `where("expire_at", "<=", now).orderBy("expire_at").limit(500)` で読み、batch delete。1 回の実行で最大 10 batch（5,000 件）。**冪等**（何度走っても同じ結果）。**`planner_activity_daily` / `planner_activity_totals` には触れない**（code に名前が無いことを `tests/site/test_planner_activity_api_policy.py` が固定）。
- fail-open: cleanup が止まっても raw が増えるだけで、Activity 本体（`/api/planner-activity`）・公開集計に影響しない。`CRON_SECRET` 未設定 → 503 で何もしない。不一致 → 401。
- 手動実行: `curl -H "Authorization: Bearer $CRON_SECRET" https://www.sidekick-lab.com/api/planner-activity-cleanup` → `{"ok":true,"collection":"planner_activity_events","deleted":N,"batches":M,"exhausted":false}`。
- Firestore TTL への置換は将来 Blaze に移行する合理的理由が生じたときに再検討（`HD-012` 第9項）。

## Human 作業（deploy 後）

1. **`CRON_SECRET` を Vercel の Environment Variables に設定**（Project → Settings → Environment Variables、Production。値は 32 文字以上のランダム文字列。設定後に **再 deploy** が必要 = 空 commit の push か Vercel の Redeploy）。未設定の間、cleanup は 503 で何もしない。
2. **cleanup の smoke test（`share.html` 配置の gate）**: Human が console で作った `planner_activity_events/ttl-bootstrap`（`expire_at` 過去）が **最初の cleanup 実行で消える**ことを確認する。方法は (a) 翌日 JST 03:30 以降に Firebase console で `ttl-bootstrap` が無いことを見る、または (b) 上記の手動 `curl` を実行し `deleted` が 1 以上で、console から `ttl-bootstrap` が消えていることを見る。**PASS するまで `share.html`（Viewer beacon）を production に配置しない**。
3. **動作確認（Activity 本体、deploy 後、開発機から。本物の event は送らない）**:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "https://www.sidekick-lab.com/api/planner-activity" -H "Content-Type: application/json" -d "{\"schema\":\"planner_activity/0\"}"
```

   → `204`。続けて `curl -s "https://www.sidekick-lab.com/api/planner-activity"` が `200` で aggregate JSON を返せば function と Firestore（Admin SDK read）は生きている。
4. **B-6 Privacy 文面**（`privacy.html` と Planner 内 `legal_documents.js`）に、送るもの・送らないもの・IP の到達・**保持期間「raw event は約 14 か月後に自動削除、集計は保持」**（Firestore TTL を使っているとは書かない）・停止方法を書く（Phase 3 と同時）。

## test

```bash
node --test tests/tools/test_planner_activity_api.mjs      # 挙動（firebase-admin を fake に差し替え）14 件
node --test tests/tools/test_planner_activity_cleanup.mjs  # cleanup（期限切れのみ・500 件単位・冪等・secret）6 件
python -m pytest tests/site/test_planner_activity_api_policy.py -q   # source 上の privacy policy ＋ cleanup / cron policy 12 件
```

## 将来（B3、V1 以降）

`HD-PLANNERACTIVITY-003`: 明示的に詳細 Activity を有効にした利用者についてのみ、plan 単位の詳細 Analytics（`plan_ref` 等）を
**optional field ＋ schema version の追加**で足す。collection / document 形は変えない。β1.00 では `plan_ref` を受け取っても捨てる。
