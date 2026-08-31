"""Story の JA/EN 公開漏れを防ぐ Gate。2026-08-31新設。

「日本語版だけ公開された」「英語版だけ公開された」という状態を、デプロイ前に
機械的に検出するためのテスト。村田さんの要件（Storyについては JA only / EN only の
公開漏れを防ぎたい）に対応する。

**本番の生成物と content/story/ を読むだけで、何も書き込まない。**

Story が増えても追加作業なしで効くよう、記事の一覧は content/story/ から動的に
読む（テスト側にファイル名・slugを列挙しない）。同じ考え方を Planner のような
JA/EN 対のページにも適用できるよう、ページ対の検証は PAGE_PAIRS で表にしている。

使い方:
    python -m pytest tests/story/test_ja_en_parity.py -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "story"))
import build_story as bs  # noqa: E402

SITE_ORIGIN = "https://www.sidekick-lab.com"
CONTENT_JA = REPO_ROOT / "content" / "story"
CONTENT_EN = CONTENT_JA / "en"
OUT_JA = REPO_ROOT / "story"
OUT_EN = REPO_ROOT / "en" / "story"
SITEMAP = REPO_ROOT / "sitemap.xml"

# Story以外にも、今回の公開単位でJA/ENが対になっているべきページ。
# 今後この種のページが増えたら、ここへ1行足せば同じ検証が効く。
PAGE_PAIRS = [
    ("planner.html", "en/planner.html", "/planner", "/en/planner"),
]

CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)">')
HREFLANG_RE = re.compile(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">')
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
DESC_RE = re.compile(r'<meta name="description" content="(.*?)">', re.DOTALL)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _entries():
    ja, _ = bs.load_entries(CONTENT_JA, language="ja")
    en, _ = bs.load_entries(CONTENT_EN, language="en") if CONTENT_EN.exists() else ([], [])
    return ja, en


pytestmark = pytest.mark.skipif(not CONTENT_JA.exists(), reason="content/story が存在しない")


# ---------------------------------------------------------------------------
# 1. JA/EN ペアの欠落 = 0
# ---------------------------------------------------------------------------

def test_every_japanese_story_has_an_english_counterpart() -> None:
    ja, en = _entries()
    en_sources = {e["source_slug"] for e in en if e.get("source_slug")}
    missing = sorted(e["slug"] for e in ja if e["slug"] not in en_sources)
    assert not missing, f"英語版が無い日本語Story: {missing}"


def test_every_english_story_points_at_an_existing_japanese_story() -> None:
    ja, en = _entries()
    ja_slugs = {e["slug"] for e in ja}
    orphans = sorted(
        e["slug"] for e in en
        if not e.get("source_slug") or e["source_slug"] not in ja_slugs
    )
    assert not orphans, f"対応する日本語Storyが無い英語Story: {orphans}"


def test_reading_order_matches_between_languages() -> None:
    """orderがJA/ENでずれていると、一覧の並びと前後リンクが言語ごとに変わってしまう。"""
    ja, en = _entries()
    en_by_source = {e["source_slug"]: e for e in en if e.get("source_slug")}
    mismatched = [
        (j["slug"], j["order"], en_by_source[j["slug"]]["order"])
        for j in ja
        if j["slug"] in en_by_source and en_by_source[j["slug"]]["order"] != j["order"]
    ]
    assert not mismatched, f"orderがJA/ENで一致しないStory: {mismatched}"


def test_series_relationship_matches_between_languages() -> None:
    ja, en = _entries()
    en_by_source = {e["source_slug"]: e for e in en if e.get("source_slug")}
    mismatched = []
    for j in ja:
        e = en_by_source.get(j["slug"])
        if e is None:
            continue
        if bool(j["series"]) != bool(e["series"]):
            mismatched.append((j["slug"], "seriesの有無"))
        elif j["series"] and (j["series_part"], j["series_total"]) != (e["series_part"], e["series_total"]):
            mismatched.append((j["slug"], "series_part/series_total"))
    assert not mismatched, f"前後編の関係がJA/ENで一致しないStory: {mismatched}"


# ---------------------------------------------------------------------------
# 2. 生成物（HTML）が両言語に存在する
# ---------------------------------------------------------------------------

def test_generated_html_exists_for_both_languages() -> None:
    ja, en = _entries()
    missing = []
    for e in ja:
        if not (OUT_JA / f"{e['slug']}.html").exists():
            missing.append(f"story/{e['slug']}.html")
    for e in en:
        if not (OUT_EN / f"{e['slug']}.html").exists():
            missing.append(f"en/story/{e['slug']}.html")
    for top in (OUT_JA / "index.html", OUT_EN / "index.html"):
        if not top.exists():
            missing.append(str(top.relative_to(REPO_ROOT)))
    assert not missing, f"生成されていないHTML: {missing}"


# ---------------------------------------------------------------------------
# 3. canonical
# ---------------------------------------------------------------------------

def test_canonical_is_self_referencing_and_language_correct() -> None:
    ja, en = _entries()
    problems = []
    checks = [(OUT_JA, "/story", ja), (OUT_EN, "/en/story", en)]
    for out_dir, prefix, entries in checks:
        expected_top = f"{SITE_ORIGIN}{prefix}"
        m = CANONICAL_RE.search(_read(out_dir / "index.html"))
        if not m or m.group(1) != expected_top:
            problems.append(f"{prefix}: canonical={m.group(1) if m else None}")
        for e in entries:
            html = _read(out_dir / f"{e['slug']}.html")
            m = CANONICAL_RE.search(html)
            expected = f"{SITE_ORIGIN}{prefix}/{e['slug']}"
            if not m or m.group(1) != expected:
                problems.append(f"{prefix}/{e['slug']}: canonical={m.group(1) if m else None}")
    assert not problems, "canonicalが不正:\n" + "\n".join(problems)


# ---------------------------------------------------------------------------
# 4. hreflang が相互参照になっている
# ---------------------------------------------------------------------------

def test_hreflang_is_reciprocal() -> None:
    """片方向のhreflangはGoogleに無視されうる。JA→EN・EN→JAの両方を確認する。"""
    ja, en = _entries()
    en_by_source = {e["source_slug"]: e for e in en if e.get("source_slug")}
    problems = []

    for j in ja:
        e = en_by_source.get(j["slug"])
        if e is None:
            continue
        ja_url = f"{SITE_ORIGIN}/story/{j['slug']}"
        en_url = f"{SITE_ORIGIN}/en/story/{e['slug']}"
        for path, label in ((OUT_JA / f"{j['slug']}.html", "ja"),
                            (OUT_EN / f"{e['slug']}.html", "en")):
            found = dict(HREFLANG_RE.findall(_read(path)))
            if found.get("ja") != ja_url or found.get("en") != en_url:
                problems.append(f"{label}:{path.name}: {found}")

    top_expected = {"ja": f"{SITE_ORIGIN}/story", "en": f"{SITE_ORIGIN}/en/story"}
    for path in (OUT_JA / "index.html", OUT_EN / "index.html"):
        if dict(HREFLANG_RE.findall(_read(path))) != top_expected:
            problems.append(f"top:{path}: hreflangが相互参照になっていない")

    assert not problems, "hreflangが相互参照になっていない:\n" + "\n".join(problems)


def test_language_switch_link_points_at_the_other_language() -> None:
    ja, en = _entries()
    en_by_source = {e["source_slug"]: e for e in en if e.get("source_slug")}
    problems = []
    for j in ja:
        e = en_by_source.get(j["slug"])
        if e is None:
            continue
        if f'href="/en/story/{e["slug"]}"' not in _read(OUT_JA / f"{j['slug']}.html"):
            problems.append(f"story/{j['slug']}: EN版への切替リンクが無い")
        if f'href="/story/{j["slug"]}"' not in _read(OUT_EN / f"{e['slug']}.html"):
            problems.append(f"en/story/{e['slug']}: JA版への切替リンクが無い")
    assert not problems, "\n".join(problems)


# ---------------------------------------------------------------------------
# 5. title / description がページ固有で空でない
# ---------------------------------------------------------------------------

def test_title_and_description_are_present_and_unique() -> None:
    pages = sorted(OUT_JA.glob("*.html")) + sorted(OUT_EN.glob("*.html"))
    titles: dict[str, list[str]] = {}
    descs: dict[str, list[str]] = {}
    empty = []
    for p in pages:
        html = _read(p)
        t = TITLE_RE.search(html)
        d = DESC_RE.search(html)
        rel = str(p.relative_to(REPO_ROOT))
        if not t or not t.group(1).strip():
            empty.append(f"{rel}: titleが空")
        else:
            titles.setdefault(t.group(1).strip(), []).append(rel)
        if not d or not d.group(1).strip():
            empty.append(f"{rel}: meta descriptionが空")
        else:
            descs.setdefault(d.group(1).strip(), []).append(rel)

    assert not empty, "\n".join(empty)
    dup_t = {k: v for k, v in titles.items() if len(v) > 1}
    dup_d = {k: v for k, v in descs.items() if len(v) > 1}
    assert not dup_t, f"titleが重複しているページ: {dup_t}"
    assert not dup_d, f"meta descriptionが重複しているページ: {dup_d}"


# ---------------------------------------------------------------------------
# 6. sitemap に両言語が載っている
# ---------------------------------------------------------------------------

def test_sitemap_contains_both_languages() -> None:
    text = _read(SITEMAP)
    ja, en = _entries()
    missing = []
    for url in [f"{SITE_ORIGIN}/story", f"{SITE_ORIGIN}/en/story"]:
        if f"<loc>{url}</loc>" not in text:
            missing.append(url)
    for e in ja:
        url = f"{SITE_ORIGIN}/story/{e['slug']}"
        if f"<loc>{url}</loc>" not in text:
            missing.append(url)
    for e in en:
        url = f"{SITE_ORIGIN}/en/story/{e['slug']}"
        if f"<loc>{url}</loc>" not in text:
            missing.append(url)
    assert not missing, f"sitemap.xmlに無いURL: {missing}"


# ---------------------------------------------------------------------------
# 7. サイト内リンク切れ（Storyから出るリンク）
# ---------------------------------------------------------------------------

def _resolve(url: str) -> Path | None:
    """ルート相対URLを、cleanUrls:true 前提で実ファイルへ解決する。"""
    path = url.split("#")[0].split("?")[0]
    if path.endswith("/"):
        path = path[:-1]
    if not path:
        return REPO_ROOT / "index.html"
    candidate = REPO_ROOT / path.lstrip("/")
    if candidate.is_dir():
        return candidate / "index.html"
    if candidate.suffix:
        return candidate
    return candidate.with_suffix(".html")


def test_internal_links_from_story_pages_resolve() -> None:
    broken = []
    for p in sorted(OUT_JA.glob("*.html")) + sorted(OUT_EN.glob("*.html")):
        html = _read(p)
        for url in set(re.findall(r'href="(/[^"#?][^"]*)"', html)):
            target = _resolve(url)
            if target is None or not target.exists():
                broken.append(f"{p.relative_to(REPO_ROOT)} -> {url}")
    assert not broken, "リンク切れ:\n" + "\n".join(sorted(broken))


# ---------------------------------------------------------------------------
# 8. Story以外のJA/EN対ページ（Planner等）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ja_file,en_file,ja_url,en_url", PAGE_PAIRS)
def test_paired_page_exists_in_both_languages(ja_file, en_file, ja_url, en_url) -> None:
    for f in (ja_file, en_file):
        assert (REPO_ROOT / f).exists(), f"{f} が生成されていない"


@pytest.mark.parametrize("ja_file,en_file,ja_url,en_url", PAGE_PAIRS)
def test_paired_page_canonical_and_hreflang(ja_file, en_file, ja_url, en_url) -> None:
    expected = {"ja": SITE_ORIGIN + ja_url, "en": SITE_ORIGIN + en_url}
    for f, url in ((ja_file, ja_url), (en_file, en_url)):
        html = _read(REPO_ROOT / f)
        m = CANONICAL_RE.search(html)
        assert m and m.group(1) == SITE_ORIGIN + url, f"{f}: canonicalが不正"
        assert dict(HREFLANG_RE.findall(html)) == expected, f"{f}: hreflangが相互参照でない"


@pytest.mark.parametrize("ja_file,en_file,ja_url,en_url", PAGE_PAIRS)
def test_paired_page_in_sitemap(ja_file, en_file, ja_url, en_url) -> None:
    text = _read(SITEMAP)
    for url in (ja_url, en_url):
        assert f"<loc>{SITE_ORIGIN}{url}</loc>" in text, f"{url} がsitemap.xmlに無い"


# ---------------------------------------------------------------------------
# 9. Story 5 ⇄ Planner の相互導線
# ---------------------------------------------------------------------------

def test_planner_story_cross_links_exist() -> None:
    """Storyを読んだ人がPlannerへ、Plannerを見た人がStoryへ行けること。"""
    problems = []
    pairs = [
        (OUT_JA / "when-and-where-should-i-go.html", "/planner"),
        (OUT_EN / "when-and-where-should-i-go.html", "/en/planner"),
        (REPO_ROOT / "planner.html", "/story/when-and-where-should-i-go"),
        (REPO_ROOT / "en" / "planner.html", "/en/story/when-and-where-should-i-go"),
    ]
    for path, expected_href in pairs:
        if not path.exists():
            problems.append(f"{path} が存在しない")
        elif f'href="{expected_href}"' not in _read(path):
            problems.append(f"{path.relative_to(REPO_ROOT)} -> {expected_href} のリンクが無い")
    assert not problems, "\n".join(problems)


def test_planner_page_states_it_is_in_development() -> None:
    """完成製品として見せないための最低限の保証（村田さんの明示要件）。"""
    assert "現在開発中" in _read(REPO_ROOT / "planner.html")
    assert "In development" in _read(REPO_ROOT / "en" / "planner.html")


# ---------------------------------------------------------------------------
# 10. グローバルナビにStoryが両言語で載っている
# ---------------------------------------------------------------------------

def test_story_is_in_global_navigation_in_both_languages() -> None:
    assert '<a href="/story"' in _read(REPO_ROOT / "index.html")
    assert '<a href="/en/story"' in _read(REPO_ROOT / "en" / "index.html")
