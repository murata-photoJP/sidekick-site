"""Sidekick QR 製品ページ（/sidekick-qr, /en/sidekick-qr）の固定テスト。2026-09-27 新設、2026-09-28 正式版 1.0.0 の Download に更新
（製品の正本 = 自作内の独立 repository Sidekickシリーズ/本体/Sidekick QR、HD-SIDEKICKQR-016）。

固定していること:

1. ページの基本（登録・canonical・相互 hreflang・og:url・h1 が 1 つ・見出し階層・sitemap 掲載・GA4 がちょうど 1 回）。
   URL /sidekick-qr は Sidekick QR の Card に載る Secondary QR の恒久的な行き先なので、変わったら落とす。
2. 必須の内容: 製品名 / by Sidekick Lab / 「写真から、Webへつなぐ。」、写真 + URL → QRカード、JPEG / PNG、Windows、ZIP・インストール不要・
   Python 不要、sRGB 基準、外部サーバーへ送信しない（QR を読んだ端末が Web へ行くことは明記）。
3. Download: 正式 artifact `/downloads/sidekick-qr/SidekickQR-1.0.1.zip`（2026-09-30 から、HD-SIDEKICKQR-023）へ直接 link（validation 用の URL は使わない）、
   その file がこの repository にあり SHA-256 が Sidekick QR の canonical record と一致、「準備中 / Coming Soon」が残っていない、
   「すべて展開」→「Sidekick QR.html」の短い説明がある。
4. まだ無い機能・内部の技術説明を載せない（Overlay・SNS テンプレート・一括・EXE・価格・Adobe RGB / ICC 等）。
5. 2026-09-28 Production Replacement（HD-SIDEKICKQR-021）: 日本語版 = 説明 ＋ Web 版（iframe `/sidekick-qr-app/app`、Primary）＋
   オフライン版の ZIP（Secondary、隠さない）。英語版は Portable の製品ページのまま（D-4 = E2）。
   `/sidekick-qr-app/` は noindex（vercel.json の X-Robots-Tag）・sitemap に載せない・日本語の製品ページの iframe 以外から link しない
   （app の bytes と analytics なしは tests/site/test_sidekick_qr_web_validation.py、GA4 の例外は test_deploy_policy.py）。
   グローバルナビ: 「🔗 Sidekick QR」が JA は DOF計算の直後・Workshop の直前、EN は DOF Calculator の直後（全ページ、aria-current は製品ページだけ）。

リポジトリを読むだけで、何も書き込まない。
"""

from __future__ import annotations

import hashlib
import json
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
DOWNLOAD_HREF = "/downloads/sidekick-qr/SidekickQR-1.1.0.zip"
# Sidekick QR repository の docs/release_artifact_1.1.0.json / tools/build_portable_zip.py（source 452cc6a）で作った正式 artifact（HD-SIDEKICKQR-030）
DOWNLOAD_SHA256 = "67d36101f28f604918d5f70ecbfe4d9fbc26213da865bf572f55a294ed992564"
# 1.0.0（HD-SIDEKICKQR-016、source e9b3900）・1.0.1（HD-SIDEKICKQR-023、source 6f53361）は immutable: 置いたまま・bytes を変えない（link はもうしない）
PREVIOUS = {"/downloads/sidekick-qr/SidekickQR-1.0.0.zip": "6bdaac3bd617b523195a07448d198ae013869a7ccd0d8c719f8862e666cbf405",
            "/downloads/sidekick-qr/SidekickQR-1.0.1.zip": "0447c2e8fd69949e54ba1242835eca71623de491f7bc17c665de15722f4964e1"}

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
                 "1.1.0", "TERMS.txt", "自動更新はありません",
                 # Web 版（HD-SIDEKICKQR-021）と privacy / analytics の境界
                 "このページの中で、そのまま使えます", "オフラインで使う", "［PNGを保存・共有］",
                 "このページの表示（ページや画像、プログラムの読み込み）にはインターネットを使います。",
                 "ページの閲覧だけを記録します", "カードを作る部分（Sidekick QR 本体）にはアクセス解析を入れていない",
                 "保存先や共有先を選んだ後の扱いは、その端末やアプリによります"):
        assert text in main, text


def test_en_required_content(rendered: dict[str, str]) -> None:
    main = _main(rendered[EN_KEY])
    for text in ("Sidekick QR", "by Sidekick Lab", "Connect a photo to the web.", "Photo + URL → QR card", "JPEG / PNG", "preview",
                 "save it as PNG", "Windows", "ZIP", "No installation", "no Python", "Images are processed on an sRGB basis.",
                 "not sent to any external server for Sidekick QR's processing.", "open the web page that code points to",
                 "1.1.0", "TERMS.txt", "no automatic updates"):
        assert text in main, text


