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
import re
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

KOZUCHI_TAGLINE = "写真を撮り、困り、試したことを残しています。"

TITLE_SEPARATOR = "｜"

# 2026-07-21追加: トップページの「おすすめ記事」手動選定ファイル。
# _統合KB側が生成するweb-published.jsonとは別の、サイト側だけで完結する設定ファイル
# （_統合KBのパイプライン・記事frontmatterには一切触れない）。
# アクセス解析による「人気記事」を安全に取得できる既存の仕組みが無いため、
# 架空の閲覧数・人気順位を作らず、村田さんが直接編集できる手動キュレーションにした。
PICKUP_CONFIG_PATH = REPO_ROOT / "data" / "knowledge" / "pickup.json"
NEW_ARRIVALS_LIMIT = 3
PICKUP_LIMIT = 3

# 英語版Knowledgeページの固定文言。JA版の文言はテンプレート側の既存の埋め込み文字列を
# そのまま維持し、この辞書経由には切り替えていない（JA出力の無変更を優先するため）。
# EN版レンダリング時にのみ、このLABELS["en"]をテンプレートへ渡す。
LABELS = {
    "en": {
        "site_name": "Knowledge",
        "tagline": "Taking photos, running into problems, and keeping a record of what I tried.",
        "about_heading": "About Knowledge",
        "about_body_1": (
            "This is where I keep a record of the problems I've actually run into in the field, "
            "what I tried, and what I learned — so I don't forget."
        ),
        "about_body_2": "I'm sharing it as-is with anyone who might need it.",
        "about_link": "Read About →",
        "about_href": "/en/about",
        "empty_list": "No articles have been published yet.",
        "breadcrumb_top": "Knowledge",
        "knowledge_top_url": "/en/knowledge",
        "updated_label": "Updated: ",
        "beginner_badge": "Beginner-friendly",
        "author_short": "Ichiro Murata · Photographer / SideKick Developer",
        "related_heading": "Related Articles",
        "product_context_label": "Related SideKick Product",
        "product_detail_link": "See details →",
        "product_trial_link": "Try it free →",
        "author_block_heading": "About the Author",
        "author_block_body": (
            "Ichiro Murata is a photographer and the developer of SideKick. This article is "
            "written from his hands-on experience shooting, retouching, critiquing, and developing. "
            "AI is used to help organize past logs and draft the text, but the final review, edits, "
            "and publish decisions are always his own."
        ),
        "ai_lab_cta_text": "Explore this topic together with AI",
        "ai_lab_cta_label": "Check it out on AI Lab",
        "ai_lab_href": "/en/ai-lab",
        "title_suffix": " | Knowledge - SideKick",
        "index_title": "Knowledge | SideKick",
        "index_meta_description": (
            "A knowledge library photographers can turn to when they run into problems with "
            "shooting, developing, or Photoshop. A record of real problems and what was tried."
        ),
        # 2026-07-21追加: トップページ構成変更（カテゴリナビ・新着・おすすめ・カテゴリ別一覧）
        "category_nav_label": "Categories",
        "category_nav_all": "All",
        "new_arrivals_eyebrow": "NEW",
        "new_arrivals_heading": "New Articles",
        "pickup_eyebrow": "PICK UP",
        "pickup_heading": "Featured Articles",
        "all_articles_heading": "All Articles",
        "published_label": "Published: ",
        "article_count_suffix": " articles",
    },
}

# products.yaml にはEN name/descriptionが無いため、公開先URLと同様にここで明示的に
# マッピングする（PRODUCT_URLS的な既存パターンを踏襲。将来products.yaml側にEN
# フィールドを追加する場合はこのマッピングを廃止する）。
PRODUCT_EN_OVERRIDES = {
    "sidekick-star": {
        "name": "SideKick Star",
        "short_description": (
            "Automates star-trail Lighten composites, Milky Way enhancement, "
            "and aircraft-trail removal."
        ),
        "detail_url": "/en/sidekick-star",
        "trial_url": "/en/ai-lab",
    },
    "sidekick-portrait": {
        "name": "SideKick Portrait",
        "short_description": "Automates portrait retouching (15 styles x 3 intensity levels).",
        "detail_url": "/en/portrait",
        "trial_url": "/en/ai-lab",
    },
    "sidekick-sky-effect": {
        "name": "SideKick Sky Effect",
        "short_description": (
            "Composites sky and ground using two different white balances for natural-looking finishing."
        ),
        "detail_url": "/en/sky-effect",
        "trial_url": "/en/ai-lab",
    },
}


