"""プランナーQRマップ（G-3 Map Viewer）の browser test（Firestore Emulator 上の実データ）。

`npm run test:qr-map:browser` から起動される（tools/qr_map/run_browser_tests.mjs が dev server ＋ seed を用意し、
PLANNER_MAP_BASE_URL / PLANNER_MAP_SEED_MANIFEST を渡す）。単独では走らせない（skip ではなく FAIL）。

地理院タイルは context.route で 1×1 PNG に差し替える（要求先が cyberjapandata.gsi.go.jp であることは数えて確かめる）。
それ以外の外部 host への要求は止めて記録し、0 件であることを確かめる。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import sync_playwright

BASE = os.environ.get("PLANNER_MAP_BASE_URL", "")
MANIFEST_PATH = os.environ.get("PLANNER_MAP_SEED_MANIFEST", "")
ARTIFACTS = Path(os.environ.get("PLANNER_MAP_ARTIFACTS", "."))
if not BASE or not MANIFEST_PATH:
    raise RuntimeError("npm run test:qr-map:browser から起動する（Emulator ＋ dev server が要る）")
assert re.match(r"^http://127\.0\.0\.1:\d+$", BASE), BASE

MANIFEST = json.loads(Path(MANIFEST_PATH).read_text(encoding="utf-8"))
PLANS = {p["key"]: p for p in MANIFEST["plans"]}
VISIBLE = [p for p in MANIFEST["plans"] if p["category"] == "visible"]
HIDDEN = [p for p in MANIFEST["plans"] if p["category"] != "visible"]
VIEWER_SHA256 = "b73c264a799401d7f6b88c9b5c09029754240826c65646d30b181f8cf9c9fa56"  # 配置済み Viewer（変更しない）
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


class Recorder:
    def __init__(self) -> None:
        self.api: list[dict] = []
        self.gsi: list[str] = []
        self.blocked: list[str] = []
        self.tile_bodies: list[str] = []

    def ops(self, op: str) -> list[dict]:
        return [r for r in self.api if r["op"] == op]


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


def new_page(browser, width=1280, height=800):
    rec = Recorder()
    context = browser.new_context(viewport={"width": width, "height": height})

    def gsi(route):
        rec.gsi.append(route.request.url)
        route.fulfill(status=200, content_type="image/png", body=PNG_1X1)

    def external(route):
        url = route.request.url
        host = urlparse(url).hostname or ""
        if host in ("127.0.0.1",):
            route.continue_()
        else:
            rec.blocked.append(url)
            route.abort()

    context.route(re.compile(r"^https?://(?!127\.0\.0\.1)(?!cyberjapandata\.gsi\.go\.jp).*"), external)
    context.route("https://cyberjapandata.gsi.go.jp/**", gsi)

    def on_request(req):
        u = urlparse(req.url)
        if u.path == "/api/qr-map":
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            rec.api.append({"op": q.get("op"), "q": q, "method": req.method, "body": req.post_data})

    def on_response(res):
        u = urlparse(res.url)
        if u.path == "/api/qr-map" and "op=tile" in u.query and res.status == 200:
            rec.tile_bodies.append(res.text())

    context.on("request", on_request)
    context.on("response", on_response)
    page = context.new_page()
    return context, page, rec


def settle(page, timeout=10_000):
    """debounce（200 ms）→ tile 取得 → 描画が終わるまで待つ。"""
    page.wait_for_timeout(350)
    page.wait_for_function(
        "() => { const s = document.getElementById('pm-status'); return s && s.dataset.kind !== 'loading'; }",
        timeout=timeout)
    page.wait_for_timeout(100)


def goto_map(page):
    page.goto(BASE + "/planner-map")
    page.wait_for_function("() => window.PlannerMap && window.PlannerMap.map")
    settle(page)


def set_view(page, lat, lon, zoom):
    page.evaluate("([lat, lon, z]) => window.PlannerMap.map.setView([lat, lon], z, {animate: false})", [lat, lon, zoom])
    settle(page)


def marker_ids(page) -> list[list[str]]:
    return page.eval_on_selector_all(
        ".leaflet-marker-icon", "els => els.map(e => (e.dataset.planIds || '').split(',').filter(Boolean))")


def all_marker_plan_ids(page) -> set[str]:
    return {pid for group in marker_ids(page) for pid in group}


def marker_for(page, plan_id):
    return page.locator(f".leaflet-marker-icon[data-plan-ids*='{plan_id}']")


# ---------------------------------------------------------------------------------------------
def test_01_03_page_loads_with_attribution_and_local_leaflet(browser):
    context, page, rec = new_page(browser)
    scripts = []
    page.on("request", lambda r: scripts.append(r.url) if r.resource_type == "script" else None)
    goto_map(page)
    assert page.locator("h1").inner_text() == "プランナーQRマップ"
    attribution = page.locator(".leaflet-control-attribution")
    assert "地理院タイル" in attribution.inner_text()
    assert attribution.locator("a[href='https://maps.gsi.go.jp/development/ichiran.html']").count() == 1
    assert scripts and all(urlparse(u).hostname == "127.0.0.1" for u in scripts), scripts
    assert any(u.endswith("/assets/vendor/leaflet-1.9.4/leaflet.js") for u in scripts)
    assert rec.gsi and all(urlparse(u).hostname == "cyberjapandata.gsi.go.jp" and "/xyz/pale/" in u for u in rec.gsi)
    assert rec.blocked == []
    context.close()


def test_04_06_bounded_tiles_level_choice_and_dedup(browser):
    context, page, rec = new_page(browser)
    goto_map(page)  # z6
    first = rec.ops("tile")
    assert first and len(first) <= 30 and {r["q"]["z"] for r in first} == {"6"}
    for zoom, level in ((8, "6"), (11, "6"), (13, "10"), (15, "10"), (17, "14")):
        before = len(rec.ops("tile"))
        set_view(page, 35.418, 138.87, zoom)
        new = rec.ops("tile")[before:]
        assert all(r["q"]["z"] == level for r in new), (zoom, new)
        assert len(new) <= 30
    # 同じ範囲へ戻っても同じ tile は取り直さない（client cache / 実行中の要求の共有）
    set_view(page, 35.418, 138.87, 13)
    set_view(page, 35.0116, 135.7681, 13)
    set_view(page, 35.418, 138.87, 13)
    keys = [(r["q"]["z"], r["q"]["x"], r["q"]["y"]) for r in rec.ops("tile")]
    assert len(keys) == len(set(keys)), "同じ tile を 2 回要求した"
    # page 表示・pan・zoom・tile・marker では open しない
    assert rec.ops("open") == []
    context.close()


def test_07_10_only_active_plans_appear(browser):
    context, page, rec = new_page(browser)
    goto_map(page)
    for p in VISIBLE:
        set_view(page, p["lat"], p["lon"], 13)
        assert p["plan_id"] in all_marker_plan_ids(page), p["key"]
    for p in HIDDEN:
        set_view(page, p["lat"], p["lon"], 13)
        assert p["plan_id"] not in all_marker_plan_ids(page), p["key"]
        assert all(p["plan_id"] not in body for body in rec.tile_bodies), p["key"]
    assert rec.ops("open") == []
    context.close()


def test_11_12_tile_responses_expose_no_fragment_or_owner_fields(browser):
    context, page, rec = new_page(browser)
    goto_map(page)
    set_view(page, 35.418, 138.87, 13)
    assert rec.tile_bodies
    allowed = {"plan_id", "lat", "lon", "genre", "genre_label", "target_label", "sky_object_label", "t_d", "location_precision"}
    for body in rec.tile_bodies:
        data = json.loads(body)
        assert set(data) <= {"z", "x", "y", "truncated", "count", "plans"}
        for plan in data["plans"]:
            assert set(plan) <= allowed, set(plan) - allowed
        for word in ("fragment", "manage_token", "owner", "snapshot", "idempotency", "delete_after", "expires_at"):
            assert word not in body, word
        for p in MANIFEST["plans"]:
            assert p["fragment"] not in body
    context.close()


def test_13_17_18_explicit_open_returns_fragment_and_existing_viewer_url(browser):
    context, page, rec = new_page(browser)
    goto_map(page)
    pearl = PLANS["pearl"]
    set_view(page, pearl["lat"], pearl["lon"], 13)
    assert rec.ops("open") == []                       # marker を描いただけでは open しない
    marker_for(page, pearl["plan_id"]).click()
    page.wait_for_selector(".pm-detail")
    opens = rec.ops("open")
    assert len(opens) == 1 and opens[0]["method"] == "POST"
    assert json.loads(opens[0]["body"]) == {"plan_id": pearl["plan_id"]}
    link = page.locator(".pm-detail a.pm-view")
    assert link.get_attribute("href") == "/share#" + pearl["fragment"]
    assert link.get_attribute("rel") == "noopener noreferrer"
    assert "パール" in page.locator(".pm-detail").inner_text()
    # 「計画を見る」→ 既存 Viewer がそのまま開く
    with page.expect_popup() as popup_info:
        link.click()
    viewer = popup_info.value
    viewer.wait_for_selector("#status.ok", timeout=15_000)
    assert viewer.url.endswith("/share#" + pearl["fragment"])
    context.close()


def test_19_viewer_itself_unchanged(browser):
    context, page, rec = new_page(browser)
    res = page.request.get(BASE + "/share")
    body = res.body().replace(b"\r\n", b"\n")
    assert hashlib.sha256(body).hexdigest() == VIEWER_SHA256
    context.close()


def test_20_21_nearby_plans_stay_individually_selectable(browser):
    context, page, rec = new_page(browser)
    goto_map(page)
    sm = PLANS["sunmoon"]
    near_keys = ["sunmoon", "milkyway", "starscape", "trails-near-40m", "trails-near-280m"]
    expected = {PLANS[k]["plan_id"] for k in near_keys}
    set_view(page, sm["lat"], sm["lon"], 13)
    groups = [set(g) for g in marker_ids(page) if expected & set(g)]
    assert groups == [expected], groups                 # 近い 5 件は 1 つにまとまって見える
    group_marker = marker_for(page, sm["plan_id"])
    assert group_marker.get_attribute("data-count") == "5"
    group_marker.click()
    page.wait_for_selector(".pm-group-list")
    assert rec.ops("open") == []                         # 一覧を出すだけでは open しない
    items = page.locator(".pm-group-item")
    assert items.count() == 5
    listed = {items.nth(i).get_attribute("data-plan-id") for i in range(5)}
    assert listed == expected                            # grouping で identity は変わらない
    opened = []
    for i in range(5):
        if i > 0:
            group_marker.click()
            page.wait_for_selector(".pm-group-list")
        page.locator(".pm-group-item").nth(i).locator("button.pm-open").click()
        page.wait_for_selector(".pm-detail")
        opened.append(page.locator(".pm-detail").get_attribute("data-plan-id"))
    assert set(opened) == expected and len(rec.ops("open")) == 5
    # 最大まで拡大すると 40 m・280 m の計画は別の pin になる（表示上の grouping だけ）
    set_view(page, sm["lat"], sm["lon"], 18)
    same_point = {PLANS[k]["plan_id"] for k in ("sunmoon", "milkyway", "starscape")}
    groups18 = [set(g) for g in marker_ids(page) if expected & set(g)]
    assert same_point in groups18 and {PLANS["trails-near-40m"]["plan_id"]} in groups18
    context.close()


def test_22_empty_area(browser):
    context, page, rec = new_page(browser)
    goto_map(page)
    set_view(page, 30.0, 150.0, 9)
    assert page.locator("#pm-status").get_attribute("data-kind") == "empty"
    assert "まだありません" in page.locator("#pm-status").inner_text()
    context.close()


def test_23_api_error_and_detail_unavailable(browser):
    context, page, rec = new_page(browser)
    goto_map(page)
    page.route("**/api/qr-map?op=tile*", lambda route: route.fulfill(status=500, body="{}"))
    set_view(page, 33.59, 130.40, 13)  # 未取得の範囲（福岡）
    status = page.locator("#pm-status")
    assert status.get_attribute("data-kind") == "error"
    assert status.locator("button.pm-retry").count() == 1
    page.unroute("**/api/qr-map?op=tile*")
    kyoto = PLANS["trails-kyoto"]
    set_view(page, kyoto["lat"], kyoto["lon"], 13)
    page.route("**/api/qr-map?op=open", lambda route: route.fulfill(status=404, content_type="application/json", body='{"error":"NOT_FOUND"}'))
    marker_for(page, kyoto["plan_id"]).click()
    page.wait_for_selector("text=この計画は表示できません")
    context.close()


def test_24_desktop_smoke(browser):
    context, page, rec = new_page(browser, 1280, 800)
    goto_map(page)
    set_view(page, 35.40, 138.75, 10)
    assert page.locator(".leaflet-marker-icon").count() >= 3
    page.screenshot(path=str(ARTIFACTS / "desktop_1280x800.png"))
    assert rec.blocked == []
    context.close()


def test_25_mobile_width_smoke(browser):
    context, page, rec = new_page(browser, 390, 844)
    goto_map(page)
    pearl = PLANS["pearl"]
    set_view(page, pearl["lat"], pearl["lon"], 13)
    marker_for(page, pearl["plan_id"]).click()
    page.wait_for_selector(".pm-detail")
    map_box = page.locator("#pm-map").bounding_box()
    panel_box = page.locator("#pm-panel").bounding_box()
    assert map_box["height"] > 200 and panel_box["y"] >= map_box["y"] + map_box["height"] - 1
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "mobile_390x844.png"))
    context.close()


def test_26_no_external_hosts_besides_gsi(browser):
    context, page, rec = new_page(browser)
    goto_map(page)
    set_view(page, 35.418, 138.87, 13)
    assert rec.blocked == []          # Firebase / Google / CDN 等への要求は 0（API は 127.0.0.1 の dev server だけ）
    assert all(urlparse(BASE).hostname == "127.0.0.1" for _ in rec.api)
    context.close()
