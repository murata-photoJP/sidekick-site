"""プランナーQRマップ G-6「Map Discovery Filter」の実 browser test（Firestore Emulator ＋ 本物の api/qr-map.js ＋ 実 UI）。

npm run test:qr-map:browser（tools/qr_map/run_browser_tests.mjs）から起動する。G-3 の seed（すべて 2027 年 = 未来）に加えて、
ここで **実 SharePlan（Planner 正本 vectors）を日時・地点だけずらして publish API で公開** する（他の test が見ない鹿児島付近）:
  分類（ダイヤ / パール / 天の川 / その他）× 撮影日時（過去・今日・今週末・7〜30 日・30 日より先）× 表示範囲の内 / 外。

固定すること（HD G-6 / HD-4 訂正）:
  - 初期は「これから」× すべての撮影対象。過去の計画は出ない。G-3 の seed（未来）は G-6 前と同じく全部出る
  - Discovery の単位は 撮影地点 × 撮影日時 × 分類。通常の Discovery（これから・今週末・7日間・30日間・期間指定）は t_d >= 今だけ
  - 過去は「過去を見る」でだけ出し、「現在も同じ条件で撮影できることを示すものではありません」を表示する
  - 撮影対象は複数選択・0 件可（ピン 0 ＋「撮影対象が選ばれていません［すべて選ぶ］」）
  - 地域 = 表示範囲。地図を動かすと自動で取り直す（「この範囲で検索」は無い）
  - 絞り込みの操作では server へ全件も open も求めない（tile だけ）
"""
from __future__ import annotations

import base64
import json
import os
import re
import uuid
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from test_planner_map_browser import BASE, VISIBLE, all_marker_plan_ids, browser, goto_map, new_page, set_view  # noqa: F401 (browser = fixture)

JST = timezone(timedelta(hours=9))
VECTORS = json.loads((Path(__file__).resolve().parents[2] / "fixtures" / "qr_map" / "cross_language_vectors.json").read_text(encoding="utf-8"))
BY_ID = {c["id"]: c for c in VECTORS["cases"]}
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
CENTER = (31.60, 130.56)          # 鹿児島付近（G-3 の seed・他の test が見ない）
OUTSIDE = (32.75, 129.87)         # 長崎（CENTER を zoom 11 で見たときの範囲の外）
PAST_NOTICE = "過去の撮影計画を表示しています。現在も同じ条件で撮影できることを示すものではありません。"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def shift_times(node, delta: timedelta):
    """wire の中の ISO 時刻をすべて同じだけずらす（天の川の interval・観測窓・presentation も一緒に。整合を保つ）。"""
    if isinstance(node, dict):
        return {k: shift_times(v, delta) for k, v in node.items()}
    if isinstance(node, list):
        return [shift_times(v, delta) for v in node]
    if isinstance(node, str) and ISO_RE.match(node):
        return iso(datetime.strptime(node, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) + delta)
    return node


