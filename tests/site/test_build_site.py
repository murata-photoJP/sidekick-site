"""build/site/build_site.py の動作確認テスト。

実際のtemplates/site・templates/knowledge（header.html/footer.html再利用元）を使う
（本番テンプレート自体の検証も兼ねる）。書き込み先はすべてtempfile上で完結し、
本番のhtml/直下には一切触れない。

使い方:
    python -m pytest tests/site/test_build_site.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "site"))
import build_site as bs  # noqa: E402


def test_render_all_default_renders_every_registered_page() -> None:
    rendered = bs.render_all(None)
    assert set(rendered) == {page["output"] for page in bs.PAGES.values()}


def test_render_all_specific_page() -> None:
    rendered = bs.render_all("workshop")
    assert list(rendered) == [Path("workshop.html")]


def test_unknown_page_raises_build_error() -> None:
    with pytest.raises(bs.BuildError):
        bs.render_all("no-such-page")


def test_workshop_title_meta_canonical() -> None:
    html = bs.render_all("workshop")[Path("workshop.html")]
    assert "<title>ワークショップ | 村田一朗 × 写真</title>" in html
    assert 'href="https://www.sidekick-lab.com/workshop"' in html
    assert html.count("<html") == 1 and html.count("</html>") == 1


def test_workshop_suppresses_lang_banner_and_en_link() -> None:
    """Workshopは対面開催の日本語限定ワークショップのため、英語案内を出さない
    （村田さんの明示要件）。"""
    html = bs.render_all("workshop")[Path("workshop.html")]
    assert "lang-banner" not in html
    assert "View English page" not in html
    assert "🇺🇸 EN" not in html


def test_workshop_nav_marks_itself_current() -> None:
    html = bs.render_all("workshop")[Path("workshop.html")]
    assert '<a href="/workshop" aria-current="page">' in html
    # 他のナビ項目にはaria-currentが付かない
    assert '<a href="/about" style="color:var(--muted);" aria-current="page">' not in html


def test_workshop_has_shared_header_and_footer() -> None:
    html = bs.render_all("workshop")[Path("workshop.html")]
    assert '<header class="hdr">' in html
    assert '<footer class="footer">' in html
    assert 'class="site-header"' not in html
    assert 'class="site-footer"' not in html


def test_workshop_body_content_and_script_preserved() -> None:
    html = bs.render_all("workshop")[Path("workshop.html")]
    assert "現在募集中のWorkshop" in html
    assert "const WORKSHOPS = [" in html
    assert "images/WS/20260413_214949_138_DxO.jpg" in html


def test_write_atomic_creates_file_without_leftover_tmp(tmp_path: Path) -> None:
    rendered = bs.render_all("workshop")
    bs.write_atomic(tmp_path, rendered)

    out = tmp_path / "workshop.html"
    assert out.exists()
    assert out.read_text(encoding="utf-8") == rendered[Path("workshop.html")]
    assert list(tmp_path.glob(".tmp-site-*")) == []


def test_main_validate_only_does_not_write(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = bs.main(["--output", str(tmp_path), "--validate-only"])
    assert exit_code == 0
    assert not (tmp_path / "workshop.html").exists()


def test_main_writes_registered_pages(tmp_path: Path) -> None:
    exit_code = bs.main(["--output", str(tmp_path)])
    assert exit_code == 0
    assert (tmp_path / "workshop.html").exists()


def test_main_unknown_page_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = bs.main(["--output", str(tmp_path), "--page", "no-such-page"])
    assert exit_code == 1
    assert not list(tmp_path.glob("*.html"))
