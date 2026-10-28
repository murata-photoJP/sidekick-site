"""Sidekick Star の緊急配布停止（2026-10-28）の回帰試験。停止を解くときは、この試験も一緒に外す。

- register-dl.html：product が star・空・未指定・想定外の値なら、一時停止のお知らせへ移り、メールアドレスを送らない。
  配布中の製品（portrait / sky / ai / planner）は今までどおり（移らない）。
- vercel.json：Star の導線（/dl-star・/buy-star・/register-dl?product=star・product なし）だけを、お知らせへ一時的に転送する。
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
NODE = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"

HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const [file, search] = process.argv.slice(-2);  // node -e では argv に script のパスが入らない
const html = fs.readFileSync(file, 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const main = scripts.find(s => s.includes('CONSENT_VERSION'));
const out = { replaced: null, fetches: 0, productKey: null };
const stubEl = () => new Proxy(function(){}, {
  get: (t, k) => (k === 'value' ? 'someone@example.com' : (k === 'checked' ? true : (k === Symbol.toPrimitive ? () => '' : stubEl()))),
  set: () => true, apply: () => stubEl(),
});
const ctx = {
  window: { location: { search, href: '', replace: (u) => { if (!out.replaced) out.replaced = u; } } },
  document: { getElementById: () => stubEl(), querySelector: () => stubEl(), querySelectorAll: () => [], addEventListener: () => {}, createElement: () => stubEl(), body: stubEl() },
  URLSearchParams, console: { log() {}, warn() {}, error() {} },
  fetch: async (url, opt) => { out.fetches++; out.productKey = JSON.parse(opt.body).productKey; return { ok: true, json: async () => ({ ok: true }) }; },
  AbortController,
  gtag: () => {}, setTimeout: () => 0, clearTimeout: () => {}, alert: () => {}, navigator: { userAgent: 'test' },
  localStorage: { getItem: () => null, setItem: () => {} }, sessionStorage: { getItem: () => null, setItem: () => {} },
};
ctx.window.document = ctx.document;
ctx.location = ctx.window.location;
vm.createContext(ctx);
let loadError = null;
try { vm.runInContext(main, ctx); } catch (e) { loadError = String(e); }
const atLoad = out.replaced;
out.replaced = null;
(async () => {
  let submitError = null;
  try { await vm.runInContext('submitEmail()', ctx); } catch (e) { submitError = String(e); }
  console.log(JSON.stringify({ atLoad, atSubmit: out.replaced, fetches: out.fetches, productKey: out.productKey,
    href: ctx.window.location.href, loadError, submitError }));
})();
"""


def run_register(search: str) -> dict:
    p = subprocess.run([NODE, "-e", HARNESS, str(REPO / "register-dl.html"), search],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("search,want", [
    ("?product=star&src=sidekick-star", "/star-download-paused"),
    ("?product=star&src=lp-star-en&lang=en", "/en/star-download-paused"),
    ("", "/star-download-paused"),
    ("?src=direct", "/star-download-paused"),
    ("?product=", "/star-download-paused"),
    ("?product=Star", "/star-download-paused"),
    ("?product=unknown&lang=en", "/en/star-download-paused"),
    ("?product=star-core", "/star-download-paused"),
    ("?product=STAR&src=x-en", "/en/star-download-paused"),
])
def test_star_and_invalid_products_go_to_the_notice_and_send_nothing(search, want):
    r = run_register(search)
    assert r["loadError"] is None and r["submitError"] is None, r
    assert r["atLoad"] == want, r
    assert r["fetches"] == 0, r          # 送信ボタンの処理を呼んでも、メールアドレスを送らない
    assert r["atSubmit"] == want, r


@pytest.mark.parametrize("product", ["portrait", "sky", "ai", "planner"])
def test_active_products_still_register(product):
    r = run_register(f"?product={product}&src=test")
    assert r["loadError"] is None and r["submitError"] is None, r
    assert r["atLoad"] is None and r["atSubmit"] is None, r   # お知らせへ移らない
    assert r["fetches"] == 1 and r["productKey"] == product, r  # 今までどおり登録を送る
    assert r["href"] == f"/dl-{product}", r                    # 製品のダウンロードの頁へ進む


# ---------- vercel.json ----------
CFG = json.loads((REPO / "vercel.json").read_text(encoding="utf-8"))


def _route(path_query: str):
    path, _, query = path_query.partition("?")
    q = dict(kv.split("=", 1) if "=" in kv else (kv, "") for kv in query.split("&") if kv)
    if path.endswith(".html"):
        path = path[:-5]
    for r in CFG["redirects"]:
        if r["source"] != path:
            continue
        has, missing = r.get("has", []), r.get("missing", [])
        if any(h["type"] != "query" for h in has):
            continue
        if all(h["key"] in q and q[h["key"]] == h["value"] for h in has) and all(m["key"] not in q for m in missing):
            return r["destination"], r.get("permanent")
    return None, None


@pytest.mark.parametrize("url,want", [
    ("/dl-star", "/star-download-paused"), ("/dl-star.html", "/star-download-paused"), ("/buy-star", "/star-download-paused"),
    ("/register-dl?product=star&src=sidekick-star", "/star-download-paused"),
    ("/register-dl?product=star&src=lp-star-en&lang=en", "/en/star-download-paused"),
    ("/register-dl", "/star-download-paused"),
])
def test_star_routes_redirect_temporarily(url, want):
    dest, permanent = _route(url)
    assert dest == want and permanent is False, (url, dest, permanent)


@pytest.mark.parametrize("url", [
    "/dl-portrait", "/dl-sky", "/dl-ai", "/dl-planner", "/buy-portrait", "/buy-sky",
    "/register-dl?product=portrait&src=lp-portrait", "/register-dl?product=sky&src=lp-sky&lang=en",
    "/register-dl?product=planner&src=sidekick-planner", "/register-dl?product=ai&src=dl-ai",
    "/sidekick-star", "/lp-star", "/star-download-paused", "/en/star-download-paused",
])
def test_other_routes_are_not_redirected(url):
    assert _route(url) == (None, None), url


def test_notice_pages_exist_in_both_languages():
    for rel in ["star-download-paused.html", "en/star-download-paused.html"]:
        text = (REPO / rel).read_text(encoding="utf-8")
        assert len(re.findall(r"<h1\b", text)) == 1, rel
        assert "安全対策" in text or "For safety" in text, rel
