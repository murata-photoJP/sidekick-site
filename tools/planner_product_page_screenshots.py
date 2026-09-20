"""Sidekick Planner 製品ページ（/sidekick-planner）用スクリーンショットを、実際の β1.00 UI から生成する。

2026-09-20 新設（Track planner-beta1-web-product-page、AI-10450）。

モックアップではなく、**実際に起動した Sidekick Planner β1.00（RC13 と同じ UI）** と
このリポジトリの Snapshot Viewer（`share.html`）を Playwright（Chromium）で操作して撮る。
製品ページに載せる画像が「実画面」であることを、この手順で再現可能にしておく。

前提（手順は docs/PLANNER_PRODUCT_PAGE.md「スクリーンショットの再生成」を参照）:

1. Sidekick Planner β1.00 の **配布物のコピー**（canonical の `dist/rc13` を直接動かさない）を
   headless で起動しておく:
       SidekickPlanner.exe --port 18795 --no-browser --no-window --no-activity-upload
   `--no-activity-upload` で匿名 Activity の送信を止める（QR 生成で本番 endpoint へ件数を送らない）。
2. このリポジトリのルートを静的配信しておく（Viewer 用。`/api/*` は無いので beacon は 404 で無害）:
       py -3.10 -m http.server 3333 --directory <html>
3. `py -3.10` に playwright（Chromium）と opencv-python（QR の読み取り）が入っていること。

使い方:
    py -3.10 tools/planner_product_page_screenshots.py --out images/planner
    py -3.10 tools/planner_product_page_screenshots.py --planner http://127.0.0.1:18795 --site http://127.0.0.1:3333 --out images/planner

生成物（PNG）: planner-overview / search-b / composition-preview / map / qr-share / viewer-mobile
検索B の座標・期間は clean-machine 試験（RC11〜RC13）と同じ値を使う
（緯度 35.3714150 / 経度 138.7834167 / 2027-03-29〜04-02 → 最良 2027-03-30T16:08:59）。
被写体は既定（富士山）、ターゲットも既定のまま。

このスクリプトは Planner のデータ・設定・本番サイト・本番 API に何も書かない
（Planner 側の出力は起動した配布物コピーの output/ にだけ残る）。
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

SEARCH_B = {
    "latitude": "35.3714150",
    "longitude": "138.7834167",
    "start": "2027-03-29",
    "end": "2027-04-02",
}
DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}


TILES_SETTLED = (
    "() => { const t = document.querySelectorAll('.leaflet-tile'); "
    "return t.length > 0 && Array.from(t).every(e => e.classList.contains('leaflet-tile-loaded')); }"
)


def wait_tiles(page, timeout: int = 120_000) -> None:
    """Leaflet の地図タイルがすべて読み込まれるまで待つ（UI は定期 polling を行うため
    networkidle は使えない）。"""
    page.wait_for_function(TILES_SETTLED, timeout=timeout)
    page.wait_for_timeout(1_200)


def decode_qr(png_bytes: bytes) -> str:
    import numpy as np  # opencv と一緒に入る
    import cv2

    array = np.frombuffer(png_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    text, _points, _ = cv2.QRCodeDetector().detectAndDecode(image)
    if not text:
        raise RuntimeError("QR を読み取れなかった")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--planner", default="http://127.0.0.1:18795", help="起動済み Planner の origin")
    parser.add_argument("--site", default="http://127.0.0.1:3333", help="静的配信中の sidekick-site の origin（Viewer 用）")
    parser.add_argument("--out", required=True, help="PNG の出力先ディレクトリ")
    parser.add_argument("--headed", action="store_true", help="ブラウザを表示して実行する（確認用）")
    args = parser.parse_args(argv)

    from playwright.sync_api import sync_playwright

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    planner_url = args.planner.rstrip("/") + "/planner"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(viewport=DESKTOP, device_scale_factor=1, locale="ja-JP")
        page = context.new_page()
        # 1. 起動直後（被写体 = 富士山、参考ライン）
        page.goto(planner_url, wait_until="load")
        page.wait_for_selector("#poi-select option", state="attached", timeout=60_000)
        wait_tiles(page)
        page.wait_for_timeout(1_500)
        page.screenshot(path=str(out / "planner-overview.png"))
        print("[ok] planner-overview.png")

        # 2. 検索B（撮影地から日時を探す）
        page.fill("#search-b-latitude", SEARCH_B["latitude"])
        page.fill("#search-b-longitude", SEARCH_B["longitude"])
        page.fill("#search-b-start", SEARCH_B["start"])
        page.fill("#search-b-end", SEARCH_B["end"])
        page.click("#search-b-run")
        # 起動時に前回の結果が復元されることがあるので、「計算中」表示の出現→消滅で完了を判定する
        page.wait_for_selector("#search-b-busy:not([hidden])", state="attached", timeout=30_000)
        page.wait_for_selector("#search-b-busy[hidden]", state="attached", timeout=300_000)
        page.wait_for_function(
            "() => /最良:/.test(document.querySelector('#search-b-summary').textContent)",
            timeout=30_000,
        )
        wait_tiles(page)
        page.wait_for_timeout(1_000)
        summary = page.inner_text("#search-b-summary")
        print("[ok] search-b summary:\n" + summary)
        page.screenshot(path=str(out / "search-b.png"))
        page.locator("#map").screenshot(path=str(out / "map.png"))
        print("[ok] search-b.png / map.png")

        # 3. 展望プレビュー（検索B 最良日時）
        page.wait_for_selector("#search-b-preview:not([disabled])", timeout=60_000)
        page.click("#search-b-preview")
        page.wait_for_selector("#view-preview:not([hidden])", timeout=60_000)
        page.wait_for_function(
            "() => document.querySelectorAll('#preview-svg *').length > 20 && "
            "!/計算中|読み込み中|候補地点を選択/.test(document.querySelector('#preview-status').textContent)",
            timeout=300_000,
        )
        page.wait_for_timeout(1_500)
        page.screenshot(path=str(out / "composition-preview.png"))
        page.locator("#view-preview").screenshot(path=str(out / "composition-preview-panel.png"))
        print("[ok] composition-preview.png / composition-preview-panel.png")

        # 4. QR 共有（スマホで見る = Viewer link）
        page.click("#qr-send-button")
        # 初回は「利用状況の記録について」→「QRで共有する前に」の 2 段の説明が挟まる。
        # 記録の ON/OFF はここでは触らない（既定のまま。送信は起動時の --no-activity-upload で止めている）。
        page.wait_for_selector("#activity-disclosure-dialog:not([hidden]), #qr-send-disclosure-dialog:not([hidden])",
                               timeout=30_000)
        if page.locator("#activity-disclosure-dialog:not([hidden])").count():
            page.click("#activity-disclosure-continue")
        page.wait_for_selector("#qr-send-disclosure-dialog:not([hidden])", timeout=30_000)
        page.click("#qr-send-disclosure-accept")
        page.wait_for_selector("#qr-send-dialog:not([hidden])", timeout=120_000)
        page.wait_for_function(
            "() => (document.querySelector('#qr-send-image').src || '').startsWith('blob:')",
            timeout=120_000,
        )
        page.wait_for_timeout(800)
        page.locator("#qr-send-dialog").screenshot(path=str(out / "qr-share.png"))
        print("[ok] qr-share.png")

        # 5. Viewer（スマホ表示）— QR から共有 URL を読み、このリポジトリの share.html で開く
        # 画面に表示中の QR 画像（blob:）をそのまま読み取る（サーバー応答は再取得しない）
        qr_b64 = page.evaluate(
            "async () => { const r = await fetch(document.querySelector('#qr-send-image').src);"
            " const b = await r.arrayBuffer(); let s = ''; new Uint8Array(b).forEach(x => s += String.fromCharCode(x));"
            " return btoa(s); }"
        )
        share_url = decode_qr(base64.b64decode(qr_b64))
        if "/share#" not in share_url:
            raise RuntimeError(f"共有 URL の形式が想定外: {share_url[:80]}")
        fragment = share_url.split("#", 1)[1]
        mobile = browser.new_context(viewport=MOBILE, device_scale_factor=2, is_mobile=True,
                                     has_touch=True, locale="ja-JP")
        viewer = mobile.new_page()
        # 静的配信（http.server）は cleanUrls を持たないので share.html を直接開く（本番は /share）
        viewer.goto(args.site.rstrip("/") + "/share.html#" + fragment, wait_until="load")
        viewer.wait_for_load_state("networkidle", timeout=120_000)   # Viewer は Leaflet ではなく自前描画。polling も無い
        viewer.wait_for_timeout(2_000)
        viewer.screenshot(path=str(out / "viewer-mobile.png"))
        viewer.screenshot(path=str(out / "viewer-mobile-full.png"), full_page=True)
        print("[ok] viewer-mobile.png / viewer-mobile-full.png")
        mobile.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
