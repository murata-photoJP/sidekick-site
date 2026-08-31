#!/usr/bin/env python3
"""Story: content/story/ 配下のMarkdown（status: published のみ）を読み、
Jinja2テンプレートへ流し込んで静的HTMLを生成するCLI。2026-08-31新設。

開発日誌のbuild_development_log.pyと同じ設計方針（Python + Jinja2 + markdown-it-py、
atomicなステージング書き込み、非公開になった記事の古いHTML削除、slug重複で停止）を
踏襲する。開発日誌との違いは次の3点で、いずれも「Storyは日付順に流れていく記録では
なく、順番に読む読み物である」ことから来ている。

  1. 並び順が date の降順ではなく front matter の order の昇順（読む順序が意味を持つ）
  2. subtitle・series（前後編）・related_links（記事末尾の導線）を持つ
  3. 入力は _DevelopmentLog からの同期ではなく、このリポジトリで直接管理する
     （sync スクリプトが無い）

テンプレートは templates/story/ にあり、header.html/footer.htmlだけは
templates/knowledge/ のものをそのまま再利用する（Jinja2のFileSystemLoaderに
両方のディレクトリを検索パスとして渡す、build_development_log.pyと同じ方式）。
CSSも既存の /assets/css/knowledge.css と kzc-* クラスを流用し、Story専用の
新規CSSファイルは追加しない。

使い方:
    python build/story/build_story.py \\
        --content content/story --output build-output/story

    python build/story/build_story.py \\
        --content content/story --output story \\
        --content-en content/story/en --output-en en/story

    python build/story/build_story.py \\
        --content content/story --output build-output/story --validate-only
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
TEMPLATES_DIR = REPO_ROOT / "templates" / "story"
KNOWLEDGE_TEMPLATES_DIR = REPO_ROOT / "templates" / "knowledge"
SITE_ORIGIN = "https://www.sidekick-lab.com"
PUBLISHABLE_STATUS = "published"
REQUIRED_FIELDS = ("title", "date", "status", "order")

FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n-{3,}\r?\n?", re.DOTALL)
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
LEADING_H1_RE = re.compile(r"^\s*#[ \t]+[^\n]*\n+")


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
    missing = [f for f in REQUIRED_FIELDS if data.get(f) in (None, "", [])]
    if missing:
        raise SkipEntry(f"{rel_path}: front matterに必須項目がありません: {missing}")
    if not DATE_RE.match(str(data["date"])):
        raise SkipEntry(f"{rel_path}: dateがYYYY-MM-DD形式ではありません: {data['date']!r}")
    if data.get("status") != PUBLISHABLE_STATUS:
        raise SkipEntry(f"{rel_path}: status={data.get('status')!r}のため対象外です")
    try:
        int(data["order"])
    except (TypeError, ValueError):
        raise SkipEntry(f"{rel_path}: orderが整数ではありません: {data['order']!r}") from None


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


def normalize_related_links(data: dict, rel_path: Path) -> list[dict]:
    """記事末尾の「この話につながる現在のSidekick」導線。label・urlの対のリスト。
    urlはサイト内のルート相対パス（先頭が/）だけを許可する（本文中に外部リンクを
    紛れ込ませないため。外部への言及は本文側の責務とする）。"""
    raw = data.get("related_links") or []
    if not isinstance(raw, list):
        raise SkipEntry(f"{rel_path}: related_linksがリストではありません")
    links = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("label") or not item.get("url"):
            raise SkipEntry(f"{rel_path}: related_linksの要素にlabel/urlがありません: {item!r}")
        url = str(item["url"])
        if not url.startswith("/"):
            raise SkipEntry(
                f"{rel_path}: related_linksのurlはルート相対パスにしてください: {url!r}"
            )
        links.append({"label": str(item["label"]), "url": url})
    return links


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
    build_knowledge.py・build_development_log.pyの同名関数と同じ理由・同じ挙動）。"""
    return LEADING_H1_RE.sub("", body_markdown, count=1)


def render_markdown(text: str) -> str:
    md = MarkdownIt("commonmark", {"html": False}).enable(["table"])
    return md.render(text)


