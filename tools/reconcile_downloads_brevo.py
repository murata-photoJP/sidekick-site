#!/usr/bin/env python3
"""Firestore の downloads コレクションと Brevo のコンタクトを突合する（読み取り専用）。

register-dl.html は Firestore への書き込みと Brevo への登録を別々に行い、
どちらの失敗も握りつぶして DL 導線を優先する設計になっている。
そのため「Firestore には居るが Brevo には居ない人」が発生しうる。
また 2026-08-20 以前は Brevo の PRODUCT 属性が1つしか持てず、
2製品目をDLすると1製品目の記録が消えていた。

このスクリプトはその2つのズレを洗い出す。**書き込みは一切行わない。**

--------------------------------------------------------------------
使い方
--------------------------------------------------------------------
  # Brevo だけ見る（Firestore なしでも動く）
  set BREVO_API_KEY=xkeysib-...
  py -3 tools/reconcile_downloads_brevo.py --brevo-only

  # Firestore も含めて突合（google-cloud-firestore が必要）
  set GOOGLE_APPLICATION_CREDENTIALS=C:\\path\\to\\serviceAccount.json
  py -3 tools/reconcile_downloads_brevo.py

  # Firestore を JSON でダンプ済みの場合（追加インストール不要）
  py -3 tools/reconcile_downloads_brevo.py --downloads-json downloads.json

  # 突合結果を CSV で書き出す（メールアドレスを含む。取り扱い注意）
  py -3 tools/reconcile_downloads_brevo.py --out E:/temp/reconcile

--------------------------------------------------------------------
必要なもの
--------------------------------------------------------------------
  requests                （インストール済み）
  google-cloud-firestore  （--downloads-json を使う場合は不要）
     pip install google-cloud-firestore

  BREVO_API_KEY               Brevo の API キー
  GOOGLE_APPLICATION_CREDENTIALS  サービスアカウント JSON のパス
     （または FIREBASE_SERVICE_ACCOUNT に JSON 本体）
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import requests

PROJECT_ID = "sidekick-6cfee"
BREVO_API = "https://api.brevo.com/v3/contacts"
BREVO_PAGE_SIZE = 500

# register-dl.html / api/add-contact.js と同じ対応表
PRODUCT_NAME_TO_KEY = {
    "Sidekick_Star": "star",
    "Sidekick_Portrait": "portrait",
    "Sidekick_SkyEffect": "sky",
    "Sidekick_AI": "ai",
}
PRODUCT_SUFFIX = {
    "star": "STAR",
    "portrait": "PORTRAIT",
    "sky": "SKY",
    "ai": "AI",
}


# --------------------------------------------------------------------
# 入力
# --------------------------------------------------------------------
def load_downloads_from_firestore(project_id: str) -> list[dict]:
    """Firestore の downloads コレクションを読む。ライブラリは遅延 import する。"""
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError:
        sys.exit(
            "google-cloud-firestore が見つかりません。\n"
            "  pip install google-cloud-firestore\n"
            "を実行するか、--downloads-json でダンプ済み JSON を渡してください。\n"
            "（Brevo 側だけ見るなら --brevo-only）"
        )

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    tmp_path = None
    if sa_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # api/*.js と同じく環境変数に JSON 本体が入っている運用に合わせる
        fd, tmp_path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(sa_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp_path

    try:
        try:
            client = firestore.Client(project=project_id)
        except Exception as exc:
            if "DefaultCredentials" not in type(exc).__name__:
                raise
            sys.exit(
                "Firestore の認証情報が見つかりません。\n"
                "\n"
                "サービスアカウント JSON のパスを環境変数に設定してください。\n"
                "PowerShell の場合:\n"
                '  $env:GOOGLE_APPLICATION_CREDENTIALS = '
                '"C:\\Program Files\\Adobe\\Adobe Photoshop (Beta)\\Presets\\Scripts'
                '\\自作\\SideKick販売ページ\\Stripe\\'
                'sidekick-6cfee-firebase-adminsdk-fbsvc-074703b048.json"\n'
                "\n"
                "（Stripe フォルダに JSON が2つあるが、どちらも同じサービスアカウント。\n"
                "  新しいほう 074703b048 を使い、失敗したら 444b734d31 を試す）"
            )
        docs = []
        for snap in client.collection("downloads").stream():
            row = snap.to_dict() or {}
            row["_id"] = snap.id
            docs.append(row)
        return docs
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def load_downloads_from_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        # {docId: {...}} 形式のダンプにも対応する
        return [dict(v, _id=k) for k, v in data.items()]
    return data


def fetch_brevo_contacts(api_key: str) -> list[dict]:
    contacts: list[dict] = []
    offset = 0
    while True:
        res = requests.get(
            BREVO_API,
            headers={"api-key": api_key, "Accept": "application/json"},
            params={"limit": BREVO_PAGE_SIZE, "offset": offset},
            timeout=30,
        )
        if res.status_code != 200:
            sys.exit(f"Brevo API エラー: {res.status_code} {res.text[:300]}")
        page = res.json().get("contacts", [])
        contacts.extend(page)
        if len(page) < BREVO_PAGE_SIZE:
            break
        offset += BREVO_PAGE_SIZE
    return contacts


# --------------------------------------------------------------------
# 集計
# --------------------------------------------------------------------
def _ts(value):
    """Firestore Timestamp / ISO文字列 / None を比較可能な文字列にする。"""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def aggregate_downloads(rows: list[dict]) -> dict[str, dict]:
    """メールアドレスごとに「実際にDLした製品」をまとめる（これが正）。"""
    agg: dict[str, dict] = {}
    unknown_products = set()

    for row in rows:
        email = (row.get("email") or "").strip().lower()
        if not email:
            continue
        entry = agg.setdefault(
            email,
            {
                "email": email,
                "products": set(),
                "versions": {},
                "count": 0,
                "first": "",
                "last": "",
                "consent_versions": set(),
                "lead_sources": set(),
                "langs": set(),
            },
        )
        entry["count"] += 1

        # lang は 2026-08-20 以降のみ記録される（それ以前は欠損）
        if row.get("lang"):
            entry["langs"].add(str(row["lang"]))

        product_name = row.get("productName") or ""
        key = PRODUCT_NAME_TO_KEY.get(product_name)
        if key:
            entry["products"].add(key)
            version = (row.get("version") or "").strip()
            if version:
                entry["versions"][key] = version
        elif product_name:
            unknown_products.add(product_name)

        when = _ts(row.get("downloadedAt"))
        if when:
            if not entry["first"] or when < entry["first"]:
                entry["first"] = when
            if when > entry["last"]:
                entry["last"] = when

        if row.get("consentVersion"):
            entry["consent_versions"].add(str(row["consentVersion"]))
        if row.get("leadSource"):
            entry["lead_sources"].add(str(row["leadSource"]))

    if unknown_products:
        print(f"  [注意] 未知の productName: {', '.join(sorted(unknown_products))}")
    return agg


def brevo_products(contact: dict) -> set[str]:
    """Brevo のコンタクトが「持っていることになっている」製品。"""
    attrs = contact.get("attributes") or {}
    owned = set()
    for key, suffix in PRODUCT_SUFFIX.items():
        value = attrs.get("HAS_" + suffix)
        if value and str(value).strip().lower() not in ("", "no", "false", "0"):
            owned.add(key)
    # 旧方式（PRODUCT 属性に最新1件だけ）も拾う
    legacy = PRODUCT_NAME_TO_KEY.get(str(attrs.get("PRODUCT") or ""))
    if legacy:
        owned.add(legacy)
    return owned


# --------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------
def mask(email: str) -> str:
    name, _, domain = email.partition("@")
    head = name[:2] if len(name) > 2 else name[:1]
    return f"{head}***@{domain}"


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def show(title: str, rows: list[dict], sample: int = 10) -> None:
    print(f"\n■ {title}: {len(rows)} 件")
    for row in rows[:sample]:
        detail = row.get("detail", "")
        print(f"    {mask(row['email'])}" + (f"  {detail}" if detail else ""))
    if len(rows) > sample:
        print(f"    … 他 {len(rows) - sample} 件")


# --------------------------------------------------------------------
def load_downloads(args) -> list[dict]:
    if args.downloads_json:
        return load_downloads_from_json(args.downloads_json)
    return load_downloads_from_firestore(args.project)


def firestore_summary(args) -> int:
    """Brevo に触れず、Firestore のダウンロード記録だけを集計する。

    Brevo 登録前に「そもそも何人いるのか・どの製品が何件か」を把握するために使う。
    """
    print("Firestore の downloads を取得中 ...")
    rows = load_downloads(args)
    print(f"  ダウンロード記録: {len(rows)} 件")

    agg = aggregate_downloads(rows)
    print(f"  ユニークなメールアドレス: {len(agg)} 件")

    print()
    print("■ 製品別（ユニークなメールアドレス数）")
    counts: dict[str, int] = defaultdict(int)
    for entry in agg.values():
        for key in entry["products"]:
            counts[key] += 1
    for key in PRODUCT_SUFFIX:
        print(f"    {key:<9} {counts.get(key, 0)} 件")

    multi = [e for e in agg.values() if len(e["products"]) > 1]
    print()
    print(f"■ 複数製品をDLした人: {len(multi)} 件"
          + ("（旧実装では Brevo 側に1製品しか残らなかった対象）" if multi else ""))

    print()
    print("■ 言語（2026-08-20 以降のみ記録）")
    lang_counts: dict[str, int] = defaultdict(int)
    for entry in agg.values():
        for lang in (entry["langs"] or {"(未記録)"}):
            lang_counts[lang] += 1
    for lang, num in sorted(lang_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {lang:<10} {num} 件")

    print()
    print("■ 同意バージョン")
    consent: dict[str, int] = defaultdict(int)
    for entry in agg.values():
        for cv in (entry["consent_versions"] or {"(未記録)"}):
            consent[cv] += 1
    for cv, num in sorted(consent.items(), key=lambda kv: -kv[1]):
        print(f"    {cv:<28} {num} 件")

    print()
    print("■ 流入元 上位10件")
    sources: dict[str, int] = defaultdict(int)
    for entry in agg.values():
        for src in entry["lead_sources"]:
            sources[src] += 1
    for src, num in sorted(sources.items(), key=lambda kv: -kv[1])[:10]:
        print(f"    {src:<24} {num} 件")

    spans = [e["first"] for e in agg.values() if e["first"]]
    if spans:
        print()
        print(f"■ 期間: {min(spans)[:10]} 〜 "
              f"{max(e['last'] for e in agg.values() if e['last'])[:10]}")

    if args.out:
        rows_out = [{
            "email": e["email"],
            "products": ",".join(sorted(e["products"])),
            "versions": ";".join(f"{k}={v}" for k, v in sorted(e["versions"].items())),
            "downloads": e["count"],
            "first": e["first"],
            "last": e["last"],
            "lead_sources": ",".join(sorted(e["lead_sources"])),
            "langs": ",".join(sorted(e["langs"])),
        } for e in sorted(agg.values(), key=lambda x: x["email"])]
        write_csv(args.out / "firestore_downloads.csv", rows_out,
                  ["email", "products", "versions", "downloads", "first", "last",
                   "lead_sources", "langs"])
        print()
        print(f"CSV を書き出しました: {args.out / 'firestore_downloads.csv'}")
        print("メールアドレスを含みます。コミットしないでください。")

    print()
    print("このスクリプトは読み取り専用です。Brevo には一切アクセスしていません。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Firestore downloads と Brevo コンタクトの突合（読み取り専用）"
    )
    parser.add_argument("--downloads-json", type=Path,
                        help="Firestore の代わりに読むダンプ JSON")
    parser.add_argument("--brevo-only", action="store_true",
                        help="Firestore を読まず Brevo の内訳だけ表示する")
    parser.add_argument("--firestore-only", action="store_true",
                        help="Brevo を読まず Firestore の内訳だけ表示する（BREVO_API_KEY 不要）")
    parser.add_argument("--project", default=PROJECT_ID, help="Firebase プロジェクトID")
    parser.add_argument("--out", type=Path,
                        help="CSV 出力先ディレクトリ（メールアドレスを含む）")
    args = parser.parse_args()

    if args.brevo_only and args.firestore_only:
        sys.exit("--brevo-only と --firestore-only は同時に指定できません。")

    # Firestore だけ見る場合は Brevo に触れないので API キーは要らない
    if args.firestore_only:
        return firestore_summary(args)

    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    if not api_key:
        sys.exit("環境変数 BREVO_API_KEY が設定されていません。"
                 "（Firestore 側だけ見るなら --firestore-only を使ってください）")

    print("Brevo のコンタクトを取得中 …")
    contacts = fetch_brevo_contacts(api_key)
    brevo = {(c.get("email") or "").strip().lower(): c for c in contacts if c.get("email")}
    print(f"  Brevo コンタクト: {len(brevo)} 件")

    # Brevo 側の製品内訳
    print("\n■ Brevo 側の製品内訳（HAS_* 属性 / 旧 PRODUCT 属性）")
    counts: dict[str, int] = defaultdict(int)
    no_product = 0
    for contact in brevo.values():
        owned = brevo_products(contact)
        if not owned:
            no_product += 1
        for key in owned:
            counts[key] += 1
    for key in PRODUCT_SUFFIX:
        print(f"    {key:<9} {counts.get(key, 0)} 件")
    print(f"    (製品不明) {no_product} 件")

    # 言語の内訳。LANG は 2026-08-20 に追加した属性なので、
    # それ以前に登録された人は「未設定」になる（日本語メールが英語圏へ飛ぶリスク）。
    print("\n■ Brevo 側の言語内訳（LANG 属性）")
    lang_counts: dict[str, int] = defaultdict(int)
    for contact in brevo.values():
        attrs = contact.get("attributes") or {}
        lang_counts[str(attrs.get("LANG") or "(未設定)")] += 1
    for lang, num in sorted(lang_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {lang:<9} {num} 件")

    if args.brevo_only:
        print("\n--brevo-only のため Firestore との突合は行いませんでした。")
        return 0

    print("\nFirestore の downloads を取得中 …")
    rows = load_downloads(args)
    print(f"  ダウンロード記録: {len(rows)} 件")

    agg = aggregate_downloads(rows)
    print(f"  ユニークなメールアドレス: {len(agg)} 件")

    missing_in_brevo: list[dict] = []
    missing_products: list[dict] = []
    for email, entry in sorted(agg.items()):
        products = ",".join(sorted(entry["products"]))
        versions = ";".join(f"{k}={v}" for k, v in sorted(entry["versions"].items()))
        if email not in brevo:
            missing_in_brevo.append({
                "email": email,
                "products": products,
                "versions": versions,
                "downloads": entry["count"],
                "first": entry["first"],
                "last": entry["last"],
                "lead_sources": ",".join(sorted(entry["lead_sources"])),
                "langs": ",".join(sorted(entry["langs"])),
                "detail": f"{products} / {entry['count']}回",
            })
            continue
        lost = entry["products"] - brevo_products(brevo[email])
        if lost:
            missing_products.append({
                "email": email,
                "missing_products": ",".join(sorted(lost)),
                "all_products": products,
                "versions": versions,
                "detail": f"Brevoに無い製品: {','.join(sorted(lost))}",
            })

    only_in_brevo = [
        {"email": e, "detail": "Firestore に記録なし"}
        for e in sorted(brevo) if e not in agg
    ]

    show("Firestore に居るが Brevo に居ない（登録に失敗した可能性）", missing_in_brevo)
    show("Brevo の製品属性が実際のDL実績より少ない（PRODUCT 上書きの影響）", missing_products)
    show("Brevo に居るが Firestore に記録がない（別経路で登録）", only_in_brevo)

    if args.out:
        out = args.out
        repo = Path(__file__).resolve().parent.parent
        if repo in out.resolve().parents or out.resolve() == repo:
            print(f"\n[警告] 出力先がリポジトリ内です: {out}")
            print("       メールアドレスを含むためコミットしないでください。")
        write_csv(out / "missing_in_brevo.csv", missing_in_brevo,
                  ["email", "products", "versions", "downloads", "first", "last",
                   "lead_sources", "langs"])
        write_csv(out / "missing_products.csv", missing_products,
                  ["email", "missing_products", "all_products", "versions"])
        write_csv(out / "only_in_brevo.csv", only_in_brevo, ["email"])
        print(f"\nCSV を書き出しました: {out}")

    print("\n--- まとめ ---")
    print(f"  Brevo 未登録        : {len(missing_in_brevo)} 件")
    print(f"  製品属性の欠落      : {len(missing_products)} 件")
    print(f"  Firestore 記録なし  : {len(only_in_brevo)} 件")
    print("\nこのスクリプトは読み取り専用です。修正は行っていません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
