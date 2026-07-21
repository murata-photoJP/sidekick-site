"""build/development-log/sync_development_log.py の動作確認テスト。

すべてtempfile上の独自ディレクトリで完結し、本番の_DevelopmentLog・
content/development-logには一切触れない。

使い方:
    python -m pytest tests/development-log/test_sync_development_log.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "development-log"))
import sync_development_log as sdl  # noqa: E402


def write_md(path: Path, **fields) -> Path:
    front = fields.pop("front_matter_text", None)
    body = fields.pop("body", "# タイトル\n\n本文です。\n")
    if front is None:
        lines = ["---"]
        for k, v in fields.items():
            if isinstance(v, list):
                lines.append(f"{k}: [{', '.join(repr(i) for i in v)}]")
            else:
                lines.append(f'{k}: "{v}"')
        lines.append("---")
        front = "\n".join(lines)
    text = front + "\n\n" + body
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def published_fields(**overrides) -> dict:
    base = {
        "title": "テスト記事タイトル★日本語",
        "date": "2026-07-18",
        "category": "AI Development",
        "status": "published",
        "summary": "テスト用の要約。",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 基本の同期・年月再帰・除外
# ---------------------------------------------------------------------------

def test_published_article_is_copied(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())

    result = sdl.apply_sync(sdl.plan_sync(source, dest), dest)

    out = dest / "2026" / "07" / "2026-07-18.md"
    assert out.exists()
    assert result["changed"] == 1
    assert "テスト記事タイトル★日本語" in out.read_text(encoding="utf-8")


def test_draft_article_is_not_copied(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-19.md", **published_fields(status="draft"))

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 0
    assert not (dest / "2026" / "07" / "2026-07-19.md").exists()
    assert any("draft" in w for w in plan["skipped"])


@pytest.mark.parametrize("status", ["review", "private", "pending"])
def test_non_published_status_excluded(tmp_path: Path, status: str) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-20.md", **published_fields(status=status))

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 0


def test_new_year_month_directory_is_picked_up_automatically(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())
    write_md(source / "2027" / "01" / "2027-01-05.md", **published_fields(title="来年の記事", date="2027-01-05"))

    plan = sdl.plan_sync(source, dest)

    slugs = {item["slug"] for item in plan["to_copy"]}
    assert slugs == {"2026-07-18", "2027-01-05"}


def test_txt_companion_file_is_ignored(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())
    (source / "2026" / "07" / "2026-07-18.txt").write_text("SNS用テキスト", encoding="utf-8")

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 1


# ---------------------------------------------------------------------------
# 冪等性・更新反映
# ---------------------------------------------------------------------------

def test_resync_same_content_reports_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())

    sdl.apply_sync(sdl.plan_sync(source, dest), dest)
    result2 = sdl.apply_sync(sdl.plan_sync(source, dest), dest)

    assert result2["changed"] == 0
    assert result2["unchanged"] == 1


def test_updated_article_is_reflected_on_resync(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields(summary="旧要約"))
    sdl.apply_sync(sdl.plan_sync(source, dest), dest)

    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields(summary="新要約"))
    result2 = sdl.apply_sync(sdl.plan_sync(source, dest), dest)

    assert result2["changed"] == 1
    assert "新要約" in (dest / "2026" / "07" / "2026-07-18.md").read_text(encoding="utf-8")


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())

    sdl.plan_sync(source, dest)  # dry-runはplanのみ呼び出し、applyしない

    assert not dest.exists()


# ---------------------------------------------------------------------------
# 壊れたファイル・必須項目不足
# ---------------------------------------------------------------------------

def test_missing_front_matter_is_skipped_not_fatal(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    (source / "2026" / "07").mkdir(parents=True)
    (source / "2026" / "07" / "broken.md").write_text("front matterが無い普通の文章です。", encoding="utf-8")
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 1
    assert any("front matter" in w for w in plan["skipped"])


def test_broken_yaml_is_skipped_not_fatal(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(
        source / "2026" / "07" / "broken.md",
        front_matter_text="---\ntitle: [これは: 壊れたyaml\n---",
    )
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 1
    assert any("解析に失敗" in w for w in plan["skipped"])


def test_missing_required_field_is_skipped(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    fields = published_fields()
    del fields["title"]
    write_md(source / "2026" / "07" / "2026-07-18.md", **fields)

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 0
    assert any("必須項目" in w for w in plan["skipped"])


def test_invalid_date_format_is_skipped(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields(date="2026/07/18"))

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 0


# ---------------------------------------------------------------------------
# slug重複（atomic: 何も書き込まない）
# ---------------------------------------------------------------------------

def test_duplicate_slug_raises_and_writes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())
    write_md(source / "2026" / "08" / "2026-08-01.md", **published_fields())
    # 2件目のfront matterへ明示的にslugを指定し、1件目のファイル名由来slugと衝突させる
    (source / "2026" / "08" / "2026-08-01.md").write_text(
        (source / "2026" / "08" / "2026-08-01.md").read_text(encoding="utf-8").replace(
            'status: "published"', 'status: "published"\nslug: "2026-07-18"'
        ),
        encoding="utf-8",
    )

    with pytest.raises(sdl.SyncError):
        sdl.plan_sync(source, dest)

    assert not dest.exists()


# ---------------------------------------------------------------------------
# 孤立ファイル（削除しない・警告のみ）
# ---------------------------------------------------------------------------

def test_removed_source_article_is_reported_as_orphaned_not_deleted(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())
    sdl.apply_sync(sdl.plan_sync(source, dest), dest)

    (source / "2026" / "07" / "2026-07-18.md").unlink()

    plan = sdl.plan_sync(source, dest)

    assert len(plan["orphaned"]) == 1
    assert (dest / "2026" / "07" / "2026-07-18.md").exists()  # 削除されていない


# ---------------------------------------------------------------------------
# 日本語・空白・括弧を含むWindowsパス
# ---------------------------------------------------------------------------

def test_handles_japanese_space_and_parenthesis_in_path(tmp_path: Path) -> None:
    source = tmp_path / "Adobe Photoshop (Beta)" / "自作" / "_DevelopmentLog (テスト)" / "public"
    dest = tmp_path / "サイト リポジトリ" / "content (development log)"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())

    result = sdl.apply_sync(sdl.plan_sync(source, dest), dest)

    assert result["changed"] == 1
    assert (dest / "2026" / "07" / "2026-07-18.md").exists()


def test_en_subdirectory_in_dest_not_flagged_as_orphaned(tmp_path: Path) -> None:
    """dest（content/development-log）配下にネストされたen/は、JA同期の孤立ファイル
    検出の対象外にする（実運用で発見した誤警告、2026-07-21追加）。"""
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())
    write_md(dest / "en" / "2026" / "07" / "2026-07-18.md", **published_fields())

    plan = sdl.plan_sync(source, dest)

    assert plan["orphaned"] == []


def test_missing_source_raises_sync_error(tmp_path: Path) -> None:
    with pytest.raises(sdl.SyncError):
        sdl.plan_sync(tmp_path / "does-not-exist", tmp_path / "content")


def test_explicit_slug_front_matter_is_preferred_over_filename(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    fields = published_fields()
    write_md(source / "2026" / "07" / "2026-07-18.md", **fields)
    text = (source / "2026" / "07" / "2026-07-18.md").read_text(encoding="utf-8")
    text = text.replace('status: "published"', 'status: "published"\nslug: "custom-slug-name"')
    (source / "2026" / "07" / "2026-07-18.md").write_text(text, encoding="utf-8")

    plan = sdl.plan_sync(source, dest)

    assert plan["to_copy"][0]["slug"] == "custom-slug-name"


def test_unremoved_memo_section_blocks_sync(tmp_path: Path) -> None:
    """PUBLIC_LOG_TEMPLATE.mdの「## メモ（公開しない）」削除忘れを検出できること。"""
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(
        source / "2026" / "07" / "2026-07-18.md",
        **published_fields(),
        body="# タイトル\n\n本文です。\n\n## メモ（公開しない）\n\nコミット: abc123\n",
    )

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 0
    assert any("メモ（公開しない）" in w for w in plan["skipped"])
    assert not dest.exists()


