#!/usr/bin/env python3
"""サイト共通ページ（手書きHTMLを段階的にJinja2化する対象）のビルドCLI。2026-07-22新設。

打ち出の小槌（build_knowledge.py）・開発日誌（build_development_log.py）と同じ設計方針
（Jinja2 + atomicな書き込み、失敗時に不完全な出力を残さない）を踏襲する。

ヘッダー/フッター（templates/knowledge/header.html・footer.html）は打ち出の小槌・
開発日誌と共用する（Jinja2のFileSystemLoaderに両ディレクトリを検索パスとして渡す、
build_development_log.pyと同じ方式）。knowledge/development-log側のビルドスクリプト・
テンプレートは変更していない。

テンプレート未定義変数を見逃さないよう、StrictUndefinedを使う（他の2つのビルドとは
異なる設定。手書きページの移行という性質上、変数の渡し忘れ・テンプレート側の
タイプミスに早く気付けることを優先した）。

現時点で対応しているページ: workshop のみ（Phase 4 試験移行）。

使い方:
    # 全ページ生成（現状はworkshopのみ）
    python build/site/build_site.py --output build-output/site

    # 1ページだけ生成
    python build/site/build_site.py --output build-output/site --page workshop

    # 検証のみ（何も書き込まない）
    python build/site/build_site.py --output build-output/site --validate-only
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, select_autoescape

REPO_ROOT = Path(__file__).resolve().parents[2]  # sidekick-site（html/）のルート
TEMPLATES_DIR = REPO_ROOT / "templates" / "site"
KNOWLEDGE_TEMPLATES_DIR = REPO_ROOT / "templates" / "knowledge"

# ページ定義: 1エントリ = 1ページ。出力パスは既存サイトのURL・ファイル名と完全に
# 一致させる（URLを変更しないため）。ナビゲーション項目自体はheader.html側に
# 一元化されているため、ここではnav_current等の「どのページか」を渡すだけでよい。
PAGES: dict[str, dict] = {
    "workshop": {
        "template": "pages/workshop.html",
        "output": Path("workshop.html"),
        "context": {
            "language": "ja",
            "nav_current": "workshop",
            # Workshopは対面開催の日本語限定ワークショップのため英語版ページを
            # 用意しない（村田さんの明示要件）。英語案内（言語バナー・ヘッダーの
            # EN切替リンク）は出さない。
            "show_lang_banner": False,
            "show_en_link": False,
        },
    },
}


class BuildError(Exception):
    """ユーザーに分かりやすいエラーメッセージとして扱う例外。"""


def build_env() -> Environment:
    for d in (TEMPLATES_DIR, KNOWLEDGE_TEMPLATES_DIR):
        if not d.exists():
            raise BuildError(f"テンプレートディレクトリが見つかりません: {d}")
    return Environment(
        loader=FileSystemLoader([str(TEMPLATES_DIR), str(KNOWLEDGE_TEMPLATES_DIR)]),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
    )


def render_page(env: Environment, key: str) -> str:
    page = PAGES.get(key)
    if page is None:
        raise BuildError(f"未登録のページです: {key!r}（対応済み: {sorted(PAGES)}）")
    try:
        template = env.get_template(page["template"])
    except TemplateNotFound as exc:
        raise BuildError(f"Jinja2テンプレートが見つかりません: {exc}") from exc
    return template.render(**page["context"])


def render_all(page_key: str | None) -> dict[Path, str]:
    """出力先相対パス→HTML文字列 のdictを返す。途中で1件でも失敗したら例外を投げ、
    何も返さない（build_knowledge.pyのrender_all()と同じ、全体をやり直す前提）。"""
    if page_key is not None and page_key not in PAGES:
        raise BuildError(f"未登録のページです: {page_key!r}（対応済み: {sorted(PAGES)}）")
    env = build_env()
    keys = [page_key] if page_key else list(PAGES)
    rendered: dict[Path, str] = {}
    for key in keys:
        rendered[PAGES[key]["output"]] = render_page(env, key)
    return rendered


def write_atomic(output_dir: Path, rendered: dict[Path, str]) -> None:
    """一時ファイル経由でatomicに書き込む。renderedはrender_all()側で全件レンダリング
    済みのものが渡ってくる（レンダリング失敗時はここに到達しない）ため、書き込み中の
    OSエラー以外で中途半端な出力が残ることはない。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    for rel_path, html in rendered.items():
        dst = output_dir / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(dst.parent), prefix=".tmp-site-", suffix=".html")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(html)
            os.replace(tmp_name, str(dst))
        except BaseException:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="サイト共通ページ 静的HTMLビルド")
    p.add_argument("--output", required=True,
                   help="出力先ディレクトリ。本番のhtml/直下を直接指定しないこと"
                        "（内容を確認したうえで本番へ反映する運用とする）")
    p.add_argument("--page", default=None,
                   help=f"生成するページ名。省略時は全ページ（対応済み: {sorted(PAGES)}）")
    p.add_argument("--validate-only", action="store_true", help="ファイルを書かず、生成可能かのみ確認する")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        rendered = render_all(args.page)
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
    try:
        write_atomic(output_dir, rendered)
    except OSError as exc:
        print(f"ERROR: 出力先へ書き込めません: {exc}", file=sys.stderr)
        return 1

    print(f"[done] {len(rendered)}ページを生成しました -> {output_dir}")
    for rel_path in sorted(rendered):
        print(f"  - {rel_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
