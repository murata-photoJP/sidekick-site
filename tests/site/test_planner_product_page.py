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
PRODUCT_VERSION = "1.0.0-beta.2"   # β1.01 = RC14（2026-09-21 release）。β1.00 = 1.0.0-beta.1 は history

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
    assert re.search(r"planner:\s*'1\.0\.0-beta\.2'", source), "register-dl の PRODUCT_VERSIONS は release の product_version"
    assert "Sidekick Planner β1.01" in source
    assert (REPO_ROOT / "dl-planner.html").exists()


# β1.01 Release Unit（AI-13050、Human GO 2026-09-21）で確定した distribution package identity（RC14）。
# 正本は Planner 側 manifests/release/distribution_package_Sidekick_Planner_1.0.0-beta.2_c3faa92.identity.json。
# β1.00（Sidekick_Planner_1.0.0-beta.1_bea1697.zip / 93c27bf1…、AI-10850）は R2 に保存したまま配布導線から外した。
PLANNER_ZIP_URL = "https://pub-123781c638d64762ac2e397ce0e98259.r2.dev/Sidekick_Planner_1.0.0-beta.2_c3faa92.zip"
PLANNER_ZIP_SHA256 = "a577b809db480be0da29bb6a1a46f7e2521769d785af4045e148b4b0d3a91804"


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
    assert "Sidekick_Planner_1.0.0-beta.2_c3faa92.zip" in source.split("setAttribute('download'")[1][:80]
    assert "Sidekick_Planner_1.0.0-beta.1_bea1697.zip" not in source.split("const PLANNER_DOWNLOAD_URL")[1].split(";")[0]
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


# ---------------------------------------------------------------------------
# 5. β1.01 beta expiry disclosure（HD-PLANNERBETA1EXPIRYLEGAL-001〜007、Legal FINAL 2026-09-21）
# ---------------------------------------------------------------------------

def _page(name: str) -> str:
    return (REPO_ROOT / "templates" / "site" / "pages" / name).read_text(encoding="utf-8")


def test_terms_section3_states_expiry_after_the_planned_end_date_ja_en() -> None:
    """Terms 第3条: 2026-10-31 日本時間、β1.01 以降は期限後起動不可、延長は新しいβ版、告知だけでは期限は変わらない。
    EN は JA の忠実 localization。β1.00 へ遡及しない（「β1.01 以降」/ "beta 1.01 and later"）。"""
    ja = _page("planner-terms.html"); en = _page("en/planner-terms.html")
    assert "2026年10月31日</strong>（日本時間。現時点の終了予定日）" in ja
    assert "終了予定日を過ぎると、本β版（β1.01 以降）は起動できなくなり、通常の機能を利用できなくなります。" in ja
    assert "延長後の終了予定日を組み込んだ新しいβ版を配布します" in ja
    assert "このページの告知だけでは変わりません" in ja
    assert "October 31, 2026</strong> (Japan time; the currently planned end date)" in en
    assert "After the planned end date, the Beta (beta 1.01 and later) can no longer be started and its normal functions can no longer be used." in en
    assert "we will distribute a new Beta version that carries the extended end date" in en
    assert "does not change by an announcement on this page alone" in en
    # 第2段落（reset なし）と第12条（免責、拡張なし）は不変
    assert "更新のたびに新しい提供期間が始まるものではありません" in ja
    assert "an update does not start a new Beta period" in en
    assert "当方の故意または重大な過失による場合を除き" in ja


def test_privacy_9_1_discloses_local_last_seen_ja_en() -> None:
    """Privacy 9-1: PC 内のみ / 判定目的 / 外部送信なし / 9-3 に含めない / 識別目的でない。9-2 は不変。"""
    ja = _page("privacy.html"); en = _page("en/privacy.html")
    assert ja.count("β版の利用期限（利用条件 第3条）を判定するため") == 1
    assert "にのみ保存する場合があります。この情報は外部へ送信せず、9-3 の利用状況の記録にも含めません。利用者を識別するためのものではありません。" in ja
    assert en.count("To determine the Beta's period of use (Section 3 of the Terms of Use)") == 1
    assert "only on your PC" in en and "is not sent anywhere and is not included in the usage records described in 9-3. It is not used to identify you." in en
    assert "上記以外の外部通信（アクセス解析、広告、第三者の計測サービス）は組み込んでいません。" in ja   # 9-2 不変


@pytest.mark.parametrize("key", [JA_KEY, EN_KEY])
def test_product_page_discloses_expiry_and_beta_1_01(rendered: dict[str, str], key: str) -> None:
    html = rendered[key]
    if key == JA_KEY:
        assert "Sidekick Planner β1.01（1.0.0-beta.2）" in html
        assert "終了予定日を過ぎると、β版（β1.01 以降）は起動できなくなります" in html
        assert "延長する場合は新しいβ版を配布します" in html
        assert "β1.00" not in html.split("<main>", 1)[1]
    else:
        assert "Sidekick Planner Beta 1.01 (1.0.0-beta.2)" in html
        assert "After the planned end date, the beta (beta 1.01 and later) can no longer be started." in html
        assert "an extension is delivered as a new beta version" in html
        assert "1.00" not in html.split("<main>", 1)[1]


def test_dl_planner_discloses_expiry_and_beta_1_01() -> None:
    source = (REPO_ROOT / "dl-planner.html").read_text(encoding="utf-8")
    body = source.split("<body>", 1)[1].split("<script>", 1)[0]
    assert "<dt>利用期限</dt>" in body
    assert "2026年10月31日（日本時間）まで。期限を過ぎると、このβ版は起動できなくなります" in body
    assert "Sidekick Planner β1.01（1.0.0-beta.2）" in body
    assert "β1.00" not in body


def test_changelog_has_the_beta_1_01_release_entry_ja_en() -> None:
    ja = _page("changelog.html"); en = _page("en/changelog.html")
    assert "Sidekick Planner β1.01 を公開しました — β版に利用期限を導入" in ja
    assert "すでに配布した β1.00 には利用期限の仕組みは含まれていませんが、利用条件上の提供期間は同じです" in ja
    assert "Sidekick Planner Beta 1.01 released — the beta now has an expiry date" in en
    assert "Beta 1.00 copies already distributed do not contain the expiry mechanism, but the beta period in the Terms of Use is the same" in en
