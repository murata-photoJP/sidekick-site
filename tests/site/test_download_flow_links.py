"""ダウンロード導線のページ内遷移が `.html` を含まないことを検証する。

`vercel.json` は `cleanUrls: true` のため、`/foo.html` は `/foo` へリダイレクトされる。
2026-07-21 の Google Search Console 対応（「リダイレクトがあります」「重複しています」）で
**内部リンクは .html なしの絶対パス**という方針を決めたが、
JavaScript による遷移（location.replace / location.href）はその網から漏れていた。

2026-08-22 に修正。同じ漏れが起きないよう、ここで固定する。

対象は register-dl.html と dl-*.html。いずれも build_site.py の対象外の手書きページ。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

DOWNLOAD_FLOW_PAGES = [
    "register-dl.html",
    "dl-star.html",
    "dl-portrait.html",
    "dl-sky.html",
    "dl-ai.html",
]

# JS で自ページから遷移する箇所
NAVIGATION = re.compile(
    r"""(?:location\.(?:replace|assign|href\s*=)\s*\(?\s*|["']\s*)(/[A-Za-z0-9\-_/]+\.html)""")

# JS の文字列リテラルに書かれたサイト内パス（DL_PAGES のような対応表を含む）
INTERNAL_PATH = re.compile(r"""['"](/(?:register-dl|dl-[a-z]+)\.html[^'"]*)['"]""")


@pytest.mark.parametrize("name", DOWNLOAD_FLOW_PAGES)
def test_JSの遷移先に_htmlを含まない(name):
    source = (REPO / name).read_text(encoding="utf-8")
    hits = INTERNAL_PATH.findall(source)
    assert not hits, (
        f"{name}: cleanUrls により余分なリダイレクトが発生する内部パス: {hits}\n"
        f"  '.html' を外してください（例: '/dl-sky.html' → '/dl-sky'）")


@pytest.mark.parametrize("name", DOWNLOAD_FLOW_PAGES)
def test_aタグのhrefにも_htmlを含まない(name):
    """HTML 側は既に方針どおりだが、あわせて固定する。"""
    source = (REPO / name).read_text(encoding="utf-8")
    hits = [h for h in re.findall(r'href="(/[^"]*)"', source) if h.endswith(".html")]
    assert not hits, f"{name}: .html 付きの内部リンク: {hits}"


def test_遷移先のページが実在する():
    """`.html` を外したパスが、実ファイルに対応していることを確認する。

    cleanUrls は `/dl-sky` を `dl-sky.html` として配信するので、
    リポジトリ側に該当ファイルが無いと 404 になる。
    """
    register = (REPO / "register-dl.html").read_text(encoding="utf-8")
    targets = re.findall(r"['\"](/dl-[a-z]+)['\"]", register)
    assert targets, "register-dl.html から遷移先を抽出できなかった"
    for target in set(targets):
        path = REPO / (target.lstrip("/") + ".html")
        assert path.exists(), f"{target} に対応する {path.name} が存在しない"


@pytest.mark.parametrize("name", ["dl-star.html", "dl-portrait.html",
                                 "dl-sky.html", "dl-ai.html"])
def test_未認可時の戻り先が自分と同じ製品を指す(name):
    """dl-*.html をコピーして作った際に product が取り違えられていないことを確認する。"""
    product = {"dl-star.html": "star", "dl-portrait.html": "portrait",
               "dl-sky.html": "sky", "dl-ai.html": "ai"}[name]
    source = (REPO / name).read_text(encoding="utf-8")
    match = re.search(r"location\.replace\('(/register-dl[^']*)'\)", source)
    assert match, f"{name}: 未認可時のリダイレクトが見つからない"
    assert f"product={product}" in match.group(1), (
        f"{name}: 戻り先が別製品を指している → {match.group(1)}")


@pytest.mark.parametrize("name,zip_name", [
    ("dl-star.html", "Sidekick_Star.zip"),
    ("dl-portrait.html", "Sidekick_Portrait.zip"),
    ("dl-sky.html", "Sidekick_SkyEffect.zip"),
    ("dl-ai.html", "Sidekick_AI.zip"),
])
def test_各DLページが自分の製品のzipを指す(name, zip_name):
    """同上。R2 の URL とダウンロード時のファイル名が一致していることを確認する。"""
    source = (REPO / name).read_text(encoding="utf-8")
    match = re.search(r"const R2_URL = '([^']+)'", source)
    assert match, f"{name}: R2_URL が見つからない"
    assert match.group(1).endswith(zip_name), (
        f"{name}: R2_URL が {zip_name} ではなく {match.group(1)} を指している")
