"""共通ヘッダー（templates/knowledge/header.html・header_en.html）が依存するCSSの回帰テスト。
2026-08-31新設。

**きっかけとなった不具合（2026-07-20 〜 2026-08-31、約6週間）**

モバイルナビの折りたたみルールが、日本語ヘッダー専用のID
`#kzc-nav-menu` を直接指すセレクタで書かれていた。

    body.kzc-js-nav #kzc-nav-menu[data-open="false"]{ display:none; }

英語ヘッダーのIDは `kzc-nav-menu-en` のため、このルールが一致せず、
**英語ページのモバイルメニューが一度も畳まれない**状態になっていた。
「Menu」ボタンは表示され、`aria-expanded` も切り替わるのに、見た目は常に全項目が
展開されたまま、という症状で、村田さんの公開前レビュー中にブラウザ実機で発見した。

同じセレクタが `knowledge.css`（打ち出の小槌・開発日誌・Story）と
`site-header.css`（サイト共通ページ）の**両方**にあり、両方とも同じ不具合だった。

このテストは、その修正（ID前方一致セレクタへの変更）が将来また片方だけ戻ったり、
IDが変わったのにCSSが追従しなかったりしないよう固定する。

**CSSファイルとテンプレートを読むだけで、何も書き込まない。**

使い方:
    python -m pytest tests/site/test_shared_header_css.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# 共通ヘッダーを読み込むページが使うCSS。両方に同じ折りたたみルールが必要。
NAV_CSS_FILES = [
    REPO_ROOT / "assets" / "css" / "knowledge.css",   # knowledge / development-log / story
    REPO_ROOT / "assets" / "css" / "site-header.css",  # site（ルート直下・en/直下）
]

HEADERS = {
    "ja": REPO_ROOT / "templates" / "knowledge" / "header.html",
    "en": REPO_ROOT / "templates" / "knowledge" / "header_en.html",
}

# 修正後のセレクタ。#kzc-nav-menu と #kzc-nav-menu-en の両方に一致する。
COLLAPSE_SELECTOR = 'nav[id^="kzc-nav-menu"][data-open="false"]'
# 不具合時のセレクタ。日本語版のIDしか指さないため復活させてはいけない。
BROKEN_SELECTOR = '#kzc-nav-menu[data-open="false"]'


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("css_path", NAV_CSS_FILES, ids=lambda p: p.name)
def test_mobile_nav_collapse_rule_is_language_agnostic(css_path: Path) -> None:
    """折りたたみルールがJA/EN両方のヘッダーに効くセレクタで書かれていること。"""
    css = _read(css_path)
    assert COLLAPSE_SELECTOR in css, (
        f"{css_path.name}: モバイルナビの折りたたみセレクタ {COLLAPSE_SELECTOR!r} が無い"
    )


@pytest.mark.parametrize("css_path", NAV_CSS_FILES, ids=lambda p: p.name)
def test_language_specific_id_selector_is_not_reintroduced(css_path: Path) -> None:
    """日本語版のIDだけを指す壊れたセレクタが復活していないこと。"""
    css = _read(css_path)
    assert BROKEN_SELECTOR not in css, (
        f"{css_path.name}: 日本語ヘッダー専用のID指定 {BROKEN_SELECTOR!r} が復活している。"
        "英語ページのモバイルメニューが畳まれなくなる（2026-07-20〜08-31の不具合）"
    )


@pytest.mark.parametrize("css_path", NAV_CSS_FILES, ids=lambda p: p.name)
def test_collapse_rule_is_inside_the_mobile_media_query(css_path: Path) -> None:
    """折りたたみルールがモバイル幅のメディアクエリ内にあること。

    外に出るとデスクトップでもナビが畳まれてしまう（2026-07-22に一度起きている、
    knowledge.cssのコメント参照）。
    """
    css = _read(css_path)
    blocks = re.findall(r"@media\s*\(max-width:\s*640px\)\s*\{(.*?)\n\}", css, re.DOTALL)
    assert blocks, f"{css_path.name}: max-width:640px のメディアクエリが見つからない"
    assert any(COLLAPSE_SELECTOR in b for b in blocks), (
        f"{css_path.name}: 折りたたみルールが max-width:640px の外にある"
    )


@pytest.mark.parametrize("lang,header_path", sorted(HEADERS.items()), ids=sorted(HEADERS))
def test_header_menu_id_matches_the_css_selector_prefix(lang: str, header_path: Path) -> None:
    """ヘッダー側のnav要素のIDが、CSSセレクタの前方一致に収まっていること。

    IDを変えるならCSSも一緒に変える必要がある、という対応関係をここで固定する。
    """
    html = _read(header_path)
    ids = re.findall(r'<nav class="nav" id="([^"]+)"', html)
    assert ids, f"{header_path.name}: <nav class=\"nav\" id=\"...\"> が見つからない"
    for nav_id in ids:
        assert nav_id.startswith("kzc-nav-menu"), (
            f"{header_path.name}: nav id={nav_id!r} が 'kzc-nav-menu' で始まらないため、"
            f"CSSの {COLLAPSE_SELECTOR!r} に一致しない"
        )


@pytest.mark.parametrize("lang,header_path", sorted(HEADERS.items()), ids=sorted(HEADERS))
def test_toggle_script_targets_the_same_menu_id(lang: str, header_path: Path) -> None:
    """トグルのJSが、そのヘッダー自身のnav要素を掴んでいること。

    JSが別のIDを見ていると data-open が付かず、CSSが正しくても畳まれない。
    """
    html = _read(header_path)
    nav_ids = re.findall(r'<nav class="nav" id="([^"]+)"', html)
    js_ids = re.findall(r'getElementById\("([^"]+)"\)', html)
    assert js_ids, f"{header_path.name}: トグルscriptのgetElementByIdが見つからない"
    assert set(js_ids) == set(nav_ids), (
        f"{header_path.name}: script が掴むID {js_ids} と nav のID {nav_ids} が一致しない"
    )
    assert f'aria-controls="{nav_ids[0]}"' in html, (
        f"{header_path.name}: トグルボタンの aria-controls が nav のIDと一致しない"
    )


def test_story_japanese_label_is_not_uppercased() -> None:
    """日本語Storyの「この話につながる現在のSidekick」が SIDEKICK に化けないこと。

    knowledge.css の .kzc-product-context-label は text-transform:uppercase を持つため、
    日本語ラベル中の "Sidekick" だけが大文字化されてしまう（村田さんの公開前レビューで
    指摘）。story.css で日本語ページに限って解除している。
    """
    story_css = _read(REPO_ROOT / "assets" / "css" / "story.css")
    m = re.search(
        r'html\[lang="ja"\]\s+\.kzc-story-related\s+\.kzc-product-context-label\s*\{([^}]*)\}',
        story_css,
    )
    assert m, "story.css に日本語Story用の text-transform 解除ルールが無い"
    assert "text-transform:none" in m.group(1).replace(" ", ""), (
        "text-transform:none が指定されていない"
    )


def test_uppercase_override_does_not_leak_outside_japanese_story() -> None:
    """解除ルールの適用範囲が「日本語 かつ Storyの記事末尾導線」に限られていること。

    打ち出の小槌・開発日誌・英語Storyのラベルは uppercase のままであるべき。
    セレクタが html[lang="ja"] と .kzc-story-related の両方で絞られていることを確認する
    （.kzc-story-related は templates/story/article.html にしか無い）。
    """
    story_css = _read(REPO_ROOT / "assets" / "css" / "story.css")
    for line in story_css.splitlines():
        if "text-transform:none" in line.replace(" ", ""):
            continue
    selectors = re.findall(r"^([^{}\n]*\.kzc-product-context-label[^{}\n]*)\{", story_css, re.MULTILINE)
    assert selectors, "story.css に .kzc-product-context-label のルールが無い"
    for sel in selectors:
        assert 'html[lang="ja"]' in sel, f"言語の絞り込みが無いセレクタ: {sel.strip()!r}"
        assert ".kzc-story-related" in sel, f"Storyへの絞り込みが無いセレクタ: {sel.strip()!r}"

    # .kzc-story-related が Story のテンプレートにしか無いことも確認する
    users = [
        p for p in (REPO_ROOT / "templates").rglob("*.html")
        if "kzc-story-related" in _read(p)
    ]
    assert [p.name for p in users] == ["article.html"], (
        f"kzc-story-related がStory以外のテンプレートでも使われている: {[str(p) for p in users]}"
    )
    assert users[0].parent.name == "story"
