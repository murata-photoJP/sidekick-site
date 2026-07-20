#!/usr/bin/env python3
"""build/knowledge/generate_knowledge_sitemap.py の動作確認テスト。

すべて tempfile 上の独自インデックス・独自sitemap.xmlで完結し、本番の
sitemap.xml・data/knowledge/web-published.json には一切触れない。

使い方:
    python tests/knowledge/test_generate_knowledge_sitemap.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "knowledge"))
import generate_knowledge_sitemap as gks  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"))


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        _safe_print(f"PASS: {name}")
    else:
        FAIL.append(name)
        _safe_print(f"FAIL: {name} {detail}")


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

def sample_article(**overrides) -> dict:
    art = {
        "id": "SKB-TEST-000001", "language": "ja",
        "public_url": "/knowledge/photoshop/sample-article",
        "updated_at": "2026-07-18", "published_at": "2026-07-17", "created_at": "2026-07-16",
    }
    art.update(overrides)
    return art


def make_index(tmp_path: Path, articles: list[dict], *, schema_version: int = 1) -> Path:
    path = tmp_path / "web-published.json"
    path.write_text(
        json.dumps({"schema_version": schema_version, "articles": articles}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


MINIMAL_SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    "  <url>\n"
    "    <loc>https://www.sidekick-lab.com/</loc>\n"
    "    <lastmod>2026-06-21</lastmod>\n"
    "    <priority>1.0</priority>\n"
    "  </url>\n"
    "</urlset>\n"
)


def make_sitemap(tmp_path: Path, text: str = MINIMAL_SITEMAP) -> Path:
    path = tmp_path / "sitemap.xml"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# テスト本体
# ---------------------------------------------------------------------------

def test_build_knowledge_urls_ja_only() -> None:
    entries = gks.build_knowledge_urls([sample_article()])
    locs = [e["loc"] for e in entries]
    check("URL抽出: 記事URLが含まれる",
          "https://www.sidekick-lab.com/knowledge/photoshop/sample-article" in locs, locs)
    check("URL抽出: JAトップページが含まれる",
          "https://www.sidekick-lab.com/knowledge" in locs, locs)
    check("URL抽出: ENトップページは含まれない(EN記事が無いため)",
          "https://www.sidekick-lab.com/en/knowledge" not in locs, locs)
    check("URL抽出: 件数は記事1+トップ1=2件", len(entries) == 2, entries)


def test_build_knowledge_urls_ja_and_en() -> None:
    articles = [
        sample_article(),
        sample_article(id="SKB-TEST-000002", language="en", public_url="/en/knowledge/photoshop/sample-article"),
    ]
    entries = gks.build_knowledge_urls(articles)
    locs = [e["loc"] for e in entries]
    check("JA+EN: ENトップページも含まれる",
          "https://www.sidekick-lab.com/en/knowledge" in locs, locs)
    check("JA+EN: 件数は記事2+トップ2=4件", len(entries) == 4, entries)


def test_build_knowledge_urls_lastmod_fallback() -> None:
    art = sample_article(updated_at=None, published_at="2026-07-01")
    entries = gks.build_knowledge_urls([art])
    article_entry = next(e for e in entries if "sample-article" in e["loc"])
    check("lastmod: updated_at欠落時はpublished_atへフォールバック",
          article_entry["lastmod"] == "2026-07-01", article_entry)


def test_build_knowledge_urls_missing_public_url_skipped() -> None:
    art = sample_article(public_url=None)
    entries = gks.build_knowledge_urls([art])
    check("public_url欠落: 記事は含まれない(トップページも含まれない、言語未検出扱い)",
          entries == [], entries)


def test_merge_into_sitemap_inserts_before_urlset_close() -> None:
    entries = gks.build_knowledge_urls([sample_article()])
    block = gks.render_url_block(entries)
    merged = gks.merge_into_sitemap(MINIMAL_SITEMAP, block)
    check("新規挿入: マーカーが含まれる", gks.MARKER_BEGIN in merged and gks.MARKER_END in merged)
    check("新規挿入: 既存の非Knowledge項目が保持される",
          "https://www.sidekick-lab.com/</loc>" in merged)
    check("新規挿入: </urlset>の直前に挿入される", merged.rstrip().endswith("</urlset>"))


def test_merge_into_sitemap_idempotent_replace() -> None:
    entries = gks.build_knowledge_urls([sample_article()])
    block = gks.render_url_block(entries)
    once = gks.merge_into_sitemap(MINIMAL_SITEMAP, block)
    twice = gks.merge_into_sitemap(once, block)
    check("冪等性: 2回適用してもマーカーは1組だけ", twice.count(gks.MARKER_BEGIN) == 1, twice.count(gks.MARKER_BEGIN))
    check("冪等性: 2回目適用後の内容が1回目と同一", once == twice)


def test_merge_into_sitemap_replaces_stale_entries() -> None:
    """記事が公開停止された場合など、以前のマーカー範囲の内容が新しい内容で
    完全に置き換わり、古いURLが残らないことを確認する。"""
    old_entries = gks.build_knowledge_urls([sample_article(id="SKB-TEST-OLD", public_url="/knowledge/old-article")])
    old_block = gks.render_url_block(old_entries)
    with_old = gks.merge_into_sitemap(MINIMAL_SITEMAP, old_block)

    new_entries = gks.build_knowledge_urls([sample_article()])
    new_block = gks.render_url_block(new_entries)
    updated = gks.merge_into_sitemap(with_old, new_block)

    check("差し替え: 古いURLが残らない", "old-article" not in updated, updated)
    check("差し替え: 新しいURLが含まれる", "sample-article" in updated, updated)


def test_generate_writes_file_and_preserves_existing_entries() -> None:
    with tempfile.TemporaryDirectory(prefix="gks_test_") as tmp:
        tmp_path = Path(tmp)
        index_path = make_index(tmp_path, [sample_article()])
        sitemap_path = make_sitemap(tmp_path)

        result = gks.generate(index_path, sitemap_path, dry_run=False)
        check("generate: knowledge_url_count=2", result["knowledge_url_count"] == 2, result)
        check("generate: changed=True", result["changed"] is True)

        text = sitemap_path.read_text(encoding="utf-8")
        check("generate: 既存の非Knowledge項目が保持される", "sidekick-lab.com/</loc>" in text)
        check("generate: Knowledge記事URLが書き込まれる", "sample-article" in text)


def test_generate_dry_run_no_side_effects() -> None:
    with tempfile.TemporaryDirectory(prefix="gks_test_") as tmp:
        tmp_path = Path(tmp)
        index_path = make_index(tmp_path, [sample_article()])
        sitemap_path = make_sitemap(tmp_path)
        text_before = sitemap_path.read_text(encoding="utf-8")

        result = gks.generate(index_path, sitemap_path, dry_run=True)
        check("dry-run: dry_run=Trueが返る", result["dry_run"] is True)
        check("dry-run: ファイルが変更されない", sitemap_path.read_text(encoding="utf-8") == text_before)


def test_generate_missing_index_raises() -> None:
    with tempfile.TemporaryDirectory(prefix="gks_test_") as tmp:
        tmp_path = Path(tmp)
        sitemap_path = make_sitemap(tmp_path)
        try:
            gks.generate(tmp_path / "does-not-exist.json", sitemap_path, dry_run=True)
            check("index不在: SitemapErrorが発生する", False, "例外が発生しなかった")
        except gks.SitemapError:
            check("index不在: SitemapErrorが発生する", True)


def test_generate_unsupported_schema_version_raises() -> None:
    with tempfile.TemporaryDirectory(prefix="gks_test_") as tmp:
        tmp_path = Path(tmp)
        index_path = make_index(tmp_path, [sample_article()], schema_version=999)
        sitemap_path = make_sitemap(tmp_path)
        try:
            gks.generate(index_path, sitemap_path, dry_run=True)
            check("schema_version不正: SitemapErrorが発生する", False, "例外が発生しなかった")
        except gks.SitemapError:
            check("schema_version不正: SitemapErrorが発生する", True)


def test_generate_missing_sitemap_bootstraps_minimal_file() -> None:
    with tempfile.TemporaryDirectory(prefix="gks_test_") as tmp:
        tmp_path = Path(tmp)
        index_path = make_index(tmp_path, [sample_article()])
        sitemap_path = tmp_path / "sitemap.xml"  # 作成しない

        result = gks.generate(index_path, sitemap_path, dry_run=False)
        check("sitemap不在: 新規作成される", sitemap_path.exists())
        text = sitemap_path.read_text(encoding="utf-8")
        check("sitemap不在: urlsetタグを含む最小限のXMLになる", "<urlset" in text and "</urlset>" in text)
        check("sitemap不在: Knowledge URLが含まれる", "sample-article" in text)


def test_generate_no_articles_produces_empty_block_no_crash() -> None:
    with tempfile.TemporaryDirectory(prefix="gks_test_") as tmp:
        tmp_path = Path(tmp)
        index_path = make_index(tmp_path, [])
        sitemap_path = make_sitemap(tmp_path)
        result = gks.generate(index_path, sitemap_path, dry_run=False)
        check("記事0件: knowledge_url_count=0", result["knowledge_url_count"] == 0, result)
        text = sitemap_path.read_text(encoding="utf-8")
        check("記事0件: 既存の非Knowledge項目は保持される", "sidekick-lab.com/</loc>" in text)


def main() -> int:
    tests = [
        test_build_knowledge_urls_ja_only,
        test_build_knowledge_urls_ja_and_en,
        test_build_knowledge_urls_lastmod_fallback,
        test_build_knowledge_urls_missing_public_url_skipped,
        test_merge_into_sitemap_inserts_before_urlset_close,
        test_merge_into_sitemap_idempotent_replace,
        test_merge_into_sitemap_replaces_stale_entries,
        test_generate_writes_file_and_preserves_existing_entries,
        test_generate_dry_run_no_side_effects,
        test_generate_missing_index_raises,
        test_generate_unsupported_schema_version_raises,
        test_generate_missing_sitemap_bootstraps_minimal_file,
        test_generate_no_articles_produces_empty_block_no_crash,
    ]
    for t in tests:
        t()

    _safe_print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
