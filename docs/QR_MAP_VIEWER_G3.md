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

## 10. G-3.1 Visual / UX Polish（2026-10-05、Human Review: 「緑の○が地図に埋もれ、何の地図か分からない」）

方針（Human Decision）: 地図を主役にせず、**撮影計画を主役にし、地図は計画を見つけるために使う**。見た目と表示だけを変え、
PublicPlan / Firestore / tile・open API / activity / expiry / SharePlan / QR / Viewer / tile 構造 / grouping 規則は変えない。

| 項目 | 内容 |
|---|---|
| 1 件の marker | 先端が撮影地点を指す pin（40×52、当たり判定 44×56）。地理院 pale に埋もれない朱色 `#c2410c` ＋ 白い記号 ＋ 白縁 ＋ 影 |
| ジャンル記号 | 意味は Planner の正本 `SUN_MOON_OBJECT_GLYPHS`（☀ 太陽 / ☾ 月、planner.js）に合わせ SVG で描く（emoji・OS の字形に頼らない）: ダイヤモンド富士 = 太陽、パール富士 = 月、太陽・月（風景）= 太陽＋月、星景 = 星、星の軌跡 = 同心の弧、未知 = 点。名前は必ず文字でも出す（aria-label・tooltip・card） |
| 複数の marker | 「N 件」の吹き出し（白地・濃い枠・重なった影 ＋ 下向きの先端）。pin とは形も文字も違う |
| 選択中 | 大きさ（1.22 倍）＋ 黄色の外枠 ＋ 濃い塗り（色だけにしない）。`aria-pressed`。pan・zoom で再描画しても保ち、panel を閉じると消える |
| 選択した地点 | panel が開いて地図が狭くなっても、選んだ地点が見える範囲に残るよう `panInside`（表示だけ。open しない） |
| header | 「みんなの撮影計画から、撮影場所を探す地図です。」＋ pin と「3件」の小さな凡例つきの 1 行説明 |
| card | genre（記号 ＋ 名前）／ 主題（被写体・天体）／ 日時（YYYY/MM/DD HH:MM 日本時間）／ actions。近くの計画は card を縦に並べ「詳しく見る」（= open）、詳細は「計画を見る」（= 既存 Viewer）、一覧へ戻る（open しない）。写真（`.pm-card-media`）・撮影者は将来 header の前・body の後に足せる構造（今は placeholder を出さない） |
| keyboard | marker は `role="button"`・tabindex 0・Enter / Space で選ぶ。focus-visible の枠 |
| 初期表示 | 中心 37.5°N（北海道〜九州が入る） |

## 11. G-3.2 First Impression / Cluster Pin Polish（2026-10-05、Human Review: 「複数の吹き出しが別種の注釈に見える」「開いた瞬間に何も無く『なにこれ？』」）

| 項目 | 内容 |
|---|---|
| 複数の pin | 1 件と同じ pin（同じ path）の中に件数（数字だけ、100 以上は「99+」）、後ろに淡いもう 1 本を重ねて「束」に見せる。先端（前の pin）が地点を指す。ジャンル記号の代わりに数字。aria-label / tooltip は「N件の撮影計画がこの付近にあります」。選択中の見た目・keyboard・押した後の動き（一覧 → 詳しく見る → POST open）は 1 件・G-3.1 と同じ |
| 凡例 | header の「3件」チップを、同じ形の小さな数字入り pin（「数字のピンは、近くにある計画の件数です。」）へ |
| 初期表示 | `map-core.js` の `INITIAL_VIEW`（中心 35.75°N 138.6°E、zoom 8 = 関東〜中部）。data tile 段 6 のまま、1920×1080 でも要求は十数枚。**MVP の暫定戦略**: 計画が全国に増えたら、存在範囲への fit・地域選択・現在地周辺・全国用の粗い index 等で見直す（未実装）。旧 zoom 6（日本全体）は大きな画面で上限 30 枚を超え「拡大してください」だけになっていた |
| 引いた表示 | 手で zoom 5 以下・上限超えの範囲へ引いた場合のガードは維持。文言を「もう少し地図を拡大すると、撮影計画を表示できます。」へ |

変更なし: PublicPlan / Firestore / tile・open API / activity / expiry / z6・z10・z14 / grouping（36 px）/ 1 件の pin / card / Viewer。

## 12. G-3.3 First Visit UX / Introduction（2026-10-05、Human Review: 「上部の説明が地図に溶け込み読まれない。『なにこれ？閉じちゃえ』になり得る」）

| 項目 | 内容 |
|---|---|
| 導入カード | header を地図とは別の層のカードへ（白地・左に朱色の帯・下に影）。h1 の中に 製品名（小さな eyebrow「プランナーQRマップ」）＋ **何ができるか（headline「みんなの撮影計画から、次に撮りたい場所を探そう。」、最大の文字）**。その下に実物と同じ形の pin の凡例 2 行（「ピンを選ぶと、撮影日時・被写体・撮影計画を見ることができます。」「数字のピンは、この付近にある計画の数です。」）。読点の後でだけ折り返す |
| 高さ | desktop 80 px（1280×800 / 1920×1080）、mobile 375 px で 137 px。地図は viewport の 83〜93 % |
| First Action Cue | **採用**。地図の下中央に小さく「気になるピンを選んでみてください」（desktop は 2 行目に「撮影日時や撮影計画を見ることができます」）。`pointer-events: none`（地図の操作を妨げない）、`aria-hidden`（導入カードと重複するので読み上げない）、modal にしない・閉じる操作も要らない。pin が見えているときだけ出し、最初に pin / 複数の pin を選んだら消える（その page を開いている間だけの状態。localStorage 等に記憶しない） |
| status | 読込中・拡大を促す・空・失敗の表示を地図の上中央へ（cue と重ならない） |

変更なし: 地図の pin・複数の pin・選択・card・Viewer への導線・初期表示（35.75°N 138.6°E zoom 8）・tile guard・activity・keyboard・panel、API / schema。
