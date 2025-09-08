#!/usr/bin/env python3
"""
Configuration management for Brewfile Analyzer
Handles dynamic detection of project structure and Brewfiles
"""
from pathlib import Path
import os


class BrewfileConfig:
    """Configuration class that auto-detects project structure"""

    def __init__(self, custom_root=None):
        # Allow environment variable override
        env_root = os.getenv('BREWFILE_PROJECT_ROOT')

        # Auto-detect project root
        if custom_root:
            self.root = Path(custom_root).resolve()
        elif env_root:
            self.root = Path(env_root).expanduser().resolve()
        else:
            # Try to find project root from current working directory first
            cwd = Path.cwd()
            # Check if we're in a brewfile-analyzer directory or have Brewfiles in current dir
            if (cwd.name == 'brewfile-analyzer' or
                any((cwd / f).exists() for f in ['Brewfile', 'brewfile', 'Brewfile.Brew', 'Brewfile.Cask', 'Brewfile.Mas', 'Brewfile.Tap', 'brewfile.brew', 'brewfile.cask', 'brewfile.mas', 'brewfile.tap'])):
                self.root = cwd
            else:
                # Fallback to script location detection
                script_dir = Path(__file__).parent
                self.root = script_dir.parent

        # Detect if this looks like the analyzer repo itself
        self.is_repo_root = all([
            (self.root / 'install.sh').exists(),
            (self.root / 'scripts').exists(),
            (self.root / 'README.md').exists(),
        ])

        # Respect opt-in to include repo-local Brewfiles
        self.include_local = os.getenv('BREWFILE_INCLUDE_LOCAL', '').lower() in ('1', 'true', 'yes')

        # Standard paths
        self.scripts_dir = self.root / 'scripts'

        # Allow custom output root (so we can read Brewfiles from one dir but
        # write generated output to another)
        output_root_env = os.getenv('BREWFILE_OUTPUT_ROOT')
        # Default to the directory containing this config.py (app root) instead of project root
        app_root = Path(__file__).parent
        default_output_root = app_root
        self.output_root = Path(output_root_env).expanduser().resolve() if output_root_env else default_output_root
        self.output_dir = self.output_root / 'docs' / 'tools'

        # Ensure output directory exists under app root (avoids polluting Brewfile project root)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Output files
        self.json_file = self.output_dir / 'tools.json'
        self.csv_file = self.output_dir / 'tools.csv'

        # Auto-detect Brewfiles
        self._detect_brewfiles()

    def _detect_brewfiles(self):
        """Auto-detect available Brewfiles (single or split format)"""
        self.brewfiles = {}

        # If we're in the repo root and not explicitly including local files, skip local Brewfiles
        if self.is_repo_root and not self.include_local:
            print("ℹ️  Detected analyzer repository root. Ignoring repo-local Brewfiles.")
            print("    Set BREWFILE_INCLUDE_LOCAL=1 to include them, or pass --root to target your Brewfiles.")
            self.brewfiles = {}
            return

        # Check for split Brewfiles first (preferred)
        split_files = {
            'brew': self.root / 'Brewfile.Brew',
            'cask': self.root / 'Brewfile.Cask',
            'mas': self.root / 'Brewfile.Mas',
            'tap': self.root / 'Brewfile.Tap'
        }
        # Also accept lowercase split names if present
        split_files_lower = {
            'brew': self.root / 'brewfile.brew',
            'cask': self.root / 'brewfile.cask',
            'mas': self.root / 'brewfile.mas',
            'tap': self.root / 'brewfile.tap'
        }

        found_split = False
        for item_type, file_path in split_files.items():
            if file_path.exists():
                self.brewfiles[item_type] = file_path
                found_split = True
        # Check lowercase split files too
        for item_type, file_path in split_files_lower.items():
            if file_path.exists():
                self.brewfiles[item_type] = file_path
                found_split = True

        # If no split files found, check for single Brewfile (case-insensitive)
        if not found_split:
            candidates = [self.root / 'Brewfile', self.root / 'brewfile']
            single_brewfile = next((p for p in candidates if p.exists()), None)
            if single_brewfile is not None:
                print(f"Found single Brewfile: {single_brewfile}")
                # Use the same file for all types (will be filtered by regex)
                self.brewfiles = {
                    'brew': single_brewfile,
                    'cask': single_brewfile,
                    'mas': single_brewfile,
                    'tap': single_brewfile
                }
            else:
                print("⚠️  No Brewfiles found! Please ensure you have either:")
                print("   - Split files: Brewfile.Brew, Brewfile.Cask, etc. (or lowercase variants)")
                print("   - Single file: Brewfile (or brewfile)")
                self.brewfiles = {}

    def get_available_types(self):
        """Get list of available Brewfile types"""
        return list(self.brewfiles.keys())

    def has_brewfiles(self):
        """Check if any Brewfiles were found"""
        return len(self.brewfiles) > 0

    def get_info(self):
        """Get configuration info for debugging"""
        return {
            'root': str(self.root),
            'output_dir': str(self.output_dir),
            'brewfiles': {k: str(v) for k, v in self.brewfiles.items()},
            'has_files': self.has_brewfiles()
        }


# Default global config instance
_config = None

def get_config(custom_root=None):
    """Get the global configuration instance"""
    global _config
    if _config is None or custom_root:
        _config = BrewfileConfig(custom_root)
    return _config


if __name__ == '__main__':
    # Test the configuration
    config = get_config()
    info = config.get_info()

    print("Brewfile Analyzer Configuration:")
    print(f"  Root: {info['root']}")
    print(f"  Output: {info['output_dir']}")
    print(f"  Has Brewfiles: {info['has_files']}")
    print("  Available Brewfiles:")
    for item_type, path in info['brewfiles'].items():
        print(f"    {item_type}: {path}")
