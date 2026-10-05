# プランナーQRマップ — Map Viewer（G-3）

状態: G-3 実装（local / Firestore Emulator のみ）。**本番 deploy・本番 Firebase 接続・本番 navigation への link はしていない。**
根拠: `HD-PLANNERQRMAP-001`〜`-016`（自作 `docs/OPEN_QUESTIONS.md`、AI-16597）。Server Core は `docs/QR_MAP_SERVER_CORE.md`（G-2）。

## 1. 構成

| path | 役割 |
|---|---|
| `planner-map.html` | 地図 page（`/planner-map`）。noindex・no-referrer・CSP（script / connect は self、img は self ＋ 地理院タイル）・analytics なし |
| `assets/planner-map/map-core.js` | 純関数（zoom → data tile 段、画面を覆う tile、同じ tile の要求をまとめる、表示上の grouping、`/share#fragment`、日本時間） |
| `assets/planner-map/planner-map.js` | Leaflet の地図・marker・panel・status |
| `assets/planner-map/planner-map.css` | 最小限の見た目（desktop は右の panel、幅 700 px 以下は下の panel） |
| `assets/vendor/leaflet-1.9.4/` | Planner の vendored Leaflet を byte 一致で self-host（`.gitattributes` で改行を変換しない） |
| `tools/qr_map/dev_server.mjs` | local 確認用 server（静的 file ＋ `/api/qr-map` を本物の handler へ）。Emulator 以外では起動しない |
| `tools/qr_map/seed_emulator.mjs` | Human Review 用 seed（実 SharePlan を publish API 経由で入れる） |
| `tools/qr_map/run_browser_tests.mjs` ＋ `tests/qr_map/browser/` | Python Playwright の browser test（Emulator 上の実データ） |
| `firebase/qr-map/firebase.test.json` | test 用 Emulator（port 8086。確認用 8085 と同時に動かせる） |

## 2. 取得（G-2 の GET tile だけ）

- 表示 zoom → server の data tile 段: zoom 6〜11 → 6、12〜15 → 10、16 以上 → 14。zoom 5（日本より広い）は取りに行かない。
  data tile が画面の tile より細かくならないようにして、1 画面の要求数を抑える（日本全体の zoom 6 で最大 30 前後）。
- 画面を覆う tile だけを要求し、30 枚を超える範囲は取りに行かない（拡大を促す）。全件取得の経路は無い。
- 同じ tile は「実行中の要求の共有」と「60 秒の client cache」で 1 回だけ。失敗は cache しない。
- tile の取得・marker / group の表示・pan / zoom では **open を呼ばない**（activity にならない）。

## 3. marker と grouping

- 画面上で半径 36 px 以内の計画を 1 つの丸（件数つき）にまとめる。**表示上のまとめだけ**で、plan を統合・変更しない。
  並びは plan_id 順（人気・新しさ・おすすめの意味を持たせない）。
- 1 件の pin を押す = その計画を開く（POST open）。まとまりを押す = 一覧を出すだけ（open しない）→ 一覧の「この計画を開く」で open。
- 最大 zoom（18）では約 40 m 離れた計画も別の pin になる（同じ地点の計画は 1 つのまとまりのまま、一覧から個別に選べる）。

## 4. 詳細と Viewer への導線

- POST open の応答（fragment を含む）で初めて詳細を出す: ジャンル・天体（星景）・被写体・撮影日時（日本時間）・撮影地点。
- 「計画を見る」= `/share#<fragment>`（既存 Viewer。`rel="noopener noreferrer"`、新しい tab）。Viewer は変更しない。
- 表示する文字は textContent だけ（HD-QR-76 の延長）。

## 5. 状態の表示

読み込み中 ／ 拡大を促す（zoom 5、範囲が広すぎる、tile が上限超え）／ この範囲にはまだ無い ／ 読み込めなかった（再試行 button）／
計画を表示できない（open が 404 = 公開終了・期限切れ）／ 開けなかった（その他の error）。黙って失敗しない。

## 6. local 確認の Origin

browser の POST には `Origin: http://127.0.0.1:port` が付く。`QR_MAP_REQUIRE_EMULATOR=1` のときだけ、dev server が
`QR_MAP_DEV_ALLOWED_ORIGINS` に自分の origin を入れて許可する（`http://127.0.0.1|localhost:port` 以外は無視、本番設定では無効）。

## 7. 実行

```
npm run qr-map:dev               # Emulator（8085）＋ seed ＋ http://127.0.0.1:8787/planner-map
npm run test:qr-map:unit
npm run test:qr-map:emulator     # Emulator（8086）
npm run test:qr-map:browser      # Emulator（8086）＋ dev server（空き port）＋ Playwright（py -3.10）
```

## 8. seed（Human Review 用、16 件）

表示されるもの 13 件: ダイヤモンド富士 3（同じ計画を 2 人が公開 ＋ GV-2）、パール富士、太陽・月、天の川、星景、星の軌跡（鎌倉付近）、
星の軌跡 derived（太陽・月の地点から約 40 m・約 280 m、札幌、京都、美ヶ原）。
表示されないもの 3 件: 期限切れ（200 日前に公開）、取り消し、運営の掲載停止。
derived = 実 SharePlan（VALID_V2-ST-1、被写体なし）の観測点だけを書き換え、Planner と同じ形で作り直したもの。

## 9. 後続 Gate

本番 navigation（Planner 製品 page の #share 付近・top hub）への link、本番 Firebase、地理院タイルの公開 Web Map 形態の Human 判断の記録、
privacy / terms 改定、Planner publish UI（G-4）。
