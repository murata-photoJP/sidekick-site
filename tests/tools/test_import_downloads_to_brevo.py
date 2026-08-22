"""tools/import_downloads_to_brevo.py が組み立てる Brevo 属性のテスト。

api/add-contact.js が1件ずつ書いた場合と同じ結果になることを確認する。
ネットワークには一切アクセスしない（build_contacts のみを対象にする）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


imp = _load("import_downloads_to_brevo")


def attrs_for(rows, email="a@example.com"):
    for c in imp.build_contacts(rows):
        if c["email"] == email:
            return c["attributes"]
    raise AssertionError(f"{email} が見つからない")


# --------------------------------------------------------------------
# 製品（上書きバグが再発しないこと）
# --------------------------------------------------------------------
def test_複数製品がすべてHAS属性になる():
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Star",
         "version": "3.16", "downloadedAt": "2026-07-01T00:00:00"},
        {"email": "a@example.com", "productName": "Sidekick_Portrait",
         "version": "3.16", "downloadedAt": "2026-08-01T00:00:00"},
    ]
    a = attrs_for(rows)
    assert a["HAS_STAR"] == "yes"
    assert a["HAS_PORTRAIT"] == "yes"
    assert a["VER_STAR"] == "3.16"
    assert a["VER_PORTRAIT"] == "3.16"


def test_DLしていない製品のHAS属性は送らない():
    rows = [{"email": "a@example.com", "productName": "Sidekick_Star",
             "downloadedAt": "2026-07-01T00:00:00"}]
    a = attrs_for(rows)
    assert "HAS_STAR" in a
    for absent in ["HAS_PORTRAIT", "HAS_SKY", "HAS_AI"]:
        assert absent not in a, f"{absent} を送ってはいけない"


# --------------------------------------------------------------------
# PRODUCT / LEAD_SOURCE は「最新のDL」
# --------------------------------------------------------------------
def test_PRODUCTとLEAD_SOURCEは最新のDLを採用する():
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Star",
         "leadSource": "lp-star", "downloadedAt": "2026-07-01T00:00:00"},
        {"email": "a@example.com", "productName": "Sidekick_Portrait",
         "leadSource": "lp-portrait", "downloadedAt": "2026-08-01T00:00:00"},
    ]
    a = attrs_for(rows)
    assert a["PRODUCT"] == "Sidekick_Portrait"
    assert a["LEAD_SOURCE"] == "lp-portrait"


def test_順序が逆でも最新を選ぶ():
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Portrait",
         "leadSource": "lp-portrait", "downloadedAt": "2026-08-01T00:00:00"},
        {"email": "a@example.com", "productName": "Sidekick_Star",
         "leadSource": "lp-star", "downloadedAt": "2026-07-01T00:00:00"},
    ]
    assert attrs_for(rows)["PRODUCT"] == "Sidekick_Portrait"


# --------------------------------------------------------------------
# バージョン（誤った値を送らないこと）
# --------------------------------------------------------------------
def test_バージョン不明ならVER属性を送らない():
    rows = [{"email": "a@example.com", "productName": "Sidekick_AI",
             "version": "", "downloadedAt": "2026-08-01T00:00:00"}]
    a = attrs_for(rows)
    assert a["HAS_AI"] == "yes"
    assert "VER_AI" not in a


# --------------------------------------------------------------------
# 言語（推測しないこと）
# --------------------------------------------------------------------
def test_言語が1つに確定するときだけLANGを送る():
    rows = [{"email": "a@example.com", "productName": "Sidekick_Star",
             "lang": "en", "downloadedAt": "2026-08-21T00:00:00"}]
    assert attrs_for(rows)["LANG"] == "en"


def test_言語が未記録ならLANGを送らない():
    """2026-08-20 以前の記録には lang が無い。推測せず空のままにする。"""
    rows = [{"email": "a@example.com", "productName": "Sidekick_Star",
             "downloadedAt": "2026-07-01T00:00:00"}]
    assert "LANG" not in attrs_for(rows)


def test_言語が混在するならLANGを送らない():
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Star",
         "lang": "ja", "downloadedAt": "2026-08-21T00:00:00"},
        {"email": "a@example.com", "productName": "Sidekick_Portrait",
         "lang": "en", "downloadedAt": "2026-08-22T00:00:00"},
    ]
    assert "LANG" not in attrs_for(rows)


def test_不正な言語値は送らない():
    rows = [{"email": "a@example.com", "productName": "Sidekick_Star",
             "lang": "xx", "downloadedAt": "2026-08-21T00:00:00"}]
    assert "LANG" not in attrs_for(rows)


# --------------------------------------------------------------------
# 共通
# --------------------------------------------------------------------
def test_INTERESTは常に付く():
    rows = [{"email": "a@example.com", "productName": "Sidekick_Star",
             "downloadedAt": "2026-07-01T00:00:00"}]
    assert attrs_for(rows)["INTEREST"] == "photography"


def test_メールアドレスは小文字に正規化される():
    rows = [{"email": "A@Example.com", "productName": "Sidekick_Star",
             "downloadedAt": "2026-07-01T00:00:00"}]
    assert [c["email"] for c in imp.build_contacts(rows)] == ["a@example.com"]


def test_空のメールアドレスは対象外():
    rows = [{"email": "", "productName": "Sidekick_Star"},
            {"productName": "Sidekick_Star"}]
    assert imp.build_contacts(rows) == []


def test_送信属性がすべて作成対象に含まれている():
    """create_brevo_attributes.py に無い属性を送ると Brevo が 400 を返す。"""
    creator = _load("create_brevo_attributes")
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Star",
         "version": "3.16", "lang": "ja", "leadSource": "lp-star",
         "downloadedAt": "2026-08-21T00:00:00"},
        {"email": "a@example.com", "productName": "Sidekick_Portrait",
         "version": "3.16", "lang": "ja", "leadSource": "lp-portrait",
         "downloadedAt": "2026-08-22T00:00:00"},
        {"email": "b@example.com", "productName": "Sidekick_SkyEffect",
         "version": "3.16", "lang": "en", "downloadedAt": "2026-08-22T00:00:00"},
        {"email": "c@example.com", "productName": "Sidekick_AI",
         "downloadedAt": "2026-08-22T00:00:00"},
    ]
    sent = set()
    for c in imp.build_contacts(rows):
        sent.update(c["attributes"])
    missing = sent - set(creator.ATTRIBUTES)
    assert not missing, f"create_brevo_attributes.py に未登録の属性: {sorted(missing)}"


def test_既定はドライランで書き込まない():
    """--apply を付けない限り Brevo へ送らないことを、コード上で担保する。"""
    source = (REPO / "tools" / "import_downloads_to_brevo.py").read_text(encoding="utf-8")
    assert 'if not args.apply:' in source
    assert '--apply が指定されていないため' in source
    # 書き込みは push() だけが行い、それは --apply の後ろにある
    assert source.index("if not args.apply:") < source.index("ok, message = push(")
