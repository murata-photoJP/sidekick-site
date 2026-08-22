#!/usr/bin/env python3
"""api/add-contact.js が使う Brevo コンタクト属性を一括作成する。

Brevo は未作成の属性を含むリクエストを 400 で拒否する。
add-contact.js は従来属性だけで自動リトライするので DL 導線は止まらないが、
属性を作るまで製品別・言語別の記録は増えない。

対象は add-contact.js が送る属性すべて（13個・すべて text 型）:
    FIRSTNAME / INTEREST / PRODUCT / LEAD_SOURCE  … 2026-06-24 の実装当初から
    HAS_STAR / HAS_PORTRAIT / HAS_SKY / HAS_AI    … その製品をDLしたか（'yes'）
    VER_STAR / VER_PORTRAIT / VER_SKY / VER_AI    … 最後にDLしたバージョン
    LANG                                           … 'ja' / 'en'

FIRSTNAME は Brevo の標準属性なので通常はスキップされる。
INTEREST / PRODUCT / LEAD_SOURCE は独自属性で、Brevo の新規アカウントには存在しない。
**これらが無いと add-contact.js のフォールバックまで 400 になり、
コンタクトが1件も登録されない**（失敗は握りつぶされるので無言で失われる）。

既存の属性は作り直さずスキップする（何度実行しても安全）。
**属性の削除・値の変更は一切行わない。**

--------------------------------------------------------------------
使い方
--------------------------------------------------------------------
    set BREVO_API_KEY=xkeysib-...

    # 何が作られるか確認するだけ
    py -3.10 tools/create_brevo_attributes.py --dry-run

    # 実際に作成する
    py -3.10 tools/create_brevo_attributes.py
"""

from __future__ import annotations

import argparse
import os
import sys

import requests

BREVO_ATTRIBUTES = "https://api.brevo.com/v3/contacts/attributes"
CATEGORY = "normal"

# 属性名 -> 用途（表示用）
# api/add-contact.js が送る属性をすべて網羅すること。
# 1つでも欠けると Brevo が 400 を返し、コンタクトが登録されない
# （add-contact.js は失敗を握りつぶすので無言で失われる）。
ATTRIBUTES = {
    # 2026-06-24 の実装当初から送っている属性。
    # FIRSTNAME は Brevo の標準属性だが、他は独自属性なので作成が必要。
    "FIRSTNAME": "名（Brevo 標準属性）",
    "INTEREST": "関心分野（固定値 photography）",
    "PRODUCT": "最新のDL製品（上書きされる）",
    "LEAD_SOURCE": "最新の流入元ページ（上書きされる）",
    # 2026-08-22 に追加した属性
    "HAS_STAR": "Sidekick Star をDL済みか",
    "HAS_PORTRAIT": "Sidekick Portrait をDL済みか",
    "HAS_SKY": "Sidekick Sky Effect をDL済みか",
    "HAS_AI": "Sidekick AI をDL済みか",
    "VER_STAR": "Star の最終DLバージョン",
    "VER_PORTRAIT": "Portrait の最終DLバージョン",
    "VER_SKY": "Sky Effect の最終DLバージョン",
    "VER_AI": "AI の最終DLバージョン",
    "LANG": "配信言語（ja / en）",
}


def fetch_existing(api_key: str) -> set[str]:
    res = requests.get(
        BREVO_ATTRIBUTES,
        headers={"api-key": api_key, "Accept": "application/json"},
        timeout=30,
    )
    if res.status_code != 200:
        sys.exit(f"Brevo API エラー（属性一覧の取得）: {res.status_code} {res.text[:300]}")
    return {
        a.get("name", "")
        for a in res.json().get("attributes", [])
        if a.get("category") == CATEGORY
    }


def create(api_key: str, name: str) -> tuple[bool, str]:
    res = requests.post(
        f"{BREVO_ATTRIBUTES}/{CATEGORY}/{name}",
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={"type": "text"},
        timeout=30,
    )
    if res.status_code in (201, 204):
        return True, "作成しました"
    # 既に存在する場合も 400 が返る
    if res.status_code == 400 and "exist" in res.text.lower():
        return True, "既に存在します"
    return False, f"{res.status_code} {res.text[:200]}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Brevo コンタクト属性の一括作成（追加のみ・削除しない）"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="作成せず、何が作られるかだけ表示する")
    args = parser.parse_args()

    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    if not api_key:
        sys.exit("環境変数 BREVO_API_KEY が設定されていません。")

    print("既存の属性を確認中 …")
    existing = fetch_existing(api_key)
    print(f"  既存: {len(existing)} 個")
    if args.dry_run and existing:
        print(f"    {', '.join(sorted(existing))}")

    missing = [name for name in ATTRIBUTES if name not in existing]
    if not missing:
        print("\n必要な属性はすべて揃っています。作成するものはありません。")
        return 0

    print(f"\n作成が必要な属性: {len(missing)} 個")
    for name in missing:
        print(f"    {name:<14} {ATTRIBUTES[name]}")

    if args.dry_run:
        print("\n--dry-run のため作成しませんでした。")
        return 0

    print("\n作成中 …")
    failed = []
    for name in missing:
        ok, message = create(api_key, name)
        print(f"    {'OK ' if ok else 'NG '} {name:<14} {message}")
        if not ok:
            failed.append(name)

    if failed:
        print(f"\n{len(failed)} 個の作成に失敗しました: {', '.join(failed)}")
        print("Brevo の管理画面（Contacts → Settings → Contact attributes）で"
              "手動作成してください。型は「テキスト」です。")
        return 1

    print(f"\n{len(missing)} 個の属性を作成しました。")
    print("次: tools/reconcile_downloads_brevo.py --brevo-only で反映を確認できます。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
