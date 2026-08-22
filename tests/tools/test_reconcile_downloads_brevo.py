"""tools/reconcile_downloads_brevo.py の突合ロジックのテスト。

2026-08-20 に修正した2件の再発防止:
  A. Brevo の PRODUCT 属性は1つしか持てず、2製品目のDLで1製品目が消えていた
  B. version が全製品共通のハードコードだった（製品別に持つ必要がある）

ネットワークには一切アクセスしない（純粋関数だけを対象にする）。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tools" / "reconcile_downloads_brevo.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("reconcile_downloads_brevo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rec = _load_module()


# --------------------------------------------------------------------
# aggregate_downloads: Firestore 側が「正」であること
# --------------------------------------------------------------------
def test_同一アドレスの複数製品DLがすべて残る():
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Star",
         "version": "3.16", "downloadedAt": "2026-06-01T00:00:00"},
        {"email": "a@example.com", "productName": "Sidekick_Portrait",
         "version": "3.16", "downloadedAt": "2026-07-01T00:00:00"},
    ]
    agg = rec.aggregate_downloads(rows)
    assert agg["a@example.com"]["products"] == {"star", "portrait"}
    assert agg["a@example.com"]["count"] == 2
    assert agg["a@example.com"]["first"] == "2026-06-01T00:00:00"
    assert agg["a@example.com"]["last"] == "2026-07-01T00:00:00"


def test_バージョンは製品ごとに保持される():
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Star", "version": "3.16"},
        {"email": "a@example.com", "productName": "Sidekick_SkyEffect", "version": "1.02"},
    ]
    agg = rec.aggregate_downloads(rows)
    assert agg["a@example.com"]["versions"] == {"star": "3.16", "sky": "1.02"}


def test_バージョン未確定の空文字は記録しない():
    """誤った値を残すくらいなら空にする、という register-dl.html 側の方針に合わせる。"""
    rows = [{"email": "a@example.com", "productName": "Sidekick_AI", "version": ""}]
    agg = rec.aggregate_downloads(rows)
    assert agg["a@example.com"]["products"] == {"ai"}
    assert agg["a@example.com"]["versions"] == {}


def test_メールアドレスは大文字小文字を無視して集約される():
    rows = [
        {"email": "A@Example.com", "productName": "Sidekick_Star"},
        {"email": "a@example.com", "productName": "Sidekick_Portrait"},
    ]
    agg = rec.aggregate_downloads(rows)
    assert list(agg) == ["a@example.com"]
    assert agg["a@example.com"]["products"] == {"star", "portrait"}


def test_メールアドレスが空の行は無視される():
    rows = [{"email": "", "productName": "Sidekick_Star"}, {"productName": "Sidekick_Star"}]
    assert rec.aggregate_downloads(rows) == {}


def test_未知の製品名でも落ちない():
    rows = [{"email": "a@example.com", "productName": "Sidekick_Unknown"}]
    agg = rec.aggregate_downloads(rows)
    assert agg["a@example.com"]["products"] == set()
    assert agg["a@example.com"]["count"] == 1


# --------------------------------------------------------------------
# brevo_products: 新旧どちらの属性も読めること
# --------------------------------------------------------------------
def test_新方式のHAS属性を読む():
    contact = {"attributes": {"HAS_STAR": "yes", "HAS_PORTRAIT": "yes"}}
    assert rec.brevo_products(contact) == {"star", "portrait"}


def test_旧方式のPRODUCT属性も拾う():
    contact = {"attributes": {"PRODUCT": "Sidekick_Portrait"}}
    assert rec.brevo_products(contact) == {"portrait"}


def test_新旧が混在しても両方読む():
    contact = {"attributes": {"HAS_STAR": "yes", "PRODUCT": "Sidekick_SkyEffect"}}
    assert rec.brevo_products(contact) == {"star", "sky"}


@pytest.mark.parametrize("value", ["", "no", "No", "false", "0", None])
def test_否定的な値は所有とみなさない(value):
    assert rec.brevo_products({"attributes": {"HAS_STAR": value}}) == set()


def test_属性が無いコンタクトでも落ちない():
    assert rec.brevo_products({}) == set()


# --------------------------------------------------------------------
# 上書きバグ（A）が検出できること
# --------------------------------------------------------------------
def test_PRODUCT上書きの被害者を検出できる():
    """Star→Portrait とDLした人は、旧実装では Brevo 上 Portrait しか残らない。"""
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Star"},
        {"email": "a@example.com", "productName": "Sidekick_Portrait"},
    ]
    agg = rec.aggregate_downloads(rows)
    brevo_contact = {"attributes": {"PRODUCT": "Sidekick_Portrait"}}  # 旧実装の結果

    lost = agg["a@example.com"]["products"] - rec.brevo_products(brevo_contact)
    assert lost == {"star"}


def test_修正後は欠落が出ない():
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Star"},
        {"email": "a@example.com", "productName": "Sidekick_Portrait"},
    ]
    agg = rec.aggregate_downloads(rows)
    brevo_contact = {"attributes": {  # 新実装の結果
        "HAS_STAR": "yes", "HAS_PORTRAIT": "yes", "PRODUCT": "Sidekick_Portrait",
    }}
    assert agg["a@example.com"]["products"] - rec.brevo_products(brevo_contact) == set()


# --------------------------------------------------------------------
# 入力形式・出力
# --------------------------------------------------------------------
def test_配列形式のJSONダンプを読める(tmp_path):
    path = tmp_path / "downloads.json"
    path.write_text(json.dumps(
        [{"email": "a@example.com", "productName": "Sidekick_Star"}]), encoding="utf-8")
    assert rec.load_downloads_from_json(path)[0]["email"] == "a@example.com"


def test_辞書形式のJSONダンプを読める(tmp_path):
    path = tmp_path / "downloads.json"
    path.write_text(json.dumps(
        {"doc1": {"email": "a@example.com", "productName": "Sidekick_Star"}}), encoding="utf-8")
    rows = rec.load_downloads_from_json(path)
    assert rows[0]["_id"] == "doc1"


def test_マスクでドメインだけ残る():
    assert rec.mask("murata@example.com") == "mu***@example.com"
    assert rec.mask("a@example.com") == "a***@example.com"


def test_CSVを書き出せる(tmp_path):
    rec.write_csv(tmp_path / "out.csv",
                  [{"email": "a@example.com", "products": "star", "detail": "無視される"}],
                  ["email", "products"])
    text = (tmp_path / "out.csv").read_text(encoding="utf-8-sig")
    assert "email,products" in text
    assert "a@example.com,star" in text
    assert "無視される" not in text  # extrasaction="ignore" が効いている


# --------------------------------------------------------------------
# 対応表が register-dl.html / api/add-contact.js と一致していること
# --------------------------------------------------------------------
def test_製品キーが3ファイルで一致している():
    register = (REPO / "register-dl.html").read_text(encoding="utf-8")
    add_contact = (REPO / "api" / "add-contact.js").read_text(encoding="utf-8")
    for key, name in [("star", "Sidekick_Star"), ("portrait", "Sidekick_Portrait"),
                      ("sky", "Sidekick_SkyEffect"), ("ai", "Sidekick_AI")]:
        assert rec.PRODUCT_NAME_TO_KEY[name] == key
        assert name in register
        assert name in add_contact
        assert rec.PRODUCT_SUFFIX[key] in add_contact


def test_register_dlに製品別バージョン表がある():
    register = (REPO / "register-dl.html").read_text(encoding="utf-8")
    assert "PRODUCT_VERSIONS" in register
    assert "const CURRENT_VERSION = '3.16';" not in register  # 全製品共通の旧実装


# --------------------------------------------------------------------
# 言語（2026-08-20 追加）
# --------------------------------------------------------------------
def test_langをメールアドレスごとに集約する():
    rows = [
        {"email": "a@example.com", "productName": "Sidekick_Star", "lang": "en"},
        {"email": "a@example.com", "productName": "Sidekick_Portrait", "lang": "en"},
        {"email": "b@example.com", "productName": "Sidekick_Star", "lang": "ja"},
    ]
    agg = rec.aggregate_downloads(rows)
    assert agg["a@example.com"]["langs"] == {"en"}
    assert agg["b@example.com"]["langs"] == {"ja"}


def test_lang未記録の古いデータでも落ちない():
    """2026-08-20 以前のドキュメントには lang フィールドが無い。"""
    rows = [{"email": "a@example.com", "productName": "Sidekick_Star"}]
    assert rec.aggregate_downloads(rows)["a@example.com"]["langs"] == set()


def test_EN側のリンクにlangが付いている():
    """EN の各ページは register-dl を ?lang=en 付きで呼ぶ必要がある。

    src だけでは Sky と Portrait が JA と区別できない（どちらも lp-sky / lp-portrait）。
    """
    import re
    for name in ["index", "lp-star", "portrait", "sidekick-star", "sidekick", "sky-effect"]:
        for path in [REPO / "en" / f"{name}.html",
                     REPO / "templates" / "site" / "pages" / "en" / f"{name}.html"]:
            links = re.findall(r"register-dl\?[^\"'<> ]*", path.read_text(encoding="utf-8"))
            assert links, f"{path} に register-dl リンクが見つからない"
            for link in links:
                assert "lang=en" in link, f"{path}: {link} に lang=en が無い"


def test_JA側のリンクにはlangを付けない():
    """JA は register-dl.html 側の既定値（ja）に任せる。"""
    import re
    for name in ["index", "lp-star", "portrait", "sidekick-star", "sidekick", "sky-effect"]:
        for path in [REPO / f"{name}.html",
                     REPO / "templates" / "site" / "pages" / f"{name}.html"]:
            for link in re.findall(r"register-dl\?[^\"'<> ]*", path.read_text(encoding="utf-8")):
                assert "lang=" not in link, f"{path}: {link} に lang が付いている"


def test_作成対象の属性がadd_contactの送信内容を網羅している():
    """create_brevo_attributes.py の作成対象に漏れがあると、Brevo が 400 を返し
    コンタクトが1件も登録されない（add-contact.js は失敗を握りつぶすので無言で失われる）。

    2026-08-22 に PRODUCT / LEAD_SOURCE / INTEREST の漏れが実際に発生したため追加。
    """
    import importlib.util as _ilu
    import re

    spec = _ilu.spec_from_file_location(
        "create_brevo_attributes", REPO / "tools" / "create_brevo_attributes.py")
    creator = _ilu.module_from_spec(spec)
    sys.modules[spec.name] = creator
    spec.loader.exec_module(creator)

    source = (REPO / "api" / "add-contact.js").read_text(encoding="utf-8")

    # legacyAttributes / newAttributes に現れる固定キー
    sent = set(re.findall(r"^\s*([A-Z][A-Z_0-9]+):\s", source, re.M))
    # newAttributes['HAS_' + suffix] のような動的キー
    for prefix in re.findall(r"newAttributes\['([A-Z_]+)'\s*\+\s*suffix\]", source):
        for suffix in rec.PRODUCT_SUFFIX.values():
            sent.add(prefix + suffix)
    # newAttributes.LANG のようなドット記法
    sent.update(re.findall(r"newAttributes\.([A-Z_]+)", source))

    assert sent, "add-contact.js から属性名を抽出できなかった"
    missing = sent - set(creator.ATTRIBUTES)
    assert not missing, (
        f"create_brevo_attributes.py に未登録の属性がある: {sorted(missing)}")


def test_旧来の独自属性も作成対象に含まれている():
    """Brevo 標準属性ではないので、新規アカウントでは作成が必要。"""
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        "create_brevo_attributes", REPO / "tools" / "create_brevo_attributes.py")
    creator = _ilu.module_from_spec(spec)
    sys.modules[spec.name] = creator
    spec.loader.exec_module(creator)
    for name in ["INTEREST", "PRODUCT", "LEAD_SOURCE"]:
        assert name in creator.ATTRIBUTES, f"{name} が作成対象に無い"


def test_add_contactがLANGを新設属性側で扱っている():
    """LANG も 2026-08-20 追加の属性なので、400 時のフォールバックで落とす必要がある。"""
    source = (REPO / "api" / "add-contact.js").read_text(encoding="utf-8")
    assert "newAttributes.LANG" in source
    assert "legacyAttributes" in source
    # フォールバックは従来属性だけを送る
    assert "attributes: legacyAttributes" in source
