#!/usr/bin/env python3
"""Firestore の downloads を Brevo のコンタクトへ一括登録する。

2026-06-24 の実装以来 BREVO_API_KEY が未設定だったため、
api/add-contact.js は一度も Brevo に書き込めていなかった（失敗を握りつぶす設計のため無言）。
その間のダウンロード者は Firestore にしか存在しない。このスクリプトで移す。

**既定はドライラン。--apply を付けたときだけ Brevo へ書き込む。**
書き込みは追加と属性更新のみで、削除・配信停止の変更は一切行わない。

--------------------------------------------------------------------
使い方
--------------------------------------------------------------------
    $env:BREVO_API_KEY = "xkeysib-..."
    $env:GOOGLE_APPLICATION_CREDENTIALS = "C:\\path\\to\\serviceAccount.json"

    # 何が登録されるか確認するだけ（既定）
    py -3.10 tools/import_downloads_to_brevo.py

    # 最初の3件だけ実際に登録して結果を確かめる
    py -3.10 tools/import_downloads_to_brevo.py --apply --limit 3

    # 全件登録
    py -3.10 tools/import_downloads_to_brevo.py --apply

Firestore を JSON でダンプ済みなら google-cloud-firestore は不要:

    py -3.10 tools/import_downloads_to_brevo.py --downloads-json downloads.json

--------------------------------------------------------------------
前提
--------------------------------------------------------------------
tools/create_brevo_attributes.py を先に実行して、Brevo 側に属性を作っておくこと。
属性が無いと Brevo が 400 を返し、1件も登録できない。

同意の範囲は register-dl.html で取得したもの（アップデート告知・重要なお知らせ・
サポート）に限られる。docs/DOWNLOAD_CONTACTS.md の「5. 同意の範囲」を参照。
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
BREVO_CONTACTS = "https://api.brevo.com/v3/contacts"

# Brevo の API は概ね 10 req/s。余裕をみて間隔を空ける
REQUEST_INTERVAL_SEC = 0.15


def _load_reconcile():
    """対応表と集計ロジックを reconcile_downloads_brevo.py と共有する。"""
    spec = importlib.util.spec_from_file_location(
        "reconcile_downloads_brevo", HERE / "reconcile_downloads_brevo.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rec = _load_reconcile()


# --------------------------------------------------------------------
def build_contacts(rows: list[dict]) -> list[dict]:
    """ダウンロード記録から、Brevo に送るコンタクト定義を組み立てる。

    api/add-contact.js が1件ずつ書くのと同じ結果になるようにする。
    PRODUCT / LEAD_SOURCE は「最新のDL」を採用する（add-contact.js の上書き挙動と同じ）。
    """
    agg = rec.aggregate_downloads(rows)

    # PRODUCT / LEAD_SOURCE は最新のDL記録から取る
    latest: dict[str, tuple[str, str, str]] = {}
    for row in rows:
        email = (row.get("email") or "").strip().lower()
        if not email:
            continue
        when = rec._ts(row.get("downloadedAt"))
        if email not in latest or when > latest[email][0]:
            latest[email] = (when,
                             str(row.get("productName") or ""),
                             str(row.get("leadSource") or ""))

    contacts = []
    for email, entry in sorted(agg.items()):
        attrs: dict[str, str] = {"INTEREST": "photography"}

        _, product_name, lead_source = latest.get(email, ("", "", ""))
        if product_name:
            attrs["PRODUCT"] = product_name
        if lead_source:
            attrs["LEAD_SOURCE"] = lead_source

        for key in sorted(entry["products"]):
            attrs["HAS_" + rec.PRODUCT_SUFFIX[key]] = "yes"
        for key, version in sorted(entry["versions"].items()):
            attrs["VER_" + rec.PRODUCT_SUFFIX[key]] = version

        # 言語は1つに確定できるときだけ入れる。
        # 混在・未記録のときは推測せず空のままにする（後から判断できるように）。
        langs = entry["langs"]
        if len(langs) == 1:
            lang = next(iter(langs))
            if lang in ("ja", "en"):
                attrs["LANG"] = lang

        contacts.append({"email": email, "attributes": attrs, "_entry": entry})
    return contacts


def push(api_key: str, email: str, attributes: dict) -> tuple[bool, str]:
    res = requests.post(
        BREVO_CONTACTS,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={"email": email, "attributes": attributes, "updateEnabled": True},
        timeout=30,
    )
    if res.status_code in (201, 204):
        return True, "登録しました" if res.status_code == 201 else "更新しました"
    return False, f"{res.status_code} {res.text[:200]}"


# --------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Firestore の downloads を Brevo へ一括登録（既定はドライラン）")
    parser.add_argument("--apply", action="store_true",
                        help="実際に Brevo へ書き込む（付けなければ何もしない）")
    parser.add_argument("--limit", type=int, default=0,
                        help="先頭 N 件だけ処理する（0 は全件）")
    parser.add_argument("--downloads-json", type=Path,
                        help="Firestore の代わりに読むダンプ JSON")
    parser.add_argument("--project", default=rec.PROJECT_ID, help="Firebase プロジェクトID")
    args = parser.parse_args()

    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    if args.apply and not api_key:
        sys.exit("環境変数 BREVO_API_KEY が設定されていません。")

    print("Firestore の downloads を取得中 ...")
    rows = rec.load_downloads(args)
    print(f"  ダウンロード記録: {len(rows)} 件")

    contacts = build_contacts(rows)
    print(f"  登録対象のメールアドレス: {len(contacts)} 件")

    if args.limit:
        contacts = contacts[:args.limit]
        print(f"  --limit により {len(contacts)} 件に絞りました")

    if not contacts:
        print("\n対象がありません。")
        return 0

    # 内訳
    no_lang = sum(1 for c in contacts if "LANG" not in c["attributes"])
    no_ver = sum(1 for c in contacts
                 if not any(k.startswith("VER_") for k in c["attributes"]))
    print(f"\n  LANG を確定できない: {no_lang} 件（言語未記録、または ja/en 混在）")
    print(f"  バージョン不明:      {no_ver} 件")

    print("\n■ 送信内容（先頭5件・アドレスは伏せています）")
    for c in contacts[:5]:
        attrs = ", ".join(f"{k}={v}" for k, v in sorted(c["attributes"].items()))
        print(f"    {rec.mask(c['email'])}")
        print(f"        {attrs}")
    if len(contacts) > 5:
        print(f"    … 他 {len(contacts) - 5} 件")

    if not args.apply:
        print("\n--apply が指定されていないため、Brevo には何も書き込んでいません。")
        print("実行するには --apply を付けてください。まずは --apply --limit 3 を推奨します。")
        return 0

    print(f"\n{len(contacts)} 件を Brevo へ登録します ...")
    ok_count, failed = 0, []
    for index, c in enumerate(contacts, 1):
        ok, message = push(api_key, c["email"], c["attributes"])
        if ok:
            ok_count += 1
        else:
            failed.append((c["email"], message))
            print(f"    NG  {rec.mask(c['email'])}  {message}")
        if index % 25 == 0 or index == len(contacts):
            print(f"    ... {index}/{len(contacts)} 完了")
        time.sleep(REQUEST_INTERVAL_SEC)

    print(f"\n成功 {ok_count} 件 / 失敗 {len(failed)} 件")
    if failed:
        print("\n失敗した宛先:")
        for email, message in failed[:20]:
            print(f"    {rec.mask(email)}  {message}")
        if len(failed) > 20:
            print(f"    … 他 {len(failed) - 20} 件")
        print("\n属性が未作成の場合は tools/create_brevo_attributes.py を先に実行してください。")
        return 1

    print("\n確認: py -3.10 tools/reconcile_downloads_brevo.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