def test_long_dash_closing_fence_is_parsed_correctly(tmp_path: Path) -> None:
    """_DevelopmentLogのテンプレートは閉じfront matterを'---------------'
    （長いハイフン列）で書いている。実データで発見した回帰を防ぐ。"""
    source = tmp_path / "public"
    dest = tmp_path / "content"
    path = source / "2026" / "07" / "2026-07-18.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        '---\ntitle: "テスト"\ndate: "2026-07-18"\nstatus: "published"\n'
        '---------------\n\n# タイトル\n\n本文です。\n',
        encoding="utf-8",
    )

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 1
    assert plan["to_copy"][0]["slug"] == "2026-07-18"


def test_en_subdirectory_excluded_from_ja_sync(tmp_path: Path) -> None:
    """public/en/ は英語版専用ディレクトリのため、--source public でのJA同期には
    含めない（同じ日付由来のslugがja/enで衝突するため、2026-07-21追加）。"""
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())
    write_md(source / "en" / "2026" / "07" / "2026-07-18.md", **published_fields(title="EN title"))

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 1
    assert plan["to_copy"][0]["slug"] == "2026-07-18"


def test_en_directory_can_be_synced_separately(tmp_path: Path) -> None:
    source_en = tmp_path / "public" / "en"
    dest_en = tmp_path / "content" / "en"
    write_md(source_en / "2026" / "07" / "2026-07-18.md", **published_fields(title="EN title"))

    result = sdl.apply_sync(sdl.plan_sync(source_en, dest_en), dest_en)

    assert result["changed"] == 1
    assert (dest_en / "2026" / "07" / "2026-07-18.md").exists()


def test_invalid_explicit_slug_is_skipped(tmp_path: Path) -> None:
    source = tmp_path / "public"
    dest = tmp_path / "content"
    write_md(source / "2026" / "07" / "2026-07-18.md", **published_fields())
    text = (source / "2026" / "07" / "2026-07-18.md").read_text(encoding="utf-8")
    text = text.replace('status: "published"', 'status: "published"\nslug: "日本語スラッグ"')
    (source / "2026" / "07" / "2026-07-18.md").write_text(text, encoding="utf-8")

    plan = sdl.plan_sync(source, dest)

    assert len(plan["to_copy"]) == 0
    assert any("URLとして不正" in w for w in plan["skipped"])
