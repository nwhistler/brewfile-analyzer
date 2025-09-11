#!/usr/bin/env python3
"""
Self-updater for the deployed Brewfile Analyzer app (no Git required).

Intended to run from the installed app directory (e.g., ~/brewfile/web_app).
Downloads the latest archive from GitHub, backs up current files, and applies
updates while preserving user data (DuckDB/JSON) and local environment files.

Defaults are conservative and safe:
- Dry-run preview unless --apply is provided
- Skips data/, backups/, .venv/, and generated docs/tools/tools.json|.csv
- Creates timestamped backups under backups/self_update/<YYYYmmdd_HHMMSS>/

Examples
  Preview updates from main:
    python3 scripts/self_update.py

  Apply updates from main:
    python3 scripts/self_update.py --apply

  Apply updates from a specific ref (tag/branch/commit):
    python3 scripts/self_update.py --apply --ref v1.2.3

  Include deletions (remove files not present upstream, with backup):
    python3 scripts/self_update.py --apply --delete
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

APP_ROOT = Path(__file__).resolve().parent.parent  # .../web_app

DEFAULT_REPO = "nwhistler/brewfile-analyzer"
DEFAULT_REF = "main"

# Paths/globs to skip when applying updates (preserve user data and env)
PRESERVE_GLOBS = [
    "data/**",                 # DuckDB and other runtime data
    "backups/**",              # Our own backups
    ".venv/**",                # Local virtualenv
    "docs/tools/tools.json",   # Generated snapshot (JSON fallback)
    "docs/tools/tools.csv",    # Generated snapshot (CSV, if used)
    ".brewfile_update_state.json",
    ".brewfile_update.lock",
]


def matches_any(path: Path, patterns: Iterable[str]) -> bool:
    rel = path.relative_to(APP_ROOT).as_posix()
    return any(fnmatch.fnmatch(rel, pat) for pat in patterns)


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def backup_existing(target: Path, backup_base: Path) -> None:
    if not target.exists():
        return
    ts_dir = backup_base / datetime.now().strftime("%Y%m%d_%H%M%S")
    rel = target.relative_to(APP_ROOT)
    dst = ts_dir / rel
    ensure_dir(dst.parent)
    shutil.copy2(target, dst)


def copy_tree_with_preserve(src_root: Path, dst_root: Path, preserve_globs: List[str], delete: bool, dry_run: bool) -> List[str]:
    """Copy src_root -> dst_root while preserving paths matching preserve_globs.

    If delete=True, remove files in dst_root that are absent in src_root (unless preserved).
    Returns a log of actions performed/planned.
    """
    log: List[str] = []
    backup_base = dst_root / "backups" / "self_update"

    # Walk source tree
    for src_path in src_root.rglob("*"):
        if src_path.is_dir():
            continue
        rel = src_path.relative_to(src_root)
        dst_path = dst_root / rel

        # Skip preserved files/dirs by destination path
        if matches_any(dst_path, preserve_globs):
            log.append(f"SKIP preserve: {rel}")
            continue

        # Plan/perform update
        if dry_run:
            log.append(f"UPDATE: {rel}")
        else:
            ensure_dir(dst_path.parent)
            # Backup existing
            backup_existing(dst_path, backup_base)
            shutil.copy2(src_path, dst_path)
            log.append(f"UPDATED: {rel}")

    if delete:
        # Remove files present in dst but not in src (unless preserved)
        src_set = {p.relative_to(src_root).as_posix() for p in src_root.rglob("*") if p.is_file()}
        for dst_path in dst_root.rglob("*"):
            if dst_path.is_dir():
                continue
            if matches_any(dst_path, preserve_globs):
                continue
            rel_posix = dst_path.relative_to(dst_root).as_posix()
            if rel_posix not in src_set:
                if dry_run:
                    log.append(f"DELETE: {rel_posix}")
                else:
                    backup_existing(dst_path, backup_base)
                    try:
                        dst_path.unlink()
                        log.append(f"DELETED: {rel_posix}")
                    except Exception as e:
                        log.append(f"ERROR delete {rel_posix}: {e}")

    return log


def download_zip(repo: str, ref: str, out_path: Path) -> None:
    # Use GitHub's archive URL; supports branches, tags, and commit SHAs
    url = f"https://codeload.github.com/{repo}/zip/refs/heads/{ref}"
    # If ref is a tag or SHA, try the generic archive URL
    if "/" in ref or ref.lower() == ref and not ref.startswith("v"):
        # leave as heads/<ref> for common cases
        pass
    try:
        urllib.request.urlretrieve(url, out_path)
    except Exception as e:
        # Fallback to archive/<ref>.zip (works for tags/commits)
        url2 = f"https://github.com/{repo}/archive/{ref}.zip"
        urllib.request.urlretrieve(url2, out_path)


def extract_zip(zip_path: Path, tmp_dir: Path) -> Path:
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp_dir)
        # Determine top-level dir (GitHub adds <repo>-<ref>/)
        names = zf.namelist()
        top = names[0].split("/")[0]
        return tmp_dir / top


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-update the deployed app from GitHub (no Git required)")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo (default: nwhistler/brewfile-analyzer)")
    parser.add_argument("--ref", default=DEFAULT_REF, help="branch/tag/commit (default: main)")
    parser.add_argument("--apply", action="store_true", help="Apply updates (default: dry-run preview)")
    parser.add_argument("--delete", action="store_true", help="Also delete files not present upstream (with backup)")

    args = parser.parse_args()

    print(f"App root: {APP_ROOT}")
    print(f"Repo: {args.repo}  Ref: {args.ref}")
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Mode: {mode}\n")

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        zip_path = tmp_dir / "update.zip"

        print("Downloading archive...")
        try:
            download_zip(args.repo, args.ref, zip_path)
        except Exception as e:
            print(f"ERROR: download failed: {e}")
            return 1

        try:
            src_root = extract_zip(zip_path, tmp_dir)
        except Exception as e:
            print(f"ERROR: extract failed: {e}")
            return 1

        print(f"Extracted: {src_root}")

        # Copy from extracted source into app root with preserve rules
        print("\nApplying file plan...")
        log = copy_tree_with_preserve(src_root, APP_ROOT, PRESERVE_GLOBS, delete=args.delete, dry_run=not args.apply)
        for line in log:
            print(f"  {line}")

        if not args.apply:
            print("\nNothing changed. Re-run with --apply to perform updates.")
        else:
            print("\n✅ Update complete.")
            print("- Preserved: data/, backups/, .venv/, docs/tools/tools.json|.csv")
            print("- Backups at: backups/self_update/<timestamp>/")
            print("- If a server is running, restart it to pick up changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
