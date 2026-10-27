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
PRODUCT_VERSION = "1.0.0-beta.4"   # β1.03 = 正式RC27（2026-10-27）。β1.02 = 1.0.0-beta.3 = RC15（自作 AI-16567）。β1.01 = 1.0.0-beta.2 / β1.00 = 1.0.0-beta.1 は history

# HD-PLANNERBETA1GENERICSURFACE-009: β1.00 の public surface に出さない語。
# β1.02（HD-PLANNERSHAREV2-034 / -037 で星景・風景が public、Human 指示 2026-10-02）: 星景・天の川・太陽・月・Milky Way・
# starscape は公開する機能の説明に使う。未公開のままの語だけを残す。
CONCEALED_TERMS = ("スキャン",)


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
    assert "2026" in html and ("11月30日" in html or "30 November 2026" in html)  # HD-LR-40 / HD-PLANNERBETAEXPIRYEXTENSION-001
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


def test_four_plan_types_are_described_as_beta_features(rendered: dict[str, str]) -> None:
    """β1.02: パールは「近日対応」ではなくβ機能。撮影計画 4 種（太陽 / パール / 星景 / 風景）を説明する。"""
    ja = rendered[JA_KEY]
    for term in ("パール（月 × 被写体）", "星景（地上の風景と星空の構図）", "風景（撮影地点から太陽・月を探す）", "天の川", "星の軌跡"):
        assert term in ja
    assert "近日対応" not in ja and "計算はまだ始められません" not in ja
    en = rendered[EN_KEY]
    for term in ("Pearl (moon × landmark)", "Starscape", "Landscape", "Milky Way", "Star trails"):
        assert term in en
    assert "coming soon" not in en and "cannot be started yet" not in en


@pytest.mark.parametrize("key", [JA_KEY, EN_KEY])
def test_beta_1_02_screens_and_mode_meanings(rendered: dict[str, str], key: str) -> None:
    """β1.02 Human Review（H-1 / H-3、2026-10-02）: 4 種の名前と意味の対応を導入に列挙し、
    星の軌跡［実在星］の新規画像を載せ、QR 共有の画像は QR＋プレビューの実画面（460×774）。"""
    html = rendered[key]
    assert html.count('src="/images/planner/star-trails-real.jpg" width="1440" height="900"') == 1
    assert 'src="/images/planner/qr-share.png" width="460" height="774"' in html
    if key == JA_KEY:
        for line in ("<strong>太陽</strong>（ダイヤモンド富士・太陽 × 被写体）", "<strong>パール</strong>（月 × 被写体）",
                     "<strong>星景</strong>（地上の風景と星空の構図）", "<strong>風景</strong>（撮影地点から太陽・月を探す）"):
            assert line in html
    else:
        for line in ("<strong>Sun</strong> (Diamond Fuji and sun × landmark)", "<strong>Pearl</strong> (moon × landmark)",
                     "<strong>Starscape</strong> (landscape and starry sky)", "<strong>Landscape</strong> (sun and moon from a shooting point)"):
            assert line in html
    assert "star-landscape-milky-way" not in html   # H-3: 天の川の screenshot は今回採用しない


# ---------------------------------------------------------------------------
# 4. 配布導線が fail-closed
# ---------------------------------------------------------------------------

def test_register_dl_maps_planner_to_dl_planner() -> None:
    source = (REPO_ROOT / "register-dl.html").read_text(encoding="utf-8")
    assert re.search(r"planner:\s*'/dl-planner'", source)
    assert re.search(r"planner:\s*'Sidekick_Planner'", source)
    assert re.search(r"planner:\s*'1\.0\.0-beta\.4'", source), "register-dl の PRODUCT_VERSIONS は release の product_version"
    assert "Sidekick Planner β1.03" in source
    assert (REPO_ROOT / "dl-planner.html").exists()


