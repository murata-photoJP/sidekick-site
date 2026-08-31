"""build/story/build_story.py の動作確認テスト。

原則としてtempfile上の独自contentディレクトリ・出力先で完結し、本番の
content/story・story/・en/story/には触れない（末尾の
test_production_story_html_matches_template だけは本番HTMLを読むが、読むだけで
書き込まない。development-logの同名テストと同じ位置づけ）。
テンプレートは実際のtemplates/story（およびheader.html/footer.html再利用元の
templates/knowledge）を使う（本番テンプレート自体の検証も兼ねる）。

使い方:
    python -m pytest tests/story -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "story"))
import build_story as bs  # noqa: E402


def write_md(path: Path, front_matter: dict | None = None, body: str | None = None) -> Path:
    fm = {
        "title": "テストStory★日本語",
        "subtitle": "――テスト用のサブタイトル",
        "order": 1,
        "date": "2026-08-31",
        "status": "published",
        "summary": "テスト用の要約文。",
    }
    if front_matter:
        fm.update(front_matter)
    lines = ["---"]
    for k, v in fm.items():
        if v is None:
            continue
        if k == "related_links":
            lines.append("related_links:")
            for item in v:
                lines.append(f'  - label: "{item["label"]}"')
                lines.append(f'    url: "{item["url"]}"')
        elif isinstance(v, int):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f'{k}: "{v}"')
    lines.append("---")
    text = "\n".join(lines) + "\n\n" + (body or "## 見出し\n\n本文です。\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def h1_count(html: str) -> int:
    return len(re.findall(r"<h1[ >]", html))


# ---------------------------------------------------------------------------
# 基本ビルド
# ---------------------------------------------------------------------------

def test_basic_build_produces_index_and_article(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "first.md", {"slug": "first"})

    entries, warnings = bs.load_entries(content)
    rendered = bs.render_all(entries)

    assert warnings == []
    assert Path("index.html") in rendered
    assert Path("first.html") in rendered
    assert "テストStory★日本語" in rendered[Path("first.html")]


def test_subtitle_is_rendered_separately_from_title(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "first.md", {"slug": "first"})
    entries, _ = bs.load_entries(content)
    html = bs.render_all(entries)[Path("first.html")]

    assert "kzc-story-subtitle" in html
    assert "――テスト用のサブタイトル" in html


def test_article_page_has_exactly_one_h1(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "first.md", {"slug": "first"},
             body="# 本文のタイトル\n\n## 見出し\n\n本文です。\n")
    entries, _ = bs.load_entries(content)
    rendered = bs.render_all(entries)

    assert h1_count(rendered[Path("first.html")]) == 1
    assert h1_count(rendered[Path("index.html")]) == 1


def test_leading_h1_in_body_is_stripped(tmp_path: Path) -> None:
    """本文冒頭の#見出しはArticle HeaderのH1と重複するため取り除かれる。"""
    content = tmp_path / "content"
    write_md(content / "first.md", {"slug": "first"},
             body="# 重複するタイトル\n\n本文です。\n")
    entries, _ = bs.load_entries(content)
    html = bs.render_all(entries)[Path("first.html")]

    assert "<h1" in html
    assert html.count("重複するタイトル") == 0


# ---------------------------------------------------------------------------
# 公開可否
# ---------------------------------------------------------------------------

def test_draft_status_excluded(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "draft.md", {"slug": "draft", "status": "draft"})
    entries, warnings = bs.load_entries(content)

    assert entries == []
    assert any("status" in w for w in warnings)


def test_missing_required_field_is_skipped(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "no-order.md", {"slug": "no-order", "order": None})
    entries, warnings = bs.load_entries(content)

    assert entries == []
    assert any("order" in w for w in warnings)


def test_non_integer_order_is_skipped(tmp_path: Path) -> None:
    content = tmp_path / "content"
    path = write_md(content / "bad.md", {"slug": "bad"})
    path.write_text(path.read_text(encoding="utf-8").replace("order: 1", 'order: "いち"'),
                    encoding="utf-8")
    entries, warnings = bs.load_entries(content)

    assert entries == []
    assert any("order" in w for w in warnings)


def test_duplicate_slug_stops_the_whole_build(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "same", "order": 1})
    write_md(content / "b.md", {"slug": "same", "order": 2})

    with pytest.raises(bs.BuildError, match="slugが重複"):
        bs.load_entries(content)


def test_duplicate_order_stops_the_whole_build(tmp_path: Path) -> None:
    """読む順序が意味を持つコンテンツなので、orderの重複は警告ではなく停止扱いにする。"""
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a", "order": 1})
    write_md(content / "b.md", {"slug": "b", "order": 1})

    with pytest.raises(bs.BuildError, match="orderが重複"):
        bs.load_entries(content)


