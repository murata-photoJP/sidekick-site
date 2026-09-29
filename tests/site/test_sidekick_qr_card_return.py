"""Sidekick QR の Secondary return endpoint `/card/qr`（vercel.json の redirect 2 件）の固定テスト。
2026-09-30 新設（Sidekick QR repository の HD-SIDEKICKQR-023、docs/FUTURE_WORK.md §8.2）。

固定していること:

1. `/card/qr` の規則はちょうど 2 件、apex / vercel.app → www の規則の後・既存の規則の前、順番は JA（has accept-language）→ EN（条件なし）。
2. どちらも 307（`permanent: false`。308 / 301 にしない = 行き先を後で変えられる）。
3. destination は固定 path ＋ 固定 UTM だけ（utm_source=sidekick-qr / utm_medium=qr-card / utm_campaign=secondary-qr）。
   source に parameter・capture を持たない（open redirect・Card ID・user ID を受け取る場所を作らない）。utm_content / utm_term を使わない。
4. 言語判定の regex: Vercel の `has` の string 値が「完全一致」か「部分一致」かは docs から確定できない（2026-09-30 時点）ので、
   **どちらの解釈でも同じ結果**になることを両方の意味で確かめる。判定の向きは JA page の client script（一覧のどこかに `ja*`）に合わせる。
5. `/card/` は入口専用: sitemap に載せない・site の HTML から link しない・`/card/` に file を置かない。
6. 既存の `/sidekick-qr` / `/en/sidekick-qr` を redirect の source にしない（旧 Card の Secondary はそのまま 200）。

production 上の実測（Vercel の proxy での一致の仕方・incoming query の扱い）は Sidekick QR repository の release 記録に残す。
リポジトリを読むだけで、何も書き込まない。
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UTM = [("utm_source", "sidekick-qr"), ("utm_medium", "qr-card"), ("utm_campaign", "secondary-qr")]
JA_DEST = "/sidekick-qr?utm_source=sidekick-qr&utm_medium=qr-card&utm_campaign=secondary-qr"
EN_DEST = "/en/sidekick-qr?utm_source=sidekick-qr&utm_medium=qr-card&utm_campaign=secondary-qr"


@pytest.fixture(scope="module")
def redirects() -> list[dict]:
    return json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))["redirects"]


@pytest.fixture(scope="module")
def card_rules(redirects) -> list[dict]:
    return [r for r in redirects if r["source"].startswith("/card")]


def test_exactly_two_rules_in_order(redirects, card_rules):
    assert [r["source"] for r in card_rules] == ["/card/qr", "/card/qr"]
    idx = [i for i, r in enumerate(redirects) if r["source"] == "/card/qr"]
    assert idx[1] == idx[0] + 1
    # host の規則（apex / vercel.app → www）が先
    host_idx = [i for i, r in enumerate(redirects) if any(h.get("type") == "host" for h in r.get("has", []))]
    assert host_idx and max(host_idx) < idx[0]
    ja, en = card_rules
    assert ja["has"] == [{"type": "header", "key": "accept-language", "value": ja["has"][0]["value"]}]
    assert "has" not in en and "missing" not in en


def test_status_307_not_permanent(card_rules):
    for r in card_rules:
        assert r["permanent"] is False
        assert "statusCode" not in r


def test_exact_destinations_and_utm(card_rules):
    ja, en = card_rules
    assert ja["destination"] == JA_DEST
    assert en["destination"] == EN_DEST
    for r, path in ((ja, "/sidekick-qr"), (en, "/en/sidekick-qr")):
        u = urlsplit(r["destination"])
        assert u.scheme == "" and u.netloc == ""  # 同じ host の固定 path（外部へ出さない）
        assert u.path == path
        assert parse_qsl(u.query) == UTM
        assert "utm_content" not in u.query and "utm_term" not in u.query
        assert ":" not in r["destination"] and "$" not in r["destination"]  # capture を使わない


def test_source_is_fixed_entry(card_rules):
    for r in card_rules:
        assert r["source"] == "/card/qr"  # parameter・wildcard なし（destination / ID を受け取らない）
        assert re.fullmatch(r"/card/qr", r["source"])


def _regex(card_rules) -> str:
    return card_rules[0]["has"][0]["value"]


JA_HEADERS = [
    "ja", "ja-JP", "JA-jp", "ja-JP,ja;q=0.9", "ja,en-US;q=0.9,en;q=0.8", "en-US,en;q=0.9,ja;q=0.8",
    "en-US, en;q=0.9, ja;q=0.8", "fr, ja", "en;q=0.5,ja", "ja;q=0.1",
]
EN_HEADERS = [
    "", "en", "en-US", "en-US,en;q=0.9", "zh-CN", "zh-CN,zh;q=0.9,en;q=0.8", "*", "fr-FR", "ko-KR,ko;q=0.9",
    "jav", "xja", "en-US,jam;q=0.8", "nja-NG", "en-JA",  # ja を含むが ja の言語タグではない
]


@pytest.mark.parametrize("semantics", ["fullmatch", "search"])
@pytest.mark.parametrize("header", JA_HEADERS)
def test_regex_japanese(card_rules, semantics, header):
    rx = re.compile(_regex(card_rules))
    assert getattr(rx, semantics)(header), header


@pytest.mark.parametrize("semantics", ["fullmatch", "search"])
@pytest.mark.parametrize("header", EN_HEADERS)
def test_regex_not_japanese(card_rules, semantics, header):
    rx = re.compile(_regex(card_rules))
    assert not getattr(rx, semantics)(header), header


@pytest.mark.parametrize("header", JA_HEADERS + EN_HEADERS)
def test_regex_same_direction_as_client_script(card_rules, header):
    """server の判定 = JA page の client script（navigator.languages のどこかが /^ja/i）と同じ向き（言語タグの単位で）。"""
    tags = [t.split(";")[0].strip() for t in header.split(",") if t.strip()]
    client = any(re.match(r"ja(-|$)", t, re.I) for t in tags)
    assert bool(re.fullmatch(_regex(card_rules), header)) == client


def test_existing_product_pages_not_redirected(redirects):
    for r in redirects:
        assert r["source"] not in ("/sidekick-qr", "/en/sidekick-qr", "/sidekick-qr-app/(.*)")


def test_card_namespace_is_entry_only():
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout.splitlines()
    assert not [p for p in tracked if p.startswith("card/") or p in ("card.html",)]
    assert "/card/" not in (REPO_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    offenders = []
    for p in tracked:
        if p.endswith(".html") and not p.startswith(("BackUp/", "validation/")):
            text = (REPO_ROOT / p).read_text(encoding="utf-8", errors="replace")
            if re.search(r"""href=["'](https://www\.sidekick-lab\.com)?/card/""", text):
                offenders.append(p)
    assert offenders == []
