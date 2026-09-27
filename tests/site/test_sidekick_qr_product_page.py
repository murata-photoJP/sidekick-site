"""Sidekick QR 製品ページ（/sidekick-qr, /en/sidekick-qr）の固定テスト。2026-09-27 新設、2026-09-28 正式版 1.0.0 の Download に更新
（製品の正本 = 自作内の独立 repository Sidekickシリーズ/本体/Sidekick QR、HD-SIDEKICKQR-016）。

固定していること:

1. ページの基本（登録・canonical・相互 hreflang・og:url・h1 が 1 つ・見出し階層・sitemap 掲載・GA4 がちょうど 1 回）。
   URL /sidekick-qr は Sidekick QR の Card に載る Secondary QR の恒久的な行き先なので、変わったら落とす。
2. 必須の内容: 製品名 / by Sidekick Lab / 「写真から、Webへつなぐ。」、写真 + URL → QRカード、JPEG / PNG、Windows、ZIP・インストール不要・
   Python 不要、sRGB 基準、外部サーバーへ送信しない（QR を読んだ端末が Web へ行くことは明記）。
3. Download: 正式 artifact `/downloads/sidekick-qr/SidekickQR-1.0.0.zip` へ直接 link（validation 用の URL は使わない）、
   その file がこの repository にあり SHA-256 が Sidekick QR の canonical record と一致、「準備中 / Coming Soon」が残っていない、
   「すべて展開」→「Sidekick QR.html」の短い説明がある。
4. まだ無い機能・内部の技術説明を載せない（Overlay・SNS テンプレート・一括・EXE・価格・Adobe RGB / ICC 等）。

リポジトリを読むだけで、何も書き込まない。
"""

from __future__ import annotations

import hashlib
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
DOWNLOAD_HREF = "/downloads/sidekick-qr/SidekickQR-1.0.0.zip"
# Sidekick QR repository の docs/RELEASE_1.0.0.md / tools/build_portable_zip.py（source e9b3900）で作った正式 artifact
DOWNLOAD_SHA256 = "6bdaac3bd617b523195a07448d198ae013869a7ccd0d8c719f8862e666cbf405"

FORBIDDEN_IN_MAIN = (
    "overlay", "オーバーレイ", "sns", "テンプレート", "template", "一括", "batch",
    "exe", "installer", "インストーラ", "shareware", "シェアウェア", "license", "ライセンス",
    "購入", "buy", "price", "価格", "adobe rgb", "display p3", "icc", "gamut", "色域",
    "準備中", "coming soon", "validation", "/validation/",
    "色を正確に保ちます", "色をそのまま保ちます", "preserves colour", "preserves color",
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


def test_listed_in_sitemap_and_the_download_is_not() -> None:
    sitemap = (REPO_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    assert f"<loc>{JA_URL}</loc>" in sitemap
    assert f"<loc>{EN_URL}</loc>" in sitemap
    assert ".zip" not in sitemap and "/downloads/" not in sitemap


@pytest.mark.parametrize("key,path", [(JA_KEY, "sidekick-qr.html"), (EN_KEY, "en/sidekick-qr.html")])
def test_production_html_is_the_template_render(rendered: dict[str, str], key: str, path: str) -> None:
    assert (REPO_ROOT / path).read_text(encoding="utf-8") == rendered[key]


# ---------------------------------------------------------------------------
# 2. 必須の内容
# ---------------------------------------------------------------------------

def test_ja_required_content(rendered: dict[str, str]) -> None:
    main = _main(rendered[JA_KEY])
    for text in ("Sidekick QR", "by Sidekick Lab", "写真から、Webへつなぐ。", "写真 ＋ URL → QRカード", "JPEG / PNG", "プレビュー",
                 "PNG で保存", "Windows", "ZIP", "インストール不要", "Python などの追加ソフトも不要", "画像は sRGB を基準に処理します。",
                 "Sidekick QR の処理のために外部のサーバーへ送信されません。", "その QRコードが指す Web ページにアクセスします",
                 "1.0.0", "TERMS.txt", "自動更新はありません"):
        assert text in main, text


def test_en_required_content(rendered: dict[str, str]) -> None:
    main = _main(rendered[EN_KEY])
    for text in ("Sidekick QR", "by Sidekick Lab", "Connect a photo to the web.", "Photo + URL → QR card", "JPEG / PNG", "preview",
                 "save it as PNG", "Windows", "ZIP", "No installation", "no Python", "Images are processed on an sRGB basis.",
                 "not sent to any external server for Sidekick QR's processing.", "open the web page that code points to",
                 "1.0.0", "TERMS.txt", "no automatic updates"):
        assert text in main, text


# ---------------------------------------------------------------------------
# 3. Download
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,steps", [(JA_KEY, ("すべて展開", "Sidekick QR.html", "ダブルクリック")),
                                       (EN_KEY, ("Extract All", "Sidekick QR.html", "Double-click"))])
def test_download_links_to_the_release_artifact(rendered: dict[str, str], key: str, steps: tuple[str, ...]) -> None:
    main = _main(rendered[key])
    hrefs = re.findall(r'href="([^"]*)"', main)
    assert hrefs.count(DOWNLOAD_HREF) == 2                                   # hero と Download 節
    assert set(hrefs) == {DOWNLOAD_HREF, "#how"}, hrefs                     # ほかの link（validation URL・登録導線）なし
    assert "<button" not in main and "<form" not in main
    for text in steps:
        assert text in main, text


def test_the_release_artifact_is_in_the_repository_with_the_canonical_hash() -> None:
    artifact = REPO_ROOT / DOWNLOAD_HREF.lstrip("/")
    assert artifact.is_file()
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == DOWNLOAD_SHA256


# ---------------------------------------------------------------------------
# 4. まだ無い機能・内部の技術説明を載せない
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [JA_KEY, EN_KEY])
def test_no_claims_beyond_the_product(rendered: dict[str, str], key: str) -> None:
    text = re.sub(r"<[^>]+>", " ", _main(rendered[key])).lower()
    for term in FORBIDDEN_IN_MAIN:
        assert re.search(rf"(?<![a-z]){re.escape(term.lower())}(?![a-z])", text) is None, term
