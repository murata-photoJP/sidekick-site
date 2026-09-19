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
| `planner_activity_events/{event_id}` | raw event（`schema` `event` `at` `day` `client_kind` ＋ event 種別の field、`received_at`、`expire_at`） | **`expire_at` = `at` ＋ 425 日**（`HD-007`: β ＋ 12 か月）。**TTL policy は Human が console で設定する（下記）** |
| `planner_activity_daily/{YYYY-MM-DD}` | 日次 increment（`share_created` `share_created_category_*` `share_created_transport_*` `share_viewed` `share_viewed_unique` `share_viewed_client_*` `share_view_failed` `share_view_failed_code_*`） | 永久（成長推移） |
| `planner_activity_totals/all` | 累計 increment（同じ field） | 永久 |

冪等: `event_id` を document id にして `create()`。重複は無視し、集計は **create 成功時だけ** 増やす（再送しても二重計上しない）。

## Human 作業（deploy 後）

1. **Firestore TTL policy**: Firebase console → Firestore → TTL → collection `planner_activity_events`、field `expire_at` を有効化（一度だけ）。
   これを設定しないと raw event は消えない（集計は影響なし）。
2. **動作確認**（deploy 後、開発機から。**本物の event は送らない** —— 集計を汚さないため。write 経路は Phase 2 の iPhone gate の実 beacon で確認する）:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST "https://www.sidekick-lab.com/api/planner-activity" -H "Content-Type: application/json" -d "{\"schema\":\"planner_activity/0\"}"
```

   → `204`（未知 schema は無視され、何も保存されない）。続けて `curl -s "https://www.sidekick-lab.com/api/planner-activity"` が
   `200` で `{"schema":"planner_activity_aggregate/1", ..., "totals": {...}, "daily": {...}}` を返せば、function と Firestore（Admin SDK read）は生きている。
   `503 firestore_unavailable` なら Vercel の `FIREBASE_SERVICE_ACCOUNT` env を確認する。
3. **B-6 Privacy 文面**（`privacy.html` と Planner 内 `legal_documents.js`）に、送るもの・送らないもの・IP の到達・保持期間・停止方法を書く（Phase 3 と同時）。

## test

```bash
node --test tests/tools/test_planner_activity_api.mjs      # 挙動（firebase-admin を fake に差し替え）14 件
python -m pytest tests/site/test_planner_activity_api_policy.py -q   # source 上の privacy policy 7 件
```

## 将来（B3、V1 以降）

`HD-PLANNERACTIVITY-003`: 明示的に詳細 Activity を有効にした利用者についてのみ、plan 単位の詳細 Analytics（`plan_ref` 等）を
**optional field ＋ schema version の追加**で足す。collection / document 形は変えない。β1.00 では `plan_ref` を受け取っても捨てる。
