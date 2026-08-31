"""共通フッター（templates/knowledge/footer.html・footer_en.html）のセマンティクス回帰テスト。
2026-09-01新設。

**きっかけとなった問題**

共通フッターが列ラベルに `<h4>` を使っていたため、本文が h1→h2 で終わるページでは
h2→h4 の**見出し階層の飛び越し**が発生していた。フッターを持つ本番84ページのうち
**76ページ**で飛び越しが起きており、`docs/COMPONENTS/00_COMPONENT_PRINCIPLES.md` の
「見出し階層（h1→h2→h3）が飛ばない構造であること」に反していた。

**採用した構造**

    <p class="footer-col-label" id="footer-col-xxx">ラベル</p>
    <ul role="list" aria-labelledby="footer-col-xxx"> ... </ul>

heading をやめた理由・role="list" を明示した理由は
templates/knowledge/footer.html の冒頭コメントに記録している。

このテストは、将来また heading へ戻したり、片方の言語だけ直したり、
本番HTMLへの反映を忘れたりしないよう固定する。

**テンプレートと本番HTMLを読むだけで、何も書き込まない。**

使い方:
    python -m pytest tests/site/test_shared_footer_semantics.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FOOTERS = {
    "ja": REPO_ROOT / "templates" / "knowledge" / "footer.html",
    "en": REPO_ROOT / "templates" / "knowledge" / "footer_en.html",
}

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.I)
HEADING_RE = re.compile(r"<(h[1-6])\b[^>]*>(.*?)</\1>", re.DOTALL | re.I)
LABEL_RE = re.compile(r'<p class="footer-col-label" id="([^"]+)">(.*?)</p>', re.DOTALL)
UL_RE = re.compile(r'<ul role="list" aria-labelledby="([^"]+)">')
COL_RE = re.compile(r'<div class="footer-col">(.*?)</div>', re.DOTALL)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _strip(html: str) -> str:
    return SCRIPT_STYLE_RE.sub("", COMMENT_RE.sub("", html))


def _footer_fragment(html: str) -> str:
    """<footer ...> ... </footer> を取り出す（コメント・script/styleは除去済み前提）。"""
    m = re.search(r'<footer class="footer">.*?</footer>', html, re.DOTALL)
    return m.group(0) if m else ""


def _production_pages() -> list[Path]:
    """共通フッターを含む本番HTMLを列挙する（テンプレート・ビルド生成物・バックアップは除く）。"""
    pages = []
    for p in sorted(REPO_ROOT.rglob("*.html")):
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(("build-output/", "BackUp/", "templates/")):
            continue
        if "sidekick_manual_package" in rel or p.name.startswith("google"):
            continue
        try:
            if 'class="footer-col"' in p.read_text(encoding="utf-8-sig", errors="replace"):
                pages.append(p)
        except OSError:
            continue
    return pages


PRODUCTION_PAGES = _production_pages()


# ---------------------------------------------------------------------------
# テンプレート側
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", sorted(FOOTERS))
def test_footer_template_has_no_heading_elements(lang: str) -> None:
    """共通フッターのテンプレートに h1〜h6 が1つも無いこと。

    <h4> に戻すと、本文が h2 で終わるページで h2->h4 の飛び越しが再発する。
    """
    body = _strip(_read(FOOTERS[lang]))
    found = [m.group(0)[:60] for m in HEADING_RE.finditer(body)]
    assert not found, f"{FOOTERS[lang].name}: 見出し要素が復活している: {found}"


@pytest.mark.parametrize("lang", sorted(FOOTERS))
def test_every_column_has_a_labelled_list(lang: str) -> None:
    """各列が「ラベル + aria-labelledby でそのラベルを参照する role=list の ul」を持つこと。"""
    body = _strip(_read(FOOTERS[lang]))
    cols = COL_RE.findall(_footer_fragment(body) or body)
    assert cols, f"{FOOTERS[lang].name}: footer-col が見つからない"
    labels = LABEL_RE.findall(body)
    uls = UL_RE.findall(body)
    assert len(labels) == len(uls), (
        f"{FOOTERS[lang].name}: ラベル{len(labels)}件 と ul{len(uls)}件 の数が一致しない"
    )
    label_ids = [i for i, _ in labels]
    assert label_ids == uls, (
        f"{FOOTERS[lang].name}: ラベルidとaria-labelledbyの対応がずれている: {label_ids} vs {uls}"
    )
    assert len(set(label_ids)) == len(label_ids), (
        f"{FOOTERS[lang].name}: id が重複している: {label_ids}"
    )


@pytest.mark.parametrize("lang", sorted(FOOTERS))
def test_lists_declare_role_list(lang: str) -> None:
    """.footer-col ul は list-style:none のため、Safari/VoiceOver がリストの
    セマンティクスを落とす。role="list" を明示していないと aria-labelledby による
    名前付けも失われるので、フッター内の ul すべてに role="list" を要求する。"""
    body = _strip(_read(FOOTERS[lang]))
    fragment = _footer_fragment(body) or body
    all_uls = re.findall(r"<ul\b[^>]*>", fragment)
    missing = [u for u in all_uls if 'role="list"' not in u]
    assert not missing, f"{FOOTERS[lang].name}: role=\"list\" が無い ul: {missing}"


def test_ja_and_en_use_the_same_structure() -> None:
    """JA/ENで同じセマンティクスが適用されていること（片方だけ直さない）。"""
    shapes = {}
    for lang, path in FOOTERS.items():
        body = _strip(_read(path))
        shapes[lang] = {
            "headings": len(HEADING_RE.findall(body)),
            "labels": len(LABEL_RE.findall(body)),
            "labelled_lists": len(UL_RE.findall(body)),
        }
    assert shapes["ja"]["headings"] == shapes["en"]["headings"] == 0, shapes
    for lang in ("ja", "en"):
        assert shapes[lang]["labels"] == shapes[lang]["labelled_lists"] >= 1, shapes
    # 列数は言語で異なってよい（Workshopは日本語限定のため）。構造の種類が同じであればよい。


@pytest.mark.parametrize("lang", sorted(FOOTERS))
def test_footer_links_are_preserved(lang: str) -> None:
    """今回の修正でフッターのリンクが増減していないこと（本数と href の集合を固定）。

    件数は 2026-09-01 時点の実測値。フッターのリンクを意図的に増減した場合は、
    ここも合わせて更新すること（無断でリンクが消えた・増えたことに気付くための番人）。
    """
    expected = {"ja": 25, "en": 22}
    body = _strip(_read(FOOTERS[lang]))
    fragment = _footer_fragment(body) or body
    hrefs = re.findall(r'<li><a href="([^"]+)"', fragment)
    assert len(hrefs) == expected[lang], (
        f"{FOOTERS[lang].name}: フッターのリンクが {expected[lang]} 本から {len(hrefs)} 本へ変わった: {hrefs}"
    )


# ---------------------------------------------------------------------------
# 本番HTML側（ビルド反映の確認）
# ---------------------------------------------------------------------------

def test_production_html_has_no_footer_headings() -> None:
    """本番HTMLのフッターに見出し要素が残っていないこと（再ビルド忘れの検出）。"""
    bad = []
    for p in PRODUCTION_PAGES:
        fragment = _footer_fragment(_strip(_read(p)))
        if not fragment:
            continue
        if HEADING_RE.search(fragment):
            bad.append(p.relative_to(REPO_ROOT).as_posix())
    assert not bad, (
        "本番HTMLのフッターに見出しが残っている（build を再実行して反映すること）:\n  "
        + "\n  ".join(bad)
    )


def test_production_html_has_labelled_footer_lists() -> None:
    """本番HTMLにもラベル付きリストが反映されていること。"""
    bad = []
    for p in PRODUCTION_PAGES:
        html = _strip(_read(p))
        fragment = _footer_fragment(html)
        if not fragment:
            continue
        labels = LABEL_RE.findall(html)
        uls = UL_RE.findall(html)
        if not labels or [i for i, _ in labels] != uls:
            bad.append(p.relative_to(REPO_ROOT).as_posix())
    assert not bad, "本番HTMLのフッターがラベル付きリストになっていない:\n  " + "\n  ".join(bad)


def test_footer_no_longer_causes_heading_level_skips() -> None:
    """フッターが原因の見出し階層の飛び越しが、全本番ページで解消していること。

    残ってよいのは、フッター以外（カード部品が h3 を使うことによる h1->h3）だけ。
    フッターのラベル文字列を含む飛び越しが1件でもあれば失敗させる。
    """
    footer_labels = set()
    for path in FOOTERS.values():
        footer_labels |= {t.strip() for _, t in LABEL_RE.findall(_strip(_read(path)))}

    offenders = []
    for p in PRODUCTION_PAGES:
        html = _strip(_read(p))
        seq = [
            (int(m.group(1)[1]), " ".join(re.sub("<[^>]+>", "", m.group(2)).split()))
            for m in HEADING_RE.finditer(html)
        ]
        prev = 0
        for level, text in seq:
            if prev and level > prev + 1 and text in footer_labels:
                offenders.append(f"{p.relative_to(REPO_ROOT).as_posix()}: h{prev}->h{level} {text!r}")
            prev = level
    assert not offenders, "フッター由来の見出し階層の飛び越しが残っている:\n  " + "\n  ".join(offenders)


def test_css_targets_the_label_class_not_a_heading() -> None:
    """CSSがフッターの列ラベルをクラスで指定していること（見た目を維持するため）。"""
    for name in ("knowledge.css", "site-header.css"):
        css = _read(REPO_ROOT / "assets" / "css" / name)
        assert ".footer-col .footer-col-label{" in css, f"{name}: ラベル用のルールが無い"
        assert ".footer-col h4" not in css, f"{name}: 旧セレクタ .footer-col h4 が残っている"
