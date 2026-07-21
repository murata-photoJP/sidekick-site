#!/usr/bin/env python3
"""開発日誌: content/development-log/ のMarkdown front matterからURLを抽出し、
sitemap.xmlへ反映するCLI。打ち出の小槌のgenerate_knowledge_sitemap.pyと同じ
マーカーコメント方式（該当区間だけを機械更新し、それ以外の手動管理項目には
一切触れない）を踏襲する。

使い方:
    python build/development-log/generate_development_log_sitemap.py \\
        --content content/development-log --sitemap sitemap.xml
    python build/development-log/generate_development_log_sitemap.py \\
        --content content/development-log --sitemap sitemap.xml --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

import yaml

SITE_ORIGIN = "https://www.sidekick-lab.com"
PUBLISHABLE_STATUS = "published"

MARKER_BEGIN = "<!-- BEGIN AUTO-GENERATED DEVELOPMENT LOG URLS (generate_development_log_sitemap.py) -->"
MARKER_END = "<!-- END AUTO-GENERATED DEVELOPMENT LOG URLS -->"

TOP_PRIORITY = "0.5"
ARTICLE_PRIORITY = "0.4"

# 閉じ側は"---"ちょうどではなく、3本以上のハイフンだけの行を許容する
# （_DevelopmentLogのテンプレートが実際に"---------------"という長いハイフン列を
# 閉じ行として使っているため。sync_development_log.py・build_development_log.pyと同じ）。
FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n-{3,}\r?\n?", re.DOTALL)
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SitemapError(Exception):
    """ユーザーに分かりやすいエラーメッセージとして扱う例外。"""


def load_entries(content_dir: Path) -> list[dict]:
    if not content_dir.exists():
        raise SitemapError(f"content_dirが見つかりません: {content_dir}")

    entries = []
    for path in sorted(content_dir.rglob("*.md")):
        rel_path = path.relative_to(content_dir)
        text = path.read_text(encoding="utf-8")
        m = FRONT_MATTER_RE.match(text)
        if not m:
            continue
        try:
            data = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict) or data.get("status") != PUBLISHABLE_STATUS:
            continue
        if not data.get("date"):
            continue

        slug = str(data.get("slug") or rel_path.stem).strip()
        if not SLUG_RE.match(slug):
            continue

        entries.append({"slug": slug, "date": str(data["date"])})

    return entries


def build_urls(entries: list[dict]) -> list[dict]:
    urls = [{
        "loc": f"{SITE_ORIGIN}/development-log/{e['slug']}",
        "lastmod": e["date"],
        "priority": ARTICLE_PRIORITY,
    } for e in entries]

    if entries:
        urls.append({"loc": f"{SITE_ORIGIN}/development-log", "lastmod": None, "priority": TOP_PRIORITY})

    urls.sort(key=lambda u: u["loc"])
    return urls


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
    pattern = re.compile(re.escape(MARKER_BEGIN) + r".*?" + re.escape(MARKER_END), re.DOTALL)
    if pattern.search(sitemap_text):
        return pattern.sub(url_block, sitemap_text)
    if "</urlset>" not in sitemap_text:
        raise SitemapError("sitemap.xmlに</urlset>が見つかりません（不正な形式の可能性）")
    return sitemap_text.replace("</urlset>", f"{url_block}\n</urlset>")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-sitemap-devlog-", suffix=".xml")
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


def generate(content_dir: Path, sitemap_path: Path, *, dry_run: bool = False) -> dict:
    entries = load_entries(content_dir)
    urls = build_urls(entries)
    url_block = render_url_block(urls)

    if not sitemap_path.exists():
        raise SitemapError(f"sitemap.xmlが見つかりません: {sitemap_path}")
    current_text = sitemap_path.read_text(encoding="utf-8")
    new_text = merge_into_sitemap(current_text, url_block)

    result = {
        "content": str(content_dir), "sitemap": str(sitemap_path),
        "url_count": len(urls), "dry_run": dry_run, "changed": new_text != current_text,
    }
    if dry_run:
        return result
    if new_text != current_text:
        _atomic_write_text(sitemap_path, new_text)
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="開発日誌のURLをsitemap.xmlへ反映する")
    p.add_argument("--content", required=True, help="content/development-log のパス")
    p.add_argument("--sitemap", required=True, help="更新対象のsitemap.xmlのパス")
    p.add_argument("--dry-run", action="store_true", help="実際には書き込まず、結果を表示するだけ")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = generate(Path(args.content), Path(args.sitemap), dry_run=args.dry_run)
    except SitemapError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    label = "[dry-run]" if result["dry_run"] else "[done]"
    print(
        f"{label} 開発日誌URL {result['url_count']}件を{result['sitemap']}へ反映"
        f"（変更あり: {result['changed']}）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
