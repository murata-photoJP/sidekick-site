#!/usr/bin/env python3
"""開発日誌: ローカルの _DevelopmentLog/public から Web リポジトリ内の
content/development-log/ へ、公開対象（status: published）の記事だけを同期するCLI。

背景:
    開発日誌（_DevelopmentLog/public/YYYY/MM/YYYY-MM-DD[a-z].md）は、
    Photoshopの Presets フォルダ配下というVercelのビルド環境から直接参照できない
    場所で生成される。そのため、ローカルで実行してWebリポジトリ内へ内容を
    コピーしておく必要がある（README/docs/DEVELOPMENT_LOG_BUILD.md 参照）。

    元ファイルの front matter には status（draft/review/published/private）が
    存在する。「_DevelopmentLog」プロジェクト側の運用ルールにより、Claude Codeが
    新規作成する記事は原則 draft であり、村田さんの明示的な承認を経て初めて
    published へ変更される。このスクリプトは published 以外を一切コピーしない
    （fail-closed。draft の内容を誤って公開リポジトリへ持ち込まない）。

同期の性質:
    - 元ファイル（_DevelopmentLog側）は一切変更しない（読み取り専用）
    - .md のみを対象とする（.txt はSNS/メール用の別成果物でWeb非対象）
    - public 配下を再帰的に探索する（年・月ディレクトリの追加に自動対応）
    - 同じ相対パスへの再同期は上書き（内容が変わっていれば反映、同じなら変更なし）
    - 元に存在しなくなった記事は自動削除しない。存在するが今回の同期対象に
      含まれていない destination 側のファイルは「孤立ファイル」として警告するのみ
    - front matter が壊れている・必須項目（title/date/status）が無いファイルは
      1件ごとにスキップして警告する（他の正常なファイルの同期は継続する）
    - 公開対象（status: published）の中で slug が重複する場合は、
      公開URLの整合性が壊れるため、書き込みを一切行わずエラー終了する
      （検証を全件終えてから初めて書き込みへ進む＝atomicな同期）

使い方:
    python build/development-log/sync_development_log.py \\
        --source "C:\\Program Files\\Adobe\\Adobe Photoshop (Beta)\\Presets\\Scripts\\自作\\_DevelopmentLog\\public" \\
        --dest content/development-log

    # 書き込まず結果だけ確認する
    python build/development-log/sync_development_log.py --source ... --dest ... --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

import yaml

PUBLISHABLE_STATUS = "published"
REQUIRED_FIELDS = ("title", "date", "status")
# 閉じ側は"---"ちょうどではなく、3本以上のハイフンだけの行を許容する
# （_DevelopmentLogのPRIVATE/PUBLIC_LOG_TEMPLATE.mdが実際に"---------------"という
# 長いハイフン列を閉じ行として使っており、実データ（2026-07-18.md）で検出した）。
FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n-{3,}\r?\n?", re.DOTALL)
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# PUBLIC_LOG_TEMPLATE.mdの「## メモ（公開しない）」は、公開前に手動で削除する運用の
# セクション（コミットハッシュ・内部スクリプト名等、非公開情報が書かれる想定）。
# 削除し忘れたまま status: published にされた場合に備え、同期の入口でも検出し、
# 見つかった場合はそのファイルを公開対象から除外する（fail-closed、二重の安全網）。
UNPUBLISHABLE_SECTION_RE = re.compile(r"^#+\s*メモ（公開しない）", re.MULTILINE)


class SyncError(Exception):
    """ユーザーに分かりやすいエラーメッセージとして扱う例外（同期を中止する）。"""


class SkipFile(Exception):
    """このファイル1件だけをスキップする理由（警告として報告し、処理は継続する）。"""


def parse_front_matter(text: str, rel_path: Path) -> tuple[dict, str]:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        raise SkipFile(f"{rel_path}: front matterが見つかりません（先頭が'---'で始まっていません）")
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise SkipFile(f"{rel_path}: front matterの解析に失敗しました（{exc}）") from exc
    if not isinstance(data, dict):
        raise SkipFile(f"{rel_path}: front matterがキーと値の組ではありません")
    return data, text[m.end():]


def validate_front_matter(data: dict, rel_path: Path) -> None:
    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        raise SkipFile(f"{rel_path}: front matterに必須項目がありません: {missing}")
    if not DATE_RE.match(str(data["date"])):
        raise SkipFile(f"{rel_path}: dateがYYYY-MM-DD形式ではありません: {data['date']!r}")


def resolve_slug(data: dict, rel_path: Path) -> str:
    """front matterのslugを優先し、無ければファイル名（拡張子除く）を使う。
    ファイル名は現行の生成規則によりYYYY-MM-DD、または同日複数回発生時の
    YYYY-MM-DDb/c/...（DEVELOPMENT_LOG_GUIDE.mdの命名規則）であり、
    そのままURLセーフなslugとして使える。"""
    explicit = data.get("slug")
    if explicit:
        slug = str(explicit).strip()
        if not SLUG_RE.match(slug):
            raise SkipFile(f"{rel_path}: front matterのslugがURLとして不正です: {slug!r}")
        return slug
    stem = rel_path.stem
    if not SLUG_RE.match(stem):
        raise SkipFile(f"{rel_path}: ファイル名からslugを生成できません（英数字とハイフンのみ対応）: {stem!r}")
    return stem


def collect_candidates(source: Path) -> list[Path]:
    if not source.exists():
        raise SyncError(f"同期元が見つかりません: {source}")
    return sorted(source.rglob("*.md"))


def plan_sync(source: Path, dest: Path) -> dict:
    """全ファイルを検証し、書き込み計画（コピー対象・スキップ・孤立ファイル）を返す。
    このステップでは一切書き込まない。slug重複を検出した場合はSyncErrorを送出する
    （呼び出し側は書き込みを行わずそのままエラー終了できる＝atomicな同期）。"""
    candidates = collect_candidates(source)

    to_copy: list[dict] = []
    skipped: list[str] = []
    slug_owners: dict[str, Path] = {}

    for path in candidates:
        rel_path = path.relative_to(source)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            skipped.append(f"{rel_path}: UTF-8として読めません（{exc}）")
            continue
        except OSError as exc:
            skipped.append(f"{rel_path}: 読み込みに失敗しました（{exc}）")
            continue

        try:
            data, body = parse_front_matter(text, rel_path)
            validate_front_matter(data, rel_path)
        except SkipFile as exc:
            skipped.append(str(exc))
            continue

        status = str(data.get("status") or "")
        if status != PUBLISHABLE_STATUS:
            skipped.append(f"{rel_path}: status={status!r}のため対象外（published以外は同期しません）")
            continue

        if UNPUBLISHABLE_SECTION_RE.search(body):
            skipped.append(
                f"{rel_path}: 「## メモ（公開しない）」セクションが本文に残ったままです。"
                "publishedにする前に、このセクションを削除してください（同期を中止しました）。"
            )
            continue

        try:
            slug = resolve_slug(data, rel_path)
        except SkipFile as exc:
            skipped.append(str(exc))
            continue

        if slug in slug_owners:
            raise SyncError(
                f"slugが重複しています（'{slug}'）: {slug_owners[slug]} と {rel_path}。"
                "公開URLが衝突するため、同期を中止しました（何も書き込んでいません）。"
            )
        slug_owners[slug] = rel_path

        to_copy.append({
            "rel_path": rel_path,
            "slug": slug,
            "title": data.get("title"),
            "text": text,
        })

    dest_existing = sorted(dest.rglob("*.md")) if dest.exists() else []
    expected_dest = {dest / item["rel_path"] for item in to_copy}
    orphaned = [p for p in dest_existing if p not in expected_dest]

    return {
        "found": len(candidates),
        "to_copy": to_copy,
        "skipped": skipped,
        "orphaned": orphaned,
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-devlog-", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def apply_sync(plan: dict, dest: Path) -> dict:
    changed = 0
    unchanged = 0
    for item in plan["to_copy"]:
        target = dest / item["rel_path"]
        if target.exists() and target.read_text(encoding="utf-8") == item["text"]:
            unchanged += 1
            continue
        _atomic_write(target, item["text"])
        changed += 1
    return {"changed": changed, "unchanged": unchanged}


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="開発日誌（public/published分）をWebリポジトリへ同期する")
    p.add_argument("--source", required=True, help="_DevelopmentLog/public のパス")
    p.add_argument("--dest", required=True, help="同期先（例: content/development-log）")
    p.add_argument("--dry-run", action="store_true", help="書き込まず結果だけ表示する")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    source = Path(args.source)
    dest = Path(args.dest)

    try:
        plan = plan_sync(source, dest)
    except SyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        result = apply_sync(plan, dest)
    else:
        result = {"changed": "(dry-run)", "unchanged": "(dry-run)"}

    print(f"[{'dry-run' if args.dry_run else 'done'}] 検出: {plan['found']}件")
    print(f"  公開対象（同期）: {len(plan['to_copy'])}件"
          f"（新規/更新: {result['changed']}, 変更なし: {result['unchanged']}）")
    print(f"  対象外・警告: {len(plan['skipped'])}件")
    for w in plan["skipped"]:
        print(f"    - {w}")
    if plan["orphaned"]:
        print(f"  警告: 同期元に見当たらない既存ファイルが{len(plan['orphaned'])}件あります"
              "（自動削除はしません。必要なら手動で確認・削除してください）")
        for p in plan["orphaned"]:
            print(f"    - {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