class BuildError(Exception):
    """ユーザーに分かりやすいエラーメッセージとして扱う例外。"""


def render_markdown(text: str) -> str:
    """Markdown本文をHTML化する。html=Falseにより、本文中の生HTMLはエスケープされ、
    そのままの生HTMLとしては出力されない（安全側のデフォルト）。"""
    md = MarkdownIt("commonmark", {"html": False}).enable(["table"])
    return md.render(text)


LEADING_H1_RE = re.compile(r"^\s*#[ \t]+[^\n]*\n+")


def strip_leading_h1(body_markdown: str) -> str:
    """本文Markdownの先頭が単一の#見出し（h1）の場合は取り除く。
    Article HeaderのH1（記事タイトル、front matterのtitle）と重複してしまうため
    （実際の記事10本すべてが本文冒頭に`# タイトル`を含んでおり、そのままレンダリングすると
    1ページにh1が2つできてしまうことが実記事の公開で判明した）。##以降（h2+）は対象外。"""
    return LEADING_H1_RE.sub("", body_markdown, count=1)


def split_title(title: str) -> tuple[str, str | None]:
    """記事タイトルを「メイン｜サブ」の形式で分割する（表示専用。SEO用のtitleタグ・
    meta description・canonical等はfront matterのtitleをそのまま使い、一切変更しない）。
    現在の全記事のtitleが「メイン｜サブ」形式のため、H1をメイン/サブタイトルに分けて
    表示することで読みやすくする。区切り文字「｜」が無い記事はそのまま1本のタイトルとして返す
    （後方互換）。"""
    if TITLE_SEPARATOR not in title:
        return title, None
    main, _, sub = title.partition(TITLE_SEPARATOR)
    main, sub = main.strip(), sub.strip()
    if not main or not sub:
        return title, None
    return main, sub


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
    /en/knowledge/{category}/{slug} -> {output_dir}/../en/knowledge/{category}/{slug}.html
    /en/knowledge -> {output_dir}/../en/knowledge/index.html

    末尾スラッシュ無しURL（vercel.jsonのtrailingSlash:false）と整合する、
    フラットな.htmlファイル出力（既存サイトの全ページと同じ形式）。

    --outputは本番のhtml/knowledge/に対応するディレクトリという既存の約束を維持する
    （日本語の出力先・運用フローを変更しないため）。英語版は本番html/en/knowledge/に
    対応する必要があり、html/knowledge/の配下ではなく兄弟ディレクトリになるため、
    output_dirから見て".."で一段上がった先の"en/knowledge/"を指す相対パスを返す
    （2026-07-20 英語Knowledge公開機能）。
    """
    parts = [p for p in public_url.strip("/").split("/") if p]
    prefix: list[str] = []
    if parts and parts[0] == "en":
        prefix = ["..", "en", "knowledge"]
        parts = parts[1:]
    if not parts or parts[0] != "knowledge":
        raise BuildError(f"public_urlの形式が不正です（'knowledge'を含みません）: {public_url!r}")
    tail = parts[1:]
    if not tail:
        return output_dir.joinpath(*prefix, "index.html")
    *category_parts, slug = tail
    if not slug or "/" in slug:
        raise BuildError(f"slugが不正です: {slug!r}")
    return output_dir.joinpath(*prefix, *category_parts, f"{slug}.html")


def build_env() -> Environment:
    if not TEMPLATES_DIR.exists():
        raise BuildError(f"テンプレートディレクトリが見つかりません: {TEMPLATES_DIR}")
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def category_display_name(category: dict, language: str) -> str:
    """カテゴリ名を言語に応じて出し分ける（en=英語name、ja=name_ja）。"""
    if language == "en":
        return category.get("name") or category.get("name_ja")
    return category.get("name_ja")


def _recency_sort_key(card: dict) -> tuple[str, str]:
    """公開日（published_at）の新しい順に並べるためのソートキー。published_atが
    完全に同一の記事が複数存在する現状データでも、実行のたびに順序が変わらないよう、
    記事IDを最終的なタイブレークに使う（2026-07-21追加、村田さんの明示要件）。"""
    return (card.get("published_at") or "", card.get("id") or "")


def build_category_groups(cards: list[dict], categories: list[dict], language: str) -> list[dict]:
    """cardsをカテゴリ別にグループ化する。カテゴリはarticle_cardsに実際に記事がある
    ものだけを対象にする（taxonomy全体を舐めない）ため、カテゴリを追加すれば
    自動的に表示され、記事が0件のカテゴリは表示されない。各カテゴリ内は
    公開日の新しい順（_recency_sort_keyで安定ソート）。カテゴリの表示順は、
    web-published.json側が既に採用しているslugのアルファベット順（categoriesの
    既存の並び）に合わせる。"""
    slug_by_name = {c["name"]: c["slug"] for c in categories if c.get("language") == language}
    slug_order = [c["slug"] for c in categories if c.get("language") == language]

    groups: dict[str, dict] = {}
    for card in cards:
        name = card["category_name"]
        slug = slug_by_name.get(name, name)
        if slug not in groups:
            groups[slug] = {"slug": slug, "name": name, "cards": []}
        groups[slug]["cards"].append(card)

    for g in groups.values():
        g["cards"].sort(key=_recency_sort_key, reverse=True)
        g["count"] = len(g["cards"])

    ordered_slugs = [s for s in slug_order if s in groups]
    ordered_slugs += sorted(s for s in groups if s not in ordered_slugs)  # 念のための保険
    return [groups[s] for s in ordered_slugs]


def load_pickup_config(language: str, config_path: Path | None = None) -> list[str]:
    """村田さんが手動で選ぶ「おすすめ記事」のID列を読む。ファイルが無い・壊れている・
    該当言語のキーが無い場合は空リスト（=未選定）を返す（fail-closed、ページ全体は
    壊さない）。_統合KB側のパイプラインやフロントマターには一切触れない、
    サイト側だけで完結する設定ファイル。config_pathはテストがtempfile上の
    独自ファイルを指定できるようにするための差し替え口（省略時は本番の
    PICKUP_CONFIG_PATHを使う）。"""
    path = config_path if config_path is not None else PICKUP_CONFIG_PATH
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    ids = data.get(language)
    if not isinstance(ids, list):
        return []
    return [i for i in ids if isinstance(i, str)]


def build_new_arrivals_and_pickup(
    cards_by_recency: list[dict], pickup_ids: list[str],
) -> tuple[list[dict], list[dict]]:
    """「新着記事」（公開日の新しい順に最大NEW_ARRIVALS_LIMIT件）と、
    「おすすめ記事」（pickup.jsonでの手動指定を優先し、指定が無い／不足する分は、
    新着記事と重複しない範囲で公開日の新しい記事から自動補完する）を組み立てる。
    アクセス解析による「人気記事」を安全に取得できる既存の仕組みが無いため、
    架空の閲覧数・人気順位は作らない（2026-07-21、村田さんの明示要件）。"""
    new_arrivals = cards_by_recency[:NEW_ARRIVALS_LIMIT]
    new_arrival_ids = {c["id"] for c in new_arrivals}

    by_id = {c["id"]: c for c in cards_by_recency}
    pickup: list[dict] = []
    seen: set[str] = set()
    for aid in pickup_ids:
        card = by_id.get(aid)
        if card and card["id"] not in seen:
            pickup.append(card)
            seen.add(card["id"])
        if len(pickup) >= PICKUP_LIMIT:
            break
    if len(pickup) < PICKUP_LIMIT:
        for card in cards_by_recency:
            if card["id"] in seen or card["id"] in new_arrival_ids:
                continue
            pickup.append(card)
            seen.add(card["id"])
            if len(pickup) >= PICKUP_LIMIT:
                break

    return new_arrivals, pickup


def resolve_related_articles(article: dict, articles_by_id: dict) -> list[dict]:
    """related_articlesの参照先を解決する。存在しないIDはSKB側で除外済みの前提だが、
    Web側でも防御的に無視する。0〜MAX_RELATED_ARTICLES件に絞る。"""
    language = article.get("language", "ja")
    result = []
    for rid in article.get("related_articles") or []:
        ra = articles_by_id.get(rid)
        if not ra:
            continue
        result.append({
            "id": ra["id"],
            "title": ra["title"],
            "meta_description": ra["meta_description"],
            "category_name": category_display_name(ra["category"], language),
            "public_url": ra["public_url"],
        })
        if len(result) >= MAX_RELATED_ARTICLES:
            break
    return result


def resolve_product_context(article: dict, products_by_id: dict) -> dict | None:
    """related_productsが存在し、かつproductsデータにdetail_urlがある場合のみ返す。
    それ以外（related_productsが空／製品データが無い／detail_urlが無い）はNone。

    2026-07-17改訂: 自動生成の「橋渡し文」は廃止した。本文の書き手（村田さん）が
    すでに文脈の中で自然に製品へ触れている記事が多く、機械的な橋渡し文がそれと
    ほぼ同じ内容を重複して表示してしまう問題があったため。中立的な参照ブロックとして、
    製品名・説明・リンクのみを提示する（見出しはテンプレート側で固定文言を付ける）。

    EN記事の場合、products.yamlにEN name/descriptionが無いため、PRODUCT_EN_OVERRIDES
    （このファイル冒頭）で明示的に上書きする。"""
    related = article.get("related_products") or []
    if not related:
        return None
    product = products_by_id.get(related[0])
    if not product or not product.get("detail_url"):
        return None

    name = product["name"]
    short_description = product["short_description"]
    detail_url = product["detail_url"]
    trial_url = product.get("trial_url") if article.get("cta_type") == "product-trial" else None

    if article.get("language") == "en":
        override = PRODUCT_EN_OVERRIDES.get(related[0])
        if not override:
            return None
        name = override["name"]
        short_description = override["short_description"]
        detail_url = override["detail_url"]
        trial_url = override["trial_url"] if trial_url else None

    return {
        "name": name,
        "short_description": short_description,
        "detail_url": detail_url,
        "trial_url": trial_url,
    }


def resolve_cta(article: dict, product_context: dict | None, labels: dict | None) -> dict | None:
    """cta_typeに応じたCTAブロックを決める。Product Context Blockが表示される場合は
    それ自体がCTAを兼ねるため、別のCTAは重ねて表示しない（1ページ1CTA原則）。"""
    if product_context:
        return None
    cta_type = article.get("cta_type") or "none"
    if cta_type != "ai-lab":
        return None
    if article.get("language") == "en" and labels:
        return {
            "type": "ai-lab", "href": labels["ai_lab_href"], "label": labels["ai_lab_cta_label"],
            "text": labels["ai_lab_cta_text"],
        }
    return {
        "type": "ai-lab", "href": "/ai-lab", "label": "AI Labで確認する",
        "text": "このテーマをAIと一緒に確認する",
    }


def compute_hreflang_alternates(article: dict, articles_by_id: dict) -> dict[str, str]:
    """記事のhreflang代替URL（{lang: 絶対URL}）を計算する。対応する翻訳が
    存在しない場合は空dictを返す（存在しないURLを出力しないため、村田さんの明示要件）。
    source_article_idで日本語記事と英語記事を対応付ける。"""
    language = article.get("language", "ja")
    if language == "ja":
        en_match = next(
            (a for a in articles_by_id.values()
             if a.get("language") == "en" and a.get("source_article_id") == article["id"]),
            None,
        )
        if not en_match:
            return {}
        return {
            "ja": SITE_ORIGIN + article["public_url"],
            "en": SITE_ORIGIN + en_match["public_url"],
        }
    if language == "en":
        ja_id = article.get("source_article_id")
        ja_match = articles_by_id.get(ja_id) if ja_id else None
        if not ja_match:
            return {}
        return {
            "ja": SITE_ORIGIN + ja_match["public_url"],
            "en": SITE_ORIGIN + article["public_url"],
        }
    return {}


def compute_lang_switch_url(article: dict, articles_by_id: dict) -> str:
    """Header/Footerの言語切替リンク（🇺🇸 EN / 🇯🇵 JA）の遷移先を計算する
    （2026-07-20追加、村田さんの明示要件）。対応する翻訳記事が存在する場合は
    その記事へ、存在しない場合は切替先言語のKnowledgeトップページへフォールバックする
    （存在しないURLにはしない）。"""
    language = article.get("language", "ja")
    if language == "en":
        ja_id = article.get("source_article_id")
        ja_match = articles_by_id.get(ja_id) if ja_id else None
        return ja_match["public_url"] if ja_match else "/knowledge"

    en_match = next(
        (a for a in articles_by_id.values()
         if a.get("language") == "en" and a.get("source_article_id") == article.get("id")),
        None,
    )
    return en_match["public_url"] if en_match else "/en/knowledge"


def render_article(env: Environment, article: dict, index: dict) -> str:
    body_markdown = article.get("body_markdown")
    if not body_markdown or not body_markdown.strip():
        raise BuildError(f"{article.get('id')}: body_markdownが空です")

    body_html = render_markdown(strip_leading_h1(body_markdown))

    try:
        template = env.get_template("article.html")
    except TemplateNotFound as exc:
        raise BuildError(f"Jinja2テンプレートが見つかりません: {exc}") from exc

    language = article.get("language", "ja")
    articles_by_id = {a["id"]: a for a in index["articles"]}
    products_by_id = {p["product_id"]: p for p in index.get("products", [])}
    labels = LABELS.get(language)

    related_articles = resolve_related_articles(article, articles_by_id)
    product_context = resolve_product_context(article, products_by_id)
    cta = resolve_cta(article, product_context, labels)
    title_main, title_sub = split_title(article["title"])
    hreflang_alternates = compute_hreflang_alternates(article, articles_by_id)
    category_name = category_display_name(article["category"], language)

    # Header/Footerの言語切替リンク（🇺🇸 EN / 🇯🇵 JA）の遷移先。対応する翻訳記事が
    # あれば記事単位で正確にリンクし、無ければ切替先言語のKnowledgeトップへ
    # フォールバックする（存在しないURLにはしない、2026-07-20村田さんの明示要件）。
    lang_switch_url = compute_lang_switch_url(article, articles_by_id)

    canonical_url = SITE_ORIGIN + article["public_url"]
    return template.render(
        article=article,
        body_html=body_html,
        canonical_url=canonical_url,
        language=language,
        labels=labels,
        category_name=category_name,
        related_articles=related_articles,
        product_context=product_context,
        cta=cta,
        show_beginner_badge=(article.get("difficulty") == "beginner"),
        nav_current="knowledge",
        title_main=title_main,
        title_sub=title_sub,
        hreflang_alternates=hreflang_alternates,
        knowledge_top_url=("/en/knowledge" if language == "en" else "/knowledge"),
        lang_switch_url=lang_switch_url,
    )


def render_index(env: Environment, index: dict, language: str = "ja",
                  pickup_config_path: Path | None = None) -> str:
    try:
        template = env.get_template("index.html")
    except TemplateNotFound as exc:
        raise BuildError(f"Jinja2テンプレートが見つかりません: {exc}") from exc

    cards = [c for c in index["article_cards"] if c.get("language") == language]
    cards_by_recency = sorted(cards, key=_recency_sort_key, reverse=True)

    # 2026-07-21追加: カテゴリナビ・新着記事・おすすめ記事・カテゴリ別一覧。
    # カテゴリ分けは既存のカテゴリ名を正規化し直すのではなく、web-published.json側が
    # 既に正規化済みのcategory_name/categoriesをそのまま使う（記事データからの自動集計）。
    category_groups = build_category_groups(cards, index.get("categories", []), language)
    pickup_ids = load_pickup_config(language, pickup_config_path)
    new_arrivals, pickup = build_new_arrivals_and_pickup(cards_by_recency, pickup_ids)

    top_path = "/en/knowledge" if language == "en" else "/knowledge"
    canonical_url = SITE_ORIGIN + top_path
    # トップページのhreflangは、日本語・英語トップが両方生成される前提で常に両方を出す
    # （全記事一括ビルドではja/en両方のindexを必ず併せて生成するため、常に有効なURLになる）。
    hreflang_alternates = {"ja": SITE_ORIGIN + "/knowledge", "en": SITE_ORIGIN + "/en/knowledge"}
    return template.render(
        cards=cards,
        total_count=len(cards),
        category_groups=category_groups,
        new_arrivals=new_arrivals,
        pickup=pickup,
        canonical_url=canonical_url,
        language=language,
        labels=LABELS.get(language),
        tagline=KOZUCHI_TAGLINE,
        nav_current="knowledge",
        hreflang_alternates=hreflang_alternates,
        knowledge_top_url=top_path,
        lang_switch_url=("/knowledge" if language == "en" else "/en/knowledge"),
    )


def render_all(index: dict, article_id: str | None,
                pickup_config_path: Path | None = None) -> dict[Path, str]:
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
        body = strip_leading_h1(a.get("body_markdown") or "")
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
        # トップページは全記事生成のときだけ併せて生成する。日本語・英語トップは
        # 常に両方生成する（英語記事が0件でも、空状態のen/knowledge/index.htmlを生成する。
        # render_index()のhreflangが常に両トップURLの存在を前提にしているため）。
        # 出力パスはpublic_url_to_output_path()と同じ規約（英語版は".."でoutput_dirの
        # 兄弟ディレクトリen/knowledge/へ escape する）に合わせる。
        rendered[Path("index.html")] = render_index(env, index, language="ja",
                                                      pickup_config_path=pickup_config_path)
        rendered[Path("..", "en", "knowledge", "index.html")] = render_index(
            env, index, language="en", pickup_config_path=pickup_config_path)

    return rendered


def find_stale_html(output_dir: Path, rendered: dict[Path, str]) -> list[Path]:
    """output_dir配下、および英語版の出力先（output_dirの兄弟ディレクトリ en/knowledge/）
    の既存.htmlのうち、今回のrenderedに含まれないものを返す
    （非公開になった/カテゴリやslugが変わった記事の古い生成物）。
    output_dirは、このツールが生成したファイルだけを置く場所という前提に立つ
    （手動で置いた無関係な.htmlも対象になるため、--outputは共有しない）。同様に
    output_dirの兄弟の en/knowledge/ も、このツールが生成した英語版ファイルだけを
    置く場所という前提に立つ（2026-07-20 英語Knowledge公開機能）。"""
    keep = {(output_dir / rel_path).resolve() for rel_path in rendered}
    roots = [output_dir, output_dir.parent / "en" / "knowledge"]
    stale: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        stale.extend(p for p in root.rglob("*.html") if p.resolve() not in keep)
    return stale


def _safe_staging_subpath(rel_path: Path) -> Path:
    """英語版の出力先（output_dirの兄弟ディレクトリ en/knowledge/）を指す".."を含む
    相対パスであっても、ステージング領域の外へ書き出さないよう安全な代替パスへ退避する
    （2026-07-20 英語Knowledge公開機能。".."をそのまま使うとステージング段階で
    いきなり本番相当のディレクトリへ書き込んでしまい、atomicにならないため）。"""
    safe_parts = ["__up__" if p == ".." else p for p in rel_path.parts]
    return Path(*safe_parts)


def stage_and_commit(rendered: dict[Path, str], output_dir: Path, cleanup_stale: bool) -> list[Path]:
    """一時ディレクトリへ全ファイルを書き出し、成功したら output_dir （日本語版）および
    その兄弟ディレクトリ en/knowledge/ （英語版）へ確定コピーする。途中で失敗した場合、
    output_dir・en/knowledge/のどちらにも一切触れない（既存の出力を壊さない）。

    cleanup_stale=Trueのとき（全記事一括生成時のみ）、新しい内容の確定コピーが
    すべて成功した後に、今回のrenderedに含まれない古い.htmlを削除する
    （新しい内容の書き込みより前には絶対に削除しない＝失敗時に「消えただけ」を防ぐ順序）。
    削除したファイルの一覧を返す（cleanup_stale=Falseなら常に空リスト）。"""
    staging = output_dir.parent / f".build-staging-{uuid.uuid4().hex}"
    try:
        for rel_path, html in rendered.items():
            target = staging / _safe_staging_subpath(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html, encoding="utf-8")

        output_dir.mkdir(parents=True, exist_ok=True)
        for rel_path in rendered:
            src = staging / _safe_staging_subpath(rel_path)
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
    p.add_argument("--pickup-config", default=None,
                   help="「おすすめ記事」手動選定ファイルのパス。省略時はdata/knowledge/pickup.json"
                        "（テストがtempfile上の独自ファイルを指定できるようにするための差し替え口）")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    pickup_config_path = Path(args.pickup_config) if args.pickup_config else None
    try:
        index = load_index(Path(args.index))
        rendered = render_all(index, args.article_id, pickup_config_path=pickup_config_path)
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