# β1.01 Release Unit（AI-13050、Human GO 2026-09-21）で確定した distribution package identity（RC14）。
# 正本は Planner 側 manifests/release/distribution_package_Sidekick_Planner_1.0.0-beta.2_c3faa92.identity.json。
# β1.00（Sidekick_Planner_1.0.0-beta.1_bea1697.zip / 93c27bf1…、AI-10850）は R2 に保存したまま配布導線から外した。
# β1.02 release candidate（自作 AI-16567）: RC15 の distribution package identity。正本は Planner 側
# manifests/release/distribution_package_Sidekick_Planner_1.0.0-beta.3_f07d84f.zip.identity.json。β1.01（RC14、a577b809…）は R2 に保存したまま導線から外す。
# β1.03 Web 候補（2026-10-27）: 正式RC27 の distribution package（Sidekick_Planner_1.0.0-beta.4_58f03e7.zip、64d44de4…、R2 upload・public 照合済み）。
# β1.02（RC15、340c2d93…）は R2 に保存したまま導線から外す。
PLANNER_ZIP_URL = "https://pub-123781c638d64762ac2e397ce0e98259.r2.dev/Sidekick_Planner_1.0.0-beta.4_58f03e7.zip"
PLANNER_ZIP_SHA256 = "64d44de4ed54b9860ee1bb747a7be929094fb9dc180b021377fa4988054b9f3a"


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
    assert "Sidekick_Planner_1.0.0-beta.4_58f03e7.zip" in source.split("setAttribute('download'")[1][:80]
    assert "Sidekick_Planner_1.0.0-beta.3_f07d84f.zip" not in source.split("const PLANNER_DOWNLOAD_URL")[1].split(";")[0]
    assert "Sidekick_Planner_1.0.0-beta.2_c3faa92.zip" not in source.split("const PLANNER_DOWNLOAD_URL")[1].split(";")[0]
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
    assert "2026年11月30日</strong>（日本時間。現時点の終了予定日）" in ja   # HD-PLANNERBETAEXPIRYEXTENSION-001
    assert "終了予定日を過ぎると、本β版（β1.01 以降）は起動できなくなり、通常の機能を利用できなくなります。" in ja
    assert "延長後の終了予定日を組み込んだ新しいβ版を配布します" in ja
    assert "このページの告知だけでは変わりません" in ja
    assert "November 30, 2026</strong> (Japan time; the currently planned end date)" in en
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
def test_product_page_discloses_expiry_and_beta_1_02(rendered: dict[str, str], key: str) -> None:
    html = rendered[key]
    if key == JA_KEY:
        assert "Sidekick Planner β1.03（1.0.0-beta.4）" in html
        assert "終了予定日を過ぎると、β版（β1.01 以降）は起動できなくなります" in html
        assert "延長する場合は新しいβ版を配布します" in html
        assert "β1.00" not in html.split("<main>", 1)[1]
    else:
        assert "Sidekick Planner Beta 1.03 (1.0.0-beta.4)" in html
        assert "After the planned end date, the beta (beta 1.01 and later) can no longer be started." in html
        assert "an extension is delivered as a new beta version" in html
        assert "1.00" not in html.split("<main>", 1)[1]


def test_dl_planner_discloses_expiry_and_beta_1_02() -> None:
    source = (REPO_ROOT / "dl-planner.html").read_text(encoding="utf-8")
    body = source.split("<body>", 1)[1].split("<script>", 1)[0]
    assert "<dt>利用期限</dt>" in body
    assert "2026年11月30日（日本時間）まで。期限を過ぎると、このβ版は起動できなくなります" in body
    assert "Sidekick Planner β1.03（1.0.0-beta.4）" in body
    assert "β1.00" not in body


