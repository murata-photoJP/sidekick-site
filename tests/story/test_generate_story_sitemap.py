"""build/story/generate_story_sitemap.py の動作確認テスト。

すべてtempfile上の独自content・sitemapで完結し、本番のcontent/story・sitemap.xmlには
一切触れない（開発日誌のtest_generate_development_log_sitemap.pyと同じ方針）。

使い方:
    python -m pytest tests/story/test_generate_story_sitemap.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "story"))
import generate_story_sitemap as gss  # noqa: E402

MINIMAL_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.sidekick-lab.com/</loc>
    <priority>1.0</priority>
  </url>
</urlset>
"""


def write_md(path: Path, slug: str, *, status: str = "published",
             date: str = "2026-08-31", order: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "t"\nslug: {slug}\norder: {order}\n'
        f'date: "{date}"\nstatus: "{status}"\n---\n\n本文。\n',
        encoding="utf-8",
    )
    return path


def make_sitemap(tmp_path: Path, text: str = MINIMAL_SITEMAP) -> Path:
    p = tmp_path / "sitemap.xml"
    p.write_text(text, encoding="utf-8")
    return p


def test_adds_story_urls_with_marker_block(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", "a")
    sitemap = make_sitemap(tmp_path)

    result = gss.generate(content, sitemap)

    text = sitemap.read_text(encoding="utf-8")
    assert gss.MARKER_BEGIN in text and gss.MARKER_END in text
    assert "<loc>https://www.sidekick-lab.com/story/a</loc>" in text
    assert "<loc>https://www.sidekick-lab.com/story</loc>" in text
    assert result["url_count"] == 2
    assert result["changed"] is True


def test_english_urls_are_added_when_requested(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", "a")
    write_md(content / "en" / "a.md", "a")
    sitemap = make_sitemap(tmp_path)

    gss.generate(content, sitemap, content_en_dir=content / "en")

    text = sitemap.read_text(encoding="utf-8")
    assert "<loc>https://www.sidekick-lab.com/story/a</loc>" in text
    assert "<loc>https://www.sidekick-lab.com/en/story/a</loc>" in text


def test_en_directory_is_excluded_from_japanese_urls(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", "a")
    write_md(content / "en" / "a.md", "a")
    sitemap = make_sitemap(tmp_path)

    gss.generate(content, sitemap)

    text = sitemap.read_text(encoding="utf-8")
    assert text.count("<loc>https://www.sidekick-lab.com/story/a</loc>") == 1
    assert "/en/story/" not in text


def test_draft_is_not_added(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", "a", status="draft")
    sitemap = make_sitemap(tmp_path)

    result = gss.generate(content, sitemap)

    assert result["url_count"] == 0
    assert "/story/a" not in sitemap.read_text(encoding="utf-8")


def test_manual_entries_outside_the_marker_are_untouched(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", "a")
    sitemap = make_sitemap(tmp_path)

    gss.generate(content, sitemap)

    text = sitemap.read_text(encoding="utf-8")
    assert "<loc>https://www.sidekick-lab.com/</loc>" in text
    assert "<priority>1.0</priority>" in text


def test_rerun_replaces_the_block_rather_than_appending(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", "a")
    sitemap = make_sitemap(tmp_path)

    gss.generate(content, sitemap)
    (content / "a.md").unlink()
    write_md(content / "b.md", "b")
    gss.generate(content, sitemap)

    text = sitemap.read_text(encoding="utf-8")
    assert text.count(gss.MARKER_BEGIN) == 1
    assert "/story/b" in text
    assert "/story/a" not in text


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", "a")
    sitemap = make_sitemap(tmp_path)
    before = sitemap.read_text(encoding="utf-8")

    result = gss.generate(content, sitemap, dry_run=True)

    assert result["dry_run"] is True
    assert result["changed"] is True
    assert sitemap.read_text(encoding="utf-8") == before


def test_missing_sitemap_raises(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", "a")

    with pytest.raises(gss.SitemapError, match="sitemap.xmlが見つかりません"):
        gss.generate(content, tmp_path / "nope.xml")


def test_broken_sitemap_raises_without_writing(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", "a")
    sitemap = make_sitemap(tmp_path, "<xml>no urlset</xml>")

    with pytest.raises(gss.SitemapError, match="urlset"):
        gss.generate(content, sitemap)
    assert sitemap.read_text(encoding="utf-8") == "<xml>no urlset</xml>"


def test_story_priority_is_above_development_log() -> None:
    """Storyは開発日誌（0.5 / 0.4）より上に置く、という意図をテストで固定する。"""
    assert float(gss.TOP_PRIORITY) > 0.5
    assert float(gss.ARTICLE_PRIORITY) > 0.4


def test_japanese_space_and_parenthesis_in_path(tmp_path: Path) -> None:
    content = tmp_path / "自作 (Beta)" / "content"
    write_md(content / "a.md", "a")
    sitemap = make_sitemap(tmp_path)

    gss.generate(content, sitemap)
    assert "/story/a" in sitemap.read_text(encoding="utf-8")
