"""カード部品の見出しレベル（heading level）の回帰テスト。2026-09-01新設。

**きっかけとなった問題**

Story一覧・開発日誌一覧では、h1 の直下にカードが並ぶのに、カードタイトルが
`<h3>` だったため **h1→h3 の見出し階層の飛び越し**が起きていた（JA/EN 計4ページ）。
docs/COMPONENTS/00_COMPONENT_PRINCIPLES.md の「見出し階層（h1→h2→h3）が
飛ばない構造であること」に反していた。

一方、打ち出の小槌の「すべての記事」ではカードが
h1 > h2「すべての記事」> h3(カテゴリ名) の下に並ぶため、`<h3>` が適切だった。
つまり **正しいレベルは部品ではなく、置かれるページの文書構造で決まる**。

**採用した構造**

3つのカード部品（story-card / devlog-card / article-card）がいずれも
`card_heading_level`（既定3）を受け取り、呼び出し側が明示的に渡す。

    Story一覧・開発日誌一覧 -> 2
    打ち出の小槌の記事一覧  -> 3

このテストは、将来また部品側でレベルを固定したり、片方の言語だけ直したり、
本番HTMLへの反映を忘れたりしないよう固定する。

**テンプレートと本番HTMLを読むだけで、何も書き込まない。**

使い方:
    python -m pytest tests/site/test_card_heading_levels.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

CARD_COMPONENTS = {
    "story-card": REPO_ROOT / "templates" / "story" / "components" / "story-card.html",
    "devlog-card": REPO_ROOT / "templates" / "development-log" / "components" / "devlog-card.html",
    "article-card": REPO_ROOT / "templates" / "knowledge" / "components" / "article-card.html",
}

# 呼び出し側テンプレート -> 渡すべき見出しレベル
CALL_SITES = {
    REPO_ROOT / "templates" / "story" / "index.html": 2,
    REPO_ROOT / "templates" / "development-log" / "index.html": 2,
    REPO_ROOT / "templates" / "knowledge" / "index.html": 3,
}

# 本番の一覧ページ -> カードタイトルに期待する見出しレベル
LIST_PAGES = {
    "story/index.html": 2,
    "en/story/index.html": 2,
    "development-log/index.html": 2,
    "en/development-log/index.html": 2,
    "knowledge/index.html": 3,
    "en/knowledge/index.html": 3,
}

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.I)
HEADING_RE = re.compile(r"<(h[1-6])\b([^>]*)>(.*?)</\1>", re.DOTALL | re.I)
CARD_TITLE_RE = re.compile(r'<(h[1-6]) class="kzc-card-title">', re.I)
SET_LEVEL_RE = re.compile(r"\{%-?\s*set\s+card_heading_level\s*=\s*(\d)\s*-?%\}")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _strip(html: str) -> str:
    return SCRIPT_STYLE_RE.sub("", COMMENT_RE.sub("", html))


def _heading_sequence(html: str) -> list[tuple[int, str, str]]:
    out = []
    for m in HEADING_RE.finditer(_strip(html)):
        level = int(m.group(1)[1])
        attrs = m.group(2)
        text = " ".join(re.sub("<[^>]+>", "", m.group(3)).split())
        out.append((level, attrs, text))
    return out


def _skips(html: str) -> list[str]:
    prev = 0
    out = []
    for level, attrs, text in _heading_sequence(html):
        if prev and level > prev + 1:
            comp = "card" if "kzc-card-title" in attrs else (
                "mini-card" if "kzc-mini-card-title" in attrs else (
                    "footer" if "footer-col" in attrs else "other"))
            out.append(f"h{prev}->h{level} [{comp}] {text[:40]!r}")
        prev = level
    return out


def _production_pages() -> list[Path]:
    pages = []
    for p in sorted(REPO_ROOT.rglob("*.html")):
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(("build-output/", "BackUp/", "templates/")):
            continue
        if "sidekick_manual_package" in rel or p.name.startswith("google"):
            continue
        pages.append(p)
    return pages


PRODUCTION_PAGES = _production_pages()


# ---------------------------------------------------------------------------
# 部品側：レベルを固定しない
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(CARD_COMPONENTS))
def test_card_component_does_not_hardcode_a_heading_level(name: str) -> None:
    """カード部品が見出しレベルを直書きしていないこと。

    正しいレベルは置かれるページの文書構造で決まるため、部品側で固定すると
    どこかのページで必ず不整合になる。
    """
    body = _read(CARD_COMPONENTS[name])
    hardcoded = re.findall(r'<h[1-6] class="kzc-card-title"', body)
    assert not hardcoded, f"{name}: 見出しレベルが直書きされている: {hardcoded}"
    assert "card_heading_level" in body, f"{name}: card_heading_level を受け取っていない"


@pytest.mark.parametrize("name", sorted(CARD_COMPONENTS))
def test_card_component_opening_and_closing_tags_use_the_same_level(name: str) -> None:
    """開始タグと終了タグが同じ式を使っていること（h2 ... </h3> のような壊れ方を防ぐ）。"""
    body = _read(CARD_COMPONENTS[name])
    opens = re.findall(r"<h\{\{([^}]+)\}\} class=\"kzc-card-title\"", body)
    closes = re.findall(r"</h\{\{([^}]+)\}\}>", body)
    assert opens and closes, f"{name}: 可変見出しタグが見つからない"
    assert [o.strip() for o in opens] == [c.strip() for c in closes], (
        f"{name}: 開始タグと終了タグの式が一致しない: {opens} vs {closes}"
    )


@pytest.mark.parametrize("name", sorted(CARD_COMPONENTS))
def test_card_component_default_level_is_three(name: str) -> None:
    """既定値が3であること（呼び出し側が指定を忘れても2026-09-01以前と同じ出力になる安全網）。"""
    body = _read(CARD_COMPONENTS[name])
    assert "card_heading_level|default(3)" in body.replace(" ", ""), (
        f"{name}: 既定値3が指定されていない"
    )


# ---------------------------------------------------------------------------
# 呼び出し側：レベルを明示する
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,level", sorted(CALL_SITES.items(), key=lambda kv: str(kv[0])),
                         ids=lambda v: v.parent.name if isinstance(v, Path) else str(v))
def test_call_site_sets_the_expected_level(path: Path, level: int) -> None:
    """一覧テンプレートがカードへ渡す見出しレベルを明示していること。"""
    found = {int(x) for x in SET_LEVEL_RE.findall(_read(path))}
    assert found == {level}, (
        f"{path.relative_to(REPO_ROOT)}: card_heading_level は {level} であるべきだが {found or '未設定'}"
    )


# ---------------------------------------------------------------------------
# 本番HTML：テンプレートと一致し、階層が飛ばない
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel,level", sorted(LIST_PAGES.items()))
def test_production_card_titles_use_the_expected_level(rel: str, level: int) -> None:
    """本番の一覧ページのカードタイトルが、期待する見出しレベルで出力されていること。

    失敗した場合はテンプレートを直したあとビルドを再実行して反映すること。
    """
    p = REPO_ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} が存在しない")
    levels = {t.lower() for t in CARD_TITLE_RE.findall(_strip(_read(p)))}
    assert levels, f"{rel}: kzc-card-title が1件も無い"
    assert levels == {f"h{level}"}, f"{rel}: カードタイトルが {levels}（期待は h{level}）"


@pytest.mark.parametrize("rel", ["story/index.html", "en/story/index.html",
                                 "development-log/index.html", "en/development-log/index.html"])
def test_story_and_devlog_indexes_have_no_heading_skip(rel: str) -> None:
    """Story一覧・開発日誌一覧（JA/EN）に見出し階層の飛び越しが無いこと。"""
    p = REPO_ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} が存在しない")
    skips = _skips(_read(p))
    assert not skips, f"{rel}: 見出し階層が飛んでいる: {skips}"


@pytest.mark.parametrize("rel", ["knowledge/index.html", "en/knowledge/index.html"])
def test_knowledge_index_keeps_its_correct_hierarchy(rel: str) -> None:
    """打ち出の小槌の既存の正しい階層を壊していないこと。

    h1 > h2(セクション) > h3(カテゴリ名・カードタイトル) が保たれ、飛び越しが無いこと。
    """
    p = REPO_ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} が存在しない")
    html = _read(p)
    assert not _skips(html), f"{rel}: 見出し階層が飛んでいる: {_skips(html)}"
    levels = [lvl for lvl, _, _ in _heading_sequence(html)]
    assert levels[0] == 1, f"{rel}: 最初の見出しが h1 ではない"
    assert 2 in levels, f"{rel}: h2 セクションが失われている"
    assert {t.lower() for t in CARD_TITLE_RE.findall(_strip(html))} == {"h3"}, (
        f"{rel}: カードタイトルが h3 でなくなっている"
    )


def test_no_card_derived_heading_skip_anywhere() -> None:
    """サイト全体で、カード部品に由来する見出し階層の飛び越しが1件も無いこと。

    カード以外に由来する既存の飛び越し（gallery・LPページ）はこのテストの対象外。
    """
    offenders = []
    for p in PRODUCTION_PAGES:
        for s in _skips(_read(p)):
            if "[card]" in s or "[mini-card]" in s:
                offenders.append(f"{p.relative_to(REPO_ROOT).as_posix()}: {s}")
    assert not offenders, "カード由来の見出し飛び越しが残っている:\n  " + "\n  ".join(offenders)


# ---------------------------------------------------------------------------
# JA/EN parity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ja,en", [
    ("story/index.html", "en/story/index.html"),
    ("development-log/index.html", "en/development-log/index.html"),
    ("knowledge/index.html", "en/knowledge/index.html"),
])
def test_ja_and_en_use_the_same_card_heading_level(ja: str, en: str) -> None:
    """同じ一覧のJA版とEN版で、カードタイトルの見出しレベルが一致すること。"""
    pja, pen = REPO_ROOT / ja, REPO_ROOT / en
    if not (pja.exists() and pen.exists()):
        pytest.skip("JA/ENどちらかが存在しない")
    lja = {t.lower() for t in CARD_TITLE_RE.findall(_strip(_read(pja)))}
    len_ = {t.lower() for t in CARD_TITLE_RE.findall(_strip(_read(pen)))}
    assert lja == len_, f"{ja}={lja} / {en}={len_} で見出しレベルが一致しない"


@pytest.mark.parametrize("ja,en", [
    ("story/index.html", "en/story/index.html"),
    ("development-log/index.html", "en/development-log/index.html"),
    ("knowledge/index.html", "en/knowledge/index.html"),
])
def test_ja_and_en_have_the_same_heading_shape(ja: str, en: str) -> None:
    """JA/ENで見出しの階層パターンが同じであること（件数の違いは許容し、レベルの並びを比較）。"""
    def shape(rel):
        levels = [lvl for lvl, _, _ in _heading_sequence(_read(REPO_ROOT / rel))]
        # 連続する同レベルを1つにまとめ、構造の形だけを比べる
        out = []
        for l in levels:
            if not out or out[-1] != l:
                out.append(l)
        return out
    pja, pen = REPO_ROOT / ja, REPO_ROOT / en
    if not (pja.exists() and pen.exists()):
        pytest.skip("JA/ENどちらかが存在しない")
    assert shape(ja) == shape(en), f"{ja}={shape(ja)} / {en}={shape(en)}"
