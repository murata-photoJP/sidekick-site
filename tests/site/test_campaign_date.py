"""AI Lab 無料キャンペーンの期限が、サイト全体で一致していることを検証する。

期限は3箇所に存在する。

  1. Firestore `config/planLimits.campaignEndDate`  … 実際の判定に使う正
  2. 各ページの JS フォールバック `new Date('YYYY-MM-DD')`
     … Firestore を読めなかったときだけ使う保険
  3. 各ページの表示テキスト（「〜2026年9月末」/ "through end of September 2026"）

2026-08-22、表示だけが 8月末 → 9月末 に更新され、
**Firestore と JS フォールバックが 8月31日のまま**という状態になっていた。
そのままなら 9月1日に「9月末まで無料」と表示したまま制限が切り替わっていた。
さらに **EN のテンプレートだけ表示が "end of August" のまま**で、
build_site.py でリビルドすると英語ページが 8月末に戻る状態でもあった。

このテストは 2 と 3 の一致を固定する（ネットワークを使わない）。
1 との照合は `tools/check_campaign_date.py` が行う。

changelog は過去の出来事の記録なので対象外。当時の日付のままで正しい。
"""

from __future__ import annotations

import calendar
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# JS フォールバック: const campaignEnd = ... : new Date('2026-09-30');
FALLBACK = re.compile(r"campaignEnd\s*=[^;]*?new Date\('(\d{4}-\d{2}-\d{2})'\)")

# 表示テキスト（JA / EN）
DISPLAY_JA = re.compile(r"(\d{4})年(\d{1,2})月末")
DISPLAY_EN = re.compile(r"through end of ([A-Z][a-z]+) (\d{4})")

MONTHS = {name: num for num, name in enumerate(calendar.month_name) if name}


def target_files() -> list[Path]:
    """検証対象。生成物とテンプレートの両方を見る。

    changelog は過去の記録なので除外する。
    build-output / BackUp は生成物・退避なので除外する。
    """
    files = []
    for path in REPO.rglob("*.html"):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith(("build-output/", "BackUp/", "development-log/", "manual/")):
            continue
        if "changelog" in path.name:
            continue
        files.append(path)
    return files


def end_of_month(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


def collect():
    """(ファイル, 種別, 正規化した日付) を集める。"""
    found = []
    for path in target_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(REPO).as_posix()
        for date in FALLBACK.findall(text):
            found.append((rel, "フォールバック", date))
        for year, month in DISPLAY_JA.findall(text):
            found.append((rel, "表示(JA)", end_of_month(int(year), int(month))))
        for month_name, year in DISPLAY_EN.findall(text):
            if month_name in MONTHS:
                found.append((rel, "表示(EN)", end_of_month(int(year), MONTHS[month_name])))
    return found


def test_期限の記述が1つでも見つかる():
    """正規表現が壊れてテストが素通りすることを防ぐ。"""
    found = collect()
    assert len(found) >= 10, f"期限の記述が {len(found)} 件しか見つからない（検出漏れの疑い）"


def test_サイト全体で期限が一致している():
    """表示・フォールバック・JA/EN・テンプレート/生成物のすべてが同じ日付を指すこと。"""
    found = collect()
    dates = {date for _, _, date in found}
    if len(dates) > 1:
        detail = "\n".join(
            f"    {date}  {kind:<14} {rel}"
            for rel, kind, date in sorted(found, key=lambda x: (x[2], x[0])))
        raise AssertionError(
            f"キャンペーン期限が {len(dates)} 種類に割れている: {sorted(dates)}\n{detail}\n"
            "  表示だけ直してフォールバックを忘れる、あるいは\n"
            "  生成物だけ直してテンプレートを忘れる、が過去に起きている。")


def test_フォールバックが全ページで同じ():
    fallbacks = [(rel, date) for rel, kind, date in collect() if kind == "フォールバック"]
    assert fallbacks, "フォールバックが1つも見つからない"
    dates = {date for _, date in fallbacks}
    assert len(dates) == 1, f"フォールバックが割れている: {sorted(dates)}"


def test_テンプレートと生成物の表示が一致している():
    """build_site.py でリビルドしたときに表示が巻き戻らないこと。

    2026-08-22 時点で、EN の生成物は September、テンプレートは August だった。
    """
    mismatches = []
    for rel, kind, date in collect():
        if not rel.startswith("templates/site/pages/"):
            continue
        output = rel.replace("templates/site/pages/", "")
        pair = [d for r, k, d in collect() if r == output and k == kind]
        if pair and date not in pair:
            mismatches.append(f"{rel}={date} vs {output}={pair}")
    assert not mismatches, "テンプレートと生成物で期限が違う:\n    " + "\n    ".join(mismatches)


@pytest.mark.parametrize("name", [
    "ai-review.html", "camera-ai.html", "pc-ai.html", "shooting-ai.html",
    "en/ai-review.html", "en/camera-ai.html", "en/pc-ai.html", "en/shooting-ai.html",
])
def test_AI各ページにフォールバックがある(name):
    """Firestore を読めなかったときに日付が undefined にならないこと。"""
    text = (REPO / name).read_text(encoding="utf-8")
    assert FALLBACK.search(text), f"{name} に campaignEnd のフォールバックが無い"
