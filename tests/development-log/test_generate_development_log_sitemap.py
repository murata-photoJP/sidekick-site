"""build/development-log/generate_development_log_sitemap.py の動作確認テスト。

すべてtempfile上の独自content・独自sitemap.xmlで完結し、本番のsitemap.xml・
content/development-logには一切触れない。

使い方:
    python -m pytest tests/development-log/test_generate_development_log_sitemap.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "development-log"))
import generate_development_log_sitemap as gdls  # noqa: E402

MINIMAL_SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    "  <url>\n    <loc>https://www.sidekick-lab.com/</loc>\n  </url>\n"
    "</urlset>\n"
)


def write_md(path: Path, status: str = "published", date: str = "2026-07-18") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "テスト"\ndate: "{date}"\nstatus: "{status}"\n---\n\n本文\n',
        encoding="utf-8",
    )


def test_published_article_url_included(tmp_path: Path) -> None:
    content = tmp_path / "content"
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(MINIMAL_SITEMAP, encoding="utf-8")
    write_md(content / "2026" / "07" / "2026-07-18.md")

    result = gdls.generate(content, sitemap)

    text = sitemap.read_text(encoding="utf-8")
    assert "https://www.sidekick-lab.com/development-log/2026-07-18" in text
    assert "https://www.sidekick-lab.com/development-log</loc>" in text
    assert result["url_count"] == 2  # 記事1件 + トップページ


def test_draft_article_excluded_from_sitemap(tmp_path: Path) -> None:
    content = tmp_path / "content"
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(MINIMAL_SITEMAP, encoding="utf-8")
    write_md(content / "2026" / "07" / "2026-07-19.md", status="draft")

    gdls.generate(content, sitemap)

    text = sitemap.read_text(encoding="utf-8")
    assert "2026-07-19" not in text


def test_no_articles_produces_no_top_page_url(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir(parents=True)
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(MINIMAL_SITEMAP, encoding="utf-8")

    gdls.generate(content, sitemap)

    text = sitemap.read_text(encoding="utf-8")
    assert "/development-log" not in text


def test_rerun_is_idempotent_no_duplicate(tmp_path: Path) -> None:
    content = tmp_path / "content"
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(MINIMAL_SITEMAP, encoding="utf-8")
    write_md(content / "2026" / "07" / "2026-07-18.md")

    gdls.generate(content, sitemap)
    gdls.generate(content, sitemap)

    text = sitemap.read_text(encoding="utf-8")
    assert text.count("BEGIN AUTO-GENERATED DEVELOPMENT LOG URLS") == 1
    assert text.count("<loc>https://www.sidekick-lab.com/development-log/2026-07-18</loc>") == 1


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    content = tmp_path / "content"
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(MINIMAL_SITEMAP, encoding="utf-8")
    write_md(content / "2026" / "07" / "2026-07-18.md")

    before = sitemap.read_text(encoding="utf-8")
    gdls.generate(content, sitemap, dry_run=True)
    after = sitemap.read_text(encoding="utf-8")

    assert before == after


def test_unrelated_manual_entries_untouched(tmp_path: Path) -> None:
    content = tmp_path / "content"
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(MINIMAL_SITEMAP, encoding="utf-8")
    write_md(content / "2026" / "07" / "2026-07-18.md")

    gdls.generate(content, sitemap)

    text = sitemap.read_text(encoding="utf-8")
    assert "https://www.sidekick-lab.com/</loc>" in text


def test_en_urls_included_with_en_prefix(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content_en = tmp_path / "content" / "en"
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(MINIMAL_SITEMAP, encoding="utf-8")
    write_md(content / "2026" / "07" / "2026-07-18.md")
    write_md(content_en / "2026" / "07" / "2026-07-18.md")

    result = gdls.generate(content, sitemap, content_en_dir=content_en)

    text = sitemap.read_text(encoding="utf-8")
    assert "https://www.sidekick-lab.com/en/development-log/2026-07-18" in text
    assert "https://www.sidekick-lab.com/en/development-log</loc>" in text
    assert result["url_count"] == 4  # ja記事+トップ、en記事+トップ


def test_en_subdirectory_excluded_from_ja_pass(tmp_path: Path) -> None:
    content = tmp_path / "content"
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(MINIMAL_SITEMAP, encoding="utf-8")
    write_md(content / "2026" / "07" / "2026-07-18.md")
    write_md(content / "en" / "2026" / "07" / "2026-07-18.md")

    result = gdls.generate(content, sitemap)

    assert result["url_count"] == 2  # 英語版を別途指定していないため、ja記事+トップのみ


def test_missing_sitemap_raises(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md")

    with pytest.raises(gdls.SitemapError):
        gdls.generate(content, tmp_path / "does-not-exist.xml")
