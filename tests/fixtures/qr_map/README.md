# プランナーQRマップ（G-2）test fixture

## cross_language_vectors.json

- 正本: 自作 repo `Sidekickシリーズ/本体/Sidekick Planner/validation/prototype/diamond_fuji_minimal/web_viewer/cross_language_vectors.json`
  （自作 commit `8ea6ef9`、2026-09-30。`build_share_viewer.py` が Python canonical codec の判定から生成）
- 写した日: 2026-10-05
- SHA-256: `5d8bddef48c7149827c95f63f9af161482f2f11fb83843f4cd62e793f81b5667`（正本と一致を確認して写した）
- 用途: server（`api/_qr_map/shareplan.js`）の受信判定が、Python canonical ／ 共有ページ（share.html）と
  **全 105 case で同じ受理・同じ code** になることを `tests/qr_map/unit/test_shareplan.mjs` が固定する。
- 本番出力（Web 配信物）には含まれない（`tests/` は `.vercelignore` 対象）。
- 正本が更新されたら、ここへ写し直して SHA-256 を書き換える。手で編集しない。
