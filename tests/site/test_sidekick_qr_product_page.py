"""Sidekick QR 製品ページ（/sidekick-qr, /en/sidekick-qr）の固定テスト。2026-09-27 新設
（製品の正本 = 自作内の独立 repository Sidekickシリーズ/本体/Sidekick QR、HD namespace HD-SIDEKICKQR）。

固定していること:

1. ページの基本（登録・canonical・相互 hreflang・og:url・h1 が 1 つ・sitemap 掲載・GA4 がちょうど 1 回）。
   URL /sidekick-qr は Sidekick QR の Card に載る Secondary QR の恒久的な行き先なので、変わったら落とす。
2. 必須の内容: 製品名 / by Sidekick Lab / 「写真から、Webへつなぐ。」、写真 + URL → QRカード、
   写真・URL・カードを送信しない、JPEG / PNG、プレビュー、PNG 保存。
3. ダウンロードは「準備中」の表示だけ: 本文にダウンロード先・installer・ZIP・EXE へのリンクが無く、
   「準備中」表示は button / link ではない。
4. まだ無い機能・未検証の品質を claim しない（HD-SIDEKICKQR-002 / -004 / -005、VB-01）。

リポジトリを読むだけで、何も書き込まない。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "site"))
import build_site as bs  # noqa: E402

JA_KEY = "sidekick-qr"
EN_KEY = "en/sidekick-qr"
JA_URL = "https://www.sidekick-lab.com/sidekick-qr"
EN_URL = "https://www.sidekick-lab.com/en/sidekick-qr"

# 本文（<main>）に出してはいけない語。まだ作っていない機能（HD-SIDEKICKQR-002 / -004）と、
# 検証前の色の claim（HD-SIDEKICKQR-005、VB-01）。
FORBIDDEN_IN_MAIN = (
    "overlay", "オーバーレイ", "sns", "テンプレート", "template", "一括", "batch",
    "exe", "installer", "インストーラ", "shareware", "シェアウェア", "license", "ライセンス",
    "購入", "buy", "price", "価格", ".zip", "色を正確に保ちます", "色をそのまま保ちます",
    "preserves colour", "preserves color", "accurate colour is guaranteed",
)


@pytest.fixture(scope="module")
def rendered() -> dict[str, str]:
    return {
        JA_KEY: bs.render_all(JA_KEY)[Path("sidekick-qr.html")],
        EN_KEY: bs.render_all(EN_KEY)[Path("en", "sidekick-qr.html")],
    }


def _main(html: str) -> str:
    m = re.search(r"<main>(.*?)</main>", html, re.S)
    assert m, "<main> が無い"
    return m.group(1)


# ---------------------------------------------------------------------------
# 1. ページの基本
# ---------------------------------------------------------------------------

def test_registered_as_language_pair() -> None:
    assert bs.PAGES[JA_KEY]["output"] == Path("sidekick-qr.html")
    assert bs.PAGES[EN_KEY]["output"] == Path("en", "sidekick-qr.html")
    assert bs.PAGES[JA_KEY]["context"]["en_redirect_url"] == "/en/sidekick-qr"
    assert bs.PAGES[JA_KEY]["context"]["enable_ogp"] is True
    assert bs.PAGES[EN_KEY]["context"]["enable_ogp"] is True


@pytest.mark.parametrize("key,canonical", [(JA_KEY, JA_URL), (EN_KEY, EN_URL)])
def test_canonical_hreflang_ogurl_h1(rendered: dict[str, str], key: str, canonical: str) -> None:
    html = rendered[key]
    assert f'<link rel="canonical" href="{canonical}">' in html
    assert f'<meta property="og:url" content="{canonical}">' in html
    assert f'<link rel="alternate" hreflang="ja" href="{JA_URL}">' in html
    assert f'<link rel="alternate" hreflang="en" href="{EN_URL}">' in html
    assert html.count("<h1") == 1
    assert "<title>Sidekick QR |" in html
    assert 'name="robots"' not in html, "製品ページは noindex にしない"
    assert html.count("googletagmanager.com/gtag/js?id=G-K73T3Y352W") == 1
    assert html.count("gtag('config'") == 1


@pytest.mark.parametrize("key", [JA_KEY, EN_KEY])
def test_heading_levels_do_not_skip(rendered: dict[str, str], key: str) -> None:
    levels = [int(n) for n in re.findall(r"<h([1-6])[\s>]", _main(rendered[key]))]
    assert levels[0] == 1
    for prev, cur in zip(levels, levels[1:]):
        assert cur <= prev + 1, f"見出しが {prev} → {cur} に飛んでいる"


def test_listed_in_sitemap() -> None:
    sitemap = (REPO_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    assert f"<loc>{JA_URL}</loc>" in sitemap
    assert f"<loc>{EN_URL}</loc>" in sitemap


@pytest.mark.parametrize("key,path", [(JA_KEY, "sidekick-qr.html"), (EN_KEY, "en/sidekick-qr.html")])
def test_production_html_is_the_template_render(rendered: dict[str, str], key: str, path: str) -> None:
    assert (REPO_ROOT / path).read_text(encoding="utf-8") == rendered[key]


# ---------------------------------------------------------------------------
# 2. 必須の内容
# ---------------------------------------------------------------------------

def test_ja_required_content(rendered: dict[str, str]) -> None:
    main = _main(rendered[JA_KEY])
    for text in ("Sidekick QR", "by Sidekick Lab", "写真から、Webへつなぐ。", "写真 ＋ URL → QRカード",
                 "写真・URL・カードは、どこにも送信しません。", "JPEG / PNG", "プレビュー", "PNG で保存"):
        assert text in main, text


def test_en_required_content(rendered: dict[str, str]) -> None:
    main = _main(rendered[EN_KEY])
    for text in ("Sidekick QR", "by Sidekick Lab", "Connect a photo to the web.", "Photo + URL → QR card",
                 "The photo, the URL and the card are not sent anywhere.", "JPEG / PNG", "preview",
                 "save it as PNG"):
        assert text in main, text


# ---------------------------------------------------------------------------
# 3. ダウンロードは「準備中」の表示だけ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,label", [(JA_KEY, "ダウンロード 準備中"), (EN_KEY, "Download Coming Soon")])
def test_download_is_coming_soon_without_any_link(rendered: dict[str, str], key: str, label: str) -> None:
    main = _main(rendered[key])
    assert label in main
    # 「準備中」表示は押せる要素ではない（button / link / form に見せない）
    assert "<button" not in main and "<form" not in main
    for m in re.finditer(rf"<[^>]*>(?:<span[^>]*></span>)?{re.escape(label)}", main):
        assert m.group(0).startswith('<p class="status-pill"'), m.group(0)
    # 本文のリンクはページ内アンカーだけ（ダウンロード先・登録導線・偽リンクを置かない）
    hrefs = re.findall(r'href="([^"]*)"', main)
    assert hrefs and all(h.startswith("#") for h in hrefs), hrefs
    assert re.search(r"<a\s[^>]*\bdownload\b", main) is None, "download 属性付きのリンクを置かない"


# ---------------------------------------------------------------------------
# 4. まだ無い機能・未検証の品質を claim しない
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [JA_KEY, EN_KEY])
def test_no_claims_beyond_the_mvp(rendered: dict[str, str], key: str) -> None:
    text = re.sub(r"<[^>]+>", " ", _main(rendered[key])).lower()
    for term in FORBIDDEN_IN_MAIN:
        assert re.search(rf"(?<![a-z]){re.escape(term.lower())}(?![a-z])", text) is None, term


@pytest.mark.parametrize("key,phrase", [(JA_KEY, "色を正確に保つことは、現時点では保証していません。"),
                                        (EN_KEY, "Accurate colour is not guaranteed at this point.")])
def test_colour_is_stated_as_unverified(rendered: dict[str, str], key: str, phrase: str) -> None:
    assert phrase in _main(rendered[key])
