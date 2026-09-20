"""Sidekick Planner β1.00 製品ページ（/sidekick-planner, /en/sidekick-planner）と、
その配布導線（register-dl → dl-planner）の固定テスト。2026-09-20 新設
（Track planner-beta1-web-product-page、AI-10450）。

固定していること:

1. ページの基本（title / canonical / 相互 hreflang / h1 が 1 つ / OGP / CTA の URL）
2. 本文が canonical の事実と食い違わないこと（版・OS・提供期間・未署名・SHA-256 の表記）
3. Public Roadmap Concealment（HD-PLANNERBETA1GENERICSURFACE-009）:
   星景・天の川・将来ジャンルとしての「太陽・月」を製品ページに出さない。
   パールは「近日対応」の形でだけ出す。
4. 配布導線: 2026-09-20 の Distribution Unit（AI-10850）までは fail-closed（2 定数が空・.zip リンク 0）を
   固定していた。以後は「検証済みの versioned R2 object 1 つだけを指す」ことを固定する
   （test_dl_planner_points_at_the_verified_distribution_package）。
5. スクリーンショット画像が実在し、テンプレートが参照する path と一致すること。

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

JA_KEY = "sidekick-planner"
EN_KEY = "en/sidekick-planner"

# release_acceptance.json（record_version 4）の artifact_identity。ページ作成時に
# canonical の dist/rc13/Sidekick Planner/SidekickPlanner.exe で再計算して一致を確認した値。
RC13_EXE_SHA256 = "709afc4e8a7b3ecd0073fc3926566b570a8c0fc8519080231ba598f18c720af7"
PRODUCT_VERSION = "1.0.0-beta.1"

# HD-PLANNERBETA1GENERICSURFACE-009: β1.00 の public surface に出さない語。
CONCEALED_TERMS = ("星景", "天の川", "太陽・月", "Milky Way", "starscape", "スキャン")


@pytest.fixture(scope="module")
def rendered() -> dict[str, str]:
    return {
        JA_KEY: bs.render_all(JA_KEY)[Path("sidekick-planner.html")],
        EN_KEY: bs.render_all(EN_KEY)[Path("en", "sidekick-planner.html")],
    }


# ---------------------------------------------------------------------------
# 1. ページの基本
# ---------------------------------------------------------------------------

def test_registered_as_language_pair() -> None:
    assert JA_KEY in bs.PAGES and EN_KEY in bs.PAGES
    assert bs.PAGES[JA_KEY]["output"] == Path("sidekick-planner.html")
    assert bs.PAGES[EN_KEY]["output"] == Path("en", "sidekick-planner.html")
    assert bs.PAGES[JA_KEY]["context"]["en_redirect_url"] == "/en/sidekick-planner"
    assert bs.PAGES[JA_KEY]["context"]["enable_ogp"] is True
    assert bs.PAGES[EN_KEY]["context"]["enable_ogp"] is True


@pytest.mark.parametrize("key,canonical", [
    (JA_KEY, "https://www.sidekick-lab.com/sidekick-planner"),
    (EN_KEY, "https://www.sidekick-lab.com/en/sidekick-planner"),
])
def test_canonical_hreflang_h1_title(rendered: dict[str, str], key: str, canonical: str) -> None:
    html = rendered[key]
    assert f'<link rel="canonical" href="{canonical}">' in html
    assert '<link rel="alternate" hreflang="ja" href="https://www.sidekick-lab.com/sidekick-planner">' in html
    assert '<link rel="alternate" hreflang="en" href="https://www.sidekick-lab.com/en/sidekick-planner">' in html
    assert html.count("<h1") == 1, "1ページに h1 は 1 つ"
    assert "<title>Sidekick Planner" in html
    assert 'property="og:image" content="https://www.sidekick-lab.com/images/planner/planner-overview.jpg"' in html
    assert html.count("<html") == 1 and html.count("</html>") == 1


def test_ja_hero_copy_is_the_canonical_tagline(rendered: dict[str, str]) -> None:
    """中心コピー（beta_capability.PRODUCT_TAGLINE と同じ文言）が h1 にあること。"""
    html = rendered[JA_KEY]
    h1 = re.search(r"<h1>(.*?)</h1>", html, flags=re.S).group(1)
    assert "撮りたいイメージから" in h1 and "撮れる場所と日時を探す" in h1
    assert "Sidekick Planner" in h1


@pytest.mark.parametrize("key,href", [
    (JA_KEY, "/register-dl?product=planner&src=sidekick-planner"),
    (EN_KEY, "/register-dl?product=planner&src=sidekick-planner&lang=en"),
])
def test_cta_points_to_register_dl_with_planner_product(rendered: dict[str, str], key: str, href: str) -> None:
    html = rendered[key]
    assert html.count(f'href="{href}"') >= 2, "Hero と末尾 CTA の 2 箇所"
    assert "product=star" not in html


@pytest.mark.parametrize("key,terms,privacy", [
    (JA_KEY, "/planner-terms", "/privacy#planner"),
    (EN_KEY, "/en/planner-terms", "/en/privacy#planner"),
])
def test_legal_links_present(rendered: dict[str, str], key: str, terms: str, privacy: str) -> None:
    html = rendered[key]
    assert f'href="{terms}"' in html
    assert f'href="{privacy}"' in html


def test_internal_links_have_no_html_suffix(rendered: dict[str, str]) -> None:
    for key, html in rendered.items():
        hits = [h for h in re.findall(r'href="(/[^"#?]*)', html) if h.endswith(".html")]
        assert not hits, f"{key}: .html 付きの内部リンク {hits}"


# ---------------------------------------------------------------------------
# 2. canonical の事実との整合
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [JA_KEY, EN_KEY])
def test_beta_facts(rendered: dict[str, str], key: str) -> None:
    html = rendered[key]
    assert PRODUCT_VERSION in html                    # 版
    assert "64-bit" in html                           # HD-OS-01
    assert "2026" in html and ("10月31日" in html or "31 October 2026" in html)  # HD-LR-40
    assert "SmartScreen" in html                      # HD-MC-13
    # 2026-09-20 Human Review（AI-11250）: SHA-256 はユーザー向け UI に出さない（内部検証には残す）
    assert "SHA-256" not in html.split("<main>", 1)[1]
    assert "2GB" in html or "2 GB" in html            # package_total_bytes ≈ 1.94 GiB


def test_page_does_not_publish_a_download_url(rendered: dict[str, str]) -> None:
    """製品ページ自体に配布物への直リンクを置かない（配布は register-dl → dl-planner 経由）。"""
    for key, html in rendered.items():
        assert not re.search(r'https?://\S+\.zip', html), f"{key}: 配布 URL が製品ページにある"


# ---------------------------------------------------------------------------
# 3. Public Roadmap Concealment
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [JA_KEY, EN_KEY])
def test_concealed_roadmap_terms_absent(rendered: dict[str, str], key: str) -> None:
    body = rendered[key].split("<main>", 1)[1].split("</main>", 1)[0]
    # HTML コメント・alt・caption も含めて本文全体を検査する
    for term in CONCEALED_TERMS:
        assert term not in body, f"{key}: 公開しない語 {term!r} が本文にある（HD-PLANNERBETA1GENERICSURFACE-009）"


def test_pearl_is_shown_only_as_coming_soon(rendered: dict[str, str]) -> None:
    ja = rendered[JA_KEY]
    assert "パール" in ja and "近日対応" in ja
    en = rendered[EN_KEY]
    assert "Pearl" in en and "coming soon" in en


# ---------------------------------------------------------------------------
# 4. 配布導線が fail-closed
# ---------------------------------------------------------------------------

def test_register_dl_maps_planner_to_dl_planner() -> None:
    source = (REPO_ROOT / "register-dl.html").read_text(encoding="utf-8")
    assert re.search(r"planner:\s*'/dl-planner'", source)
    assert re.search(r"planner:\s*'Sidekick_Planner'", source)
    assert re.search(r"planner:\s*'1\.0\.0-beta\.1'", source), "register-dl の PRODUCT_VERSIONS は release の product_version"
    assert "Sidekick Planner β1.00" in source
    assert (REPO_ROOT / "dl-planner.html").exists()


# Distribution Unit（AI-10850、Human GO 2026-09-20）で確定した distribution package identity。
# 正本は Planner 側 manifests/release/distribution_package_Sidekick_Planner_1.0.0-beta.1_bea1697.identity.json。
PLANNER_ZIP_URL = "https://pub-123781c638d64762ac2e397ce0e98259.r2.dev/Sidekick_Planner_1.0.0-beta.1_bea1697.zip"
PLANNER_ZIP_SHA256 = "93c27bf1f37641cfc05109d8c0f5876b402bd975b2a01fd59333ed0d3bca83e1"


def test_dl_planner_points_at_the_verified_distribution_package() -> None:
    """配布開始後の形（2026-09-20 に意図的に更新。それまでは 2 定数が空の fail-closed を固定していた）:
    配布 URL は既存製品と同じ R2 bucket の versioned object 1 つだけ、ZIP hash は canonical record の値、
    準備中表示（fail-closed 経路）は残っていること。配布停止は 2 定数を空へ戻す。"""
    source = (REPO_ROOT / "dl-planner.html").read_text(encoding="utf-8")
    assert f"const PLANNER_DOWNLOAD_URL = '{PLANNER_ZIP_URL}';" in source
    assert f"const PLANNER_ZIP_SHA256 = '{PLANNER_ZIP_SHA256}';" in source
    zips = set(re.findall(r'https?://\S+?\.zip', source))
    assert zips == {PLANNER_ZIP_URL}, f"配布 URL は R2 の Planner object 1 つだけ: {zips}"
    assert "pub-123781c638d64762ac2e397ce0e98259.r2.dev" in PLANNER_ZIP_URL   # dl-star.html と同じ bucket
    assert "Sidekick_Planner_1.0.0-beta.1_bea1697.zip" in source.split("setAttribute('download'")[1][:80]
    assert 'id="pending-state"' in source and "配布は準備中" in source          # fail-closed 経路は残す
    assert source.count("<h1") == 1


def test_dl_planner_discloses_unsigned_build_per_hd_mc_13() -> None:
    """HD-MC-13 の disclosure（未署名・SmartScreen・証明書取得手続き中・公式配布元・security 無効化を案内しない）は維持。
    2026-09-20 Human Review（AI-11250）: SHA-256 の値と照合の案内は **ユーザー向け UI から外す**
    （dl-star 等の既存 DL ページと同じ）。hash は内部 gate（JS 定数）と canonical record にだけ残す。"""
    source = (REPO_ROOT / "dl-planner.html").read_text(encoding="utf-8")
    body = source.split("<body>", 1)[1].split("<script>", 1)[0]
    assert "SHA-256" not in body and "照合" not in body
    assert RC13_EXE_SHA256 not in body
    assert "SmartScreen" in body
    assert "署名されていません" in body
    assert "取得手続き中" in body
    assert "sidekick-lab.com" in body                          # 公式配布元
    assert "無効にする必要はありません" in body                 # security の無効化を案内しない
    assert 'href="/planner-terms"' in body and 'href="/privacy#planner"' in body
    # 既存製品と同じ方針（DL ページに hash を出さない）
    for name in ("dl-star.html", "dl-portrait.html", "dl-sky.html", "dl-ai.html"):
        assert "SHA-256" not in (REPO_ROOT / name).read_text(encoding="utf-8")


def test_dl_planner_redirects_unauthorized_to_its_own_product() -> None:
    source = (REPO_ROOT / "dl-planner.html").read_text(encoding="utf-8")
    match = re.search(r"location\.replace\('(/register-dl[^']*)'\)", source)
    assert match and "product=planner" in match.group(1)


def test_add_contact_and_tools_know_the_planner_key() -> None:
    add_contact = (REPO_ROOT / "api" / "add-contact.js").read_text(encoding="utf-8")
    assert re.search(r"planner:\s*'PLANNER'", add_contact)
    assert "'Sidekick_Planner':  'planner'" in add_contact or "'Sidekick_Planner': 'planner'" in add_contact
    attrs = (REPO_ROOT / "tools" / "create_brevo_attributes.py").read_text(encoding="utf-8")
    assert '"HAS_PLANNER"' in attrs and '"VER_PLANNER"' in attrs


# ---------------------------------------------------------------------------
# 5. スクリーンショット
# ---------------------------------------------------------------------------

def test_referenced_screenshots_exist(rendered: dict[str, str]) -> None:
    for key, html in rendered.items():
        srcs = set(re.findall(r'src="(/images/planner/[^"]+)"', html))
        assert srcs, f"{key}: スクリーンショットの参照が無い"
        for src in srcs:
            assert (REPO_ROOT / src.lstrip("/")).exists(), f"{key}: {src} が存在しない"


def test_every_screenshot_has_alt_text(rendered: dict[str, str]) -> None:
    for key, html in rendered.items():
        for tag in re.findall(r"<img[^>]*>", html):
            if "/images/planner/" not in tag:
                continue
            alt = re.search(r'alt="([^"]*)"', tag)
            assert alt and len(alt.group(1)) > 20, f"{key}: alt が無いか短すぎる: {tag[:80]}"


def test_screenshot_script_is_present_and_documented() -> None:
    script = REPO_ROOT / "tools" / "planner_product_page_screenshots.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "--no-activity-upload" in text, "Activity の本番送信を止めて撮る手順であること"
    assert (REPO_ROOT / "docs" / "PLANNER_PRODUCT_PAGE.md").exists()
