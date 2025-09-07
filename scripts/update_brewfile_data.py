#!/usr/bin/env python3
"""
Brewfile Periodic Update System
Automatically updates Brewfile data when changes are detected.
Can be integrated with brew bundle commands for seamless updates.

Features:
- Detects changes in Brewfiles
- Supports both manual and automated updates
- Can be hooked to brew bundle workflows
- Provides detailed logging and status reporting
- Supports force updates and dry-run mode
- Preserves user edits to descriptions and examples

Usage:
    python3 scripts/update_brewfile_data.py              # Check and update if needed
    python3 scripts/update_brewfile_data.py --force      # Force update regardless
    python3 scripts/update_brewfile_data.py --dry-run    # Show what would be updated
    python3 scripts/update_brewfile_data.py --watch      # Watch for file changes
    python3 scripts/update_brewfile_data.py --setup-hook # Set up brew bundle hook
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Dynamic path setup
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from config import get_config  # noqa: E402

# Constants
UPDATE_STATE_FILE = ".brewfile_update_state.json"
HOOK_SCRIPT_NAME = "brewfile_update_hook.sh"
LOCK_FILE = ".brewfile_update.lock"


class BrewfileUpdater:
    """Main class for managing Brewfile updates"""

    def __init__(self, config_root: Optional[str] = None, verbose: bool = True):
        self.config = get_config(config_root)
        self.verbose = verbose
        self.state_file = self.config.root / UPDATE_STATE_FILE
        self.lock_file = self.config.root / LOCK_FILE

    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        if self.verbose or level == "ERROR":
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {level}: {message}")

    def get_file_hash(self, file_path: Path) -> Optional[str]:
        """Calculate SHA-256 hash of a file"""
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            self.log(f"Error hashing {file_path}: {e}", "ERROR")
            return None

    def get_brewfile_hashes(self) -> Dict[str, str]:
        """Get current hashes of all Brewfiles"""
        hashes = {}
        for file_type, file_path in self.config.brewfiles.items():
            if file_path.exists():
                file_hash = self.get_file_hash(file_path)
                if file_hash:
                    hashes[str(file_path)] = file_hash
        return hashes

    def load_state(self) -> Dict:
        """Load previous update state"""
        if not self.state_file.exists():
            return {
                "last_update": None,
                "last_hashes": {},
                "update_count": 0,
                "last_error": None
            }

        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.log(f"Error loading state file: {e}", "ERROR")
            return {"last_update": None, "last_hashes": {}, "update_count": 0}

    def save_state(self, state: Dict):
        """Save current update state"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.log(f"Error saving state file: {e}", "ERROR")

    def acquire_lock(self) -> bool:
        """Acquire update lock to prevent concurrent updates"""
        if self.lock_file.exists():
            # Check if lock is stale (older than 5 minutes)
            try:
                lock_time = self.lock_file.stat().st_mtime
                if time.time() - lock_time > 300:  # 5 minutes
                    self.log("Removing stale lock file")
                    self.lock_file.unlink()
                else:
                    self.log("Another update is already in progress", "ERROR")
                    return False
            except Exception:
                pass

        try:
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception as e:
            self.log(f"Could not acquire lock: {e}", "ERROR")
            return False

    def release_lock(self):
        """Release update lock"""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception as e:
            self.log(f"Error releasing lock: {e}", "ERROR")

    def has_changes(self, current_hashes: Dict[str, str], previous_hashes: Dict[str, str]) -> Tuple[bool, List[str]]:
        """Check if there are changes in Brewfiles"""
        changed_files = []

        # Check for new or modified files
        for file_path, current_hash in current_hashes.items():
            previous_hash = previous_hashes.get(file_path)
            if previous_hash != current_hash:
                changed_files.append(file_path)

        # Check for deleted files
        for file_path in previous_hashes:
            if file_path not in current_hashes:
                changed_files.append(f"{file_path} (deleted)")

        return len(changed_files) > 0, changed_files

    def preserve_user_edits(self, new_data: list) -> list:
        """Preserve user-edited descriptions and examples"""
        if not self.config.json_file.exists():
            return new_data

        try:
            with open(self.config.json_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

            # Create lookup for existing tools by name
            existing_tools = {tool['name']: tool for tool in existing_data}

            # Preserve user edits in new data
            for tool in new_data:
                name = tool['name']
                existing_tool = existing_tools.get(name)

                if existing_tool and existing_tool.get('user_edited'):
                    # Preserve user-edited fields
                    if 'description' in existing_tool and existing_tool.get('user_edited'):
                        tool['description'] = existing_tool['description']
                        tool['user_edited'] = True
                        tool['last_edited'] = existing_tool.get('last_edited')

                    if 'example' in existing_tool and existing_tool.get('user_edited'):
                        tool['example'] = existing_tool['example']
                        tool['user_edited'] = True
                        tool['last_edited'] = existing_tool.get('last_edited')

            self.log(f"Preserved user edits for {sum(1 for tool in new_data if tool.get('user_edited'))} tools")
            return new_data

        except Exception as e:
            self.log(f"Error preserving user edits: {e}", "ERROR")
            return new_data

    def run_generator(self) -> bool:
        """Run the main data generator script with user edit preservation"""
        try:
            # Import and run the generator
            from gen_tools_data import main as gen_main

            # Generate new data
            result = gen_main()
            if result != 0:
                return False

            # Preserve user edits if data was generated successfully
            if self.config.json_file.exists():
                with open(self.config.json_file, 'r', encoding='utf-8') as f:
                    new_data = json.load(f)

                # Apply user edit preservation
                preserved_data = self.preserve_user_edits(new_data)

                # Save back with preserved edits
                with open(self.config.json_file, 'w', encoding='utf-8') as f:
                    json.dump(preserved_data, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            self.log(f"Error running generator: {e}", "ERROR")
            return False

    def update_data(self, force: bool = False, dry_run: bool = False) -> bool:
        """Update Brewfile data if changes detected or forced"""
        if not self.acquire_lock():
            return False

        try:
            self.log("Starting Brewfile data update check...")

            # Check if config has Brewfiles
            if not self.config.has_brewfiles():
                self.log("No Brewfiles found - skipping update", "ERROR")
                return False

            # Get current state
            current_hashes = self.get_brewfile_hashes()
            state = self.load_state()
            previous_hashes = state.get("last_hashes", {})

            # Check for changes
            has_changed, changed_files = self.has_changes(current_hashes, previous_hashes)

            if dry_run:
                if has_changed:
                    self.log("DRY RUN: Changes detected in:")
                    for file_path in changed_files:
                        self.log(f"  - {file_path}")
                    self.log("DRY RUN: Would update data files")
                else:
                    self.log("DRY RUN: No changes detected")
                return True

            if not force and not has_changed:
                self.log("No changes detected - skipping update")
                return True

            if has_changed:
                self.log("Changes detected in:")
                for file_path in changed_files:
                    self.log(f"  - {file_path}")

            if force:
                self.log("Force update requested")

            # Run the update
            self.log("Updating Brewfile data...")
            success = self.run_generator()

            if success:
                # Update state
                state.update({
                    "last_update": datetime.now().isoformat(),
                    "last_hashes": current_hashes,
                    "update_count": state.get("update_count", 0) + 1,
                    "last_error": None
                })
                self.save_state(state)
                self.log("✅ Brewfile data updated successfully")

                # Show output files
                if self.config.json_file.exists():
                    self.log(f"Updated: {self.config.json_file}")
                if self.config.csv_file.exists():
                    self.log(f"Updated: {self.config.csv_file}")

                return True
            else:
                error_msg = f"Data generation failed at {datetime.now().isoformat()}"
                state["last_error"] = error_msg
                self.save_state(state)
                self.log(f"❌ {error_msg}", "ERROR")
                return False

        finally:
            self.release_lock()

    def setup_brew_bundle_hook(self) -> bool:
        """Set up a brew bundle hook for automatic updates"""
        # Always place the hook in the repository root alongside scripts/
        code_root = Path(__file__).resolve().parent.parent
        hook_path = code_root / HOOK_SCRIPT_NAME
        update_script_path = code_root / 'scripts' / 'update_brewfile_data.py'
        venv_python = code_root / '.venv' / 'bin' / 'python'

        py_cmd = f"{venv_python}" if venv_python.exists() else "python3"

        hook_content = f'''#!/bin/bash
# Brewfile Update Hook
# Automatically updates Brewfile data before brew bundle commands
# Generated by Brewfile Analyzer - preserves user edits

set -e

UPDATE_SCRIPT="{update_script_path}"
PY_CMD="{py_cmd}"

echo "🔄 Running Brewfile data update (preserving user edits)..."

if [ -f "$UPDATE_SCRIPT" ]; then
    "$PY_CMD" "$UPDATE_SCRIPT" "$@"
    if [ $? -eq 0 ]; then
        echo "✅ Brewfile data updated successfully (user edits preserved)"
    else
        echo "❌ Brewfile data update failed"
        exit 1
    fi
else
    echo "❌ Update script not found: $UPDATE_SCRIPT"
    exit 1
fi
'''

        try:
            with open(hook_path, 'w') as f:
                f.write(hook_content)

            # Make executable
            os.chmod(hook_path, 0o755)

            self.log(f"✅ Created brew bundle hook: {hook_path}")
            self.log("   Hook preserves user-edited descriptions and examples")
            self.log("\nTo use the hook, run:")
            self.log(f"  {hook_path} && brew bundle")
            self.log("\nOr create an alias in your shell:")
            self.log(f"  alias brew-bundle='{hook_path} && brew bundle'")
            self.log("\nFor automatic integration, add to your shell profile:")
            self.log(f"  echo 'alias brew-bundle=\"{hook_path} && brew bundle\"' >> ~/.zshrc")

            return True

        except Exception as e:
            self.log(f"Error creating hook script: {e}", "ERROR")
            return False

    def watch_files(self, interval: int = 5):
        """Watch Brewfiles for changes and auto-update"""
        self.log(f"👀 Watching Brewfiles for changes (check every {interval}s)...")
        self.log("Press Ctrl+C to stop")

        try:
            while True:
                self.update_data()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.log("\n⏹ File watching stopped")

    def status(self) -> Dict:
        """Get current update status"""
        state = self.load_state()
        current_hashes = self.get_brewfile_hashes()
        has_changed, changed_files = self.has_changes(current_hashes, state.get("last_hashes", {}))

        return {
            "has_changes": has_changed,
            "changed_files": changed_files,
            "last_update": state.get("last_update"),
            "update_count": state.get("update_count", 0),
            "last_error": state.get("last_error"),
            "brewfile_count": len(current_hashes),
            "output_files_exist": {
                "json": self.config.json_file.exists(),
                "csv": self.config.csv_file.exists()
            }
        }


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Brewfile Periodic Update System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    Check and update if changes detected
  %(prog)s --force           Force update regardless of changes
  %(prog)s --dry-run         Show what would be updated
  %(prog)s --status          Show current update status
  %(prog)s --watch           Watch for changes and auto-update
  %(prog)s --setup-hook      Create brew bundle integration hook

Integration with brew bundle:
  ./brewfile_update_hook.sh && brew bundle
        """
    )

    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force update even if no changes detected"
    )

    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be updated without making changes"
    )

    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show current update status and exit"
    )

    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Watch files for changes and auto-update"
    )

    parser.add_argument(
        "--watch-interval",
        type=int,
        default=5,
        help="Interval in seconds for file watching (default: 5)"
    )

    parser.add_argument(
        "--setup-hook",
        action="store_true",
        help="Set up brew bundle integration hook"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce output verbosity"
    )

    parser.add_argument(
        "--config-root",
        help="Custom project root directory"
    )

    args = parser.parse_args()

    # Create updater instance
    updater = BrewfileUpdater(
        config_root=args.config_root,
        verbose=not args.quiet
    )

    try:
        if args.status:
            # Show status
            status = updater.status()
            print("Brewfile Update Status:")
            print("=" * 50)
            print(f"Has changes: {status['has_changes']}")
            if status['changed_files']:
                print("Changed files:")
                for file_path in status['changed_files']:
                    print(f"  - {file_path}")
            print(f"Last update: {status['last_update'] or 'Never'}")
            print(f"Update count: {status['update_count']}")
            print(f"Brewfile count: {status['brewfile_count']}")
            print(f"Output files exist: JSON={status['output_files_exist']['json']}, CSV={status['output_files_exist']['csv']}")
            if status['last_error']:
                print(f"Last error: {status['last_error']}")
            return 0

        elif args.setup_hook:
            # Set up brew bundle hook
            success = updater.setup_brew_bundle_hook()
            return 0 if success else 1

        elif args.watch:
            # Watch for file changes
            updater.watch_files(args.watch_interval)
            return 0

        else:
            # Regular update
            success = updater.update_data(
                force=args.force,
                dry_run=args.dry_run
            )
            return 0 if success else 1

    except KeyboardInterrupt:
        updater.log("\nOperation cancelled by user")
        return 1
    except Exception as e:
        updater.log(f"Unexpected error: {e}", "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
