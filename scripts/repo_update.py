#!/usr/bin/env python3
"""
Repository updater: fetches upstream changes and optionally updates local files
with backups.

Default behavior (safe):
- Fetch origin/<branch> (default: origin/main)
- Show files changed upstream relative to your current HEAD
- Dry-run (no writes) unless --apply is passed

Update strategy when --apply is used:
- For added/modified files upstream (A/M), back up your current copy (if any)
  under backups/repo_sync/<YYYYmmdd_HHMMSS>/path/to/file and replace it with
  the upstream content from origin/<branch>.
- Deleted upstream files are skipped by default (enable via --delete to remove
  locally with backup).

Examples:
  # Preview changes from origin/main
  python3 scripts/repo_update.py

  # Apply updates for all upstream-changed files
  python3 scripts/repo_update.py --apply

  # Only update scripts/*.py and config.py
  python3 scripts/repo_update.py --apply --include-glob 'scripts/*.py' --paths config.py

  # Remove files deleted upstream (with backups)
  python3 scripts/repo_update.py --apply --delete
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
import fnmatch

def detect_repo_root() -> Path:
    """Best-effort detection of the Git repository root.

    Tries, in order:
    1) git rev-parse --show-toplevel from current working directory
    2) Walk up from script location until a .git directory is found
    3) Walk up from current working directory until a .git directory is found
    """
    # 1) Ask Git from CWD
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(Path.cwd()),
            capture_output=True,
            text=True,
            check=False,
        )
        if cp.returncode == 0 and cp.stdout.strip():
            return Path(cp.stdout.strip()).resolve()
    except Exception:
        pass

    # 2) Search upward from script path
    script_path = Path(__file__).resolve()
    for parent in [script_path] + list(script_path.parents):
        candidate = parent if parent.is_dir() else parent.parent
        if (candidate / ".git").exists():
            return candidate

    # 3) Search upward from CWD
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            return parent

    raise RuntimeError("Could not detect Git repository root. Run this inside a Git repo.")


REPO_ROOT = detect_repo_root()
BACKUP_ROOT = REPO_ROOT / "backups" / "repo_sync"


@dataclass
class Change:
    status: str  # e.g., 'A', 'M', 'D', 'R100 path1 path2' (we'll normalize)
    path: str
    new_path: Optional[str] = None  # for renames


def run_git(args: List[str], cwd: Path = REPO_ROOT, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--no-pager", *args], cwd=str(cwd), capture_output=True, text=text, check=False)


def fetch(remote: str, no_tags: bool = True) -> None:
    args = ["fetch", remote]
    if no_tags:
        args.append("--no-tags")
    cp = run_git(args)
    if cp.returncode != 0:
        raise RuntimeError(f"git fetch failed: {cp.stderr.strip()}")


def list_upstream_changes(remote: str, branch: str) -> List[Change]:
    # Compare local HEAD..remote/branch
    cp = run_git(["diff", "--name-status", "HEAD..{}{}".format(remote + "/", branch)])
    if cp.returncode != 0:
        raise RuntimeError(f"git diff failed: {cp.stderr.strip()}")
    changes: List[Change] = []
    for line in cp.stdout.splitlines():
        if not line.strip():
            continue
        # Formats: "M\tpath", "A\tpath", "D\tpath", "R100\told\tnew"
        parts = line.split("\t")
        if not parts:
            continue
        status_raw = parts[0]
        if status_raw.startswith("R"):  # rename
            if len(parts) >= 3:
                changes.append(Change(status="R", path=parts[1], new_path=parts[2]))
        else:
            if len(parts) >= 2:
                changes.append(Change(status=status_raw, path=parts[1]))
    return changes


def filter_paths(changes: List[Change], includes: List[str], excludes: List[str], paths: List[str]) -> List[Change]:
    def match_any(patterns: Iterable[str], p: str) -> bool:
        return any(fnmatch.fnmatch(p, pat) for pat in patterns)

    # Preinclude/Preexclude via explicit paths first
    path_set = set(paths or [])

    filtered: List[Change] = []
    for ch in changes:
        p = ch.path if ch.status != "R" else (ch.new_path or ch.path)
        # If explicit paths are provided, only include those (exact path match)
        if path_set and p not in path_set:
            continue
        if includes and not match_any(includes, p):
            continue
        if excludes and match_any(excludes, p):
            continue
        filtered.append(ch)
    return filtered


def ensure_backup_path(dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)


def backup_file(src_path: Path, backup_base: Path) -> Optional[Path]:
    if not src_path.exists():
        return None
    rel = src_path.relative_to(REPO_ROOT)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_base / ts / rel.parent
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / rel.name
    shutil.copy2(src_path, backup_path)
    return backup_path


def get_remote_file(remote: str, branch: str, path: str) -> bytes:
    # git show remote/branch:path
    cp = run_git(["show", f"{remote}/{branch}:{path}"], text=False)
    if cp.returncode != 0:
        raise RuntimeError(f"git show failed for {path}: {cp.stderr.decode(errors='ignore').strip()}")
    return cp.stdout


def apply_updates(changes: List[Change], remote: str, branch: str, delete: bool, dry_run: bool) -> List[Tuple[str, str]]:
    actions: List[Tuple[str, str]] = []  # (action, path)
    for ch in changes:
        # Determine target path
        target_rel = ch.path if ch.status != "R" else (ch.new_path or ch.path)
        target_path = REPO_ROOT / target_rel

        if ch.status in ("A", "M", "R"):
            # Backup existing file
            if dry_run:
                actions.append(("UPDATE", target_rel))
            else:
                backup_file(target_path, BACKUP_ROOT)
                blob = get_remote_file(remote, branch, target_rel)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "wb") as f:
                    f.write(blob)
                actions.append(("UPDATED", target_rel))
        elif ch.status == "D":
            if not delete:
                actions.append(("SKIP_DELETE", target_rel))
                continue
            if dry_run:
                actions.append(("DELETE", target_rel))
            else:
                backup_file(target_path, BACKUP_ROOT)
                if target_path.exists():
                    target_path.unlink()
                actions.append(("DELETED", target_rel))
        else:
            actions.append((f"SKIP_{ch.status}", target_rel))
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update local files from upstream (origin/<branch>) with backups",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--remote", default="origin", help="Git remote (default: origin)")
    parser.add_argument("--branch", default="main", help="Remote branch name (default: main)")
    parser.add_argument("--apply", action="store_true", help="Apply updates (default: dry-run preview)")
    parser.add_argument("--delete", action="store_true", help="Also delete files removed upstream (with backup)")
    parser.add_argument("--include-glob", action="append", default=[], help="Include only paths matching this glob (can repeat)")
    parser.add_argument("--exclude-glob", action="append", default=[], help="Exclude paths matching this glob (can repeat)")
    parser.add_argument("--paths", nargs="*", default=[], help="Specific paths to update (exact match)")

    args = parser.parse_args()

    # 1) Fetch upstream
    print(f"Fetching {args.remote}/{args.branch}...")
    try:
        fetch(args.remote, no_tags=True)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    # 2) List upstream changes
    try:
        raw_changes = list_upstream_changes(args.remote, args.branch)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    # 3) Filter
    changes = filter_paths(raw_changes, args.include_glob, args.exclude_glob, args.paths)

    if not changes:
        print("No upstream changes to apply for the given filters.")
        return 0

    # 4) Show plan
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\nPlanned actions ({mode}):")
    for ch in changes:
        p = ch.path if ch.status != "R" else f"{ch.path} -> {ch.new_path}"
        print(f"  {ch.status}\t{p}")

    # 5) Apply
    actions = apply_updates(changes, args.remote, args.branch, delete=args.delete, dry_run=not args.apply)

    # 6) Summary
    print("\nSummary:")
    for act, path in actions:
        print(f"  {act}: {path}")

    if not args.apply:
        print("\nNothing was changed. Re-run with --apply to perform updates.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
