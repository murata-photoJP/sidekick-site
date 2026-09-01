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
    """
    declared = []
    for p in PRODUCTION_PAGES:
        r = _meta(p)["robots"]
        if r:
            declared.append(f"{p.relative_to(REPO_ROOT).as_posix()}: {r}")
    assert not declared, "meta robots を持つページが増えている:\n  " + "\n  ".join(declared)


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
