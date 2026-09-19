"""`api/planner-activity.js` の privacy policy を source 上で固定する（HD-PLANNERACTIVITY-001〜011、AI-6205）。

挙動の test は `tests/tools/test_planner_activity_api.mjs`（`node --test`）にある。ここは Node が無い環境でも
`pytest tests -q` で「保存してはいけないものを読んでいない」ことだけを守る。

**リポジトリを読むだけで、何も書き込まない。**

使い方:
    python -m pytest tests/site/test_planner_activity_api_policy.py -q
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API = REPO_ROOT / "api" / "planner-activity.js"
SOURCE = API.read_text(encoding="utf-8")
CODE = "\n".join(line for line in SOURCE.splitlines() if not line.lstrip().startswith("//"))


def test_ip_and_geo_headers_are_never_read() -> None:
    """IP・IP 由来の地理情報は「到達するが保存しない」（HD-006、AI-6001 §3）。読む code が無いこと。"""
    for marker in ("x-vercel-ip", "x-forwarded-for", "x-real-ip", "remoteAddress", "socket.remote"):
        assert marker not in CODE, marker


def test_user_agent_is_classified_not_stored() -> None:
    assert "classifyUserAgent(req.headers && req.headers['user-agent'])" in CODE
    # UA の生文字列を document に入れる code が無い
    assert re.search(r"user_agent\s*:", CODE) is None
    assert re.search(r"ua\s*:\s*", CODE) is None


def test_forbidden_fields_are_not_part_of_the_stored_document() -> None:
    """allow-list の外（plan_ref / poi_id / installation_id / country / 緯度経度）を document に書かない。"""
    normalize = CODE[CODE.index("function normalizeEvent"):CODE.index("function incrementsFor")]
    for key in ("plan_ref", "poi_id", "installation_id", "country", "latitude", "longitude", "fragment", "payload"):
        assert key not in normalize, key
    for key in ("schema", "event", "at", "day", "client_kind", "category", "transport", "repeat", "code"):
        assert key in normalize, key


def test_vocabularies_match_the_decision() -> None:
    assert "const SCHEMA = 'planner_activity/1';" in CODE
    assert "['share_created', 'share_viewed', 'share_view_failed']" in CODE
    assert "['mountain', 'structure']" in CODE            # HD-010 C-2
    assert "['viewer', 'planner']" in CODE                # HD-011
    assert "const PUBLIC_K = 5;" in CODE                  # HD-009
    assert "const RETENTION_DAYS = 425;" in CODE          # HD-007 (β + 12 か月)


def test_post_never_fails_the_caller() -> None:
    """Viewer の表示・Planner の QR 発行を止めない: POST 経路の応答は 204 だけ。"""
    post_path = CODE[CODE.index("if (req.method !== 'POST')"):]
    statuses = set(re.findall(r"res\.status\((\d{3})\)", post_path))
    assert statuses == {"405", "204"}, statuses


def test_collections_are_the_documented_ones() -> None:
    for name in ("planner_activity_events", "planner_activity_daily", "planner_activity_totals"):
        assert f"collection('{name}')" in CODE, name
    # raw event は create（重複は無視 = 冪等）。update / delete を持たない
    assert ".create(" in CODE
    assert ".delete(" not in CODE


def test_no_third_party_analytics_or_outbound_calls() -> None:
    for marker in ("googletagmanager", "clarity.ms", "fetch(", "https://api."):
        assert marker not in CODE, marker
