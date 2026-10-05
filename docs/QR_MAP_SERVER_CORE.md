# プランナーQRマップ — PublicPlan Server Core（G-2）

状態: G-2 実装（local / Firestore Emulator のみ）。**本番 deploy・本番 Firebase 接続はしていない。**
根拠: G-0 設計（HD-G0-001〜012）、G-1 Governance（HD-G1-001〜008）、2026-10-05。

## 1. 既存の QR / SharePlan / Viewer との関係

```
Planner ─┬─ SharePlan ─ QR ─ /share（Viewer）      … 変更なし。server に依存しない
         └─ SharePlan ─ PublicPlan ─ Map            … 今回追加（publish は Planner から明示 opt-in）
```

- PublicPlan は SharePlan fragment の **immutable な写し**。SharePlan / QR / fragment に plan_id を入れない。
- `api/qr-map.js` が止まっても、QR → `/share#fragment` は従来どおり動く（Viewer は server を参照しない）。

## 2. ファイル

| path | 役割 |
|---|---|
| `api/qr-map.js` | HTTP（1 function、`?op=` で route）。Vercel Function はこの 1 本だけ増える |
| `api/_qr_map/config.js` | 定数・環境変数（`_` 始まりの directory は Function にならない） |
| `api/_qr_map/shareplan.js` | fragment の受信判定と表示値の導出 |
| `api/_qr_map/viewer_decoder.generated.js` | **share.html の受信口の機械的な写し**（手で編集しない） |
| `api/_qr_map/tokens.js` | plan_id / manage_token / SHA-256 / 定数時間比較 |
| `api/_qr_map/lifecycle.js` | active / activity / 物理削除の判定（純関数） |
| `api/_qr_map/tiles.js` | data tile（z/x/y）の key |
| `api/_qr_map/firestore.js` | QR Map 専用 Firebase への接続と誤接続 guard |
| `api/_qr_map/store.js` | publish / unpublish / openDetail / getTile / removeByOperator / deleteEligible |
| `tools/qr_map/extract_viewer_decoder.mjs` | share.html → generated module（`--check` で一致確認） |
| `firebase/qr-map/` | emulator 設定・deny-all rules・composite index 定義（配信しない） |
| `tests/qr_map/unit/` | 純関数・HTTP 境界・105 vectors（emulator 不要） |
| `tests/qr_map/emulator/` | Firestore Emulator 結合 test ＋ live local smoke |

## 3. SharePlan の受信（single source of truth）

server は SharePlan を別実装しない。`share.html` の `const SPEC = {` から `/* ---- geometry` の直前までを
1 文字も変えずに切り出し、末尾に `module.exports` を足しただけの module を使う
（`DecompressionStream` / `Blob` / `TextDecoder` / `atob` は Node 24 の global）。
`tests/qr_map/unit/test_viewer_decoder_drift.mjs` が「share.html から再生成した結果 == 置いてある module」を固定する。
Viewer を更新したら `npm run qr-map:extract-decoder` を実行する。

判定の一致は Planner 正本の `cross_language_vectors.json`（105 case、`tests/fixtures/qr_map/README.md`）で固定する。
server が足すのは: 文字数上限、zlib 後続 byte の拒否（多重防御）、version / genre の allow-list。
表示値（座標・日時・被写体名）は fragment から server が導き、client が送る値は使わない。

## 4. Firestore（QR Map 専用 project。既存 sidekick-6cfee には接続しない）

- `qr_map_plans/{plan_id}`: 1 公開 = 1 document（cell に配列で積まない）
  - `snapshot{fragment, payload_sha256, share_version, genre}` / `display{lat, lon, t_d, genre, genre_label, target_label, sky_object_label}` … publish 後は変更しない
  - `tiles{z6, z10, z14}`（data tile key。表示上の区分けで identity ではない）
  - `owner{kind:"anonymous", manage_token_sha256, owner_user_id:null}`
  - `state`（published / unpublished / removed）, `consent_version`, `location_precision:"exact"`
  - `published_at, state_changed_at, last_activity_at, expires_at, delete_after, idempotency_key_sha256`