def derived(vector_id: str, when: datetime, lat: float, lon: float) -> str:
    wire = json.loads(zlib.decompress(base64.urlsafe_b64decode(BY_ID[vector_id]["payload"] + "==")).decode("utf-8"))
    if wire["v"] == 1:
        wire["td"] = iso(when)
        wire["ox"], wire["oy"] = lat, lon
    else:
        original = datetime.strptime(wire["t"]["d"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        wire = shift_times(wire, when.astimezone(timezone.utc).replace(microsecond=0) - original)
        wire["o"]["x"], wire["o"]["y"] = lat, lon
    raw = zlib.compress(json.dumps(wire, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def publish(fragment: str) -> str:
    body = json.dumps({"fragment": fragment, "idempotency_key": "g6-" + uuid.uuid4().hex, "consent_version": "qr-map-consent/1"})
    req = Request(BASE + "/api/qr-map?op=publish", data=body.encode("utf-8"), method="POST",
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=20) as res:
        value = json.loads(res.read().decode("utf-8"))
    assert re.match(r"^[0-9a-f]{32}$", value["plan_id"]), value
    return value["plan_id"]


def weekend_range(now: datetime) -> tuple[datetime, datetime]:
    """独立に書いた「今週末」（JST）: 月〜金 = 次の土曜 00:00 〜 日曜 23:59:59、土 = 今 〜 日曜の終わり、日 = 今 〜 今日の終わり。"""
    n = now.astimezone(JST)
    day = n.replace(hour=0, minute=0, second=0, microsecond=0)
    wd = n.weekday()   # 月 0 … 日 6
    if wd == 5:
        return now, day + timedelta(days=2) - timedelta(microseconds=1)
    if wd == 6:
        return now, day + timedelta(days=1) - timedelta(microseconds=1)
    sat = day + timedelta(days=5 - wd)
    return sat, sat + timedelta(days=2) - timedelta(microseconds=1)


@pytest.fixture(scope="module")
def g6():
    now = datetime.now(timezone.utc)
    wk_start, wk_end = weekend_range(now)
    wk_point = max(wk_start, now + timedelta(minutes=30)) + timedelta(hours=1)   # 週末の中で、今より後
    if wk_point > wk_end:
        wk_point = wk_end - timedelta(minutes=5)
    lat, lon = CENTER
    spec = [
        # key, vector, 撮影日時, 地点（範囲内は CENTER 付近に少しずつずらす）, 分類
        ("diamond-today", "VALID_GV-1", now + timedelta(hours=3), (lat + 0.010, lon), "diamond"),
        ("pearl-weekend", "VALID_GV-3", wk_point, (lat - 0.010, lon), "pearl"),
        ("milky-20d", "VALID_V2-SLMW-1", now + timedelta(days=20), (lat, lon + 0.012), "milky_way"),
        ("other-60d", "VALID_V2-ST-1", now + timedelta(days=60), (lat, lon - 0.012), "other"),
        ("diamond-past", "VALID_GV-1", now - timedelta(days=10), (lat + 0.020, lon + 0.020), "diamond"),
        ("pearl-past", "VALID_GV-3", now - timedelta(days=40), (lat - 0.020, lon - 0.020), "pearl"),
        ("milky-past", "VALID_V2-SLMW-1", now - timedelta(days=3), (lat + 0.020, lon - 0.020), "milky_way"),
        ("diamond-outside", "VALID_GV-1", now + timedelta(hours=3), OUTSIDE, "diamond"),
    ]
    plans = {}
    for key, vector, when, (plat, plon), category in spec:
        plans[key] = {"plan_id": publish(derived(vector, when, plat, plon)), "when": when, "category": category,
                      "inside": (plat, plon) != OUTSIDE}
    return {"now": now, "weekend": (wk_start, wk_end), "plans": plans}


def ids_where(g6, pred) -> set[str]:
    return {p["plan_id"] for p in g6["plans"].values() if p["inside"] and pred(p)}


def open_filter(page):
    if page.get_attribute("#pm-filter-toggle", "aria-expanded") != "true":
        page.click("#pm-filter-toggle")
    page.wait_for_selector("#pm-filter-panel", state="visible")


def choose_period(page, period: str):
    open_filter(page)
    page.check(f'input[name="pm-period"][value="{period}"]')
    page.wait_for_timeout(150)


def set_categories(page, wanted: list[str]):
    open_filter(page)
    for box in page.query_selector_all('#pm-filter-panel input[type="checkbox"]'):
        value = box.get_attribute("value")
        if (value in wanted) != box.is_checked():
            box.click()
    page.wait_for_timeout(150)


def g6_ids_on_map(page, g6) -> set[str]:
    mine = {p["plan_id"] for p in g6["plans"].values()}
    return all_marker_plan_ids(page) & mine


def count_text(page) -> str:
    return page.text_content("#pm-filter-count") or ""


def open_g6_view(browser, g6, width=1280, height=800):
    context, page, rec = new_page(browser, width, height)
    goto_map(page)
    set_view(page, CENTER[0], CENTER[1], 12)
    return context, page, rec


def test_g6_initial_is_upcoming_all_categories_and_hides_past(browser, g6):
    context, page, rec = open_g6_view(browser, g6)
    try:
        upcoming = ids_where(g6, lambda p: p["when"] >= g6["now"])
        assert g6_ids_on_map(page, g6) == upcoming
        assert "これから・すべての撮影対象" in page.text_content("#pm-filter-summary")
        assert page.is_hidden("#pm-past-notice")
        assert count_text(page).startswith("この範囲 ")
        assert rec.ops("open") == []                     # 絞り込み・表示では open しない
    finally:
        context.close()


def test_g6_initial_shows_the_same_g3_seed_plans_as_before(browser, g6):
    """regression: G-3 の seed（すべて未来）は、初期状態で G-6 前と同じく全部出る。"""
    context, page, rec = new_page(browser)
    try:
        goto_map(page)
        seen = all_marker_plan_ids(page)
        visible_in_initial = {p["plan_id"] for p in VISIBLE if p.get("plan_id")}
        tile_ids = set()
        for body in rec.tile_bodies:
            tile_ids |= {p["plan_id"] for p in json.loads(body)["plans"]}
        assert tile_ids & visible_in_initial, "初期表示の tile に seed が無い"
        assert (tile_ids & visible_in_initial) <= seen     # tile で受け取った未来の seed は全部ピンになる
    finally:
        context.close()


def test_g6_categories_multi_select_and_zero(browser, g6):
    context, page, rec = open_g6_view(browser, g6)
    try:
        upcoming = lambda p: p["when"] >= g6["now"]
        set_categories(page, ["diamond", "pearl"])
        assert g6_ids_on_map(page, g6) == ids_where(g6, lambda p: upcoming(p) and p["category"] in ("diamond", "pearl"))
        assert "ダイヤモンド / パール" in page.text_content("#pm-filter-summary")
        set_categories(page, ["milky_way", "other"])
        assert g6_ids_on_map(page, g6) == ids_where(g6, lambda p: upcoming(p) and p["category"] in ("milky_way", "other"))
        set_categories(page, [])
        assert all_marker_plan_ids(page) == set()
        assert "撮影対象が選ばれていません" in page.text_content("#pm-status")
        page.click("#pm-status .pm-retry")                 # ［すべて選ぶ］
        page.wait_for_timeout(150)
        assert g6_ids_on_map(page, g6) == ids_where(g6, upcoming)
        assert rec.ops("open") == []
    finally:
        context.close()


def test_g6_periods_weekend_7_30_days(browser, g6):
    context, page, rec = open_g6_view(browser, g6)
    try:
        now = g6["now"]
        wk_start, wk_end = g6["weekend"]
        choose_period(page, "weekend")
        assert g6_ids_on_map(page, g6) == ids_where(g6, lambda p: p["when"] >= max(now, wk_start) and p["when"] <= wk_end)
        end7 = (now.astimezone(JST).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=8)) - timedelta(microseconds=1)
        choose_period(page, "days7")
        assert g6_ids_on_map(page, g6) == ids_where(g6, lambda p: now <= p["when"] <= end7)
        end30 = (now.astimezone(JST).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=31)) - timedelta(microseconds=1)
        choose_period(page, "days30")
        assert g6_ids_on_map(page, g6) == ids_where(g6, lambda p: now <= p["when"] <= end30)
        for period in ("weekend", "days7", "days30"):
            choose_period(page, period)
            assert page.is_hidden("#pm-past-notice"), period
        assert rec.ops("open") == []
    finally:
        context.close()


def test_g6_past_mode_is_separate_and_warns(browser, g6):
    context, page, rec = open_g6_view(browser, g6)
    try:
        choose_period(page, "past")
        assert g6_ids_on_map(page, g6) == ids_where(g6, lambda p: p["when"] < g6["now"])
        assert page.is_visible("#pm-past-notice")
        assert page.text_content("#pm-past-notice") == PAST_NOTICE
        assert "過去・すべての撮影対象" in page.text_content("#pm-filter-summary")
        choose_period(page, "upcoming")
        assert page.is_hidden("#pm-past-notice")
        assert g6_ids_on_map(page, g6) == ids_where(g6, lambda p: p["when"] >= g6["now"])
    finally:
        context.close()


def test_g6_custom_range_never_mixes_past(browser, g6):
    context, page, rec = open_g6_view(browser, g6)
    try:
        now_jst = g6["now"].astimezone(JST)
        choose_period(page, "custom")
        page.fill("#pm-filter-from", (now_jst - timedelta(days=60)).strftime("%Y-%m-%d"))
        page.fill("#pm-filter-to", (now_jst + timedelta(days=25)).strftime("%Y-%m-%d"))
        page.dispatch_event("#pm-filter-to", "change")
        page.wait_for_timeout(150)
        end = (now_jst.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=26)) - timedelta(microseconds=1)
        assert g6_ids_on_map(page, g6) == ids_where(g6, lambda p: g6["now"] <= p["when"] <= end)
        assert page.is_visible("#pm-filter-custom-hint")       # 今より前は含めない →「過去を見る」へ案内
        assert page.is_hidden("#pm-past-notice")
        page.fill("#pm-filter-from", (now_jst - timedelta(days=60)).strftime("%Y-%m-%d"))
        page.fill("#pm-filter-to", (now_jst - timedelta(days=1)).strftime("%Y-%m-%d"))
        page.dispatch_event("#pm-filter-to", "change")
        page.wait_for_timeout(150)
        assert g6_ids_on_map(page, g6) == set()                # すべて過去の期間指定でも、過去は出さない
    finally:
        context.close()


def test_g6_viewport_is_the_region_and_follows_map_moves(browser, g6):
    context, page, rec = open_g6_view(browser, g6)
    try:
        outside = g6["plans"]["diamond-outside"]["plan_id"]
        assert outside not in all_marker_plan_ids(page)
        before = len(rec.ops("tile"))
        set_view(page, OUTSIDE[0], OUTSIDE[1], 12)               # 地図を動かすだけで取り直す（ボタンは無い）
        assert len(rec.ops("tile")) > before
        assert outside in all_marker_plan_ids(page)
        assert page.query_selector("text=この範囲で検索") is None
        assert all(r["method"] == "GET" for r in rec.ops("tile"))
        assert rec.ops("open") == []
    finally:
        context.close()


def test_g6_detail_and_viewer_still_work_for_a_filtered_plan(browser, g6):
    context, page, rec = open_g6_view(browser, g6)
    try:
        set_categories(page, ["pearl"])
        page.click("#pm-filter-panel .pm-filter-done")
        target = g6["plans"]["pearl-weekend"]["plan_id"]
        marker = page.query_selector(f'.leaflet-marker-icon[data-plan-ids="{target}"]')
        assert marker is not None
        marker.click()
        page.wait_for_selector("#pm-panel", state="visible")
        page.wait_for_function("() => !!document.querySelector('#pm-panel a[href^=\"/share#\"], #pm-panel .pm-view')")
        assert len(rec.ops("open")) == 1                        # 人が選んだときだけ open
    finally:
        context.close()


def test_g6_mobile_bottom_sheet_does_not_cover_the_map_when_closed(browser, g6):
    context, page, rec = open_g6_view(browser, g6, width=390, height=844)
    try:
        box = page.query_selector("#pm-filter-toggle").bounding_box()
        assert box["width"] <= 230 and box["height"] <= 64
        assert page.is_hidden("#pm-filter-panel")
        open_filter(page)
        sheet = page.evaluate("""() => { const s = document.getElementById('pm-filter-panel'); const r = s.getBoundingClientRect();
          return {position: getComputedStyle(s).position, bottom: Math.round(window.innerHeight - r.bottom), height: r.height, width: r.width}; }""")
        assert sheet["position"] == "fixed" and sheet["bottom"] == 0 and sheet["width"] >= 380
        assert sheet["height"] <= 844 * 0.63
        page.click("#pm-filter-panel .pm-filter-done")
        assert page.is_hidden("#pm-filter-panel")
        page.screenshot(path=str(Path(os.environ.get("PLANNER_MAP_ARTIFACTS", ".")) / "g6_mobile.png"))
    finally:
        context.close()
