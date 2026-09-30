"""Sidekick QR EXIF Viewer（/exif、HD-SIDEKICKQR-028）の配置を固定する。

- `exif.html` = Sidekick QR repository の `viewer/exif.html`（正本）と byte 一致（SHA-256 を固定。正本を変えたら copy し直し、ここも更新する）
- vercel.json: `/exif` に `X-Robots-Tag: noindex, nofollow`（ちょうど 1 件）。`/exif` への redirect は無い（fragment を 1 回で開く）
- page: meta robots noindex・referrer no-referrer・CSP connect-src 'none'・analytics / beacon / 外部 resource なし・link は /sidekick-qr だけ
- sitemap に載せない・ほかのページから link しない
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VIEWER = REPO_ROOT / "exif.html"
# Sidekick QR `viewer/exif.html`（source 9c4ed9a、HD-SIDEKICKQR-028）
VIEWER_SHA256 = "b4ee3e254205feb49108b5aa806fec21ce7769daf518c4d4447c14e8ee6e48e1"


def _vercel() -> dict:
    return json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))


def test_the_viewer_is_the_canonical_copy() -> None:
    assert hashlib.sha256(VIEWER.read_bytes()).hexdigest() == VIEWER_SHA256


def test_exif_has_exactly_one_noindex_header() -> None:
    entries = [h for h in _vercel()["headers"] if h["source"] == "/exif"]
    assert entries == [{"source": "/exif", "headers": [{"key": "X-Robots-Tag", "value": "noindex, nofollow"}]}]


def test_exif_is_not_redirected() -> None:
    for rule in _vercel()["redirects"]:
        assert not rule["source"].startswith("/exif"), rule
        assert not str(rule.get("destination", "")).startswith("/exif"), rule


def test_the_page_is_noindex_no_referrer_and_cannot_connect() -> None:
    html = VIEWER.read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, nofollow">' in html
    assert '<meta name="referrer" content="no-referrer">' in html
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html).group(1)
    for directive in ("default-src 'none'", "connect-src 'none'", "img-src 'none'", "form-action 'none'", "base-uri 'none'"):
        assert directive in csp
    assert "unsafe-inline" not in csp.split("script-src", 1)[1].split(";", 1)[0]


def test_the_page_has_no_analytics_beacon_or_external_resource() -> None:
    html = VIEWER.read_text(encoding="utf-8")
    visible = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    for token in ("googletagmanager", "gtag(", "sendBeacon", "fetch(", "XMLHttpRequest", "WebSocket", "reportActivity", "/api/"):
        assert token not in visible, token
    assert re.findall(r"(?:src|href)=\"([^\"]+)\"", visible) == ["/sidekick-qr"]


def test_exif_is_not_in_the_sitemap_and_not_linked() -> None:
    assert "/exif" not in (REPO_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    linked = []
    for page in REPO_ROOT.rglob("*.html"):
        rel = page.relative_to(REPO_ROOT).as_posix()
        if rel == "exif.html" or rel.startswith(("build-output/", "BackUp/", "templates/", "node_modules/")):
            continue
        if re.search(r'href="(https://www\.sidekick-lab\.com)?/exif["#?]', page.read_text(encoding="utf-8", errors="ignore")):
            linked.append(rel)
    assert linked == []
