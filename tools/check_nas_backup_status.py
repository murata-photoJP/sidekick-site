#!/usr/bin/env python3
"""NAS backup freshness check for the sidekick-site workspace — READ ONLY (Phase 3F.1, 2026-09-16).

The sales-page folder (the parent of this repository, "SideKick販売ページ/") is excluded from the 'jisaku'
repository and is backed up to the NAS only by a manual robocopy file copy (nas_backup.ps1 next to this
repository's parent). That copy includes this repository's .git directory, so the NAS holds a full but
possibly stale git history. This script answers one question without touching anything:

    Is the NAS copy of this Web repository CURRENT, STALE or UNAVAILABLE, and how far behind is it?

Output (and nothing else — no file lists, no secret names, no directory listings):

    LOCAL HEAD   : <sha>  (<branch>)
    NAS HEAD     : <sha>
    ahead commits: <n>            local commits missing from the NAS copy
    last backup  : <robocopy "Ended" line from the backup log, or "unknown">
    backup status: CURRENT | STALE | UNAVAILABLE

Exit code: 0 = CURRENT, 1 = STALE, 2 = UNAVAILABLE (NAS not reachable / copy missing), 3 = error.

It never runs the backup. Refreshing the NAS copy is a Human decision (run nas_backup.bat yourself).

Usage:
    py -3.10 -B tools/check_nas_backup_status.py
    py -3.10 -B tools/check_nas_backup_status.py --nas-root "Z:\\mahoroba999\\ProgramSoce"   # default
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_NAS_ROOT = r"Z:\mahoroba999\ProgramSoce"
LOG_NAME = "_nas_backup_log.txt"          # written by nas_backup.ps1 (robocopy /LOG+); only "Ended :" lines are read


def git(*args: str) -> str | None:
    """Run a read-only git query; None on any failure (never raises)."""
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def nas_workspace_dir(local_repo: Path, nas_root: Path) -> Path:
    """Mirror nas_backup.ps1: <nas_root>\\<name of the jisaku folder>\\<name of the sales-page folder>."""
    workspace = local_repo.parent                    # SideKick販売ページ
    return nas_root / workspace.parent.name / workspace.name


def last_backup_ended(log_path: Path) -> str:
    """Last robocopy 'Ended :' summary line of the backup log (only that line is read; file names are never returned)."""
    if not log_path.is_file():
        return "unknown (no backup log)"
    last = None
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if re.match(r"\s*Ended\s*:", line):
                    last = line.strip()
    except OSError:
        return "unknown (log unreadable)"
    return last or "unknown (no completed run in log)"


def check(local_repo: Path, nas_root: Path) -> tuple[dict[str, str], int]:
    local_repo = local_repo.resolve()
    info: dict[str, str] = {}
    head = git("-C", str(local_repo), "rev-parse", "HEAD")
    branch = git("-C", str(local_repo), "rev-parse", "--abbrev-ref", "HEAD") or "?"
    if head is None:
        info["error"] = f"not a git repository: {local_repo}"
        return info, 3
    info["LOCAL HEAD"] = f"{head}  ({branch})"
    nas_dir = nas_workspace_dir(local_repo, nas_root)
    nas_git = nas_dir / local_repo.name / ".git"
    if not nas_root.exists():
        info["NAS HEAD"] = f"unavailable (NAS root not reachable: {nas_root})"
        info["backup status"] = "UNAVAILABLE"
        return info, 2
    if not nas_git.is_dir():
        info["NAS HEAD"] = f"unavailable (no backup copy at {nas_git})"
        info["backup status"] = "UNAVAILABLE"
        return info, 2
    nas_head = git("--git-dir", str(nas_git), "rev-parse", "HEAD")
    if nas_head is None:
        info["NAS HEAD"] = f"unavailable (backup .git unreadable at {nas_git})"
        info["backup status"] = "UNAVAILABLE"
        return info, 2
    info["NAS HEAD"] = nas_head
    ahead = git("-C", str(local_repo), "rev-list", "--count", f"{nas_head}..HEAD")
    if ahead is None:
        info["ahead commits"] = "unknown (NAS HEAD is not in the local history — copies have diverged)"
        status = "STALE"
    else:
        info["ahead commits"] = f"{ahead}            local commits missing from the NAS copy"
        status = "CURRENT" if ahead == "0" and nas_head == head else "STALE"
    info["last backup"] = last_backup_ended(local_repo.parent / LOG_NAME)
    info["backup status"] = status
    return info, 0 if status == "CURRENT" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="READ-ONLY freshness check of the NAS file-copy backup of this repository.")
    parser.add_argument("--local", default=str(Path(__file__).resolve().parents[1]), help="local repository root (default: this repository)")
    parser.add_argument("--nas-root", default=DEFAULT_NAS_ROOT, help=f"NAS root used by nas_backup.ps1 (default: {DEFAULT_NAS_ROOT})")
    args = parser.parse_args(argv)
    info, code = check(Path(args.local), Path(args.nas_root))
    width = max(len(k) for k in info)
    for key, value in info.items():
        print(f"{key.ljust(width)}: {value}")
    if code == 1:
        print("→ NAS backup is behind local. Refreshing it (nas_backup.bat) is a Human decision; this script never runs it.")
    return code


if __name__ == "__main__":
    sys.exit(main())