# ---------------------------------------------------------------------------
# 3. Download
# ---------------------------------------------------------------------------

def test_ja_download_is_the_offline_option(rendered: dict[str, str]) -> None:
    main = _main(rendered[JA_KEY])
    hrefs = re.findall(r'href="([^"]*)"', main)
    assert hrefs.count(DOWNLOAD_HREF) == 1                                   # 「オフラインで使う」節（Secondary）
    assert set(hrefs) == {DOWNLOAD_HREF, "#how", "#offline"}, hrefs         # ほかの link（validation URL・登録導線）なし
    assert 'id="download-link"' in main and 'id="offline"' in main
    assert "<button" not in main and "<form" not in main
    for text in ("すべて展開", "Sidekick QR.html", "ダブルクリック"):
        assert text in main, text


def test_en_download_links_to_the_release_artifact(rendered: dict[str, str]) -> None:
    main = _main(rendered[EN_KEY])
    hrefs = re.findall(r'href="([^"]*)"', main)
    assert hrefs.count(DOWNLOAD_HREF) == 2                                   # hero と Download 節
    assert set(hrefs) == {DOWNLOAD_HREF, "#how"}, hrefs                     # ほかの link（validation URL・登録導線）なし
    assert "<button" not in main and "<form" not in main and "<iframe" not in main   # 英語版は Web 版にしない（D-4 = E2）
    for text in ("Extract All", "Sidekick QR.html", "Double-click"):
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


# ---------------------------------------------------------------------------
# 5. Web 版（Production Replacement、HD-SIDEKICKQR-021）
# ---------------------------------------------------------------------------

APP_SRC = "/sidekick-qr-app/app"


def test_ja_embeds_the_web_app_as_the_primary(rendered: dict[str, str]) -> None:
    main = _main(rendered[JA_KEY])
    frames = re.findall(r"<iframe[^>]*>", main)
    assert len(frames) == 1
    assert f'src="{APP_SRC}"' in frames[0] and 'allow="web-share"' in frames[0] and 'title="Sidekick QR（カードを作る）"' in frames[0]
    assert main.index("<iframe") < main.index(DOWNLOAD_HREF)                 # Web 版が先（Primary）、ZIP は後（Secondary）
    assert (REPO_ROOT / "sidekick-qr-app" / "app.html").is_file()


def test_the_app_is_noindex_unlisted_and_only_embedded_by_the_ja_page() -> None:
    vercel = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    rule = [h for h in vercel.get("headers", []) if h["source"] == "/sidekick-qr-app/(.*)"]
    assert rule and {"key": "X-Robots-Tag", "value": "noindex, nofollow"} in rule[0]["headers"]
    assert "sidekick-qr-app" not in (REPO_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    embedding = []
    for p in REPO_ROOT.rglob("*.html"):
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(("build-output/", "BackUp/", "templates/", "sidekick-qr-app/", "validation/")):
            continue
        if APP_SRC in p.read_text(encoding="utf-8", errors="replace"):
            embedding.append(rel)
    assert embedding == ["sidekick-qr.html"], embedding


def _nav(html: str, menu: str) -> str:
    return html.split(f'id="{menu}"')[1].split("</nav>")[0]


def test_global_nav_has_sidekick_qr_right_after_dof() -> None:
    rendered = bs.render_all(None)
    for key, page in bs.PAGES.items():
        html = rendered[page["output"]]
        if key.startswith("en/"):
            nav = _nav(html, "kzc-nav-menu-en")
            order = ['href="/en/tools/dof"', 'href="/en/sidekick-qr"', 'href="/en/lp-star"']
        else:
            nav = _nav(html, "kzc-nav-menu")
            order = ['href="/tools/dof"', 'href="/sidekick-qr"', 'href="/workshop"']
        assert nav.count(order[1]) == 1, key
        links = re.findall(r'<a href="([^"]+)"', nav)
        i = links.index(order[1].split('"')[1])
        assert links[i - 1] == order[0].split('"')[1] and links[i + 1] == order[2].split('"')[1], (key, links)
        assert "🔗 Sidekick QR</a>" in nav
        current = f'{order[1]} aria-current="page"' in nav
        assert current == (key in (JA_KEY, EN_KEY)), key


def test_previous_release_zip_is_kept_unchanged(rendered: dict[str, str]) -> None:
    """1.0.0 / 1.0.1 の ZIP は上書き・削除しない（HD-SIDEKICKQR-023 / -030）。製品ページからは最新の 1.1.0 だけへ link する。"""
    for href, sha256 in PREVIOUS.items():
        artifact = REPO_ROOT / href.lstrip("/")
        assert artifact.is_file(), href
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == sha256, href
        for key in (JA_KEY, EN_KEY):
            assert href not in rendered[key], (href, key)
