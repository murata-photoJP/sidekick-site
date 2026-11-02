"""`api/planner-activity.js` の privacy policy を source 上で固定する（HD-PLANNERACTIVITY-001〜011・014、AI-6205・AI-29516）。

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
CLEANUP = REPO_ROOT / "api" / "planner-activity-cleanup.js"
CLEANUP_CODE = "\n".join(line for line in CLEANUP.read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("//"))
VERCEL_JSON = REPO_ROOT / "vercel.json"


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
    """Viewer の表示・Planner の QR 発行を止めない: POST 経路の応答は 204 だけ。

    例外は 1 つ（HD-PLANNERACTIVITY-014、AI-29516）: Authorization 付きで認証が一致しない要求への 401。
    一般の利用者・Viewer は Authorization を送らないので、この 401 に当たらない。
    """
    post_path = CODE[CODE.index("if (req.method !== 'POST')"):]
    statuses = set(re.findall(r"res\.status\((\d{3})\)", post_path))
    assert statuses == {"405", "204", "401"}, statuses
    rejected = post_path[post_path.index("if (auth === 'rejected')"):]
    assert rejected.index("res.status(401)") < rejected.index("}")
    assert post_path.count("res.status(401)") == 1


# ---------------------------------------------------------------- 開発者の識別（HD-PLANNERACTIVITY-014、AI-29516）

def test_developer_auth_is_header_only_constant_time_and_fail_closed() -> None:
    auth = CODE[CODE.index("function developerAuth"):CODE.index("function queryParam")]
    assert "PLANNER_ACTIVITY_DEVELOPER_TOKEN" in auth
    assert "crypto.timingSafeEqual(given, want)" in auth
    assert "if (raw === undefined || raw === null) return 'none';" in auth
    assert "if (expected.length < DEVELOPER_TOKEN_MIN_LENGTH) return 'rejected';" in auth
    assert "const DEVELOPER_TOKEN_MIN_LENGTH = 32;" in CODE
    assert "req.body" not in auth                     # body の値で開発者にならない（偽装できない）


def test_developer_events_are_not_aggregated_and_carry_only_audience() -> None:
    store = CODE[CODE.index("async function storeEvents"):CODE.index("async function readAggregate")]
    assert "if (developer) doc.audience = AUDIENCE_DEVELOPER;" in store
    skip = store.index("if (developer) { stored += 1; continue; }")
    assert skip < store.index("planner_activity_daily") and skip < store.index("planner_activity_totals")
    assert "const AUDIENCE_DEVELOPER = 'developer';" in CODE
    # token・Authorization を document にも log にも入れない
    for marker in ("token:", "authorization:", "token_hash", "createHash"):
        assert marker not in CODE, marker
    for line in CODE.splitlines():
        if "console." in line:
            assert "expected" not in line and "given" not in line and "raw" not in line, line


def test_public_aggregate_does_not_read_developer_events() -> None:
    aggregate = CODE[CODE.index("async function readAggregate"):CODE.index("async function readDeveloperCheck")]
    assert "planner_activity_events" not in aggregate
    assert "audience" not in aggregate


def test_developer_check_requires_auth_and_is_not_cached() -> None:
    check = CODE[CODE.index("async function readDeveloperCheck"):CODE.index("module.exports = async function handler")]
    assert check.index("res.setHeader('Cache-Control', 'no-store');") < check.index("developerAuth(req)")
    assert "if (developerAuth(req) !== 'ok') return res.status(401).end();" in check
    assert "data.audience !== AUDIENCE_DEVELOPER" in check
    assert ".where(" not in check and ".limit(" not in check   # 一覧は返さない（1 件の有無だけ）


def test_no_secret_value_is_committed() -> None:
    """env の名前以外に、32 文字以上の token らしい文字列 literal を持たない。"""
    for literal in re.findall(r"'([^'\n]{32,})'|\"([^\"\n]{32,})\"", CODE):
        value = literal[0] or literal[1]
        assert " " in value or "/" in value or ":" in value, value


def test_collections_are_the_documented_ones() -> None:
    for name in ("planner_activity_events", "planner_activity_daily", "planner_activity_totals"):
        assert f"collection('{name}')" in CODE, name
    # raw event は create（重複は無視 = 冪等）。update / delete を持たない
    assert ".create(" in CODE
    assert ".delete(" not in CODE


def test_no_third_party_analytics_or_outbound_calls() -> None:
    for marker in ("googletagmanager", "clarity.ms", "fetch(", "https://api."):
        assert marker not in CODE, marker


# ---------------------------------------------------------------- cleanup（HD-PLANNERACTIVITY-012、AI-6217）

def test_cleanup_only_touches_the_raw_event_collection() -> None:
    """削除するのは planner_activity_events だけ。daily / totals の名前が cleanup の code に無い。"""
    assert "const COLLECTION = 'planner_activity_events';" in CLEANUP_CODE
    for name in ("planner_activity_daily", "planner_activity_totals", "downloads", "reviews", "users"):
        assert name not in CLEANUP_CODE, name
    assert CLEANUP_CODE.count("collection(") == 1


def test_cleanup_deletes_only_expired_documents_in_bounded_batches() -> None:
    """where 無しの delete を書かない。expire_at <= now、500 件、上限回数。"""
    assert ".where('expire_at', '<=', now)" in CLEANUP_CODE
    assert "const BATCH_SIZE = 500;" in CLEANUP_CODE
    assert re.search(r"const MAX_BATCHES = \d+;", CLEANUP_CODE)
    assert ".limit(BATCH_SIZE)" in CLEANUP_CODE
    assert "batch.delete(doc.ref)" in CLEANUP_CODE
    assert CLEANUP_CODE.count(".delete(") == 1


def test_cleanup_is_protected_by_cron_secret_and_does_nothing_without_it() -> None:
    assert "process.env.CRON_SECRET" in CLEANUP_CODE
    assert "'Bearer ' + secret" in CLEANUP_CODE
    assert "cron_secret_not_configured" in CLEANUP_CODE
    assert "if (!secret) return false;" in CLEANUP_CODE


def test_cleanup_is_independent_of_the_activity_endpoint() -> None:
    """Activity 本体（planner-activity.js）は cleanup を require しない。cleanup も本体を require しない。"""
    assert "planner-activity-cleanup" not in CODE
    assert "require('./planner-activity" not in CLEANUP_CODE


def test_vercel_cron_runs_the_cleanup_once_a_day() -> None:
    import json
    config = json.loads(VERCEL_JSON.read_text(encoding="utf-8-sig"))
    crons = config.get("crons", [])
    # ほかの機能の Cron（QR マップの /api/qr-map-cleanup、site a991c5c・HD-PLANNERQRMAP-044）が並んでもよい。
    # Planner の Activity cleanup がちょうど 1 本あることだけを確かめる。
    planner = [c for c in crons if c["path"] == "/api/planner-activity-cleanup"]
    assert len(planner) == 1
    schedule = planner[0]["schedule"].split()
    assert len(schedule) == 5 and schedule[2:] == ["*", "*", "*"]      # 1 日 1 回（Hobby の精度）
    assert schedule[0].isdigit() and schedule[1].isdigit()
