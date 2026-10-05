# Leaflet 1.9.4（self-host）

- 用途: プランナーQRマップ（`/planner-map`）の地図表示。CDN は使わない（HD-PLANNERQRMAP-012、DEPLOY_CHECKLIST の外部 script 禁止）。
- 出典: 自作 repo `Sidekickシリーズ/本体/Sidekick Planner/validation/prototype/diamond_fuji_minimal/assets/web/leaflet/`
  （自作 commit `9d1e114`、2026-09-07。Sidekick Planner が β から使っている vendored copy）を byte 一致で写した（2026-10-05、G-3）。
- License: BSD-2-Clause（同梱 `LICENSE`）。
- SHA-256:
  - `leaflet.js` `db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a`
  - `leaflet.css` `a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6`
  - `LICENSE` `53e8dc25862014e4324741ca18fbe3611e11d42ef69f59f86ea8c5389647d4cb`
  - `images/marker-icon.png` `574c3a5cca85f4114085b6841596d62f00d7c892c7b03f28cbfa301deb1dc437` ほか 4 枚（tests/qr_map/unit が全件照合する）
- 手で編集しない。更新するときは Planner の vendored copy と同時に入れ替え、SHA-256 をここと test に書き直す。