# ---------------------------------------------------------------------------
# 並び順（開発日誌との最大の違い）
# ---------------------------------------------------------------------------

def test_entries_are_sorted_by_order_ascending_not_by_date(tmp_path: Path) -> None:
    content = tmp_path / "content"
    # 日付は order と逆順にしておく。dateで並べていたら検出できる。
    write_md(content / "c.md", {"slug": "c", "order": 3, "date": "2026-01-01"})
    write_md(content / "a.md", {"slug": "a", "order": 1, "date": "2026-03-01"})
    write_md(content / "b.md", {"slug": "b", "order": 2, "date": "2026-02-01"})

    entries, _ = bs.load_entries(content)
    assert [e["slug"] for e in entries] == ["a", "b", "c"]


def test_index_lists_entries_in_reading_order(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a", "order": 1, "title": "最初の話"})
    write_md(content / "b.md", {"slug": "b", "order": 2, "title": "次の話"})

    entries, _ = bs.load_entries(content)
    index = bs.render_all(entries)[Path("index.html")]
    assert index.index("最初の話") < index.index("次の話")


def test_prev_and_next_links_follow_order(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a", "order": 1, "title": "1本目"})
    write_md(content / "b.md", {"slug": "b", "order": 2, "title": "2本目"})
    write_md(content / "c.md", {"slug": "c", "order": 3, "title": "3本目"})

    entries, _ = bs.load_entries(content)
    rendered = bs.render_all(entries)

    middle = rendered[Path("b.html")]
    assert "/story/a" in middle
    assert "/story/c" in middle

    first = rendered[Path("a.html")]
    assert "前の話" not in first
    last = rendered[Path("c.html")]
    assert "次の話" not in last


# ---------------------------------------------------------------------------
# シリーズ（前後編）
# ---------------------------------------------------------------------------

def test_series_pair_links_to_each_other(tmp_path: Path) -> None:
    content = tmp_path / "content"
    series = {"series": "道具を作るということ", "series_total": 2}
    write_md(content / "part1.md",
             dict(series, slug="part1", order=1, series_part=1, title="前編タイトル"))
    write_md(content / "part2.md",
             dict(series, slug="part2", order=2, series_part=2, title="後編タイトル"))

    entries, _ = bs.load_entries(content)
    rendered = bs.render_all(entries)

    assert "前編" in rendered[Path("part1.html")]
    assert "後編タイトル" in rendered[Path("part1.html")]
    assert "後編" in rendered[Path("part2.html")]
    assert "前編タイトル" in rendered[Path("part2.html")]


def test_series_badge_appears_on_index_cards(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "part1.md", {"slug": "part1", "order": 1,
                                    "series": "道具を作るということ",
                                    "series_part": 1, "series_total": 2})
    entries, _ = bs.load_entries(content)
    index = bs.render_all(entries)[Path("index.html")]

    assert "道具を作るということ" in index
    assert "前編" in index


def test_non_series_entry_has_no_series_markup(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "solo.md", {"slug": "solo"})
    entries, _ = bs.load_entries(content)
    html = bs.render_all(entries)[Path("solo.html")]

    assert "kzc-story-series" not in html


# ---------------------------------------------------------------------------
# 記事末尾の導線
# ---------------------------------------------------------------------------

def test_related_links_are_rendered(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {
        "slug": "a",
        "related_links": [{"label": "Sidekick Star", "url": "/sidekick-star"}],
    })
    entries, _ = bs.load_entries(content)
    html = bs.render_all(entries)[Path("a.html")]

    assert "この話につながる現在のSidekick" in html
    assert 'href="/sidekick-star"' in html


def test_related_link_with_external_url_is_rejected(tmp_path: Path) -> None:
    """本文外の導線に外部リンクを紛れ込ませない（サイト内のルート相対パスのみ許可）。"""
    content = tmp_path / "content"
    write_md(content / "a.md", {
        "slug": "a",
        "related_links": [{"label": "どこか", "url": "https://example.com/"}],
    })
    entries, warnings = bs.load_entries(content)

    assert entries == []
    assert any("ルート相対パス" in w for w in warnings)


# ---------------------------------------------------------------------------
# JA/EN 対応付け
# ---------------------------------------------------------------------------

def test_hreflang_is_reciprocal_for_translated_pair(tmp_path: Path) -> None:
    ja = tmp_path / "ja"
    en = tmp_path / "en"
    write_md(ja / "a.md", {"slug": "a"})
    write_md(en / "a.md", {"slug": "a", "source_slug": "a", "title": "EN title"})

    ja_entries, _ = bs.load_entries(ja, language="ja")
    en_entries, _ = bs.load_entries(en, language="en")
    hreflang = bs.compute_hreflang_by_slug(ja_entries, en_entries)

    assert hreflang["a"]["ja"] == "https://www.sidekick-lab.com/story/a"
    assert hreflang["a"]["en"] == "https://www.sidekick-lab.com/en/story/a"

    rendered_ja = bs.render_all(ja_entries, language="ja", hreflang_by_slug=hreflang)
    html = rendered_ja[Path("a.html")]
    assert 'hreflang="ja"' in html
    assert 'hreflang="en"' in html


def test_untranslated_entry_gets_no_hreflang(tmp_path: Path) -> None:
    """存在しないURLを出力しない（打ち出の小槌・開発日誌と同じ方針）。"""
    ja = tmp_path / "ja"
    en = tmp_path / "en"
    write_md(ja / "a.md", {"slug": "a"})
    write_md(ja / "b.md", {"slug": "b", "order": 2})
    write_md(en / "a.md", {"slug": "a", "source_slug": "a", "title": "EN title"})

    ja_entries, _ = bs.load_entries(ja, language="ja")
    en_entries, _ = bs.load_entries(en, language="en")
    hreflang = bs.compute_hreflang_by_slug(ja_entries, en_entries)

    assert "b" not in hreflang
    html = bs.render_all(ja_entries, language="ja", hreflang_by_slug=hreflang)[Path("b.html")]
    assert "hreflang=" not in html


def test_lang_switch_falls_back_to_top_when_untranslated(tmp_path: Path) -> None:
    ja = tmp_path / "ja"
    write_md(ja / "b.md", {"slug": "b"})
    ja_entries, _ = bs.load_entries(ja, language="ja")
    url = bs.compute_lang_switch_url(ja_entries[0], "ja", {})
    assert url == "/en/story"


def test_en_directory_is_excluded_from_ja_load(tmp_path: Path) -> None:
    """content/story/en/ をJA読み込み時に拾わない（slug衝突を起こさない）。"""
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a"})
    write_md(content / "en" / "a.md", {"slug": "a", "source_slug": "a"})

    entries, _ = bs.load_entries(content, language="ja")
    assert [e["slug"] for e in entries] == ["a"]


def test_english_date_format(tmp_path: Path) -> None:
    en = tmp_path / "en"
    write_md(en / "a.md", {"slug": "a", "date": "2026-08-31"})
    entries, _ = bs.load_entries(en, language="en")
    assert entries[0]["date_display"] == "August 31, 2026"


def test_japanese_date_format(tmp_path: Path) -> None:
    ja = tmp_path / "ja"
    write_md(ja / "a.md", {"slug": "a", "date": "2026-08-31"})
    entries, _ = bs.load_entries(ja, language="ja")
    assert entries[0]["date_display"] == "2026年8月31日"


# ---------------------------------------------------------------------------
# 警告（生成は止めない）
# ---------------------------------------------------------------------------

def test_heading_skip_is_warned(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a"}, body="## h2\n\n#### h4\n\n本文。\n")
    _, warnings = bs.load_entries(content)
    assert any("見出し階層が飛んでいます" in w for w in warnings)


def test_h1_in_body_after_the_first_is_warned(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a"}, body="## h2\n\n# 途中のh1\n\n本文。\n")
    _, warnings = bs.load_entries(content)
    assert any("本文にh1があります" in w for w in warnings)


def test_local_image_path_is_warned(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a"},
             body="## h2\n\n![説明](./local.jpg)\n")
    _, warnings = bs.load_entries(content)
    assert any("Web上の絶対パスではありません" in w for w in warnings)


def test_empty_alt_is_warned(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a"},
             body="## h2\n\n![](/images/x.jpg)\n")
    _, warnings = bs.load_entries(content)
    assert any("alt属性が空です" in w for w in warnings)


# ---------------------------------------------------------------------------
# 書き込み（atomic・古いHTMLの削除）
# ---------------------------------------------------------------------------

def test_stage_and_commit_writes_all_pages(tmp_path: Path) -> None:
    content = tmp_path / "content"
    output = tmp_path / "out"
    write_md(content / "a.md", {"slug": "a"})
    entries, _ = bs.load_entries(content)
    rendered = bs.render_all(entries)

    bs.stage_and_commit(rendered, output)

    assert (output / "index.html").exists()
    assert (output / "a.html").exists()
    assert not list(output.parent.glob(".build-staging-story-*"))


def test_unpublished_article_html_is_removed(tmp_path: Path) -> None:
    content = tmp_path / "content"
    output = tmp_path / "out"
    write_md(content / "a.md", {"slug": "a"})
    write_md(content / "b.md", {"slug": "b", "order": 2})

    entries, _ = bs.load_entries(content)
    bs.stage_and_commit(bs.render_all(entries), output)
    assert (output / "b.html").exists()

    (content / "b.md").unlink()
    entries, _ = bs.load_entries(content)
    removed = bs.stage_and_commit(bs.render_all(entries), output)

    assert not (output / "b.html").exists()
    assert [p.name for p in removed] == ["b.html"]


def test_japanese_space_and_parenthesis_in_path(tmp_path: Path) -> None:
    """Windowsの日本語・空白・括弧を含むパスでも動く（devlogの同種テストと同じ理由）。"""
    content = tmp_path / "自作 (Beta)" / "content"
    output = tmp_path / "自作 (Beta)" / "out"
    write_md(content / "a.md", {"slug": "a"})

    entries, _ = bs.load_entries(content)
    bs.stage_and_commit(bs.render_all(entries), output)
    assert (output / "a.html").exists()


# ---------------------------------------------------------------------------
# メタデータ
# ---------------------------------------------------------------------------

def test_canonical_and_meta_description(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a", "summary": "この記事の要約。"})
    entries, _ = bs.load_entries(content)
    html = bs.render_all(entries)[Path("a.html")]

    assert '<link rel="canonical" href="https://www.sidekick-lab.com/story/a">' in html
    assert 'name="description" content="この記事の要約。"' in html


def test_meta_description_falls_back_to_body_excerpt(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a", "summary": None},
             body="## 見出し\n\nこれは本文の冒頭です。\n")
    entries, _ = bs.load_entries(content)
    html = bs.render_all(entries)[Path("a.html")]

    assert 'name="description" content=""' not in html
    assert "これは本文の冒頭です。" in html


def test_index_top_hreflang_only_when_en_is_built(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a"})
    entries, _ = bs.load_entries(content)

    without = bs.render_all(entries)[Path("index.html")]
    withen = bs.render_all(entries, include_top_hreflang=True)[Path("index.html")]

    assert "hreflang=" not in without
    assert 'hreflang="en"' in withen


def test_nav_marks_story_as_current(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "a.md", {"slug": "a"})
    entries, _ = bs.load_entries(content)
    rendered = bs.render_all(entries)

    for rel in (Path("a.html"), Path("index.html")):
        assert '<a href="/story" aria-current="page"' in rendered[rel]


def test_english_pages_use_english_header_and_footer(tmp_path: Path) -> None:
    en = tmp_path / "en"
    write_md(en / "a.md", {"slug": "a", "title": "EN title"})
    entries, _ = bs.load_entries(en, language="en")
    html = bs.render_all(entries, language="en")[Path("a.html")]

    assert '<html lang="en">' in html
    assert 'href="/en/development-log"' in html
    assert "About the Author" in html


# ---------------------------------------------------------------------------
# テンプレート ↔ 本番HTML（DEPLOY_CHECKLIST 1.）
# ---------------------------------------------------------------------------

def _normalize_html_story(text: str) -> str:
    """BOM と CRLF を正規化（内容の差ではない）。"""
    return text.lstrip("﻿").replace("\r\n", "\n")


def test_production_story_html_matches_template() -> None:
    """本番のStoryページについて、テンプレートレンダリング結果 == 本番HTMLを検証する。

    失敗した場合は build_story.py を再実行して再ビルドすること
    （docs/DEPLOY_CHECKLIST.md「1. テンプレート↔本番HTML の差分チェック」）。
    """
    content_dir = REPO_ROOT / "content" / "story"
    content_en_dir = content_dir / "en"

    if not content_dir.exists():
        pytest.skip("content/story が存在しない")

    ja_entries, _ = bs.load_entries(content_dir, language="ja")
    en_entries: list = []
    if content_en_dir.exists():
        en_entries, _ = bs.load_entries(content_en_dir, language="en")

    hreflang = bs.compute_hreflang_by_slug(ja_entries, en_entries)
    rendered_ja = bs.render_all(ja_entries, language="ja",
                                hreflang_by_slug=hreflang, include_top_hreflang=True)
    rendered_en = bs.render_all(en_entries, language="en",
                                hreflang_by_slug=hreflang, include_top_hreflang=True)

    failures: list[str] = []
    for rendered, prod_dir, label in (
        (rendered_ja, REPO_ROOT / "story", "story"),
        (rendered_en, REPO_ROOT / "en" / "story", "en/story"),
    ):
        for rel_path, built_html in rendered.items():
            prod_path = prod_dir / rel_path
            if not prod_path.exists():
                failures.append(f"  {label}/{rel_path}: 本番HTMLが存在しない")
                continue
            prod = _normalize_html_story(prod_path.read_text(encoding="utf-8-sig"))
            built = _normalize_html_story(built_html)
            if prod != built:
                failures.append(
                    f"  {label}/{rel_path}: 差分あり"
                    f" (本番={len(prod.splitlines())}行,"
                    f" テンプレート={len(built.splitlines())}行)"
                )

    assert not failures, "テンプレートと本番HTMLに差分があります:\n" + "\n".join(failures)
