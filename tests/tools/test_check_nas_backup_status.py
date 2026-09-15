"""tools/check_nas_backup_status.py — READ-ONLY NAS backup freshness checker (Phase 3F.1).

Uses throw-away git repositories under tmp_path; never touches the real NAS or the real workspace.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_nas_backup_status", ROOT / "tools" / "check_nas_backup_status.py")
cns = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cns)


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


def _repo_with_commits(path: Path, n: int) -> list[str]:
    path.mkdir(parents=True)
    _git("init", "-q", "-b", "main", cwd=path)
    _git("config", "user.email", "t@example.invalid", cwd=path)
    _git("config", "user.name", "t", cwd=path)
    shas = []
    for i in range(n):
        (path / "f.txt").write_text(f"{i}\n", encoding="utf-8")
        _git("add", "f.txt", cwd=path)
        _git("commit", "-q", "-m", f"c{i}", cwd=path)
        shas.append(_git("rev-parse", "HEAD", cwd=path))
    return shas


@pytest.fixture
def workspace(tmp_path):
    """<tmp>/jisaku/sales/html (local repo) and <tmp>/nas/jisaku/sales/html (NAS copy) — same layout as nas_backup.ps1."""
    local = tmp_path / "jisaku" / "sales" / "html"
    shas = _repo_with_commits(local, 3)
    nas_root = tmp_path / "nas"
    nas_copy = nas_root / "jisaku" / "sales" / "html"
    nas_copy.parent.mkdir(parents=True)
    _git("clone", "-q", str(local), str(nas_copy), cwd=tmp_path)          # a copy of the same history
    _git("reset", "-q", "--hard", shas[0], cwd=nas_copy)                   # NAS copy is 2 commits behind
    return local, nas_root, shas


def test_stale_reports_ahead_count_and_last_backup(workspace):
    local, nas_root, shas = workspace
    (local.parent / cns.LOG_NAME).write_text("   Files :  1  1  0\n   Ended : 2026912 6:11:05\nsecret_file_name.json  copied\n", encoding="utf-8")
    info, code = cns.check(local, nas_root)
    assert code == 1 and info["backup status"] == "STALE"
    assert info["LOCAL HEAD"].startswith(shas[-1]) and info["NAS HEAD"] == shas[0]
    assert info["ahead commits"].startswith("2 ")
    assert info["last backup"] == "Ended : 2026912 6:11:05"                 # only the summary line, never file names
    assert "secret_file_name" not in " ".join(info.values())


def test_current_when_nas_copy_matches_local(workspace):
    local, nas_root, shas = workspace
    nas_copy = nas_root / "jisaku" / "sales" / "html"
    _git("reset", "-q", "--hard", shas[-1], cwd=nas_copy)
    info, code = cns.check(local, nas_root)
    assert code == 0 and info["backup status"] == "CURRENT" and info["ahead commits"].startswith("0 ")
    assert info["last backup"].startswith("unknown")                         # no log → unknown, never a guess


def test_unavailable_when_nas_missing(workspace, tmp_path):
    local, nas_root, _ = workspace
    info, code = cns.check(local, tmp_path / "no-such-nas")
    assert code == 2 and info["backup status"] == "UNAVAILABLE" and "NAS HEAD" in info
    empty_root = tmp_path / "empty-nas"; empty_root.mkdir()
    info2, code2 = cns.check(local, empty_root)                               # root exists, copy does not
    assert code2 == 2 and info2["backup status"] == "UNAVAILABLE"


def test_diverged_nas_head_is_stale_not_crash(workspace):
    local, nas_root, _ = workspace
    nas_copy = nas_root / "jisaku" / "sales" / "html"
    (nas_copy / "g.txt").write_text("x", encoding="utf-8")
    _git("add", "g.txt", cwd=nas_copy)
    _git("commit", "-q", "-m", "only on nas", cwd=nas_copy)
    info, code = cns.check(local, nas_root)
    assert code == 1 and info["backup status"] == "STALE" and "diverged" in info["ahead commits"]


def test_cli_prints_only_status_lines_and_never_runs_a_backup(workspace):
    local, nas_root, _ = workspace
    proc = subprocess.run([sys.executable, "-B", str(ROOT / "tools" / "check_nas_backup_status.py"), "--local", str(local), "--nas-root", str(nas_root)],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 1
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert [ln.split(":")[0].strip() for ln in lines[:5]] == ["LOCAL HEAD", "NAS HEAD", "ahead commits", "last backup", "backup status"]
    assert "Human decision" in proc.stdout
    assert not (local.parent / cns.LOG_NAME).exists()                        # nothing written anywhere
    assert set(p.name for p in nas_root.rglob("*") if p.is_file() and ".git" not in p.parts) == {"f.txt"}
