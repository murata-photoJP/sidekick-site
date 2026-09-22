"""デプロイ時に効く2つの「手書きの一覧」が実体とずれていないことを固定する。2026-09-01新設。

**きっかけとなった問題**

どちらも同じ壊れ方をした。「リポジトリ側が増えたのに、手書きの一覧が追随せず放置された」。

1. `sitemap.xml` の site系ページ部分にはジェネレータが無い。EN全ページを一括登録した
   コミット（2026-07-14）の時点で `/en/legal`・`/en/privacy` はまだ存在せず、
   後から追加したコミット（2026-07-25）が sitemap に触れなかったため、
   38日間 sitemap から漏れていた。JA側の `/legal`・`/privacy` は載っており、
   両者は相互 hreflang を持つ対だったので、非対称は意図ではなく追随漏れだった。

2. `docs/DEPLOY_CHECKLIST.md` の「pytest の実行範囲」に書かれたスイート一覧と件数が
   古かった（318件と書かれたまま実測399件）。件数は Unit ごとに増えるため確定値を
   文書へ書かない方針へ変更したが、**スイート一覧**は残す必要があるので、
   一覧と実体の一致だけをここで固定する。

**この2つを1ファイルにまとめている理由**

対象（sitemap / 文書）は違うが、防いでいる失敗は同じ「手書き一覧の追随漏れ」であり、
どちらもデプロイ直前に効く。別々のファイルに分けると、次に同種の一覧が増えたときに
置き場所が分からなくなる。

**リポジトリを読むだけで、何も書き込まない。**

使い方:
    python -m pytest tests/site/test_deploy_policy.py -q
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SITEMAP = REPO_ROOT / "sitemap.xml"
CHECKLIST = REPO_ROOT / "docs" / "DEPLOY_CHECKLIST.md"
ORIGIN = "https://www.sidekick-lab.com"

CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')
HREFLANG_RE = re.compile(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"')
ROBOTS_RE = re.compile(r'<meta name="robots" content="([^"]+)"')

# sitemapへ載せない導線ページ。単独の機能ページで対になる言語版を持たないため、
# 下の4条件（3. 対の言語版がある）を満たさない。docs/DEPLOY_CHECKLIST.md「2-2.」参照。
TRANSACTIONAL = {
    "buy-portrait.html", "buy-sky.html", "buy-star.html",
    "dl-ai.html", "dl-portrait.html", "dl-sky.html", "dl-star.html",
    "register-dl.html", "thanks.html", "thanks-portrait.html", "thanks-sky.html",
}

# 写真実践塾（photo-kouza.com）の講座を紹介する単独LP。日本語限定で対になる
# 言語版が無いため4条件では掲載可否が決まらない。2026-09-01に村田さんが
# 「独立した検索Landingとしてindexさせる（C-1）」と決定した。
# 根拠と、noindex・canonical統合を採らなかった理由は
# docs/DEPLOY_CHECKLIST.md「2-2.」の「単独LP（star-lp / kouzu-lp）の扱い」にある。
STANDALONE_LP = {"star-lp.html", "kouzu-lp.html"}

# 設計上noindexにするページ。`/share`はQR・共有リンクから開く道具ページで、
# fragment（`#`以降）が無いと「共有された撮影計画が見つかりません」しか表示しない。
# 検索から入る導線が無く、索引されても空の器が検索結果へ出るだけになる。
# なお撮影計画そのものはfragmentにしか無く、fragmentはサーバーへ送られないため、
# 共有された撮影計画がそもそも索引されることはない。
# 2026-09-06、QR Share V1 Web Viewer（Planner側 AI-0373 が生成）の本番配置で追加。
# 根拠は docs/DEPLOY_CHECKLIST.md「2-2.」の「Snapshot Viewer（/share）の扱い」にある。
NOINDEX_BY_DESIGN = {"share.html"}


def _production_pages() -> list[Path]:
    """本番へ配置されるHTML。ビルドの一時出力・バックアップ・テンプレートは除く。"""
    pages = []
    for p in sorted(REPO_ROOT.rglob("*.html")):
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(("build-output/", "BackUp/", "templates/")):
            continue
        if "sidekick_manual_package" in rel or p.name.startswith("google"):
            continue
        pages.append(p)
    return pages


def _public_url(rel: str) -> str:
    """本番URL。vercel.jsonが cleanUrls:true・trailingSlash:false のため拡張子を落とし、
    ディレクトリの index.html はディレクトリ自身のURLになる。"""
    slug = rel[:-len(".html")]
    if slug == "index":
        return f"{ORIGIN}/"
    if slug.endswith("/index"):
        slug = slug[: -len("/index")]
    return f"{ORIGIN}/{slug}"


def _sitemap_text() -> str:
    return SITEMAP.read_text(encoding="utf-8-sig")


def _sitemap_locs() -> list[str]:
    return re.findall(r"<loc>\s*(.*?)\s*</loc>", _sitemap_text())


PRODUCTION_PAGES = _production_pages()
SITEMAP_LOCS = _sitemap_locs()
SITEMAP_SET = set(SITEMAP_LOCS)


def _meta(p: Path) -> dict:
    t = p.read_text(encoding="utf-8-sig", errors="replace")
    m = CANONICAL_RE.search(t)
    r = ROBOTS_RE.search(t)
    return {
        "canonical": m.group(1) if m else None,
        "hreflang": dict(HREFLANG_RE.findall(t)),
        "robots": r.group(1) if r else None,
    }


# ---------------------------------------------------------------------------
# sitemap.xml そのものの健全性
# ---------------------------------------------------------------------------

def test_sitemap_is_well_formed_xml() -> None:
    """sitemap.xml がXMLとして壊れていないこと（手書き部分があるため毎回確認する）。"""
    ET.parse(SITEMAP)


def test_sitemap_has_no_duplicate_url() -> None:
    """同じURLが2回載っていないこと。"""
    dup = sorted({u for u in SITEMAP_LOCS if SITEMAP_LOCS.count(u) > 1})
    assert not dup, f"sitemapにURLの重複がある: {dup}"


def test_sitemap_urls_use_the_canonical_form() -> None:
    """全URLが www あり・拡張子なしであること。

    apex（wwwなし）と `.html` 付きはどちらも vercel.json のリダイレクト対象で、
    sitemapへ書くとリダイレクトURLを申告することになる。
    """
    bad = [u for u in SITEMAP_LOCS if not u.startswith(ORIGIN) or u.endswith(".html")]
    assert not bad, f"リダイレクトされる形式のURLがsitemapにある: {bad}"


def test_every_sitemap_url_has_a_production_file() -> None:
    """sitemapの全URLに対応する本番HTMLが存在すること（死んだURLを申告しない）。"""
    have = {_public_url(p.relative_to(REPO_ROOT).as_posix()) for p in PRODUCTION_PAGES}
    missing = sorted(set(SITEMAP_LOCS) - have)
    assert not missing, f"対応する本番HTMLが無いURLがsitemapにある: {missing}"


# ---------------------------------------------------------------------------
# 掲載条件（docs/DEPLOY_CHECKLIST.md「2-2.」の4条件）
# ---------------------------------------------------------------------------

def test_indexable_language_pairs_are_all_in_the_sitemap() -> None:
    """self-canonical・noindexなし・相互hreflangを持つページは、sitemapへ載っていること。

    `/en/legal`・`/en/privacy` が JA側だけ載って EN側が漏れていた再発を防ぐ。
    導線ページ（buy-*/dl-*/thanks*/register-dl）は対の言語版を持たないため対象外。
    """
    missing = []
    for p in PRODUCTION_PAGES:
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel in TRANSACTIONAL:
            continue
        m = _meta(p)
        url = _public_url(rel)
        if not m["canonical"] or m["robots"] or len(m["hreflang"]) < 2:
            continue
        if url not in SITEMAP_SET:
            missing.append(f"{rel} -> {url}")
    assert not missing, (
        "index可能で相互hreflangを持つのにsitemapへ載っていないページ:\n  "
        + "\n  ".join(missing)
    )


def test_language_pairs_are_listed_symmetrically() -> None:
    """相互hreflangを持つ対は、JA/ENの両方がsitemapへ載っているか両方載っていないこと。"""
    asym = []
    for p in PRODUCTION_PAGES:
        m = _meta(p)
        if len(m["hreflang"]) < 2:
            continue
        listed = {lang: (href in SITEMAP_SET) for lang, href in m["hreflang"].items()}
        if len(set(listed.values())) > 1:
            rel = p.relative_to(REPO_ROOT).as_posix()
            asym.append(f"{rel}: {listed}")
    assert not asym, "JA/ENでsitemap掲載が非対称な対がある:\n  " + "\n  ".join(sorted(set(asym)))


@pytest.mark.parametrize("url", [
    f"{ORIGIN}/legal", f"{ORIGIN}/en/legal",
    f"{ORIGIN}/privacy", f"{ORIGIN}/en/privacy",
    f"{ORIGIN}/terms", f"{ORIGIN}/en/terms",
])
def test_legal_pages_are_listed_in_both_languages(url: str) -> None:
    """法務3ページがJA/ENとも載っていること（今回の修正対象を名指しで固定する）。"""
    assert url in SITEMAP_SET, f"{url} がsitemapに無い"


@pytest.mark.parametrize("rel", sorted(STANDALONE_LP))
def test_standalone_lp_has_self_canonical(rel: str) -> None:
    """単独LPが自分自身を指すcanonicalを持つこと（C-1決定）。

    他ページへ統合するcanonicalを入れてしまわないよう、値まで固定する。
    """
    p = REPO_ROOT / rel
    m = _meta(p)
    expected = _public_url(rel)
    assert m["canonical"] == expected, (
        f"{rel}: canonical={m['canonical']}（期待は self canonical の {expected}）"
    )


@pytest.mark.parametrize("rel", sorted(STANDALONE_LP))
def test_standalone_lp_og_url_matches_canonical(rel: str) -> None:
    """単独LPの og:url が canonical と同じ正規URLであること。

    もとは `https://sidekick-lab.com/{slug}.html` を指しており、apex（vercel.jsonで
    wwwへ301）と `.html`（cleanUrlsで301）の二重にリダイレクトされる形式だった。
    build_site.py の生成ページは og:url に canonical をそのまま流用している。
    """
    t = (REPO_ROOT / rel).read_text(encoding="utf-8-sig")
    m = re.search(r'<meta property="og:url" content="([^"]+)"', t)
    assert m, f"{rel}: og:url が無い"
    assert m.group(1) == _public_url(rel), f"{rel}: og:url={m.group(1)}"


@pytest.mark.parametrize("rel", sorted(STANDALONE_LP))
def test_standalone_lp_is_in_the_sitemap(rel: str) -> None:
    """単独LPがsitemapへ載っていること（indexさせる方針の裏づけ）。"""
    url = _public_url(rel)
    assert url in SITEMAP_SET, f"{url} がsitemapに無い"


def test_no_production_page_declares_noindex() -> None:
    """noindex指定が入ったら気付けるようにする。

    2026-09-01時点で `<meta name="robots">` を持つ本番ページは1つも無い。
    候補だったstar-lp/kouzu-lpも、同日の決定でnoindexではなくindex（C-1）になった。
    noindexを使い始めるのは方針判断なので、黙って増えないよう固定する。
    増やすときはこのテストと docs/DEPLOY_CHECKLIST.md「2-2.」を同時に更新すること。

    2026-09-06、`/share`（Snapshot Viewer）を NOINDEX_BY_DESIGN として明示的に許可した。
    許可は名指しの1件だけで、それ以外は従来どおり0件で固定している。
    """
    declared = []
    for p in PRODUCTION_PAGES:
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel in NOINDEX_BY_DESIGN:
            continue
        r = _meta(p)["robots"]
        if r:
            declared.append(f"{rel}: {r}")
    assert not declared, "meta robots を持つページが増えている:\n  " + "\n  ".join(declared)


@pytest.mark.parametrize("rel", sorted(NOINDEX_BY_DESIGN))
def test_noindex_by_design_pages_keep_their_noindex(rel: str) -> None:
    """設計上noindexにしたページが、黙ってindex可能へ戻らないこと。

    上のテストを例外つきにした以上、例外側も固定しないと「noindexが外れたのに
    誰も気付かない」という逆向きの見落としが生まれる。両方向を固定する。
    """
    p = REPO_ROOT / rel
    assert p.exists(), f"{rel} が存在しない"
    robots = _meta(p)["robots"]
    assert robots and "noindex" in robots, f"{rel}: robots={robots}（noindexが外れている）"


# ---------------------------------------------------------------------------
# docs/DEPLOY_CHECKLIST.md のスイート一覧
# ---------------------------------------------------------------------------

def test_deploy_checklist_lists_every_test_suite() -> None:
    """DEPLOY_CHECKLISTのスイート一覧が `tests/` の実体と一致すること。

    スイートを追加・改名したのに文書を直し忘れると、デプロイ前に一部のテストが
    実行されないまま「全部通した」と報告されうる。
    """
    actual = {
        d.name for d in (REPO_ROOT / "tests").iterdir()
        if d.is_dir() and d.name != "__pycache__" and any(d.glob("test_*.py"))
    }
    documented = set(re.findall(r"^- `tests/([A-Za-z0-9_-]+)`$", CHECKLIST.read_text(encoding="utf-8-sig"), re.M))
    assert documented == actual, (
        f"DEPLOY_CHECKLISTのスイート一覧={sorted(documented)} / 実体={sorted(actual)}"
    )


def test_deploy_checklist_does_not_fix_a_total_test_count() -> None:
    """合計件数を確定値として書き戻していないこと。

    件数はUnitごとに増えるため、確定値として書くと必ず陳腐化する
    （実際に318件のまま実測399件まで放置された）。参考値であることが分かる形
    （「参考値」と明記する）でのみ数字を書いてよい。
    """
    text = CHECKLIST.read_text(encoding="utf-8-sig")
    section = text.split("## 2. pytest の実行範囲", 1)[1].split("\n## ", 1)[0]
    assert "参考値" in section, "件数を参考値と明示する記述が失われている"
    bad = [ln.strip() for ln in section.splitlines()
           if re.search(r"pytest tests -q.*は\s*\d+件", ln)]
    assert not bad, f"合計件数が確定値として書かれている: {bad}"


# ---------------------------------------------------------------------------
# GA4（gtag.js）の配置ポリシー（2026-09-22新設）
# ---------------------------------------------------------------------------
#
# **きっかけとなった問題**
#
# GA4タグは 2026-06-06（a80e497）に当時の手書きHTML 20ファイルへ個別に貼られた。
# その後に Jinja2 テンプレートとして新設した打ち出の小槌（2026-07-17）・開発日誌・Story・
# tools/dof・ichiro-murata には貼られず、本番で配信されていた 98 ページ（全体の 2/3）が
# GA4「ページとスクリーン」に一切記録されていなかった。2026-09-21、村田さんが
# 「記事を開くとリアルタイムには出るのに、30日レポートで記事URLが0件」という形で発見した
# （リアルタイムに出ていたのは同セッションの別ページのイベント）。
#
# 上の sitemap / DEPLOY_CHECKLIST と同じ「増えた実体に手書き（貼付）が追随しなかった」失敗なので、
# ここで固定する。**GA4導入以前の /knowledge/ 等のPVは「0」ではなく「未計測（UNKNOWN / NOT
# MEASURED）」として扱う。** 導入日と計測境界は docs/ANALYTICS_GA4.md にある。
#
# 方針
# - 本番HTMLは share.html（設計上 analytics なし）を除き、全ページが gtag.js を **ちょうど1回** 持つ。
# - Measurement ID は G-K73T3Y352W の1つだけ。別IDが混ざったら気付けるようにする
#   （firebase-init.js の measurementId G-SBJEMRYFZQ は Firebase 設定であり、
#   getAnalytics を呼んでいないので HTML には現れない。HTML に現れたら混入）。
# - テンプレート側でも固定する：knowledge / development-log / story の base.html と
#   site 系の全ページテンプレートが、共用パーシャル `components/ga4.html` を include するか
#   同等のスニペットを直書きしていること。本番HTMLの検査だけだと「再ビルドするまで気付かない」
#   （この文書の「背景」と同じ構造）ので、テンプレートも見る。

GA4_MEASUREMENT_ID = "G-K73T3Y352W"
GA4_PARTIAL = REPO_ROOT / "templates" / "knowledge" / "components" / "ga4.html"
GA4_INCLUDE = 'include "components/ga4.html"'

GA4_LOADER_RE = re.compile(r'googletagmanager\.com/gtag/js\?id=(G-[A-Z0-9]+)')
GA4_CONFIG_RE = re.compile(r"gtag\('config',\s*'(G-[A-Z0-9]+)'")

# 設計上 analytics を持たないページ。`/share` は QR・共有リンクから開く道具ページで、
# 「外部スクリプト・外部CSS・外部フォント・外部画像・analytics をいずれも持たない単一の静的HTML」
# であることが Planner 側のテストで固定されている（docs/DEPLOY_CHECKLIST.md「Snapshot Viewer
# （/share）の扱い」）。noindex と同じく、名指しの1件だけを許可する。
NO_ANALYTICS_BY_DESIGN = {"share.html"}

# テンプレートから生成する4系統のうち、base.html に GA4 を置く3系統。
# site 系は各ページテンプレートが extra_head に置く（既存の手書き移行ページはスニペット直書き、
# 2026-09-22 に追加した tools/dof・ichiro-murata はパーシャル include）ため、下の
# test_every_site_page_template_carries_ga4 で全ページテンプレートを見る。
GA4_BASE_TEMPLATES = [
    Path("templates", "knowledge", "base.html"),
    Path("templates", "development-log", "base.html"),
    Path("templates", "story", "base.html"),
]


def _ga4_ids(text: str) -> tuple[list[str], list[str]]:
    """(gtag.js ローダーのID一覧, gtag('config') のID一覧)。"""
    return GA4_LOADER_RE.findall(text), GA4_CONFIG_RE.findall(text)


def test_ga4_partial_defines_the_measurement_id_exactly_once() -> None:
    """共用パーシャルが、ローダーと config の両方で意図したIDをちょうど1回ずつ持つこと。"""
    assert GA4_PARTIAL.exists(), f"{GA4_PARTIAL.relative_to(REPO_ROOT).as_posix()} が無い"
    loader, config = _ga4_ids(GA4_PARTIAL.read_text(encoding="utf-8-sig"))
    assert loader == [GA4_MEASUREMENT_ID], f"loader={loader}"
    assert config == [GA4_MEASUREMENT_ID], f"config={config}"


def test_every_production_page_has_exactly_one_ga4_tag() -> None:
    """share.html を除く全本番HTMLが gtag.js ローダーと gtag('config') をちょうど1回ずつ持つこと。

    0回＝計測されない（今回の再発防止の本体）。2回以上＝page_view が二重に送られる
    （base.html と個別ページの両方に置いた場合に起きる）。どちらも失敗にする。
    """
    bad = []
    for p in PRODUCTION_PAGES:
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel in NO_ANALYTICS_BY_DESIGN:
            continue
        loader, config = _ga4_ids(p.read_text(encoding="utf-8-sig", errors="replace"))
        if len(loader) != 1 or len(config) != 1:
            bad.append(f"{rel}: loader={len(loader)} config={len(config)}")
    assert not bad, (
        "GA4タグが無い、または重複している本番ページ:\n  " + "\n  ".join(bad)
    )


def test_production_pages_use_only_the_intended_measurement_id() -> None:
    """本番HTMLに現れる Measurement ID が G-K73T3Y352W だけであること。"""
    found = {}
    for p in PRODUCTION_PAGES:
        rel = p.relative_to(REPO_ROOT).as_posix()
        loader, config = _ga4_ids(p.read_text(encoding="utf-8-sig", errors="replace"))
        for mid in loader + config:
            if mid != GA4_MEASUREMENT_ID:
                found.setdefault(mid, []).append(rel)
    assert not found, f"意図しない Measurement ID が本番HTMLにある: {found}"


@pytest.mark.parametrize("rel", sorted(NO_ANALYTICS_BY_DESIGN))
def test_no_analytics_by_design_pages_stay_free_of_analytics(rel: str) -> None:
    """設計上 analytics を持たないページに、黙って GA4 / Clarity が入らないこと（逆向きの固定）。"""
    p = REPO_ROOT / rel
    assert p.exists(), f"{rel} が存在しない"
    t = p.read_text(encoding="utf-8-sig", errors="replace")
    hits = [s for s in ("googletagmanager", "gtag(", "clarity.ms") if s in t]
    assert not hits, f"{rel}: analytics が混入している: {hits}"


@pytest.mark.parametrize("rel", [t.as_posix() for t in GA4_BASE_TEMPLATES])
def test_template_family_base_includes_ga4(rel: str) -> None:
    """knowledge / development-log / story の base.html が共用パーシャルを include していること。

    本番HTMLの検査（上）だけだと、テンプレートから include を外しても次の再ビルドまで
    気付かない。テンプレート側も固定する。
    """
    t = (REPO_ROOT / rel).read_text(encoding="utf-8-sig")
    assert t.count(GA4_INCLUDE) == 1, f"{rel}: {GA4_INCLUDE} が {t.count(GA4_INCLUDE)} 回（期待は1回）"


def test_every_site_page_template_carries_ga4() -> None:
    """site 系の全ページテンプレートが GA4（include または直書き）をちょうど1回持つこと。

    site 系は base.html に GA4 を置いていない（手書き移行ページが各自 extra_head に持つため、
    base に置くと二重になる）。新しいページテンプレートを追加したときに漏れないよう、
    ページテンプレート全件をここで見る。
    """
    bad = []
    for p in sorted((REPO_ROOT / "templates" / "site" / "pages").rglob("*.html")):
        rel = p.relative_to(REPO_ROOT).as_posix()
        t = p.read_text(encoding="utf-8-sig")
        n = t.count(GA4_INCLUDE) + len(GA4_CONFIG_RE.findall(t))
        if n != 1:
            bad.append(f"{rel}: {n}")
    assert not bad, "GA4 が無い／重複している site ページテンプレート:\n  " + "\n  ".join(bad)