def test_changelog_has_the_beta_1_02_release_entry_ja_en() -> None:
    ja = _page("changelog.html"); en = _page("en/changelog.html")
    assert "Sidekick Planner β1.02 を公開しました — 撮影計画は 4 種類に" in ja
    assert "すでに配布した β1.01 の利用期限（2026年10月31日）は変わりません" in ja
    assert "Sidekick Planner Beta 1.02 released — four plan types" in en
    assert "The expiry of beta 1.01 copies already distributed (31 October 2026) does not change" in en
    assert ja.index("β1.02 を公開しました") < ja.index("β1.01 を公開しました")   # 新しい entry が上


def test_changelog_has_the_beta_1_01_release_entry_ja_en() -> None:
    ja = _page("changelog.html"); en = _page("en/changelog.html")
    assert "Sidekick Planner β1.01 を公開しました — β版に利用期限を導入" in ja
    assert "すでに配布した β1.00 には利用期限の仕組みは含まれていませんが、利用条件上の提供期間は同じです" in ja
    assert "Sidekick Planner Beta 1.01 released — the beta now has an expiry date" in en
    assert "Beta 1.00 copies already distributed do not contain the expiry mechanism, but the beta period in the Terms of Use is the same" in en


def test_beta_1_03_known_issues_and_changelog_ja_en(rendered: dict[str, str]) -> None:
    """β1.03 Web 候補（2026-10-27、Human 承認「既知の問題と2026年11月30日までの試用期限を正確に記載」）:
    製品ページ JA/EN の「β1.03 について」に既知の問題の行、changelog JA/EN に β1.03 の entry（β1.02 より上、期限 11/30）。"""
    ja = rendered[JA_KEY]; en = rendered[EN_KEY]
    assert '<th scope="row">既知の問題</th>' in ja and "日付を正しく入力し直すと再表示されます" in ja
    assert '<th scope="row">Known issues</th>' in en and "It reappears when you enter the date correctly" in en
    cja = _page("changelog.html"); cen = _page("en/changelog.html")
    assert "Sidekick Planner β1.03 を公開しました" in cja
    assert "β1.03 は 2026年11月30日（日本時間）までご利用いただけます" in cja
    assert "Sidekick Planner Beta 1.03 released" in cen
    assert "Beta 1.03 can be used until 30 November 2026 (Japan time)" in cen
    assert cja.index("β1.03 を公開しました") < cja.index("β1.02 を公開しました")   # 新しい entry が上
    assert cen.index("Beta 1.03 released") < cen.index("Beta 1.02 released")


@pytest.mark.parametrize("key,label", [
    ("index", '<div class="hc-name">Sidekick Planner β1.03</div>'),
    ("en/index", '<div class="hc-name">Sidekick Planner Beta 1.03</div>'),
    ("ichiro-murata", '<div class="prod-name">🗺️ Sidekick Planner β1.03</div>'),
    ("en/ichiro-murata", '<div class="prod-name">🗺️ Sidekick Planner Beta 1.03</div>'),
])
def test_product_cards_name_the_current_beta(key: str, label: str) -> None:
    """2026-10-27: β1.03 公開後もトップページと著者ページの製品カードが β1.00 のままだった（Human が本番で確認）。
    版を上げるときは製品ページ・dl-planner と一緒にこのカードも更新する。"""
    (html,) = bs.render_all(key).values()
    assert label in html
    body = re.sub(r"<!--.*?-->", "", html.split("<body", 1)[1], flags=re.S)   # 履歴コメントの β1.00 は対象外
    assert not re.search(r"Sidekick Planner (β|Beta )1\.0[0-2]\b", body)


@pytest.mark.parametrize("key", [JA_KEY, EN_KEY])
def test_head_meta_names_the_current_beta(rendered: dict[str, str], key: str) -> None:
    """meta description に β1.01 が残っていた（2026-10-27 発見）。<head> の版表記は β1.03 だけ。"""
    head = re.sub(r"<!--.*?-->|/\*.*?\*/", "", rendered[key].split("</head>", 1)[0], flags=re.S)
    assert not re.search(r"(β|[Bb]eta )1\.0[0-2]\b", head)
