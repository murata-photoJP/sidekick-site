"""残っていた見出しセマンティクスの回帰テスト。2026-09-01新設。

**きっかけとなった問題**

footer由来（2026-09-01, commit a4a3c97）とカード部品由来（同日, commit 8c3433c）の
見出し階層の飛び越しを解消したあと、サイト全体の監査で次の4種類が残っていた。

    gallery.html / en/gallery.html   h1 -> h3（作品タイトル）
    kouzu-lp.html                    h2 -> h4（比較カード・受講後カード）
    star-lp.html                     h2 -> h4（受講後カード）
    register-dl.html                 h1 が無い

いずれも「h3をh2にする」「h1を足す」といった機械的な操作では直さず、
**その要素が本当に見出しなのか**を先に判断した。

**採用した判断**

gallery：飛び越しの原因は作品タイトルのh3ではなく、その上にある
    `<div class="section-label">`（「1x.com Awarded 作品」「販売中の作品」）が
    実質は節見出しなのに div で書かれていたこと。div を h2 にすると
    h1 > h2(節) > h3(作品タイトル) となり、ページの実際の構造どおりになる。
    作品タイトルのh3は動かしていない。

kouzu-lp / star-lp：h4 はいずれも h2 の直下にある小見出しで、
    中間の h3 は存在しない。star-lp は同じページ内の「実際に学べること」で
    既に h3 を小見出しとして使っており、h3 がこのページの小見出しレベルである。
    したがって h4 -> h3 が正しい（見出しでない要素へ変えるべきものは無かった）。

register-dl：ダウンロード同意の機能ページ。ページの主題を表す
    `<div class="product-name" id="ph-name">` が実質のページ見出しなので h1 にした。
    同意ブロックの見出し `<div class="consent-title">` も同じ理由で h2 にした。
    **新しい表示文言は一切追加していない**（不可視見出し・ダミー見出しも追加しない）。

**見た目を変えないための措置**

    .section-label   h2 のUA既定 margin-top を打ち消す `margin-top:0` を追加
    .future-card h3  `.article h3` の `letter-spacing:-.015em` を拾わないよう
                     `letter-spacing:normal`（h4 のときの継承値）を明示

**テンプレートと本番HTMLを読むだけで、何も書き込まない。**

使い方:
    python -m pytest tests/site/test_remaining_heading_semantics.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.I)
HEADING_RE = re.compile(r"<(h[1-6])\b([^>]*)>(.*?)</\1>", re.DOTALL | re.I)

# 修正した4種類のページ。gallery のみテンプレート生成、他3本は手書きの本番ファイル。
GALLERY_PAGES = ("gallery.html", "en/gallery.html")
GALLERY_TEMPLATES = ("templates/site/pages/gallery.html", "templates/site/pages/en/gallery.html")
LP_PAGES = ("kouzu-lp.html", "star-lp.html")

SECTION_LABEL_H2 = '<h2 class="section-label"'
SECTION_LABEL_DIV = '<div class="section-label"'


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8-sig")


def _strip(html: str) -> str:
    return SCRIPT_STYLE_RE.sub("", COMMENT_RE.sub("", html))


def _headings(html: str) -> list[tuple[int, str, str]]:
    out = []
    for m in HEADING_RE.finditer(_strip(html)):
        text = " ".join(re.sub("<[^>]+>", "", m.group(3)).split())
        out.append((int(m.group(1)[1]), m.group(2), text))
    return out


def _origin(attrs: str) -> str:
    """飛び越しの由来を、どの部品が出したかで分類する。"""
    if "kzc-card-title" in attrs:
        return "card"
    if "kzc-mini-card-title" in attrs:
        return "mini-card"
    if "footer-col" in attrs:
        return "footer"
    return "other"


def _skips(html: str) -> list[str]:
    prev = 0
    out = []
    for level, attrs, text in _headings(html):
        if prev and level > prev + 1:
            out.append(f"h{prev}->h{level} [{_origin(attrs)}] {text[:40]!r}")
        prev = level
    return out


def _shape(rel: str) -> list[int]:
    """連続する同レベルをまとめた見出しの形。件数の違いを無視して構造だけを比べる。"""
    out: list[int] = []
    for lvl, _, _ in _headings(_read(rel)):
        if not out or out[-1] != lvl:
            out.append(lvl)
    return out


def _production_pages() -> list[Path]:
    """本番へ配置されるHTML。ビルドの一時出力・バックアップ・テンプレートは除く。"""
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
# gallery：section-label が節見出しであること
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", GALLERY_TEMPLATES)
def test_gallery_template_section_label_is_a_heading(rel: str) -> None:
    """テンプレート側で section-label が h2 になっていること（div へ戻さない）。"""
    body = _read(rel)
    assert SECTION_LABEL_DIV not in body, f"{rel}: section-label が div に戻っている"
    assert body.count(SECTION_LABEL_H2) == 2, (
        f"{rel}: h2.section-label は2つあるべきだが {body.count(SECTION_LABEL_H2)} 個"
    )


@pytest.mark.parametrize("rel", GALLERY_TEMPLATES)
def test_gallery_template_section_label_keeps_its_position(rel: str) -> None:
    """h2 のUA既定 margin-top を打ち消す指定が残っていること（見た目を変えないため）。"""
    css = _read(rel).replace(" ", "").replace("\n", "")
    block = css.split(".section-label{", 1)[1].split("}", 1)[0]
    assert "margin-top:0" in block, (
        f"{rel}: .section-label の margin-top:0 が失われている（h2 の既定余白が出てしまう）"
    )


@pytest.mark.parametrize("rel", GALLERY_PAGES)
def test_gallery_production_matches_the_template_decision(rel: str) -> None:
    """本番HTMLへビルド結果が反映されていること。"""
    body = _read(rel)
    assert SECTION_LABEL_DIV not in body, f"{rel}: 本番が古いまま（ビルド未反映）"
    assert body.count(SECTION_LABEL_H2) == 2, f"{rel}: h2.section-label が2つない"


@pytest.mark.parametrize("rel", GALLERY_PAGES)
def test_gallery_work_titles_stay_h3(rel: str) -> None:
    """作品タイトルは h3 のままであること。

    節見出しを足して直したのであって、作品タイトルのレベルを上げたのではない。
    """
    levels = [
        lvl for lvl, _, text in _headings(_read(rel))
        if "Inner Structure" in text or "Quiet Line" in text
    ]
    assert levels, f"{rel}: 作品タイトルの見出しが見つからない"
    assert set(levels) == {3}, (
        f"{rel}: 作品タイトルが h{sorted(set(levels))} になっている（h3 のままであるべき）"
    )


def test_gallery_ja_and_en_have_the_same_heading_shape() -> None:
    """galleryのJA版とEN版で見出しの階層パターンが同じであること。"""
    assert _shape("gallery.html") == _shape("en/gallery.html"), (
        f"gallery={_shape('gallery.html')} / en/gallery={_shape('en/gallery.html')}"
    )


# ---------------------------------------------------------------------------
# LP：h2 直下の小見出しは h3
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel", LP_PAGES)
def test_lp_has_no_h4(rel: str) -> None:
    """LPに h4 が残っていないこと（h2 の直下に h4 を置くと必ず飛び越しになる）。"""
    assert "<h4" not in _strip(_read(rel)).lower(), f"{rel}: h4 が残っている"


@pytest.mark.parametrize("rel", LP_PAGES)
def test_lp_card_css_targets_h3(rel: str) -> None:
    """カードのCSSセレクタが h3 を指していること（タグだけ変えてCSSを直し忘れない）。"""
    css = _read(rel)
    assert ".future-card h3{" in css, f"{rel}: .future-card h3 のCSSが無い"
    assert ".future-card h4{" not in css, f"{rel}: .future-card h4 の古いCSSが残っている"


@pytest.mark.parametrize("rel", LP_PAGES)
def test_lp_future_card_keeps_its_letter_spacing(rel: str) -> None:
    """`.article h3` の letter-spacing を拾わないよう明示していること（見た目を変えないため）。"""
    block = _read(rel).replace(" ", "").split(".future-cardh3{", 1)[1].split("}", 1)[0]
    assert "letter-spacing:normal" in block, (
        f"{rel}: .future-card h3 に letter-spacing:normal が無い（.article h3 の字間が効いてしまう）"
    )


def test_kouzu_lp_compare_card_css_targets_h3() -> None:
    """kouzu-lp の比較カードのCSSも h3 を指していること。"""
    css = _read("kouzu-lp.html")
    for sel in (".compare-card h3{", ".compare-card.before h3{", ".compare-card.after h3{"):
        assert sel in css, f"kouzu-lp.html: {sel} が無い"
    assert ".compare-card h4{" not in css, "kouzu-lp.html: .compare-card h4 の古いCSSが残っている"


# ---------------------------------------------------------------------------
# register-dl：機能ページにもページ主題を表す h1 を置く
# ---------------------------------------------------------------------------

def test_register_dl_has_exactly_one_h1() -> None:
    """register-dl.html に h1 がちょうど1つあること。"""
    levels = [lvl for lvl, _, _ in _headings(_read("register-dl.html"))]
    assert levels.count(1) == 1, f"register-dl.html: h1 が {levels.count(1)} 個（1個であるべき）"


def test_register_dl_h1_is_the_product_name() -> None:
    """h1 は製品名の要素であること。JSが textContent で書き換える要素なのでidも保つ。"""
    body = _read("register-dl.html")
    assert '<h1 class="product-name" id="ph-name">' in body, (
        "register-dl.html: product-name が h1 でない"
    )
    assert "getElementById('ph-name').textContent" in body, (
        "register-dl.html: JSが #ph-name を textContent で更新する前提が崩れている"
    )


def test_register_dl_consent_title_is_h2() -> None:
    """同意ブロックの見出しが h2 であること。"""
    assert '<h2 class="consent-title">' in _read("register-dl.html"), (
        "register-dl.html: consent-title が h2 でない"
    )


def test_register_dl_adds_no_new_visible_text() -> None:
    """見出し階層のために新しい表示文言を足していないこと。

    h1・h2 の文言は、もともとページに表示されていた文字列と同じでなければならない。
    """
    texts = [t for lvl, _, t in _headings(_read("register-dl.html")) if lvl in (1, 2)]
    assert texts == ["Sidekick Star", "個人情報の取り扱いについて"], f"想定外の見出し文言: {texts}"


# ---------------------------------------------------------------------------
# サイト全体
# ---------------------------------------------------------------------------

def test_every_production_page_has_exactly_one_h1() -> None:
    """本番HTML全ページに h1 がちょうど1つあること。"""
    bad = []
    for p in PRODUCTION_PAGES:
        n = [lvl for lvl, _, _ in _headings(p.read_text(encoding="utf-8-sig"))].count(1)
        if n != 1:
            bad.append(f"{p.relative_to(REPO_ROOT).as_posix()}: h1={n}")
    assert not bad, "h1 が1つでないページ:\n  " + "\n  ".join(bad)


def test_no_heading_level_skip_anywhere() -> None:
    """本番HTML全ページで見出し階層の飛び越しが1件も無いこと。

    2026-09-01時点で例外は無い。将来ページを追加するときもこの状態を保つこと。
    """
    bad = []
    for p in PRODUCTION_PAGES:
        for s in _skips(p.read_text(encoding="utf-8-sig")):
            bad.append(f"{p.relative_to(REPO_ROOT).as_posix()}: {s}")
    assert not bad, "見出し階層が飛んでいるページ:\n  " + "\n  ".join(bad)


@pytest.mark.parametrize("origin", ["footer", "card", "mini-card"])
def test_previously_fixed_origins_stay_fixed(origin: str) -> None:
    """先行2Unitで直した由来（footer / カード部品）の飛び越しが再発していないこと。"""
    bad = []
    for p in PRODUCTION_PAGES:
        for s in _skips(p.read_text(encoding="utf-8-sig")):
            if f"[{origin}]" in s:
                bad.append(f"{p.relative_to(REPO_ROOT).as_posix()}: {s}")
    assert not bad, f"{origin} 由来の飛び越しが再発している:\n  " + "\n  ".join(bad)
