"""build/development-log/build_development_log.py の動作確認テスト。

すべてtempfile上の独自contentディレクトリ・出力先で完結し、本番の
content/development-log・html/development-logには一切触れない。
テンプレートは実際のtemplates/development-log（およびheader.html/footer.html
再利用元のtemplates/knowledge）を使う（本番テンプレート自体の検証も兼ねる）。

使い方:
    python -m pytest tests/development-log/test_build_development_log.py -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "development-log"))
import build_development_log as bdl  # noqa: E402


def write_md(path: Path, front_matter: dict | None = None, body: str | None = None) -> Path:
    fm = {
        "title": "テスト開発日誌★日本語",
        "date": "2026-07-18",
        "category": "AI Development",
        "status": "published",
        "summary": "テスト用の要約文。",
    }
    if front_matter:
        fm.update(front_matter)
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            items = ", ".join(f'"{i}"' for i in v)
            lines.append(f"{k}: [{items}]")
        else:
            lines.append(f'{k}: "{v}"')
    lines.append("---")
    text = "\n".join(lines) + "\n\n" + (body or "# タイトル\n\n## 見出し\n\n本文です。\n")
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
    output = tmp_path / "out"
    write_md(content / "2026" / "07" / "2026-07-18.md")

    entries, warnings = bdl.load_entries(content)
    rendered = bdl.render_all(entries)

    assert Path("index.html") in rendered
    assert Path("2026-07-18.html") in rendered
    assert "テスト開発日誌★日本語" in rendered[Path("2026-07-18.html")]


def test_draft_status_excluded_defense_in_depth(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-19.md", front_matter={"status": "draft"})

    entries, warnings = bdl.load_entries(content)

    assert len(entries) == 0
    assert any("status" in w for w in warnings)


def test_missing_required_field_skipped_not_fatal(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "broken.md")
    (content / "2026" / "07" / "broken.md").write_text(
        (content / "2026" / "07" / "broken.md").read_text(encoding="utf-8").replace(
            'title: "テスト開発日誌★日本語"\n', ""
        ),
        encoding="utf-8",
    )
    write_md(content / "2026" / "07" / "2026-07-18.md")

    entries, warnings = bdl.load_entries(content)

    assert len(entries) == 1
    assert any("必須項目" in w for w in warnings)


def test_empty_body_skipped(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md", body="   \n")

    entries, warnings = bdl.load_entries(content)

    assert len(entries) == 0
    assert any("本文が空" in w for w in warnings)


# ---------------------------------------------------------------------------
# 並び順・slug重複
# ---------------------------------------------------------------------------

def test_entries_sorted_by_date_descending(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md", front_matter={"date": "2026-07-18"})
    write_md(content / "2026" / "07" / "2026-07-20.md", front_matter={"date": "2026-07-20"})
    write_md(content / "2026" / "07" / "2026-07-19.md", front_matter={"date": "2026-07-19"})

    entries, _ = bdl.load_entries(content)

    assert [e["slug"] for e in entries] == ["2026-07-20", "2026-07-19", "2026-07-18"]


def test_duplicate_slug_raises_build_error(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md")
    write_md(content / "2026" / "08" / "2026-08-01.md", front_matter={"slug": "2026-07-18"})

    with pytest.raises(bdl.BuildError):
        bdl.load_entries(content)


# ---------------------------------------------------------------------------
# Markdownの安全な表示・見出し重複除去
# ---------------------------------------------------------------------------

def test_raw_html_is_escaped(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md", body="本文<script>alert(1)</script>です。\n")

    entries, _ = bdl.load_entries(content)
    rendered = bdl.render_all(entries)
    html = rendered[Path("2026-07-18.html")]

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_leading_h1_in_body_is_stripped_no_duplicate_h1(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md", body="# タイトル\n\n本文です。\n")

    entries, _ = bdl.load_entries(content)
    rendered = bdl.render_all(entries)
    html = rendered[Path("2026-07-18.html")]

    assert h1_count(html) == 1


def test_utf8_no_mojibake(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md")

    entries, _ = bdl.load_entries(content)
    rendered = bdl.render_all(entries)

    assert "テスト開発日誌★日本語" in rendered[Path("2026-07-18.html")]
    assert "縺" not in rendered[Path("2026-07-18.html")]  # 典型的な文字化けパターンが出ていない


# ---------------------------------------------------------------------------
# meta descriptionのフォールバック
# ---------------------------------------------------------------------------

def test_meta_description_uses_summary_when_present(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md", front_matter={"summary": "これが要約です。"})

    entries, _ = bdl.load_entries(content)
    rendered = bdl.render_all(entries)

    assert "これが要約です。" in rendered[Path("2026-07-18.html")]


def test_meta_description_falls_back_to_body_excerpt_when_no_summary(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(
        content / "2026" / "07" / "2026-07-18.md",
        front_matter={"summary": ""},
        body="# タイトル\n\nこれは要約が無い場合に本文から作られる説明文の確認用です。\n",
    )

    entries, _ = bdl.load_entries(content)
    excerpt = bdl.plain_text_excerpt(entries[0]["body_markdown"])

    assert "これは要約が無い場合" in excerpt


# ---------------------------------------------------------------------------
# 画像パスの警告
# ---------------------------------------------------------------------------

def test_windows_absolute_image_path_warns(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(
        content / "2026" / "07" / "2026-07-18.md",
        body="# タイトル\n\n![説明](C:\\Users\\murat\\image.png)\n",
    )

    entries, warnings = bdl.load_entries(content)

    assert any("Web上の絶対パスではありません" in w for w in warnings)


def test_web_image_path_no_warning(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(
        content / "2026" / "07" / "2026-07-18.md",
        body="# タイトル\n\n![説明](/assets/images/example.png)\n",
    )

    entries, warnings = bdl.load_entries(content)

    assert not any("Web上の絶対パスではありません" in w for w in warnings)


def test_empty_alt_text_warns(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md", body="# タイトル\n\n![](/assets/images/example.png)\n")

    entries, warnings = bdl.load_entries(content)

    assert any("alt属性が空です" in w for w in warnings)


# ---------------------------------------------------------------------------
# ステージング書き込み・古いHTML削除
# ---------------------------------------------------------------------------

def test_stage_and_commit_writes_expected_files(tmp_path: Path) -> None:
    content = tmp_path / "content"
    output = tmp_path / "out"
    write_md(content / "2026" / "07" / "2026-07-18.md")

    entries, _ = bdl.load_entries(content)
    rendered = bdl.render_all(entries)
    bdl.stage_and_commit(rendered, output)

    assert (output / "index.html").exists()
    assert (output / "2026-07-18.html").exists()


def test_stale_html_removed_when_article_no_longer_present(tmp_path: Path) -> None:
    content = tmp_path / "content"
    output = tmp_path / "out"
    write_md(content / "2026" / "07" / "2026-07-18.md")
    entries, _ = bdl.load_entries(content)
    bdl.stage_and_commit(bdl.render_all(entries), output)
    assert (output / "2026-07-18.html").exists()

    (content / "2026" / "07" / "2026-07-18.md").unlink()
    entries2, _ = bdl.load_entries(content)
    removed = bdl.stage_and_commit(bdl.render_all(entries2), output)

    assert not (output / "2026-07-18.html").exists()
    assert (output / "index.html").exists()  # index.htmlは毎回再生成されるので残る
    assert any(p.name == "2026-07-18.html" for p in removed)


def test_failure_does_not_leave_partial_output(tmp_path: Path) -> None:
    content = tmp_path / "content"
    output = tmp_path / "out"
    write_md(content / "2026" / "07" / "2026-07-18.md")
    entries, _ = bdl.load_entries(content)
    rendered = bdl.render_all(entries)
    # 既存出力が無い状態で書き込み先を読み取り専用のファイルにするのは環境依存のため、
    # ここではステージングディレクトリの後始末（成功時に残っていないこと）だけを確認する。
    bdl.stage_and_commit(rendered, output)
    staging_dirs = list(output.parent.glob(".build-staging-devlog-*"))
    assert staging_dirs == []


# ---------------------------------------------------------------------------
# canonical / パンくず / 戻るリンク
# ---------------------------------------------------------------------------

def test_canonical_url_present(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md")

    entries, _ = bdl.load_entries(content)
    html = bdl.render_all(entries)[Path("2026-07-18.html")]

    assert 'rel="canonical" href="https://www.sidekick-lab.com/development-log/2026-07-18"' in html


def test_back_to_list_link_present(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md")

    entries, _ = bdl.load_entries(content)
    html = bdl.render_all(entries)[Path("2026-07-18.html")]

    assert 'href="/development-log"' in html


def test_index_page_lists_article_link(tmp_path: Path) -> None:
    content = tmp_path / "content"
    write_md(content / "2026" / "07" / "2026-07-18.md")

    entries, _ = bdl.load_entries(content)
    html = bdl.render_all(entries)[Path("index.html")]

    assert 'href="/development-log/2026-07-18"' in html


def test_empty_state_index_no_crash(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir(parents=True)

    entries, _ = bdl.load_entries(content)
    html = bdl.render_all(entries)[Path("index.html")]

    assert "まだ公開されている開発日誌がありません" in html


def test_unremoved_memo_section_excluded_from_build(tmp_path: Path) -> None:
    """PUBLIC_LOG_TEMPLATE.mdの「## メモ（公開しない）」削除忘れをビルド側でも検出できること
    （sync側の防御をすり抜けて手動でcontent/development-logに置かれた場合の多層防御）。"""
    content = tmp_path / "content"
    write_md(
        content / "2026" / "07" / "2026-07-18.md",
        body="# タイトル\n\n本文です。\n\n## メモ（公開しない）\n\nコミット: abc123\n",
    )

    entries, warnings = bdl.load_entries(content)

    assert len(entries) == 0
    assert any("メモ（公開しない）" in w for w in warnings)


def test_long_dash_closing_fence_does_not_leak_into_body(tmp_path: Path) -> None:
    """_DevelopmentLogのテンプレートは閉じfront matterを'---------------'
    （長いハイフン列）で書いており、実データ（2026-07-18.md）で本文冒頭に
    余ったハイフンが紛れ込む不具合を発見した。回帰しないことを確認する。"""
    content = tmp_path / "content"
    path = content / "2026" / "07" / "2026-07-18.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        '---\ntitle: "テスト"\ndate: "2026-07-18"\nstatus: "published"\n'
        '---------------\n\n# タイトル\n\n本文です。\n',
        encoding="utf-8",
    )

    entries, warnings = bdl.load_entries(content)

    assert entries[0]["body_markdown"].lstrip().startswith("#")
    assert "------" not in bdl.render_all(entries)[Path("2026-07-18.html")]


def test_format_date_ja() -> None:
    assert bdl.format_date_ja("2026-07-08") == "2026年7月8日"
