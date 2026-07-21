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


EN_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def format_date_en(date_str: str) -> str:
    m = DATE_RE.match(date_str)
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    return f"{EN_MONTH_NAMES[mo - 1]} {d}, {y}"


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


def load_entries(content_dir: Path, *, language: str = "ja") -> tuple[list[dict], list[str]]:
    if not content_dir.exists():
        raise BuildError(f"content_dirが見つかりません: {content_dir}")

    entries: list[dict] = []
    warnings: list[str] = []
    slug_owners: dict[str, Path] = {}

    # content/development-log/en/ は英語版記事専用のディレクトリ（sync_development_log.pyの
    # collect_candidates()と同じ理由）。language="ja"でcontent_dir=content/development-logを
    # 読む際に、ネストされたen/を一緒に拾ってslugが衝突しないよう除外する。
    # language="en"の場合はcontent_dir自体がen/なので、この条件に該当するパスは無い。
    md_paths = sorted(
        p for p in content_dir.rglob("*.md")
        if p.relative_to(content_dir).parts[0] != "en"
    )
    for path in md_paths:
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

        date_formatter = format_date_en if language == "en" else format_date_ja
        entries.append({
            "slug": slug,
            "title": data["title"],
            "date": data["date"],
            "date_display": date_formatter(str(data["date"])),
            "category": data.get("category") or None,
            "tags": data.get("tags") or [],
            "summary": data.get("summary") or None,
            "related_product": data.get("related_product") or None,
            "related_url": data.get("related_url") or None,
            "source_slug": data.get("source_slug") or None,
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


def compute_hreflang_by_slug(ja_entries: list[dict], en_entries: list[dict]) -> dict[str, dict[str, str]]:
    """ja記事のslug・en記事のslugそれぞれから、対応する翻訳先の絶対URLを引ける
    dictを作る。対応する翻訳が無い記事はキーに含めない（存在しないURLを
    出力しないため、打ち出の小槌のcompute_hreflang_alternates()と同じ方針）。"""
    by_slug: dict[str, dict[str, str]] = {}
    en_by_source_slug = {e["source_slug"]: e for e in en_entries if e.get("source_slug")}

    for ja in ja_entries:
        en_match = en_by_source_slug.get(ja["slug"])
        if not en_match:
            continue
        urls = {
            "ja": SITE_ORIGIN + f"/development-log/{ja['slug']}",
            "en": SITE_ORIGIN + f"/en/development-log/{en_match['slug']}",
        }
        by_slug[ja["slug"]] = urls
        by_slug[en_match["slug"]] = urls

    return by_slug


def compute_lang_switch_url(entry: dict, language: str, hreflang_by_slug: dict[str, dict[str, str]]) -> str:
    """Header/Footerの言語切替リンクの遷移先。対応する翻訳記事があればその記事へ、
    無ければ切替先言語のDevelopment Logトップへフォールバックする
    （存在しないURLにはしない、打ち出の小槌のcompute_lang_switch_url()と同じ方針）。"""
    other = "ja" if language == "en" else "en"
    urls = hreflang_by_slug.get(entry["slug"])
    if urls and other in urls:
        path = urls[other][len(SITE_ORIGIN):]
        return path
    return "/en/development-log" if language == "ja" else "/development-log"


def render_all(entries: list[dict], *, language: str = "ja",
                hreflang_by_slug: dict[str, dict[str, str]] | None = None,
                include_top_hreflang: bool = False) -> dict[Path, str]:
    env = build_env()

    try:
        article_tpl = env.get_template("article.html")
        index_tpl = env.get_template("index.html")
    except TemplateNotFound as exc:
        raise BuildError(f"Jinja2テンプレートが見つかりません: {exc}") from exc

    hreflang_by_slug = hreflang_by_slug or {}
    top_url = "/en/development-log" if language == "en" else "/development-log"
    rendered: dict[Path, str] = {}

    for e in entries:
        body_html = render_markdown(strip_leading_h1(e["body_markdown"]))
        meta_description = e["summary"] or plain_text_excerpt(e["body_markdown"])
        public_url = f"{top_url}/{e['slug']}"
        entry_ctx = dict(e, meta_description=meta_description)
        html = article_tpl.render(
            entry=entry_ctx,
            body_html=body_html,
            canonical_url=SITE_ORIGIN + public_url,
            nav_current="development-log",
            language=language,
            devlog_top_url=top_url,
            hreflang_alternates=hreflang_by_slug.get(e["slug"], {}),
            lang_switch_url=compute_lang_switch_url(e, language, hreflang_by_slug),
        )
        rendered[Path(f"{e['slug']}.html")] = html

    list_entries = [dict(e, public_url=f"{top_url}/{e['slug']}") for e in entries]
    index_hreflang = (
        {"ja": SITE_ORIGIN + "/development-log", "en": SITE_ORIGIN + "/en/development-log"}
        if include_top_hreflang else {}
    )
    index_html = index_tpl.render(
        entries=list_entries,
        canonical_url=SITE_ORIGIN + top_url,
        nav_current="development-log",
        language=language,
        hreflang_alternates=index_hreflang,
        lang_switch_url=("/development-log" if language == "en" else "/en/development-log"),
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
    p.add_argument("--content", required=True, help="content/development-log のパス（日本語）")
    p.add_argument("--output", required=True,
                   help="日本語版の出力先ディレクトリ。本番のdevelopment-log/を直接指定しないこと"
                        "（ローカル確認用ディレクトリを指定し、確認後に手動で本番へコピーする運用）")
    p.add_argument("--content-en", default=None,
                   help="英語版記事のパス（省略時は英語版を生成しない）")
    p.add_argument("--output-en", default=None,
                   help="英語版の出力先ディレクトリ（--content-en指定時は必須。"
                        "本番のen/development-log/を直接指定しないこと）")
    p.add_argument("--validate-only", action="store_true", help="書き込まず、生成可能かのみ確認する")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.content_en and not args.output_en:
        print("ERROR: --content-en を指定する場合は --output-en も指定してください", file=sys.stderr)
        return 1

    try:
        ja_entries, ja_warnings = load_entries(Path(args.content), language="ja")
        en_entries: list[dict] = []
        en_warnings: list[str] = []
        if args.content_en:
            en_entries, en_warnings = load_entries(Path(args.content_en), language="en")

        hreflang_by_slug = compute_hreflang_by_slug(ja_entries, en_entries)
        include_top_hreflang = bool(args.content_en)

        rendered_ja = render_all(
            ja_entries, language="ja", hreflang_by_slug=hreflang_by_slug,
            include_top_hreflang=include_top_hreflang,
        )
        rendered_en = None
        if args.content_en:
            rendered_en = render_all(
                en_entries, language="en", hreflang_by_slug=hreflang_by_slug,
                include_top_hreflang=include_top_hreflang,
            )
    except BuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - 想定外の例外も壊れた出力を残さず終了する
        print(f"ERROR: 予期しないエラー: {exc}", file=sys.stderr)
        return 1

    for w in ja_warnings + en_warnings:
        print(f"WARNING: {w}")

    if args.validate_only:
        print(f"[ok] validate-only（ja）: {len(rendered_ja)}ページを生成可能です（記事{len(ja_entries)}件）")
        for rel_path in sorted(rendered_ja):
            print(f"  - {rel_path}")
        if rendered_en is not None:
            print(f"[ok] validate-only（en）: {len(rendered_en)}ページを生成可能です（記事{len(en_entries)}件）")
            for rel_path in sorted(rendered_en):
                print(f"  - {rel_path}")
        return 0

    output_dir = Path(args.output)
    try:
        removed = stage_and_commit(rendered_ja, output_dir)
        removed_en: list[Path] = []
        if rendered_en is not None:
            removed_en = stage_and_commit(rendered_en, Path(args.output_en))
    except OSError as exc:
        print(f"ERROR: 出力先へ書き込めません: {exc}", file=sys.stderr)
        return 1

    print(f"[done] {len(rendered_ja)}ページを生成しました -> {output_dir}（記事{len(ja_entries)}件）")
    for rel_path in sorted(rendered_ja):
        print(f"  - {rel_path}")
    if removed:
        print(f"[done] 非公開になった開発日誌の古いHTMLを{len(removed)}件削除しました")
        for p in sorted(removed):
            print(f"  - {p.relative_to(output_dir)}")

    if rendered_en is not None:
        print(f"[done] {len(rendered_en)}ページを生成しました -> {args.output_en}（記事{len(en_entries)}件）")
        for rel_path in sorted(rendered_en):
            print(f"  - {rel_path}")
        if removed_en:
            print(f"[done] 非公開になった開発日誌（英語）の古いHTMLを{len(removed_en)}件削除しました")
            for p in sorted(removed_en):
                print(f"  - {p.relative_to(Path(args.output_en))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
