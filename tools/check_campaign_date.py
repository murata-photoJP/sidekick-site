#!/usr/bin/env python3
"""AI Lab 無料キャンペーンの期限が、Firestore とサイトで一致しているか確認する（読み取り専用）。

期限は3箇所にある。

  1. Firestore `config/planLimits.campaignEndDate`  … 実際の判定に使う正
  2. 各ページの JS フォールバック `new Date('YYYY-MM-DD')`
  3. 各ページの表示テキスト（「〜2026年9月末」/ "through end of September 2026"）

2026-08-22、表示だけが 8月末 → 9月末 に更新され、
Firestore と JS フォールバックが 8月31日のまま取り残されていた。
そのままなら 9月1日に「9月末まで無料」と表示したまま制限が切り替わっていた。

2 と 3 の一致は tests/site/test_campaign_date.py が pytest で固定している。
このスクリプトは **1 と照合する**（Firestore へアクセスするため pytest から分離した）。

--------------------------------------------------------------------
使い方
--------------------------------------------------------------------
    $env:GOOGLE_APPLICATION_CREDENTIALS = "C:\\...\\Stripe\\sidekick-6cfee-...json"
    py -3.10 tools/check_campaign_date.py

キャンペーン期限を変えるときは、次の3つを同時に直すこと。

    1. Firebase コンソール → Firestore → config/planLimits → campaignEndDate
    2. 各ページの new Date('...')          … このスクリプトが検出する
    3. 各ページの表示テキスト               … 同上
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def _load_checker():
    """日付の抽出ロジックはテストと共有する（二重管理を避ける）。"""
    spec = importlib.util.spec_from_file_location(
        "test_campaign_date", REPO / "tests" / "site" / "test_campaign_date.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    checker = _load_checker()

    print("サイト内の期限を収集中 ...")
    found = checker.collect()
    site_dates = sorted({date for _, _, date in found})
    print(f"  {len(found)} 箇所 / {len(site_dates)} 種類: {', '.join(site_dates)}")

    if len(site_dates) > 1:
        print("\n[NG] サイト内で期限が割れています。")
        for rel, kind, date in sorted(found, key=lambda x: (x[2], x[0])):
            print(f"    {date}  {kind:<14} {rel}")
        print("\n  pytest tests/site/test_campaign_date.py でも検出されます。")
        return 1

    try:
        from google.cloud import firestore  # type: ignore
    except ImportError:
        print("\ngoogle-cloud-firestore が無いため Firestore との照合はできません。")
        print("  pip install google-cloud-firestore")
        print("サイト内の一致だけは確認できました。")
        return 0

    print("\nFirestore の config/planLimits を取得中 ...")
    try:
        client = firestore.Client(project="sidekick-6cfee")
        snap = client.collection("config").document("planLimits").get()
    except Exception as exc:
        print(f"[NG] Firestore に接続できません: {exc}")
        print("  GOOGLE_APPLICATION_CREDENTIALS にサービスアカウント JSON のパスを設定してください。")
        return 1

    if not snap.exists:
        print("[NG] config/planLimits が存在しません。")
        return 1

    data = snap.to_dict() or {}
    firestore_date = str(data.get("campaignEndDate") or "")
    print(f"  campaignEndDate = {firestore_date or '(未設定)'}")
    for key in ("free_campaign", "free_after", "sidekick_user"):
        if key in data:
            print(f"  {key} = {data[key]}")

    site_date = site_dates[0]
    print()
    if firestore_date == site_date:
        print(f"[OK] Firestore とサイトが一致しています: {site_date}")
        return 0

    print(f"[NG] 食い違っています。")
    print(f"    Firestore : {firestore_date or '(未設定)'}  ← 実際の判定に使われる値")
    print(f"    サイト     : {site_date}  ← 利用者に見えている値")
    print()
    print("  どちらかが利用者への説明と違う挙動になります。")
    print("  Firestore は Firebase コンソールから、サイトはリポジトリを直してください。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
