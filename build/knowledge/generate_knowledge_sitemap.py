#!/usr/bin/env python3
"""打ち出の小槌: web-published.json からKnowledge記事のURLを抽出し、
sitemap.xmlへ反映するCLI。

背景: sitemap.xmlはこれまで手動管理されており、Knowledge記事のURLを
登録する工程が存在しなかった（最初の記事公開以降、一度も反映されていなかった）。
このスクリプトはweb-published.json（_統合KB側が生成する唯一の公開インデックス）
を入力に、Knowledge記事のURLを機械的に導出し、sitemap.xml内の該当セクション
だけを更新する。

sitemap.xml中の非Knowledge項目（LP・製品ページ・AI Lab等、手動管理のまま）は
一切変更しない。Knowledge項目は
    <!-- BEGIN AUTO-GENERATED KNOWLEDGE URLS (generate_knowledge_sitemap.py) -->
    ...
    <!-- END AUTO-GENERATED KNOWLEDGE URLS -->
というマーカーコメントで囲まれた範囲としてのみ管理し、再実行しても重複しない
（既存のマーカー範囲を丸ごと置き換えるだけ）。マーカーが無い場合は
</urlset>の直前へ新規挿入する。

使い方:
    python build/knowledge/generate_knowledge_sitemap.py \
        --index data/knowledge/web-published.json --sitemap sitemap.xml
    python build/knowledge/generate_knowledge_sitemap.py \
        --index data/knowledge/web-published.json --sitemap sitemap.xml --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SITE_ORIGIN = "https://www.sidekick-lab.com"
SUPPORTED_SCHEMA_VERSIONS = {1}

MARKER_BEGIN = "<!-- BEGIN AUTO-GENERATED KNOWLEDGE URLS (generate_knowledge_sitemap.py) -->"
MARKER_END = "<!-- END AUTO-GENERATED KNOWLEDGE URLS -->"

# 既存sitemap.xmlの他ページ（/gallery・/workshop等の情報系ページ）の優先度体系に
# 合わせた値。Knowledgeトップは記事一覧ページとして/galleryと同程度、個別記事は
# /faqと同程度に位置づけた（村田さんの確認を推奨、暫定値）。
TOP_PRIORITY = {"ja": "0.6", "en": "0.5"}
ARTICLE_PRIORITY = {"ja": "0.5", "en": "0.4"}


class SitemapError(Exception):
    """ユーザーに分かりやすいエラーメッセージとして扱う例外。"""


def load_articles(index_path: Path) -> list[dict]:
    if not index_path.exists():
        raise SitemapError(f"web-published.jsonが見つかりません: {index_path}")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise SitemapError(f"未対応のschema_versionです: {schema_version!r}")
    return data.get("articles") or []


def build_knowledge_urls(articles: list[dict]) -> list[dict]:
    """記事一覧から、sitemap用のURLエントリ（loc/lastmod/priority）を
    言語別トップページ＋各記事分だけ作る。存在する言語のトップページのみ
    含める（例: en記事が無ければ/en/knowledgeは含めない。推測で含めない）。"""
    languages_present: set[str] = set()
    entries: list[dict] = []

    for art in articles:
        lang = art.get("language")
        public_url = art.get("public_url")
        if lang not in ("ja", "en") or not public_url:
            continue
        languages_present.add(lang)
        lastmod = art.get("updated_at") or art.get("published_at") or art.get("created_at")
        entries.append({
            "loc": f"{SITE_ORIGIN}{public_url}",
            "lastmod": lastmod,
            "priority": ARTICLE_PRIORITY[lang],
        })

    for lang in sorted(languages_present):
        top_path = "/en/knowledge" if lang == "en" else "/knowledge"
        entries.append({
            "loc": f"{SITE_ORIGIN}{top_path}",
            "lastmod": None,
            "priority": TOP_PRIORITY[lang],
        })

    entries.sort(key=lambda e: e["loc"])
    return entries


def render_url_block(entries: list[dict]) -> str:
    lines = [MARKER_BEGIN]
    for e in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{e['loc']}</loc>")
        if e["lastmod"]:
            lines.append(f"    <lastmod>{e['lastmod']}</lastmod>")
        lines.append(f"    <priority>{e['priority']}</priority>")
        lines.append("  </url>")
    lines.append(MARKER_END)
    return "\n".join(lines)


def merge_into_sitemap(sitemap_text: str, url_block: str) -> str:
    """既存のマーカー範囲を置き換える、または</urlset>の直前へ新規挿入する。
    マーカー以外の既存内容（非Knowledge項目）は一切変更しない。"""
    pattern = re.compile(re.escape(MARKER_BEGIN) + r".*?" + re.escape(MARKER_END), re.DOTALL)
    if pattern.search(sitemap_text):
        return pattern.sub(url_block, sitemap_text)

    if "</urlset>" not in sitemap_text:
        raise SitemapError("sitemap.xmlに</urlset>が見つかりません（不正な形式の可能性）")
    return sitemap_text.replace("</urlset>", f"{url_block}\n</urlset>")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-sitemap-", suffix=".xml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def generate(index_path: Path, sitemap_path: Path, *, dry_run: bool = False) -> dict:
    articles = load_articles(index_path)
    entries = build_knowledge_urls(articles)
    url_block = render_url_block(entries)

    if not sitemap_path.exists():
        # 既存sitemap.xmlが無い場合のみ、最小限のurlsetを新規作成する
        # （通常運用では既存ファイルへのマージのみを想定する）。
        current_text = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            "</urlset>\n"
        )
    else:
        current_text = sitemap_path.read_text(encoding="utf-8")

    new_text = merge_into_sitemap(current_text, url_block)

    result = {
        "index": str(index_path), "sitemap": str(sitemap_path),
        "knowledge_url_count": len(entries), "dry_run": dry_run,
        "changed": new_text != current_text,
    }
    if dry_run:
        return result

    if new_text != current_text:
        _atomic_write_text(sitemap_path, new_text)
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Knowledge記事のURLをsitemap.xmlへ反映する")
    p.add_argument("--index", required=True, help="web-published.jsonのパス")
    p.add_argument("--sitemap", required=True, help="更新対象のsitemap.xmlのパス")
    p.add_argument("--dry-run", action="store_true", help="実際には書き込まず、結果を表示するだけ")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = generate(Path(args.index), Path(args.sitemap), dry_run=args.dry_run)
    except SitemapError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    label = "[dry-run]" if result["dry_run"] else "[done]"
    print(
        f"{label} Knowledge URL {result['knowledge_url_count']}件を{result['sitemap']}へ反映"
        f"（変更あり: {result['changed']}）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
