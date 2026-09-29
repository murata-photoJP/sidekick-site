"""Sidekick QR Web 版の validation surface と、Web app の copy の固定テスト（2026-09-28、HD-SIDEKICKQR-018、Sidekick QR repository AI-15986）。

固定していること:

1. validation surface（`validation/sidekick-qr-web/<id>/`）: analytics なし（GA4 / Clarity なし）・shell は meta noindex・vercel.json の X-Robots-Tag（`/validation/(.*)`）、
   sitemap・他のページから link されない、shell の iframe が同じ folder の `sidekick-qr-app/app` を指す、shell = テンプレートの生成物。
2. Web app の copy（`sidekick-qr-web-manifest.json` のある folder すべて）: 置いてある file = manifest（SHA-256）、manifest 以外の file なし、
   core の js が Portable 1.0.0（SidekickQR-1.0.0.zip）と byte 一致、入口 app.html は Portable の入口 ＋ Web 版だけの script を読む 1 行
   （その 1 行を除くと Portable の入口と byte 一致）、Web 版だけの module は web_share.js（HD-SIDEKICKQR-020）だけ（D-5）、
   analytics / 通信の code なし、CSP connect-src 'none'、shell の iframe に allow="web-share"。
   正本は Sidekick QR repository の app/（tools/export_web_app.py で書き出す）。ここが落ちたら、site 側で直さず Sidekick QR 側から書き出し直す。

リポジトリを読むだけで、何も書き込まない。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "build" / "site"))
import build_site as bs  # noqa: E402

PREFIX = "validation/sidekick-qr-web/"
VALIDATION_DIR = REPO_ROOT / "validation" / "sidekick-qr-web" / bs.SIDEKICK_QR_WEB_VALIDATION_ID
MANIFEST = "sidekick-qr-web-manifest.json"
# Sidekick QR 1.0.0（Portable、SidekickQR-1.0.0.zip sha256 6bdaac3b…）の入口 HTML と js の SHA-256（Sidekick QR repository docs/release_artifact_1.0.0.json）
PORTABLE_ENTRY = "6cee5c4d3bd61e6d193eb615001a674d1fea9af88f3daa7e0c37129e30c30dd1"
WEB_ENTRY_LINE = b'\n<script src="js/web_share.js"></script>'
WEB_ONLY = {"js/web_share.js"}
# 1.0.1（HD-SIDEKICKQR-023、SidekickQR-1.0.1.zip sha256 0447c2e8…）: 1.0.0 と違うのは card_template.js（Secondary = /card/qr）だけ
PORTABLE_1_0_1 = {
    "js/app.js": "c82d776210b0f77b",
    "js/card_engine.js": "e230f82d88b4cd42f0c646b4963295afc8dd4af972aea3f3efe80aad1b83c9fc",
    "js/card_template.js": "4d11ef85e90c11c8",
    "js/image_adapter.js": "ca554d5468e41573",
    "js/qr_encoder.js": "60cb49d492b0d12e",
    "js/startup_check.js": "860982c514cc7f7e3b5bff34f31f5a51a432f5f55315031c2d1a2749d6c1d7b0",
    "js/url_policy.js": "15b3ae650ebceedf",
}
PORTABLE_1_0_0 = {
    "js/app.js": "c82d776210b0f77b",
    "js/card_engine.js": "e230f82d88b4cd42f0c646b4963295afc8dd4af972aea3f3efe80aad1b83c9fc",
    "js/card_template.js": "dfdb766a5b0a50e3257af92eea797d854ce4bd647ae80fac5818b3586fa1d802",
    "js/image_adapter.js": "ca554d5468e41573",
    "js/qr_encoder.js": "60cb49d492b0d12e",
    "js/startup_check.js": "860982c514cc7f7e3b5bff34f31f5a51a432f5f55315031c2d1a2749d6c1d7b0",
    "js/url_policy.js": "15b3ae650ebceedf",
}
ANALYTICS = ("googletagmanager", "gtag(", "google-analytics", "clarity.ms", "clarity(")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _app_copies() -> list[Path]:
    return sorted(p.parent for p in REPO_ROOT.rglob(MANIFEST) if "build-output" not in p.parts)


# ---------------------------------------------------------------------------
# 1. validation surface
# ---------------------------------------------------------------------------

def test_validation_pages_have_no_analytics() -> None:
    pages = sorted(VALIDATION_DIR.rglob("*.html"))
    assert len(pages) == 2                                                   # shell と app
    for p in pages:
        text = p.read_text(encoding="utf-8").lower()
        assert not [s for s in ANALYTICS if s in text], p


def test_validation_is_noindex() -> None:
    shell = (VALIDATION_DIR / "index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, nofollow">' in shell
    vercel = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    rule = [h for h in vercel.get("headers", []) if h["source"] == "/validation/(.*)"]
    assert rule and {"key": "X-Robots-Tag", "value": "noindex, nofollow"} in rule[0]["headers"]


def test_validation_is_not_linked_or_listed() -> None:
    sitemap = (REPO_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    assert "validation" not in sitemap and "sidekick-qr-app" not in sitemap
    linked = []
    for p in REPO_ROOT.rglob("*.html"):
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel.startswith((PREFIX, "build-output/", "BackUp/", "templates/")):
            continue
        if "sidekick-qr-web" in p.read_text(encoding="utf-8", errors="replace"):
            linked.append(rel)
    assert not linked, linked


def test_the_shell_embeds_its_own_app_copy_and_matches_the_template() -> None:
    shell = (VALIDATION_DIR / "index.html").read_text(encoding="utf-8")
    src = re.search(r'<iframe id="sqr-app" src="([^"]+)"', shell).group(1)
    assert src == "/" + VALIDATION_DIR.relative_to(REPO_ROOT).as_posix() + "/sidekick-qr-app/app"
    assert 'allow="web-share"' in re.search(r'<iframe id="sqr-app"[^>]*>', shell).group(0)
    assert (VALIDATION_DIR / "sidekick-qr-app" / "app.html").is_file()
    assert shell == bs.render_all("validation/sidekick-qr-web")[bs.PAGES["validation/sidekick-qr-web"]["output"]]
    assert shell.count("<h1") == 1


# ---------------------------------------------------------------------------
# 2. Web app の copy（drift 検出）
# ---------------------------------------------------------------------------

def test_there_is_an_app_copy() -> None:
    assert VALIDATION_DIR / "sidekick-qr-app" in _app_copies()


# copy ごとの Portable の版: validation surface は 2026-09-28 の 1.0.0 のまま（HD-SIDEKICKQR-024、今後の review には使わない）、
# production の /sidekick-qr-app/ は 2026-09-30 から 1.0.1（HD-SIDEKICKQR-023）
PORTABLE = {
    "1.0.0": (PORTABLE_1_0_0, "6bdaac3bd617b523195a07448d198ae013869a7ccd0d8c719f8862e666cbf405"),
    "1.0.1": (PORTABLE_1_0_1, "0447c2e8fd69949e54ba1242835eca71623de491f7bc17c665de15722f4964e1"),
}
EXPECTED_VERSION = {VALIDATION_DIR / "sidekick-qr-app": "1.0.0", REPO_ROOT / "sidekick-qr-app": "1.0.1"}


@pytest.mark.parametrize("copy", _app_copies(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_app_copy_has_the_expected_version(copy: Path) -> None:
    manifest = json.loads((copy / MANIFEST).read_text(encoding="utf-8"))
    assert manifest["version"] == EXPECTED_VERSION[copy]


@pytest.mark.parametrize("copy", _app_copies(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_app_copy_matches_its_manifest_and_portable(copy: Path) -> None:
    manifest = json.loads((copy / MANIFEST).read_text(encoding="utf-8"))
    core, artifact_sha256 = PORTABLE[manifest["version"]]
    listed = {f["path"]: f["sha256"] for f in manifest["files"]}
    present = sorted(p.relative_to(copy).as_posix() for p in copy.rglob("*") if p.is_file() and p.name != MANIFEST)
    assert present == sorted(listed), "manifest に無い file / 足りない file"
    for name, digest in listed.items():
        assert _sha(copy / name) == digest, f"{name}: manifest と違う（site で直さず Sidekick QR から書き出し直す）"
        if name in core:
            assert digest.startswith(core[name]), f"{name}: Portable {manifest['version']} と違う（D-5、core は fork しない）"
    entry = (copy / "app.html").read_bytes()
    assert entry.count(WEB_ENTRY_LINE) == 1
    assert hashlib.sha256(entry.replace(WEB_ENTRY_LINE, b"")).hexdigest() == PORTABLE_ENTRY, "app.html が Portable の入口 ＋ 1 行ではない"
    assert sorted(listed) == sorted(set(core) | {"app.html"} | WEB_ONLY)
    roles = {f["path"]: f.get("role", "") for f in manifest["files"]}
    assert roles["js/web_share.js"] == "web only"
    assert manifest["portable_identity"]["artifact_sha256"] == artifact_sha256


@pytest.mark.parametrize("copy", _app_copies(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_app_copy_has_no_analytics_and_keeps_its_csp(copy: Path) -> None:
    for p in copy.rglob("*"):
        if p.suffix in (".html", ".js"):
            text = p.read_text(encoding="utf-8").lower()
            assert not [s for s in ANALYTICS if s in text], p
    assert "connect-src 'none'" in (copy / "app.html").read_text(encoding="utf-8")
