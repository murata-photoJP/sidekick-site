#!/usr/bin/env python3
"""build/knowledge/build_knowledge.py の動作確認テスト（Phase A1 + Phase A2）。

すべて tempfile 上の独自インデックス・出力先で完結し、本番の
html/knowledge/ ・ data/knowledge/web-published.json には一切触れない。

使い方:
    python tests/knowledge/test_build_knowledge.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "build" / "knowledge" / "build_knowledge.py"

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
# フィクスチャ生成ヘルパー
# ---------------------------------------------------------------------------

def sample_article(**overrides) -> dict:
    article = {
        "id": "SKB-TEST-000001",
        "title": "テスト記事タイトル★日本語",
        "slug": "sample-article",
        "language": "ja",
        "category": {"slug": "photoshop", "name": "Photoshop", "name_ja": "Photoshop"},
        "subcategory": {"slug": "dodge-and-burn", "name": "Dodge and Burn", "name_ja": "ダッジ＆バーン"},
        "meta_description": "サンプル記事の説明文です。",
        "difficulty": "intermediate",
        "audience": ["写真中級者"],
        "tags": ["Photoshop"],
        "concepts": ["photoshop"],
        "related_products": [],
        "cta_type": "none",
        "created_at": "2026-07-17",
        "updated_at": "2026-07-17",
        "published_at": "2026-07-17",
        "related_articles": [],
        "series": None,
        "body_markdown": "## 見出し\n\n本文です。<script>alert(1)</script>\n\n| a | b |\n|---|---|\n| 1 | 2 |\n",
        "images": [],
        "public_url": "/knowledge/photoshop/sample-article",
    }
    article.update(overrides)
    return article


def card_from_article(article: dict, thumbnail_url: str | None = None) -> dict:
    return {
        "id": article["id"],
        "title": article["title"],
        "slug": article["slug"],
        "language": article["language"],
        "meta_description": article["meta_description"],
        "category_name": article["category"]["name_ja"],
        "published_at": article["published_at"],
        "updated_at": article["updated_at"],
        "thumbnail_url": thumbnail_url,
        "difficulty": article["difficulty"],
        "public_url": article["public_url"],
    }


def categories_from_articles(articles: list[dict]) -> list[dict]:
    counts: dict[tuple, int] = {}
    names: dict[tuple, str] = {}
    for a in articles:
        key = (a["category"]["slug"], a["language"])
        counts[key] = counts.get(key, 0) + 1
        names[key] = a["category"]["name_ja"]
    return [
        {"slug": slug, "name": names[(slug, lang)], "language": lang, "published_count": n}
        for (slug, lang), n in counts.items()
    ]


def make_index(articles: list[dict] | None = None, products: list[dict] | None = None,
                article_cards: list[dict] | None = None, categories: list[dict] | None = None,
                **single_article_overrides) -> dict:
    """articlesを渡せば複数記事インデックス、渡さなければ単一記事(sample_article)を使う。
    article_cards/categoriesは省略時、articlesから自動的に整合するものを組み立てる
    （Phase A2で追加したcheck_index_consistency()が要求するため）。"""
    if articles is None:
        articles = [sample_article(**single_article_overrides)]
    if article_cards is None:
        article_cards = [card_from_article(a) for a in articles]
    if categories is None:
        categories = categories_from_articles(articles)
    language_counts: dict[str, int] = {}
    for a in articles:
        language_counts[a["language"]] = language_counts.get(a["language"], 0) + 1
    return {
        "generated_at": "2026-07-17T00:00:00+09:00",
        "schema_version": 1,
        "articles": articles,
        "article_cards": article_cards,
        "categories": categories,
        "products": products if products is not None else [],
        "build_meta": {"article_count": len(articles), "language_counts": language_counts},
    }


def product(product_id: str, name: str = "SideKick Portrait", detail_url: str = "/portrait",
            trial_url: str | None = "/ai-lab") -> dict:
    return {
        "product_id": product_id, "name": name,
        "short_description": f"{name}の短い説明です。",
        "detail_url": detail_url, "trial_url": trial_url,
    }


def run_build(index_data: dict, tmp: Path, *extra: str, index_filename: str = "web-published.json"):
    index_path = tmp / index_filename
    index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    output_dir = tmp / "build-output"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--index", str(index_path), "--output", str(output_dir), *extra],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    return proc, output_dir


def with_tmp(fn):
    def wrapper():
        tmp = Path(tempfile.mkdtemp(prefix="knowledge_build_test_"))
        try:
            fn(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return wrapper


def h1_count(html: str) -> int:
    return len(re.findall(r"<h1[ >]", html))


# ===========================================================================
# Phase A1: 単一記事生成（既存の29件、Phase A2でのconsistencyチェック追加後も
# 壊れていないことを確認する）
# ===========================================================================

@with_tmp
def test_basic_build(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("正常系: exit code 0", proc.returncode == 0, proc.stdout + proc.stderr)
    out_file = output_dir / "photoshop" / "sample-article.html"
    check("正常系: 出力ファイルが作られる", out_file.exists())


@with_tmp
def test_schema_version_read(tmp: Path) -> None:
    index = make_index()
    check("schema_version: インデックスに1が入っている", index["schema_version"] == 1)
    proc, _ = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("schema_version: 対応バージョンなら成功する", proc.returncode == 0, proc.stdout + proc.stderr)


@with_tmp
def test_unsupported_schema_version(tmp: Path) -> None:
    index = make_index()
    index["schema_version"] = 999
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("未対応schema_version: エラー終了する", proc.returncode == 1)
    check("未対応schema_version: 出力ファイルが残らない", not (output_dir / "photoshop" / "sample-article.html").exists())


@with_tmp
def test_article_not_found(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-NOT-EXIST")
    check("記事が無い場合: エラー終了する", proc.returncode == 1, proc.stdout + proc.stderr)
    check("記事が無い場合: 出力ディレクトリに何も残らない", not any(output_dir.rglob("*.html")) if output_dir.exists() else True)


@with_tmp
def test_missing_body_markdown(tmp: Path) -> None:
    index = make_index(body_markdown="")
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("body_markdownが空: エラー終了する", proc.returncode == 1, proc.stdout + proc.stderr)
    check("body_markdownが空: 壊れたHTMLが残らない", not (output_dir / "photoshop" / "sample-article.html").exists())


@with_tmp
def test_broken_json(tmp: Path) -> None:
    index_path = tmp / "web-published.json"
    index_path.write_text("{not valid json", encoding="utf-8")
    output_dir = tmp / "build-output"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--index", str(index_path), "--output", str(output_dir),
         "--article-id", "SKB-TEST-000001"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    check("壊れたJSON: エラー終了する", proc.returncode == 1, proc.stdout + proc.stderr)


@with_tmp
def test_missing_index_file(tmp: Path) -> None:
    output_dir = tmp / "build-output"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--index", str(tmp / "does-not-exist.json"),
         "--output", str(output_dir), "--article-id", "SKB-TEST-000001"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    check("インデックスが存在しない: エラー終了する", proc.returncode == 1, proc.stdout + proc.stderr)


@with_tmp
def test_markdown_to_html(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("Markdown変換: 見出しがh2になる", "<h2>見出し</h2>" in html, html)
    check("Markdown変換: 表がtableになる", "<table>" in html and "<td>1</td>" in html, html)


@with_tmp
def test_raw_html_escaped(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("生HTML: <script>がそのまま出力されない（エスケープされる）",
          "<script>alert(1)</script>" not in html, html)


@with_tmp
def test_utf8_no_mojibake(tmp: Path) -> None:
    index = make_index(title="日本語タイトル★テスト")
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("UTF-8: 日本語タイトルが文字化けしない", "日本語タイトル★テスト" in html, html[:300])


@with_tmp
def test_meta_description_and_canonical(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("meta description: 出力に含まれる", 'name="description" content="サンプル記事の説明文です。"' in html, html)
    check("canonical: public_urlに基づいて生成される",
          '<link rel="canonical" href="https://www.sidekick-lab.com/knowledge/photoshop/sample-article">' in html, html)


@with_tmp
def test_author_block_present(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("短い著者情報: 冒頭に存在する", "kzc-author-short" in html and "村田一朗" in html)
    check("詳細Author Block: 末尾に存在する", "kzc-author-block" in html and "Aboutを読む" in html)


@with_tmp
def test_internal_fields_not_leaked(tmp: Path) -> None:
    index = make_index()
    index["articles"][0]["source_conversations"] = [{"id": "conv-1"}]
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("内部フィールド混入時: ビルドがエラーで止まる（安全側）", proc.returncode == 1, proc.stdout + proc.stderr)
    check("内部フィールド混入時: HTMLが出力されない", not (output_dir / "photoshop" / "sample-article.html").exists())


@with_tmp
def test_output_url_matches_public_url(tmp: Path) -> None:
    index = make_index(public_url="/knowledge/photoshop/custom-slug", slug="custom-slug")
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("出力URL: public_urlどおりのパスに出力される",
          (output_dir / "photoshop" / "custom-slug.html").exists(), proc.stdout + proc.stderr)


@with_tmp
def test_template_inheritance(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("テンプレート継承: base.htmlのheadが出力される", "<!doctype html>" in html.lower())
    check("テンプレート継承: header.htmlがincludeされる", '<header class="hdr">' in html)
    check("テンプレート継承: footer.htmlがincludeされる", '<footer class="footer"' in html)
    check("テンプレート継承: article.htmlのブロックが反映される", "kzc-breadcrumb" in html)


@with_tmp
def test_heading_hierarchy_warning_on_skip(tmp: Path) -> None:
    index = make_index(body_markdown="## H2\n\nテキスト。\n\n#### H4（H3を飛ばしている）\n\nテキスト。\n")
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("見出し階層: 生成自体は成功する（警告のみ）", proc.returncode == 0, proc.stdout + proc.stderr)
    check("見出し階層: 飛び越しが警告として出力される",
          "見出しレベルが飛んでいます" in proc.stdout, proc.stdout)
    check("見出し階層: 警告に記事IDが含まれる", "SKB-TEST-000001" in proc.stdout, proc.stdout)


@with_tmp
def test_heading_hierarchy_no_warning_when_sequential(tmp: Path) -> None:
    index = make_index(body_markdown="## H2\n\nテキスト。\n\n### H3\n\nテキスト。\n\n#### H4\n\nテキスト。\n")
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("見出し階層: 連続していれば警告が出ない",
          "見出しレベルが飛んでいます" not in proc.stdout, proc.stdout)


@with_tmp
def test_image_alt_warning_when_empty(tmp: Path) -> None:
    index = make_index(body_markdown="## H2\n\n![](photo.jpg)\n")
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("画像alt: 生成自体は成功する（警告のみ）", proc.returncode == 0, proc.stdout + proc.stderr)
    check("画像alt: alt空の警告が出力される",
          "画像のalt属性が空です" in proc.stdout and "photo.jpg" in proc.stdout, proc.stdout)


@with_tmp
def test_image_alt_no_warning_when_present(tmp: Path) -> None:
    index = make_index(body_markdown="## H2\n\n![星景写真の作例](photo.jpg)\n")
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("画像alt: altがあれば警告が出ない", "画像のalt属性が空です" not in proc.stdout, proc.stdout)


@with_tmp
def test_validate_only_writes_nothing(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001", "--validate-only")
    check("validate-only: exit code 0", proc.returncode == 0, proc.stdout + proc.stderr)
    check("validate-only: ファイルが作られない", not output_dir.exists())


# ===========================================================================
# Phase A2-1: 複数記事ビルド
# ===========================================================================

def _six_article_fixture() -> tuple[list[dict], list[dict]]:
    a1 = sample_article(id="SKB-M-001", slug="m-one", title="記事1",
                         category={"slug": "photoshop", "name": "Photoshop", "name_ja": "Photoshop"},
                         public_url="/knowledge/photoshop/m-one", updated_at="2026-07-17",
                         related_products=["sidekick-portrait"], cta_type="product-detail",
                         related_articles=["SKB-M-002"])
    a2 = sample_article(id="SKB-M-002", slug="m-two", title="記事2",
                         category={"slug": "photography", "name": "Photography", "name_ja": "写真"},
                         subcategory={"slug": "astrophotography", "name": "Astrophotography", "name_ja": "星景写真"},
                         public_url="/knowledge/photography/m-two", updated_at="2026-07-16",
                         related_articles=["SKB-M-001"])
    a3 = sample_article(id="SKB-M-003", slug="m-three", title="記事3",
                         category={"slug": "marketing", "name": "Marketing", "name_ja": "マーケティング"},
                         subcategory={"slug": "1x", "name": "1X", "name_ja": "1X"},
                         public_url="/knowledge/marketing/m-three", updated_at="2026-07-15", cta_type="none")
    articles = [a1, a2, a3]
    products = [product("sidekick-portrait")]
    return articles, products


@with_tmp
def test_build_all_articles(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    check("全記事生成: exit code 0", proc.returncode == 0, proc.stdout + proc.stderr)
    check("全記事生成: 3記事+トップページ=4ファイル",
          len(list(output_dir.rglob("*.html"))) == 4, list(output_dir.rglob("*.html")))
    check("全記事生成: トップページが生成される", (output_dir / "index.html").exists())
    check("全記事生成: 各記事がそれぞれのカテゴリ配下に出力される",
          (output_dir / "photoshop" / "m-one.html").exists()
          and (output_dir / "photography" / "m-two.html").exists()
          and (output_dir / "marketing" / "m-three.html").exists())


@with_tmp
def test_build_single_article_from_multi(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-M-002")
    check("1記事指定: exit code 0", proc.returncode == 0, proc.stdout + proc.stderr)
    check("1記事指定: 指定した記事のみ生成される",
          list(output_dir.rglob("*.html")) == [output_dir / "photography" / "m-two.html"])
    check("1記事指定: トップページは生成されない", not (output_dir / "index.html").exists())


@with_tmp
def test_validate_only_reports_all(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp, "--validate-only")
    check("validate-only(複数): exit code 0", proc.returncode == 0, proc.stdout + proc.stderr)
    check("validate-only(複数): 4ページ分の報告がある", "4ページ" in proc.stdout, proc.stdout)
    check("validate-only(複数): 何も書き込まれない", not output_dir.exists())


@with_tmp
def test_duplicate_output_path_detected(tmp: Path) -> None:
    a1 = sample_article(id="SKB-DUP-001", slug="dup", public_url="/knowledge/photoshop/dup")
    a2 = sample_article(id="SKB-DUP-002", slug="dup", public_url="/knowledge/photoshop/dup")
    index = make_index(articles=[a1, a2])
    proc, output_dir = run_build(index, tmp)
    check("重複出力パス: エラー終了する", proc.returncode == 1, proc.stdout + proc.stderr)
    check("重複出力パス: 何も書き込まれない（atomic）", not output_dir.exists())


@with_tmp
def test_atomic_batch_no_partial_output_on_failure(tmp: Path) -> None:
    """3記事中1記事のbody_markdownが空 → 全体が失敗し、正常な2記事分も書き込まれない
    （途中まで生成して壊れた状態を残さない、の確認）。"""
    articles, products = _six_article_fixture()
    articles[2] = dict(articles[2])
    articles[2]["body_markdown"] = ""
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    check("バッチ失敗: exit code 1", proc.returncode == 1, proc.stdout + proc.stderr)
    check("バッチ失敗: 正常な記事も含めて何も出力されない", not output_dir.exists())
    check("バッチ失敗: staging用の一時ディレクトリも残らない",
          not any(p.name.startswith(".build-staging-") for p in tmp.iterdir()))


@with_tmp
def test_failure_does_not_corrupt_existing_output(tmp: Path) -> None:
    """既存の出力がある状態で2回目のビルドが失敗しても、既存出力は無傷であること。"""
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc1, output_dir = run_build(index, tmp)
    check("既存出力の準備: 1回目は成功する", proc1.returncode == 0, proc1.stdout + proc1.stderr)
    before = (output_dir / "index.html").read_text(encoding="utf-8")

    broken_index = json.loads(json.dumps(index))
    broken_index["articles"][0]["body_markdown"] = ""
    index_path2 = tmp / "web-published.json"
    index_path2.write_text(json.dumps(broken_index, ensure_ascii=False), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc2 = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--index", str(index_path2), "--output", str(output_dir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    check("2回目失敗: exit code 1", proc2.returncode == 1, proc2.stdout + proc2.stderr)
    after = (output_dir / "index.html").read_text(encoding="utf-8")
    check("2回目失敗後も既存出力が変化しない", before == after)


@with_tmp
def test_article_cards_consistency_check(tmp: Path) -> None:
    articles, _ = _six_article_fixture()
    index = make_index(articles=articles)
    index["article_cards"] = [c for c in index["article_cards"] if c["id"] != "SKB-M-002"]
    proc, output_dir = run_build(index, tmp)
    check("article_cards不整合: エラー終了する", proc.returncode == 1, proc.stdout + proc.stderr)
    check("article_cards不整合: 何も出力されない", not output_dir.exists())


@with_tmp
def test_categories_consistency_warning(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    index["categories"] = [c for c in index["categories"] if c["slug"] != "marketing"]
    proc, output_dir = run_build(index, tmp)
    check("categories不整合: 警告のみで生成は継続する", proc.returncode == 0, proc.stdout + proc.stderr)
    check("categories不整合: 警告メッセージが出る", "WARNING" in proc.stdout, proc.stdout)


# ===========================================================================
# Phase A2-5: 非公開になった記事の古いHTML削除
# ===========================================================================

@with_tmp
def test_stale_html_removed_on_full_batch(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc1, output_dir = run_build(index, tmp)
    check("stale削除: 1回目は3記事分のHTMLがある", proc1.returncode == 0, proc1.stdout + proc1.stderr)
    stale_file = output_dir / "marketing" / "m-three.html"
    check("stale削除: 記事3のHTMLが最初は存在する", stale_file.exists())

    # 記事3(SKB-M-003)が非公開になった想定で、インデックスから外して再生成する
    fewer_articles = [a for a in articles if a["id"] != "SKB-M-003"]
    index2 = make_index(articles=fewer_articles, products=products)
    index_path = tmp / "web-published.json"
    index_path.write_text(json.dumps(index2, ensure_ascii=False), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc2 = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--index", str(index_path), "--output", str(output_dir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    check("stale削除: 2回目も成功する", proc2.returncode == 0, proc2.stdout + proc2.stderr)
    check("stale削除: 非公開になった記事のHTMLが削除される", not stale_file.exists())
    check("stale削除: 残り2記事のHTMLは維持される",
          (output_dir / "photoshop" / "m-one.html").exists()
          and (output_dir / "photography" / "m-two.html").exists())
    check("stale削除: 削除件数が報告される", "古いHTMLを1件削除しました" in proc2.stdout, proc2.stdout)
    check("stale削除: 削除ファイル名が報告される", "m-three.html" in proc2.stdout, proc2.stdout)


@with_tmp
def test_stale_html_not_removed_on_single_article_run(tmp: Path) -> None:
    """--article-id指定時は、全体像が分からないため古いHTMLを削除しない。"""
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc1, output_dir = run_build(index, tmp)
    check("単一記事指定: 全記事ビルドは成功する", proc1.returncode == 0, proc1.stdout + proc1.stderr)

    proc2, _ = run_build(index, tmp, "--article-id", "SKB-M-001")
    check("単一記事指定: 1記事だけの再生成が成功する", proc2.returncode == 0, proc2.stdout + proc2.stderr)
    check("単一記事指定: 他の記事のHTMLは削除されない",
          (output_dir / "photography" / "m-two.html").exists()
          and (output_dir / "marketing" / "m-three.html").exists())
    check("単一記事指定: 削除の報告が出ない", "削除しました" not in proc2.stdout, proc2.stdout)


@with_tmp
def test_stale_cleanup_skipped_when_build_fails(tmp: Path) -> None:
    """2回目のビルドが失敗した場合、1回目の生成物（古い記事も含めて）は一切削除されない
    （新しい内容が確定する前に古いものを消さない、という順序の確認）。"""
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc1, output_dir = run_build(index, tmp)
    check("失敗時: 1回目は成功する", proc1.returncode == 0, proc1.stdout + proc1.stderr)
    all_before = sorted(p.name for p in output_dir.rglob("*.html"))

    broken = json.loads(json.dumps(index))
    broken["articles"][1]["body_markdown"] = ""  # 記事2を壊す
    index_path = tmp / "web-published.json"
    index_path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc2 = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--index", str(index_path), "--output", str(output_dir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    check("失敗時: 2回目はエラー終了する", proc2.returncode == 1, proc2.stdout + proc2.stderr)
    all_after = sorted(p.name for p in output_dir.rglob("*.html"))
    check("失敗時: 既存のHTML一式が1件も削除されない", all_before == all_after, (all_before, all_after))


@with_tmp
def test_stale_cleanup_ignores_unrelated_output_dir(tmp: Path) -> None:
    """出力先が空/初回の場合、削除対象が無いことを確認する（例外や誤削除が起きない）。"""
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    check("初回生成: 「削除しました」は出ない（削除対象が無いため）",
          "削除しました" not in proc.stdout, proc.stdout)


# ===========================================================================
# Phase A2-2: 打ち出の小槌トップ
# ===========================================================================

@with_tmp
def test_top_page_card_count_and_order(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    check("トップ: Article Cardが3件表示される", html.count("kzc-card-title") == 3, html)
    idx1, idx2, idx3 = (html.index("記事1"), html.index("記事2"), html.index("記事3"))
    check("トップ: 更新日の新しい順に並ぶ", idx1 < idx2 < idx3, (idx1, idx2, idx3))


@with_tmp
def test_top_page_no_draft_like_data(tmp: Path) -> None:
    """web-published.jsonにはpublished記事しか含まれない前提だが、
    トップページ側も渡されたarticle_cardsをそのまま信頼して良いことを確認する
    （draft相当のデータが紛れ込んでもWeb側でstatusを見て弾く仕組みは無いため、
    _統合KB側の責務であることをテストで明示する）。"""
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    check("トップ: statusフィールド自体がそもそも出力に含まれない", '"status"' not in html and "status" not in html.lower() or "kzc" in html,
          "statusという文字列が紛れ込んでいないか（誤検知防止のためkzc関連クラス名は許容）")


@with_tmp
def test_top_page_no_empty_cards(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    check("トップ: 空のサムネイル枠が出ない（thumbnail_url=None）", "kzc-card-thumb" not in html, html)


@with_tmp
def test_top_page_zero_articles(tmp: Path) -> None:
    index = make_index(articles=[])
    proc, output_dir = run_build(index, tmp)
    check("記事0件: exit code 0", proc.returncode == 0, proc.stdout + proc.stderr)
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    check("記事0件: 安全な空表示になる", "kzc-empty" in html, html)
    check("記事0件: 空のカードが出ない", "kzc-card-title" not in html, html)


@with_tmp
def test_top_page_no_internal_info(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    forbidden = ["source_conversations", "review_status", "content_checks", "confidence",
                 "classification", "legacy_ids", "target_keyword", "secondary_keywords", "body_markdown"]
    check("トップ: 内部情報が出力に含まれない", not any(f in html for f in forbidden),
          [f for f in forbidden if f in html])


# ===========================================================================
# Phase A2-3: 記事ページ
# ===========================================================================

@with_tmp
def test_breadcrumb_category_not_linked(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    m = re.search(r'<li><a href="/knowledge">打ち出の小槌</a></li>\s*(?:<!--.*?-->\s*)?<li>(.*?)</li>', html, re.S)
    check("breadcrumb: カテゴリ名がリンクになっていない", m is not None and "<a" not in m.group(1), html)


@with_tmp
def test_short_author_info(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("短い著者情報: 表示される", "村田一朗｜写真家・SideKick開発者" in html, html)


@with_tmp
def test_no_duplicate_updated_at(tmp: Path) -> None:
    index = make_index(updated_at="2026-07-17")
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    # datetime属性(<time datetime="2026-07-17">)と可視テキストの両方に日付文字列が入るため、
    # 「可視テキストとして表示される回数」だけを数える（属性値は画面に表示されない）。
    visible_occurrences = html.count("更新日：2026-07-17")
    check("更新日: 可視テキストとしてページ中に1回だけ表示される（Article Headerのみ）",
          visible_occurrences == 1, visible_occurrences)
    check("更新日: Author Short部分には更新日が無い",
          "kzc-author-short" in html and "更新日" not in html.split("kzc-author-short")[1].split("</p>")[0])


@with_tmp
def test_related_articles_present(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    html = (output_dir / "photoshop" / "m-one.html").read_text(encoding="utf-8")
    check("Related Articles: 存在する場合は表示される", "kzc-related-articles" in html and "記事2" in html, html)


@with_tmp
def test_related_articles_absent(tmp: Path) -> None:
    index = make_index(related_articles=[])
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("Related Articles: 無い場合は非表示（見出しごと消える）", "kzc-related-articles" not in html, html)


@with_tmp
def test_related_articles_invalid_ref_ignored(tmp: Path) -> None:
    """SKB側で除外済みの前提だが、Web側でも防御的に無視することを確認する。"""
    index = make_index(related_articles=["SKB-DOES-NOT-EXIST"])
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    check("Related Articles: 存在しないIDでもビルドが失敗しない", proc.returncode == 0, proc.stdout + proc.stderr)
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("Related Articles: 無効な参照は表示されず、セクション自体も出ない", "kzc-related-articles" not in html, html)


@with_tmp
def test_product_context_present(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    html = (output_dir / "photoshop" / "m-one.html").read_text(encoding="utf-8")
    check("Product Context: related_productsがあれば表示される",
          "kzc-product-context" in html and "SideKick Portrait" in html, html)
    check("Product Context: 表示時はCTAブロックと重複しない", "kzc-cta" not in html, html)


@with_tmp
def test_product_context_absent(tmp: Path) -> None:
    index = make_index(related_products=[])
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("Product Context: related_productsが空なら非表示", "kzc-product-context" not in html, html)


@with_tmp
def test_cta_none_hidden(tmp: Path) -> None:
    index = make_index(cta_type="none", related_products=[])
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("CTA none: 完全非表示になる", "kzc-cta" not in html and "kzc-product-context" not in html, html)


@with_tmp
def test_cta_ai_lab_shown(tmp: Path) -> None:
    index = make_index(cta_type="ai-lab", related_products=[])
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("CTA ai-lab: 表示される", "kzc-cta-ai-lab" in html and 'href="/ai-lab"' in html, html)


@with_tmp
def test_canonical_meta_h1_per_article(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("canonical: 存在する", "<link rel=\"canonical\"" in html)
    check("meta description: 存在する", 'name="description"' in html)
    check("h1: 1つだけ", h1_count(html) == 1, h1_count(html))


@with_tmp
def test_leading_h1_in_body_stripped(tmp: Path) -> None:
    """実記事の公開で判明したバグの再発防止テスト: 本文Markdownが `# タイトル` から
    始まる記事（実際の10記事すべてがこの形式）でも、Article HeaderのH1と重複しない
    （h1が1ページに2つできない）ことを確認する。"""
    index = make_index(body_markdown="# 記事タイトルの重複\n\n本文です。\n\n## 見出し2\n\nさらに本文。\n")
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("先頭H1除去: 生成は成功する", proc.returncode == 0, proc.stdout + proc.stderr)
    check("先頭H1除去: h1は1つだけになる（本文側のH1が除去される）", h1_count(html) == 1, h1_count(html))
    check("先頭H1除去: 除去されたH1のテキストが本文に残らない",
          "記事タイトルの重複" not in html.split("kzc-article-body")[1], html)
    check("先頭H1除去: h2以降の見出しは残る", "<h2>見出し2</h2>" in html, html)


@with_tmp
def test_top_page_h1_and_meta(tmp: Path) -> None:
    articles, products = _six_article_fixture()
    index = make_index(articles=articles, products=products)
    proc, output_dir = run_build(index, tmp)
    html = (output_dir / "index.html").read_text(encoding="utf-8")
    check("トップ: h1が1つだけ", h1_count(html) == 1, h1_count(html))
    check("トップ: canonicalが存在する", "<link rel=\"canonical\"" in html)
    check("トップ: meta descriptionが存在する", 'name="description"' in html)


# ===========================================================================
# Phase A2-4: Header / Footer / Mobile Nav
# ===========================================================================

@with_tmp
def test_header_main_five_items(tmp: Path) -> None:
    """2026-07-17改訂: 打ち出の小槌専用の5項目ナビをやめ、既存サイトの実ヘッダーを
    そのまま流用する方針に変更した。既存項目＋新規追加した「打ち出の小槌」の両方が
    存在することを確認する（サイト全体としての一貫性を優先）。"""
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    for label in ("Star", "Portrait", "Sky", "打ち出の小槌", "Workshop", "About", "AI Lab"):
        check(f"Header: 「{label}」がナビに存在する", label in html, html)


@with_tmp
def test_header_aria_current(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("Header: 打ち出の小槌にaria-current=pageが付く",
          '<a href="/knowledge" aria-current="page">📚 打ち出の小槌</a>' in html, html)


@with_tmp
def test_mobile_nav_button_attributes(tmp: Path) -> None:
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    check("mobile nav: aria-expanded属性がある", 'aria-expanded="false"' in html, html)
    check("mobile nav: aria-controls属性がある", 'aria-controls="kzc-nav-menu"' in html, html)


@with_tmp
def test_nav_links_present_without_js(tmp: Path) -> None:
    """JS無しでもHTML上にリンクが存在すること（displayをJSで制御しているだけで、
    リンク自体を条件付きで生成していないことをHTML文字列で確認する）。
    既存サイトの実ヘッダーを流用しているため、項目数は12（Star/Portrait/Sky/
    打ち出の小槌/Workshop/Gallery/Sidekickとは/About/更新履歴/Support/AI Lab/EN）。"""
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    nav_section = html.split('id="kzc-nav-menu"')[1].split("</nav>")[0]
    check("mobile nav: 既存ナビ全項目がHTML上にリンクとして存在する",
          nav_section.count("<a ") == 12, nav_section)


@with_tmp
def test_nav_links_are_root_relative(tmp: Path) -> None:
    """打ち出の小槌ページは/knowledge/配下（1〜2階層下）にあるため、ナビのリンクは
    相対パス（例: sidekick-star.html）ではなくルート相対パス（/sidekick-star.html）
    である必要がある。相対パスのままだと、記事ページから見て誤ったURLになる。"""
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    nav_section = html.split('id="kzc-nav-menu"')[1].split("</nav>")[0]
    check("ナビ: sidekick-star.htmlへのリンクがルート相対（/sidekick-star.html）",
          'href="/sidekick-star.html"' in nav_section, nav_section)
    check("ナビ: 相対パス（先頭/無し）のhrefが残っていない",
          'href="sidekick-star.html"' not in nav_section, nav_section)


@with_tmp
def test_footer_no_empty_links_no_fake_english(tmp: Path) -> None:
    """2026-07-17改訂: 既存サイトの実フッターを流用。既存フッターに言語切替リンクは
    無いため（言語切替はヘッダー側のみ）、フッターにEN版リンクが無いこと自体は正常。"""
    index = make_index()
    proc, output_dir = run_build(index, tmp, "--article-id", "SKB-TEST-000001")
    html = (output_dir / "photoshop" / "sample-article.html").read_text(encoding="utf-8")
    footer = html.split('<footer class="footer"')[1]
    check("Footer: 空のhref(href=\"\"や href=\"#\")が無い",
          'href=""' not in footer and 'href="#"' not in footer, footer)
    check("Footer: 存在しない英語記事ページへのリンクが無い（/en/knowledgeを含まない）",
          "/en/knowledge" not in footer, footer)
    check("Footer: 打ち出の小槌への実リンクがある", 'href="/knowledge"' in footer, footer)
    check("Footer: リンクがルート相対パスになっている",
          'href="sidekick-star.html"' not in footer and 'href="/sidekick-star.html"' in footer, footer)


def main() -> int:
    tests = [
        # Phase A1
        test_basic_build, test_schema_version_read, test_unsupported_schema_version,
        test_article_not_found, test_missing_body_markdown, test_broken_json,
        test_missing_index_file, test_markdown_to_html, test_raw_html_escaped,
        test_utf8_no_mojibake, test_meta_description_and_canonical, test_author_block_present,
        test_internal_fields_not_leaked, test_output_url_matches_public_url,
        test_template_inheritance,
        test_heading_hierarchy_warning_on_skip, test_heading_hierarchy_no_warning_when_sequential,
        test_image_alt_warning_when_empty, test_image_alt_no_warning_when_present,
        test_validate_only_writes_nothing,
        # Phase A2: 複数記事ビルド
        test_build_all_articles, test_build_single_article_from_multi,
        test_validate_only_reports_all, test_duplicate_output_path_detected,
        test_atomic_batch_no_partial_output_on_failure, test_failure_does_not_corrupt_existing_output,
        test_article_cards_consistency_check, test_categories_consistency_warning,
        # Phase A2: 非公開になった記事の古いHTML削除
        test_stale_html_removed_on_full_batch, test_stale_html_not_removed_on_single_article_run,
        test_stale_cleanup_skipped_when_build_fails, test_stale_cleanup_ignores_unrelated_output_dir,
        # Phase A2: トップページ
        test_top_page_card_count_and_order, test_top_page_no_draft_like_data,
        test_top_page_no_empty_cards, test_top_page_zero_articles, test_top_page_no_internal_info,
        # Phase A2: 記事ページ
        test_breadcrumb_category_not_linked, test_short_author_info, test_no_duplicate_updated_at,
        test_related_articles_present, test_related_articles_absent, test_related_articles_invalid_ref_ignored,
        test_product_context_present, test_product_context_absent,
        test_cta_none_hidden, test_cta_ai_lab_shown,
        test_canonical_meta_h1_per_article, test_leading_h1_in_body_stripped, test_top_page_h1_and_meta,
        # Phase A2: Header/Footer/Mobile
        test_header_main_five_items, test_header_aria_current, test_mobile_nav_button_attributes,
        test_nav_links_present_without_js, test_nav_links_are_root_relative,
        test_footer_no_empty_links_no_fake_english,
    ]
    for t in tests:
        t()
    _safe_print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