- `qr_map_idempotency/{sha256(key)}`: `{plan_id, payload_sha256, created_at, delete_after}`
- `qr_map_counters/publish-YYYY-MM-DD`: 日次 publish 件数（global circuit breaker）
- 取得は 1 tile = 1 query: `state == "published" AND tiles.zN == key AND expires_at > now LIMIT 201`。
  超えたら `truncated` ＋ `count()` 集計（document は読まない）。composite index は `firebase/qr-map/firestore.indexes.json`
  （本番では deploy が必要。emulator は index を要求しない）。
- `snapshot` は index から外す（fragment は検索しない）。

### cell 配列方式を採らなかった理由

1 公開 = 1 document なら、document size（1 MiB）・同一 document への書き込み競合・人気 cell の hotspot・
期限切れのための配列書き換えが起きない。読み取りは tile ごとの 1 query（上限付き）＋ 必要時のみ count 集計。

## 5. API

| op | method | 入力 | 出力 / 備考 |
|---|---|---|---|
| publish | POST | fragment, idempotency_key, consent_version | 201 plan_id, manage_token, published_at, expires_at（再送は 200 replayed） |
| unpublish | POST | plan_id, manage_token | 200 state。不一致・不存在は同じ 404 |
| open | POST | plan_id | 200 fragment ほか。**詳細を明示的に開いた = activity**（GET にしない: 先読み・crawler で延長しない） |
| tile | GET | z（6 / 10 / 14）, x, y | 200 plans[], truncated, count。activity 更新なし。`s-maxage=60` |

共通: Origin は付いていれば `https://www.sidekick-lab.com` のみ（Planner は Origin 無し）、POST は `application/json`、
body 8 KB、応答は `no-store`（tile 以外）・`X-Robots-Tag: noindex`。IP / IP hash / User-Agent は保存も log もしない。

## 6. manage_token と idempotency

- token: `crypto.randomBytes(32)`（256 bit、base64url）。DB は SHA-256 のみ。比較は `timingSafeEqual`。
- 同じ idempotency_key の再送は同じ plan_id を返す。最初の応答を失った client のため、**24 時間以内の再送では
  token を出し直す**（DB の hash を差し替える → 旧 token は無効）。24 時間を過ぎた再送は plan_id だけ返す。
  同じ key で別の fragment は 409。

## 7. lifecycle

- active = `state == published && now < expires_at`（expired は state にしない）
- open で `last_activity_at = now`, `expires_at = now + 180 日`（前回から 24 時間未満なら書かない）
- 物理削除: `delete_after = (unpublish / removed の時刻 | expires_at) + 30 日`。`deleteEligible()` が
  `delete_after <= now` を上限付きで消す。**cron への配線は後続 Gate。**

## 8. 誤接続の防止

- `QR_MAP_REQUIRE_EMULATOR=1` のとき emulator 以外を拒否。emulator は `demo-` project だけ。
- `sidekick-6cfee`（既存サイト）は常に拒否。`NODE_ENV=test` で本番を拒否。設定不足は黙って倒れず 503。
- 名前付き app `qr-map` を使い、既存 api/*.js の既定 app と混ざらない。
- tests は本番用 service account 環境変数を消してから始め、`FIRESTORE_EMULATOR_HOST` が無ければ FAIL する。

## 9. 実行

```
npm install --no-package-lock     # 依存（firebase-admin）。node_modules は gitignore
npm run test:qr-map:unit          # emulator 不要
npm run test:qr-map:emulator      # Java 21 が必要（npx firebase-tools@15.32.1 が Firestore Emulator を起動）
```

firebase-tools は `package.json` に入れない（Vercel は devDependency も build 時に install するため、
本番 build に巨大な CLI を持ち込まない）。lockfile も作らない（既存サイトの deploy の挙動を変えない）。

## 10. 後続 Gate へ残すこと

- 本番用 QR Map Firebase project の作成・index deploy・環境変数（`QR_MAP_FIREBASE_PROJECT_ID` /
  `QR_MAP_FIREBASE_SERVICE_ACCOUNT` / `QR_MAP_PUBLISH_ENABLED` / `QR_MAP_DAILY_PUBLISH_LIMIT`）
- Vercel WAF rate limit の設定、cleanup cron の配線、Vercel Pro 移行（HD-G1-002）
- `package.json` の `engines.node = 24.x` は **サイト全体の Function の runtime を 24.x にする**。本番へ出す前に既存 API の回帰確認が要る
- Planner の publish UI（G-4）、Map page（G-3）、privacy / terms 改定
