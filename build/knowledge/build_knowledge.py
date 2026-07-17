#!/usr/bin/env python3
"""打ち出の小槌: web-published.json（_統合KB側が生成）から静的HTMLを生成するビルドスクリプト。

責任分界（_SideKick_Development/docs/COMPONENTS/10_PHASE0_DECISIONS.md セクション7・8）:
    _統合KB側 : 公開可否の判断・データ正規化・web-published.json生成（本文はMarkdown原文）
    このスクリプト: 公開インデックスを読み、Markdown本文をHTML化し、
                    Jinja2テンプレートへ流し込み、静的HTMLを出力する

Phase A2範囲: 打ち出の小槌トップ・複数記事の一括生成に対応。
既存の html/knowledge/ への実配置・Vercelへのデプロイは行わない
（--output に本番ディレクトリを直接指定しない運用とする）。

使い方:
    # 全記事 + トップページを生成
    python build/knowledge/build_knowledge.py --index data/knowledge/web-published.json --output build-output/knowledge

    # 1記事だけ生成
    python build/knowledge/build_knowledge.py --index data/knowledge/web-published.json --output build-output/knowledge --article-id SKB-ART-000001

    # 検証のみ（何も書き込まない）
    python build/knowledge/build_knowledge.py --index data/knowledge/web-published.json --output build-output/knowledge --validate-only
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from markdown_it import MarkdownIt

REPO_ROOT = Path(__file__).resolve().parents[2]  # sidekick-site（html/）のルート
TEMPLATES_DIR = REPO_ROOT / "templates" / "knowledge"
SUPPORTED_SCHEMA_VERSIONS = {1}
SITE_ORIGIN = "https://www.sidekick-lab.com"
MAX_RELATED_ARTICLES = 3

# _統合KB側が既に除外しているはずだが、Web側でも二重に確認する（防御的チェック）。
FORBIDDEN_FIELDS = {
    "review_status", "source_conversations", "source_files", "content_checks",
    "confidence", "classification", "classification_review", "migration_notes",
    "legacy_ids", "target_keyword", "secondary_keywords",
}

# 製品ごとの、文脈に自然な一言（機械的に同じ文言を使い回さない）。
PRODUCT_BRIDGE_TEXT = {
    "sidekick-star": "この工程を毎回手作業で繰り返しているなら、SideKick Starで自動化できます。",
    "sidekick-portrait": "この工程を毎回手作業で繰り返しているなら、SideKick Portraitで自動化できます。",
    "sidekick-sky-effect": "この工程を毎回手作業で繰り返しているなら、SideKick Sky Effectで自動化できます。",
    "_default": "この工程を繰り返しているなら、SideKickで自動化できる部分があります。",
}

KOZUCHI_TAGLINE = "写真を撮り、困り、試したことを残しています。"


class BuildError(Exception):
    """ユーザーに分かりやすいエラーメッセージとして扱う例外。"""


def render_markdown(text: str) -> str:
    """Markdown本文をHTML化する。html=Falseにより、本文中の生HTMLはエスケープされ、
    そのままの生HTMLとしては出力されない（安全側のデフォルト）。"""
    md = MarkdownIt("commonmark", {"html": False}).enable(["table"])
    return md.render(text)


def check_heading_hierarchy(body_markdown: str) -> list[str]:
    """本文中の見出しレベルが1段階を超えて飛んでいないかを確認する（警告のみ、生成は止めない）。
    記事本文の見出しはh2から始まる想定（h1はページタイトル用に予約されているため、
    基準となる直前レベルを1として扱う）。直前の見出しより深くなる方向への
    飛び越し（例: h2の次にh4）だけを検出する。浅くなる方向（h5の次にh2等）は正常な
    セクション区切りなので対象外。"""
    md = MarkdownIt("commonmark", {"html": False})
    tokens = md.parse(body_markdown)
    warnings = []
    prev_level = 1  # ページのh1を基準にする
    for t in tokens:
        if t.type == "heading_open":
            level = int(t.tag[1:])
            if level > prev_level + 1:
                warnings.append(
                    f"見出しレベルが飛んでいます: h{prev_level}の次にh{level}が出現しています"
                    f"（'{t.tag}'）"
                )
            prev_level = level
    return warnings


def check_image_alt_text(body_markdown: str) -> list[str]:
    """本文中の画像でalt未指定/空白のみのものを検出する（警告のみ、生成は止めない）。
    意味の無いダミーalt（'image'等）を自動で埋めることはしない
    （中身の無いalt文字列は、空alt以上に読み上げの妨げになりうるため）。"""
    md = MarkdownIt("commonmark", {"html": False})
    tokens = md.parse(body_markdown)
    warnings = []
    for t in tokens:
        if t.type == "inline" and t.children:
            for c in t.children:
                if c.type == "image" and not c.content.strip():
                    src = c.attrs.get("src", "?")
                    warnings.append(f"画像のalt属性が空です（説明文を追加してください）: {src}")
    return warnings


def load_index(path: Path) -> dict:
    if not path.exists():
        raise BuildError(f"公開インデックスが見つかりません: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise BuildError(f"公開インデックスがUTF-8として読めません: {path} ({exc})") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BuildError(f"公開インデックスのJSONが壊れています: {path} ({exc})") from exc

    version = data.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise BuildError(
            f"未対応のschema_version: {version!r}（対応: {sorted(SUPPORTED_SCHEMA_VERSIONS)}）"
        )
    for key in ("articles", "article_cards", "categories", "products"):
        if key not in data:
            raise BuildError(f"公開インデックスに必須キー{key!r}がありません")
    return data


def check_index_consistency(index: dict) -> list[str]:
    """article_cardsとの整合・categoriesとの整合を確認する。致命的な不整合は例外、
    軽微なものは警告として返す。"""
    warnings: list[str] = []

    article_ids = {a["id"] for a in index["articles"]}
    card_ids = {c["id"] for c in index["article_cards"]}
    missing_cards = article_ids - card_ids
    if missing_cards:
        raise BuildError(f"article_cardsに存在しない記事があります: {sorted(missing_cards)}")
    extra_cards = card_ids - article_ids
    if extra_cards:
        warnings.append(f"articlesに存在しないarticle_cardsがあります（無視します）: {sorted(extra_cards)}")

    category_keys = {(c["slug"], c["language"]) for c in index["categories"]}
    for a in index["articles"]:
        key = (a["category"]["slug"], a["language"])
        if key not in category_keys:
            warnings.append(f"{a['id']}: categoriesの集計に無いカテゴリ組み合わせです: {key}")

    return warnings


def assert_no_forbidden_fields(obj: dict, label: str) -> None:
    leaked = FORBIDDEN_FIELDS & set(obj.keys())
    if leaked:
        raise BuildError(f"{label}に内部フィールドが混入しています: {sorted(leaked)}")


def public_url_to_output_path(public_url: str, output_dir: Path) -> Path:
    """/knowledge/{category}/{slug} -> {output_dir}/{category}/{slug}.html
    /knowledge -> {output_dir}/index.html

    末尾スラッシュ無しURL（vercel.jsonのtrailingSlash:false）と整合する、
    フラットな.htmlファイル出力（既存サイトの全ページと同じ形式）。
    """
    parts = [p for p in public_url.strip("/").split("/") if p]
    if not parts or parts[0] not in ("knowledge",):
        # en/knowledge等、将来のprefixにも最低限対応する
        if len(parts) >= 2 and parts[1] == "knowledge":
            parts = parts[1:]
        else:
            raise BuildError(f"public_urlの形式が不正です（'knowledge'を含みません）: {public_url!r}")
    tail = parts[1:]
    if not tail:
        return output_dir / "index.html"
    *category_parts, slug = tail
    if not slug or "/" in slug:
        raise BuildError(f"slugが不正です: {slug!r}")
    return output_dir.joinpath(*category_parts, f"{slug}.html")


def build_env() -> Environment:
    if not TEMPLATES_DIR.exists():
        raise BuildError(f"テンプレートディレクトリが見つかりません: {TEMPLATES_DIR}")
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def resolve_related_articles(article: dict, articles_by_id: dict) -> list[dict]:
    """related_articlesの参照先を解決する。存在しないIDはSKB側で除外済みの前提だが、
    Web側でも防御的に無視する。0〜MAX_RELATED_ARTICLES件に絞る。"""
    result = []
    for rid in article.get("related_articles") or []:
        ra = articles_by_id.get(rid)
        if not ra:
            continue
        result.append({
            "id": ra["id"],
            "title": ra["title"],
            "meta_description": ra["meta_description"],
            "category_name": ra["category"]["name_ja"],
            "public_url": ra["public_url"],
        })
        if len(result) >= MAX_RELATED_ARTICLES:
            break
    return result


def resolve_product_context(article: dict, products_by_id: dict) -> dict | None:
    """related_productsが存在し、かつproductsデータにdetail_urlがある場合のみ返す。
    それ以外（related_productsが空／製品データが無い／detail_urlが無い）はNone。"""
    related = article.get("related_products") or []
    if not related:
        return None
    product = products_by_id.get(related[0])
    if not product or not product.get("detail_url"):
        return None
    return {
        "name": product["name"],
        "short_description": product["short_description"],
        "detail_url": product["detail_url"],
        "trial_url": product.get("trial_url") if article.get("cta_type") == "product-trial" else None,
        "bridge_text": PRODUCT_BRIDGE_TEXT.get(product["product_id"], PRODUCT_BRIDGE_TEXT["_default"]),
    }


def resolve_cta(article: dict, product_context: dict | None) -> dict | None:
    """cta_typeに応じたCTAブロックを決める。Product Context Blockが表示される場合は
    それ自体がCTAを兼ねるため、別のCTAは重ねて表示しない（1ページ1CTA原則）。"""
    if product_context:
        return None
    cta_type = article.get("cta_type") or "none"
    if cta_type == "ai-lab":
        return {
            "type": "ai-lab", "href": "/ai-lab", "label": "AI Labで確認する",
            "text": "このテーマをAIと一緒に確認する",
        }
    return None


def render_article(env: Environment, article: dict, index: dict) -> str:
    body_markdown = article.get("body_markdown")
    if not body_markdown or not body_markdown.strip():
        raise BuildError(f"{article.get('id')}: body_markdownが空です")

    body_html = render_markdown(body_markdown)

    try:
        template = env.get_template("article.html")
    except TemplateNotFound as exc:
        raise BuildError(f"Jinja2テンプレートが見つかりません: {exc}") from exc

    articles_by_id = {a["id"]: a for a in index["articles"]}
    products_by_id = {p["product_id"]: p for p in index.get("products", [])}

    related_articles = resolve_related_articles(article, articles_by_id)
    product_context = resolve_product_context(article, products_by_id)
    cta = resolve_cta(article, product_context)

    canonical_url = SITE_ORIGIN + article["public_url"]
    return template.render(
        article=article,
        body_html=body_html,
        canonical_url=canonical_url,
        language=article.get("language", "ja"),
        related_articles=related_articles,
        product_context=product_context,
        cta=cta,
        show_beginner_badge=(article.get("difficulty") == "beginner"),
        nav_current="knowledge",
    )


def render_index(env: Environment, index: dict, language: str = "ja") -> str:
    try:
        template = env.get_template("index.html")
    except TemplateNotFound as exc:
        raise BuildError(f"Jinja2テンプレートが見つかりません: {exc}") from exc

    cards = [c for c in index["article_cards"] if c.get("language") == language]
    cards.sort(key=lambda c: c.get("updated_at") or "", reverse=True)  # 更新日の新しい順

    canonical_url = SITE_ORIGIN + "/knowledge"
    return template.render(
        cards=cards,
        canonical_url=canonical_url,
        language=language,
        tagline=KOZUCHI_TAGLINE,
        nav_current="knowledge",
    )


def render_all(index: dict, article_id: str | None) -> dict[Path, str]:
    """出力先相対パス(Pathの形をした「output配下でのrelパス」)→HTML文字列 のdictを返す。
    途中で1件でも失敗したら例外を投げ、何も返さない（全体をやり直す前提）。"""
    warnings = check_index_consistency(index)
    for w in warnings:
        print(f"WARNING: {w}")

    for a in index["articles"]:
        assert_no_forbidden_fields(a, f"article {a.get('id')}")
    for c in index["article_cards"]:
        assert_no_forbidden_fields(c, f"article_card {c.get('id')}")

    env = build_env()
    targets = index["articles"]
    if article_id:
        targets = [a for a in targets if a["id"] == article_id]
        if not targets:
            raise BuildError(f"対象記事が見つかりません: {article_id!r}")

    for a in targets:
        body = a.get("body_markdown") or ""
        for w in check_heading_hierarchy(body):
            print(f"WARNING: {a.get('id')}: {w}")
        for w in check_image_alt_text(body):
            print(f"WARNING: {a.get('id')}: {w}")

    rendered: dict[Path, str] = {}
    seen_output_paths: dict[Path, str] = {}

    for article in targets:
        html = render_article(env, article, index)
        rel_path = public_url_to_output_path(article["public_url"], Path("."))
        if rel_path in seen_output_paths:
            raise BuildError(
                f"出力パスが重複しています: {rel_path}"
                f"（{seen_output_paths[rel_path]} と {article['id']}）"
            )
        seen_output_paths[rel_path] = article["id"]
        rendered[rel_path] = html

    if article_id is None:
        # トップページは全記事生成のときだけ併せて生成する
        rendered[Path("index.html")] = render_index(env, index)

    return rendered


def find_stale_html(output_dir: Path, rendered: dict[Path, str]) -> list[Path]:
    """output_dir配下の既存.htmlのうち、今回のrenderedに含まれないものを返す
    （非公開になった/カテゴリやslugが変わった記事の古い生成物）。
    output_dirは、このツールが生成したファイルだけを置く場所という前提に立つ
    （手動で置いた無関係な.htmlも対象になるため、--outputは共有しない）。"""
    if not output_dir.exists():
        return []
    keep = {(output_dir / rel_path).resolve() for rel_path in rendered}
    return [p for p in output_dir.rglob("*.html") if p.resolve() not in keep]


def stage_and_commit(rendered: dict[Path, str], output_dir: Path, cleanup_stale: bool) -> list[Path]:
    """一時ディレクトリへ全ファイルを書き出し、成功したら output_dir へ確定コピーする。
    途中で失敗した場合、output_dirには一切触れない（既存の出力を壊さない）。

    cleanup_stale=Trueのとき（全記事一括生成時のみ）、新しい内容の確定コピーが
    すべて成功した後に、今回のrenderedに含まれない古い.htmlを削除する
    （新しい内容の書き込みより前には絶対に削除しない＝失敗時に「消えただけ」を防ぐ順序）。
    削除したファイルの一覧を返す（cleanup_stale=Falseなら常に空リスト）。"""
    staging = output_dir.parent / f".build-staging-{uuid.uuid4().hex}"
    try:
        for rel_path, html in rendered.items():
            target = staging / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html, encoding="utf-8")

        output_dir.mkdir(parents=True, exist_ok=True)
        for rel_path in rendered:
            src = staging / rel_path
            dst = output_dir / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            # 一時ファイル経由でatomicに確定する（同一ボリューム上のstagingからの移動）
            fd, tmp_name = tempfile.mkstemp(dir=str(dst.parent), prefix=".tmp-knowledge-", suffix=".html")
            os.close(fd)
            shutil.copyfile(src, tmp_name)
            os.replace(tmp_name, str(dst))
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    if not cleanup_stale:
        return []

    removed = []
    for stale_path in find_stale_html(output_dir, rendered):
        stale_path.unlink()
        removed.append(stale_path)
    return removed


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="打ち出の小槌 静的HTMLビルド")
    p.add_argument("--index", required=True, help="web-published.jsonのパス")
    p.add_argument("--output", required=True,
                   help="出力先ディレクトリ。本番のhtml/knowledge/を直接指定しないこと"
                        "（Phase A2ではローカル確認用ディレクトリを指定する運用とする）")
    p.add_argument("--article-id", default=None, help="生成する記事ID。省略時は全記事+トップページを生成")
    p.add_argument("--validate-only", action="store_true", help="ファイルを書かず、生成可能かのみ確認する")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        index = load_index(Path(args.index))
        rendered = render_all(index, args.article_id)
    except BuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - 想定外の例外も壊れた出力を残さず終了する
        print(f"ERROR: 予期しないエラー: {exc}", file=sys.stderr)
        return 1

    if args.validate_only:
        total_chars = sum(len(h) for h in rendered.values())
        print(f"[ok] validate-only: {len(rendered)}ページを生成可能です（合計{total_chars}文字）")
        for rel_path in sorted(rendered):
            print(f"  - {rel_path}")
        return 0

    output_dir = Path(args.output)
    # 古いHTMLの削除は、全記事一括生成のとき（=今回のrenderedが公開状態の全体を
    # 正しく表している）のときだけ行う。--article-id指定時は一部しか分からないため行わない。
    cleanup_stale = args.article_id is None
    try:
        removed = stage_and_commit(rendered, output_dir, cleanup_stale)
    except OSError as exc:
        print(f"ERROR: 出力先へ書き込めません: {exc}", file=sys.stderr)
        return 1

    print(f"[done] {len(rendered)}ページを生成しました -> {output_dir}")
    for rel_path in sorted(rendered):
        print(f"  - {rel_path}")
    if removed:
        print(f"[done] 非公開になった記事の古いHTMLを{len(removed)}件削除しました")
        for p in sorted(removed):
            print(f"  - {p.relative_to(output_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
