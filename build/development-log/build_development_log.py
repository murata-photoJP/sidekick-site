#!/usr/bin/env python3
"""開発日誌: content/development-log/ 配下のMarkdown（_DevelopmentLogから同期済み、
status: published のみ）を読み、Jinja2テンプレートへ流し込んで静的HTMLを生成するCLI。

打ち出の小槌のbuild_knowledge.pyと同じ設計方針（Python + Jinja2 + markdown-it-py、
atomicなステージング書き込み、非公開になった記事の古いHTML削除）を踏襲するが、
入力がJSON（web-published.json）ではなくMarkdown＋YAML front matterである点が異なる
（sync_development_log.pyがコピーした時点でstatus: published以外は含まれない前提だが、
このスクリプト自身もfront matterを独立して検証する＝多層防御）。

テンプレートは templates/development-log/ にあり、header.html/footer.htmlだけは
templates/knowledge/ のものをそのまま再利用する（Jinja2のFileSystemLoaderに
両方のディレクトリを検索パスとして渡す）。開発日誌だけ別サイトのような
見た目にならないよう、既存のCSS（/assets/css/knowledge.css）・既存のkzc-*クラスを
そのまま流用する（開発日誌専用の新規CSSは追加していない）。

使い方:
    python build/development-log/build_development_log.py \\
        --content content/development-log --output build-output/development-log

    python build/development-log/build_development_log.py \\
        --content content/development-log --output build-output/development-log --validate-only
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from markdown_it import MarkdownIt

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates" / "development-log"
KNOWLEDGE_TEMPLATES_DIR = REPO_ROOT / "templates" / "knowledge"
SITE_ORIGIN = "https://www.sidekick-lab.com"
PUBLISHABLE_STATUS = "published"
REQUIRED_FIELDS = ("title", "date", "status")

# 閉じ側は"---"ちょうどではなく、3本以上のハイフンだけの行を許容する
# （_DevelopmentLogのPRIVATE/PUBLIC_LOG_TEMPLATE.mdが実際に"---------------"という
# 長いハイフン列を閉じ行として使っており、実データ（2026-07-18.md）で検出した）。
FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n-{3,}\r?\n?", re.DOTALL)
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
LEADING_H1_RE = re.compile(r"^\s*#[ \t]+[^\n]*\n+")
# sync_development_log.pyと同じ安全網（多層防御）。sync側で既に除外されている前提だが、
# content/development-logが手動編集された場合等に備え、ビルド側でも独立して検出する。
UNPUBLISHABLE_SECTION_RE = re.compile(r"^#+\s*メモ（公開しない）", re.MULTILINE)

MONTH_NAMES_JA = None  # 日本語表記は単純に「{年}年{月}月{日}日」で、月名テーブルは不要


class BuildError(Exception):
    """ユーザーに分かりやすいエラーメッセージとして扱う例外。"""


class SkipEntry(Exception):
    """このファイル1件だけをスキップする理由（警告として報告し、処理は継続する）。"""


def parse_front_matter(text: str, rel_path: Path) -> tuple[dict, str]:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        raise SkipEntry(f"{rel_path}: front matterが見つかりません")
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise SkipEntry(f"{rel_path}: front matterの解析に失敗しました（{exc}）") from exc
    if not isinstance(data, dict):
        raise SkipEntry(f"{rel_path}: front matterがキーと値の組ではありません")
    return data, text[m.end():]


def validate_front_matter(data: dict, rel_path: Path) -> None:
    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        raise SkipEntry(f"{rel_path}: front matterに必須項目がありません: {missing}")
    if not DATE_RE.match(str(data["date"])):
        raise SkipEntry(f"{rel_path}: dateがYYYY-MM-DD形式ではありません: {data['date']!r}")
    if data.get("status") != PUBLISHABLE_STATUS:
        raise SkipEntry(f"{rel_path}: status={data.get('status')!r}のため対象外です")


def resolve_slug(data: dict, rel_path: Path) -> str:
    explicit = data.get("slug")
    if explicit:
        slug = str(explicit).strip()
        if not SLUG_RE.match(slug):
            raise SkipEntry(f"{rel_path}: front matterのslugがURLとして不正です: {slug!r}")
        return slug
    stem = rel_path.stem
    if not SLUG_RE.match(stem):
        raise SkipEntry(f"{rel_path}: ファイル名からslugを生成できません: {stem!r}")
    return stem


def format_date_ja(date_str: str) -> str:
    m = DATE_RE.match(date_str)
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    return f"{y}年{mo}月{d}日"


def strip_leading_h1(body_markdown: str) -> str:
    """本文冒頭が単一の#見出しの場合は取り除く（Article HeaderのH1と重複するため。
    打ち出の小槌build_knowledge.pyの同名関数と同じ理由・同じ挙動）。"""
    return LEADING_H1_RE.sub("", body_markdown, count=1)


def render_markdown(text: str) -> str:
    md = MarkdownIt("commonmark", {"html": False}).enable(["table"])
    return md.render(text)


def plain_text_excerpt(body_markdown: str, limit: int = 120) -> str:
    """meta descriptionのフォールバック用に、本文冒頭から安全に短い要約を作る。
    Markdown記法を軽く取り除くだけで、意味を変えるような要約・言い換えは行わない。"""
    text = strip_leading_h1(body_markdown)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*`_>#-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def check_image_paths(body_markdown: str, rel_path: Path) -> list[str]:
    """画像srcがWindowsローカル絶対パスや相対ファイルパスのまま残っていないかを警告する
    （本番からローカル絶対パスを参照しない、というプロジェクト全体の原則）。"""
    md = MarkdownIt("commonmark", {"html": False})
    tokens = md.parse(body_markdown)
    warnings = []
    for t in tokens:
        if t.type == "inline" and t.children:
            for c in t.children:
                if c.type != "image":
                    continue
                src = c.attrs.get("src", "")
                if not src:
                    warnings.append(f"{rel_path}: 画像srcが空です")
                elif not (src.startswith("http://") or src.startswith("https://") or src.startswith("/")):
                    warnings.append(f"{rel_path}: 画像srcがWeb上の絶対パスではありません: {src!r}")
                if not c.content.strip():
                    warnings.append(f"{rel_path}: 画像のalt属性が空です: {src!r}")
    return warnings


def load_entries(content_dir: Path) -> tuple[list[dict], list[str]]:
    if not content_dir.exists():
        raise BuildError(f"content_dirが見つかりません: {content_dir}")

    entries: list[dict] = []
    warnings: list[str] = []
    slug_owners: dict[str, Path] = {}

    for path in sorted(content_dir.rglob("*.md")):
        rel_path = path.relative_to(content_dir)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            warnings.append(f"{rel_path}: UTF-8として読めません（{exc}）")
            continue

        try:
            data, body = parse_front_matter(text, rel_path)
            validate_front_matter(data, rel_path)
            slug = resolve_slug(data, rel_path)
        except SkipEntry as exc:
            warnings.append(str(exc))
            continue

        if not body.strip():
            warnings.append(f"{rel_path}: 本文が空です")
            continue

        if UNPUBLISHABLE_SECTION_RE.search(body):
            warnings.append(
                f"{rel_path}: 「## メモ（公開しない）」セクションが本文に残ったままのため除外しました。"
                "元ファイルからこのセクションを削除し、再同期してください。"
            )
            continue

        if slug in slug_owners:
            raise BuildError(
                f"slugが重複しています（'{slug}'）: {slug_owners[slug]} と {rel_path}"
            )
        slug_owners[slug] = rel_path

        warnings.extend(check_image_paths(body, rel_path))

        entries.append({
            "slug": slug,
            "title": data["title"],
            "date": data["date"],
            "date_display": format_date_ja(str(data["date"])),
            "category": data.get("category") or None,
            "tags": data.get("tags") or [],
            "summary": data.get("summary") or None,
            "related_product": data.get("related_product") or None,
            "related_url": data.get("related_url") or None,
            "body_markdown": body,
        })

    entries.sort(key=lambda e: (e["date"], e["slug"]), reverse=True)
    return entries, warnings


def build_env() -> Environment:
    if not TEMPLATES_DIR.exists():
        raise BuildError(f"テンプレートディレクトリが見つかりません: {TEMPLATES_DIR}")
    return Environment(
        loader=FileSystemLoader([str(TEMPLATES_DIR), str(KNOWLEDGE_TEMPLATES_DIR)]),
        autoescape=select_autoescape(["html"]),
    )


def render_all(entries: list[dict]) -> dict[Path, str]:
    env = build_env()

    try:
        article_tpl = env.get_template("article.html")
        index_tpl = env.get_template("index.html")
    except TemplateNotFound as exc:
        raise BuildError(f"Jinja2テンプレートが見つかりません: {exc}") from exc

    rendered: dict[Path, str] = {}

    for e in entries:
        body_html = render_markdown(strip_leading_h1(e["body_markdown"]))
        meta_description = e["summary"] or plain_text_excerpt(e["body_markdown"])
        public_url = f"/development-log/{e['slug']}"
        entry_ctx = dict(e, meta_description=meta_description)
        html = article_tpl.render(
            entry=entry_ctx,
            body_html=body_html,
            canonical_url=SITE_ORIGIN + public_url,
            nav_current="development-log",
        )
        rendered[Path(f"{e['slug']}.html")] = html

    list_entries = [dict(e, public_url=f"/development-log/{e['slug']}") for e in entries]
    index_html = index_tpl.render(
        entries=list_entries,
        canonical_url=SITE_ORIGIN + "/development-log",
        nav_current="development-log",
    )
    rendered[Path("index.html")] = index_html

    return rendered


def find_stale_html(output_dir: Path, rendered: dict[Path, str]) -> list[Path]:
    keep = {(output_dir / rel).resolve() for rel in rendered}
    if not output_dir.exists():
        return []
    return [p for p in output_dir.rglob("*.html") if p.resolve() not in keep]


def stage_and_commit(rendered: dict[Path, str], output_dir: Path) -> list[Path]:
    """一時ディレクトリへ全ファイルを書き出し、成功したら output_dir へ確定コピーする。
    途中で失敗した場合、output_dirには一切触れない（既存の出力を壊さない）。
    新しい内容の書き込みがすべて成功した後にだけ、古い（非公開になった）.htmlを削除する。"""
    staging = output_dir.parent / f".build-staging-devlog-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
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
            fd, tmp_name = tempfile.mkstemp(dir=str(dst.parent), prefix=".tmp-devlog-", suffix=".html")
            os.close(fd)
            shutil.copyfile(src, tmp_name)
            os.replace(tmp_name, str(dst))
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    removed = []
    for stale_path in find_stale_html(output_dir, rendered):
        stale_path.unlink()
        removed.append(stale_path)
    return removed


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="開発日誌 静的HTMLビルド")
    p.add_argument("--content", required=True, help="content/development-log のパス")
    p.add_argument("--output", required=True,
                   help="出力先ディレクトリ。本番のdevelopment-log/を直接指定しないこと"
                        "（ローカル確認用ディレクトリを指定し、確認後に手動で本番へコピーする運用）")
    p.add_argument("--validate-only", action="store_true", help="書き込まず、生成可能かのみ確認する")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        entries, warnings = load_entries(Path(args.content))
        rendered = render_all(entries)
    except BuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - 想定外の例外も壊れた出力を残さず終了する
        print(f"ERROR: 予期しないエラー: {exc}", file=sys.stderr)
        return 1

    for w in warnings:
        print(f"WARNING: {w}")

    if args.validate_only:
        print(f"[ok] validate-only: {len(rendered)}ページを生成可能です（記事{len(entries)}件）")
        for rel_path in sorted(rendered):
            print(f"  - {rel_path}")
        return 0

    output_dir = Path(args.output)
    try:
        removed = stage_and_commit(rendered, output_dir)
    except OSError as exc:
        print(f"ERROR: 出力先へ書き込めません: {exc}", file=sys.stderr)
        return 1

    print(f"[done] {len(rendered)}ページを生成しました -> {output_dir}（記事{len(entries)}件）")
    for rel_path in sorted(rendered):
        print(f"  - {rel_path}")
    if removed:
        print(f"[done] 非公開になった開発日誌の古いHTMLを{len(removed)}件削除しました")
        for p in sorted(removed):
            print(f"  - {p.relative_to(output_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