def plain_text_excerpt(body_markdown: str, limit: int = 120) -> str:
    """meta descriptionのフォールバック用。Markdown記法を軽く取り除くだけで、
    意味を変えるような要約・言い換えは行わない。"""
    text = strip_leading_h1(body_markdown)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*`_>#-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def check_image_paths(body_markdown: str, rel_path: Path) -> list[str]:
    """画像srcがWindowsローカル絶対パスや相対ファイルパスのまま残っていないかを警告する
    （build_development_log.pyの同名関数と同じ）。"""
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


def check_heading_levels(body_markdown: str, rel_path: Path) -> list[str]:
    """見出し階層の飛び越しを検出する（h2の次にh4が来る等）。本文にh1がある場合も
    警告する（Article HeaderのH1と重複し1ページ1h1が崩れるため）。build_knowledge.pyと
    同じく警告のみで生成は止めない。"""
    warnings = []
    prev = 2
    for m in re.finditer(r"^(#{1,6})\s+(\S[^\n]*)$", strip_leading_h1(body_markdown), re.MULTILINE):
        level = len(m.group(1))
        if level == 1:
            warnings.append(f"{rel_path}: 本文にh1があります（1ページ1h1が崩れます）: {m.group(2)[:30]!r}")
        elif level > prev + 1:
            warnings.append(
                f"{rel_path}: 見出し階層が飛んでいます（h{prev} -> h{level}）: {m.group(2)[:30]!r}"
            )
        prev = level
    return warnings


def load_entries(content_dir: Path, *, language: str = "ja") -> tuple[list[dict], list[str]]:
    if not content_dir.exists():
        raise BuildError(f"content_dirが見つかりません: {content_dir}")

    entries: list[dict] = []
    warnings: list[str] = []
    slug_owners: dict[str, Path] = {}
    order_owners: dict[int, Path] = {}

    # content/story/en/ は英語版記事専用のディレクトリ。language="ja"で
    # content_dir=content/story を読む際に、ネストされたen/を一緒に拾って
    # slugが衝突しないよう除外する（build_development_log.pyと同じ理由）。
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
            related_links = normalize_related_links(data, rel_path)
        except SkipEntry as exc:
            warnings.append(str(exc))
            continue

        if not body.strip():
            warnings.append(f"{rel_path}: 本文が空です")
            continue

        if slug in slug_owners:
            raise BuildError(
                f"slugが重複しています（'{slug}'）: {slug_owners[slug]} と {rel_path}"
            )
        slug_owners[slug] = rel_path

        order = int(data["order"])
        if order in order_owners:
            raise BuildError(
                f"orderが重複しています（{order}）: {order_owners[order]} と {rel_path}"
            )
        order_owners[order] = rel_path

        warnings.extend(check_image_paths(body, rel_path))
        warnings.extend(check_heading_levels(body, rel_path))

        date_formatter = format_date_en if language == "en" else format_date_ja
        entries.append({
            "slug": slug,
            "order": order,
            "title": data["title"],
            "subtitle": data.get("subtitle") or None,
            "date": str(data["date"]),
            "date_display": date_formatter(str(data["date"])),
            "summary": data.get("summary") or None,
            "series": data.get("series") or None,
            "series_part": data.get("series_part") or None,
            "series_total": data.get("series_total") or None,
            "related_links": related_links,
            "source_slug": data.get("source_slug") or None,
            "body_markdown": body,
        })

    entries.sort(key=lambda e: e["order"])
    return entries, warnings


def attach_series_neighbours(entries: list[dict]) -> None:
    """同じseriesに属する記事同士を、order順で前後にリンクする。
    Story 2/3のような前後編を、読者が迷わず行き来できるようにするため。"""
    by_series: dict[str, list[dict]] = {}
    for e in entries:
        if e["series"]:
            by_series.setdefault(e["series"], []).append(e)
    for group in by_series.values():
        group.sort(key=lambda e: e["order"])
        for i, e in enumerate(group):
            e["series_prev"] = group[i - 1] if i > 0 else None
            e["series_next"] = group[i + 1] if i + 1 < len(group) else None
    for e in entries:
        e.setdefault("series_prev", None)
        e.setdefault("series_next", None)


def build_env() -> Environment:
    if not TEMPLATES_DIR.exists():
        raise BuildError(f"テンプレートディレクトリが見つかりません: {TEMPLATES_DIR}")
    return Environment(
        loader=FileSystemLoader([str(TEMPLATES_DIR), str(KNOWLEDGE_TEMPLATES_DIR)]),
        autoescape=select_autoescape(["html"]),
    )


def compute_hreflang_by_slug(ja_entries: list[dict], en_entries: list[dict]) -> dict[str, dict[str, str]]:
    """ja記事のslug・en記事のslugそれぞれから、対応する翻訳先の絶対URLを引けるdictを作る。
    対応する翻訳が無い記事はキーに含めない（存在しないURLを出力しない、
    build_development_log.pyのcompute_hreflang_by_slug()と同じ方針）。"""
    by_slug: dict[str, dict[str, str]] = {}
    en_by_source_slug = {e["source_slug"]: e for e in en_entries if e.get("source_slug")}

    for ja in ja_entries:
        en_match = en_by_source_slug.get(ja["slug"])
        if not en_match:
            continue
        urls = {
            "ja": SITE_ORIGIN + f"/story/{ja['slug']}",
            "en": SITE_ORIGIN + f"/en/story/{en_match['slug']}",
        }
        by_slug[ja["slug"]] = urls
        by_slug[en_match["slug"]] = urls

    return by_slug


def compute_lang_switch_url(entry: dict, language: str, hreflang_by_slug: dict[str, dict[str, str]]) -> str:
    """Header/Footerの言語切替リンクの遷移先。対応する翻訳記事があればその記事へ、
    無ければ切替先言語のStoryトップへフォールバックする。"""
    other = "ja" if language == "en" else "en"
    urls = hreflang_by_slug.get(entry["slug"])
    if urls and other in urls:
        return urls[other][len(SITE_ORIGIN):]
    return "/en/story" if language == "ja" else "/story"


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
    top_url = "/en/story" if language == "en" else "/story"
    attach_series_neighbours(entries)

    # 記事ページ側で「前の話／次の話」を出すため、order順の前後を持たせる。
    for i, e in enumerate(entries):
        e["prev_entry"] = entries[i - 1] if i > 0 else None
        e["next_entry"] = entries[i + 1] if i + 1 < len(entries) else None

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
            nav_current="story",
            language=language,
            story_top_url=top_url,
            hreflang_alternates=hreflang_by_slug.get(e["slug"], {}),
            lang_switch_url=compute_lang_switch_url(e, language, hreflang_by_slug),
        )
        rendered[Path(f"{e['slug']}.html")] = html

    list_entries = [dict(e, public_url=f"{top_url}/{e['slug']}") for e in entries]
    index_hreflang = (
        {"ja": SITE_ORIGIN + "/story", "en": SITE_ORIGIN + "/en/story"}
        if include_top_hreflang else {}
    )
    index_html = index_tpl.render(
        entries=list_entries,
        canonical_url=SITE_ORIGIN + top_url,
        nav_current="story",
        language=language,
        story_top_url=top_url,
        hreflang_alternates=index_hreflang,
        lang_switch_url=("/story" if language == "en" else "/en/story"),
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
    staging = output_dir.parent / f".build-staging-story-{os.getpid()}"
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
            fd, tmp_name = tempfile.mkstemp(dir=str(dst.parent), prefix=".tmp-story-", suffix=".html")
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
    p = argparse.ArgumentParser(description="Story 静的HTMLビルド")
    p.add_argument("--content", required=True, help="content/story のパス（日本語）")
    p.add_argument("--output", required=True, help="日本語版の出力先ディレクトリ")
    p.add_argument("--content-en", default=None,
                   help="英語版記事のパス（省略時は英語版を生成しない）")
    p.add_argument("--output-en", default=None,
                   help="英語版の出力先ディレクトリ（--content-en指定時は必須）")
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
        print(f"[done] 非公開になったStoryの古いHTMLを{len(removed)}件削除しました")
        for p in sorted(removed):
            print(f"  - {p.relative_to(output_dir)}")

    if rendered_en is not None:
        print(f"[done] {len(rendered_en)}ページを生成しました -> {args.output_en}（記事{len(en_entries)}件）")
        for rel_path in sorted(rendered_en):
            print(f"  - {rel_path}")
        if removed_en:
            print(f"[done] 非公開になったStory（英語）の古いHTMLを{len(removed_en)}件削除しました")
            for p in sorted(removed_en):
                print(f"  - {p.relative_to(Path(args.output_en))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
