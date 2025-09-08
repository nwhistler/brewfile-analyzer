#!/usr/bin/env python3
"""
Brewfile data generator with portable configuration
Supports both single Brewfiles and split Brewfiles
"""
import json
import os
import re
import subprocess
import sys
import getpass

# Dynamically detect the project root (parent of scripts directory)
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.insert(0, project_root)

from config import get_config  # noqa: E402

# Optional DuckDB backend
try:
    from scripts import db as dbmod
except Exception:
    dbmod = None

# Try to import AI description generator
try:
    from scripts.ai_descriptions import AIDescriptionGenerator, load_ai_config
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    AIDescriptionGenerator = None
    load_ai_config = None
    print("AI description generation not available - using fallback descriptions")

# Regex patterns for parsing Brewfiles (robust to single/double quotes and spacing)
PATTERNS = {
    'brew': re.compile(r'^\s*brew\s*["\']([^"\']+)["\']', re.IGNORECASE),
    'cask': re.compile(r'^\s*cask\s*["\']([^"\']+)["\']', re.IGNORECASE),
    'mas': re.compile(r'^\s*mas\s*["\']([^"\']+)["\']\s*,\s*id:\s*(\d+)', re.IGNORECASE),
    'tap': re.compile(r'^\s*tap\s*["\']([^"\']+)["\']', re.IGNORECASE)
}

# Known examples for CLI tools - feel free to customize!
KNOWN_EXAMPLES = {
    'ack': "ack -i 'pattern' lib/",
    'ag': "ag 'TODO' src",
    'bat': "bat -n README.md",
    'btop': "btop",
    'delta': "git diff | delta",
    'dust': "dust -r .",
    'eza': "eza -lah --git",
    'fd': "fd pattern src",
    'fzf': "fd . | fzf",
    'git': "git status",
    'htop': "htop",
    'jq': "jq '.name' package.json",
    'neovim': "nvim file.txt",
    'ripgrep': "rg -n 'foo' src",
    'tmux': "tmux new -s dev",
    'tree': "tree -L 2",
    'zoxide': "z project"
}


def parse_brewfile(file_path, pattern, item_type):
    """Parse a Brewfile and extract items of a specific type."""
    items = []
    if not file_path or not file_path.exists():
        return items

    try:
        content = file_path.read_text(encoding='utf-8')
        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            match = pattern.match(line)
            if match:
                item = {'name': match.group(1), 'type': item_type}

                # Special handling for MAS apps (they have IDs)
                if item_type == 'mas' and len(match.groups()) > 1:
                    item['mas_id'] = match.group(2)

                items.append(item)

    except Exception as e:
        print(f"Warning: Error reading {file_path}: {e}")

    return items


def remove_duplicates(items):
    """Remove duplicate items while preserving order."""
    seen = set()
    unique_items = []
    for item in items:
        key = (item['name'].lower(), item['type'])
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    return unique_items


def collect_items(config):
    """Collect all items from available Brewfiles."""
    all_items = []

    print(f"Scanning for packages in {config.root}...")

    for item_type, file_path in config.brewfiles.items():
        if file_path.exists():
            pattern = PATTERNS.get(item_type)
            if pattern:
                items = parse_brewfile(file_path, pattern, item_type)
                all_items.extend(items)
                if items:
                    print(f"  Found {len(items)} {item_type} items in {file_path.name}")

    # Remove duplicates and sort
    unique_items = remove_duplicates(all_items)
    total_count = len(unique_items)

    if total_count == 0:
        print("⚠️  No packages found! Check your Brewfile format.")
        return []

    print(f"Total unique packages: {total_count}")
    return sorted(unique_items, key=lambda x: x['name'].lower())


def get_brew_description(name):
    """Get description from brew info command."""
    try:
        cmd = ['brew', 'info', '--json=v2', name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            if 'formulae' in data and data['formulae']:
                desc = data['formulae'][0].get('desc', '')
                return desc if desc else None

    except Exception:
        pass
    return None


def get_cask_description(name):
    """Get description from brew cask info command."""
    try:
        cmd = ['brew', 'info', '--cask', '--json=v2', name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            if 'casks' in data and data['casks']:
                desc = data['casks'][0].get('desc', '')
                return desc if desc else None

    except Exception:
        pass
    return None


def get_enhanced_description(name, item_type, mas_id=''):
    """Get enhanced description with fallbacks."""
    # First try official sources
    if item_type == 'brew':
        official_desc = get_brew_description(name)
        if official_desc:
            return official_desc
    elif item_type == 'cask':
        official_desc = get_cask_description(name)
        if official_desc:
            return official_desc

    # Enhanced fallback descriptions
    fallbacks = {
        'brew': {
            'ack': 'Text search tool optimized for source code',
            'ag': 'Fast code search tool similar to ack but faster',
            'bat': 'Syntax-highlighted cat command with Git integration',
            'delta': 'Syntax-highlighting pager for Git diffs',
            'dust': 'Modern disk usage analyzer with tree visualization',
            'eza': 'Modern ls replacement with colors and Git status',
            'fd': 'Simple and fast alternative to find command',
            'fzf': 'Command-line fuzzy finder for interactive selections',
            'git': 'Distributed version control system',
            'htop': 'Interactive process viewer and system monitor',
            'jq': 'Command-line JSON processor',
            'neovim': 'Modern Vim-based text editor',
            'ripgrep': 'Fast text search tool that recursively searches directories',
            'tmux': 'Terminal multiplexer for managing multiple sessions',
            'tree': 'Directory listing tool that displays files in tree format'
        },
        'cask': {
            '1password': 'Password manager for storing and generating secure passwords',
            'docker': 'Platform for developing and running containerized applications',
            'firefox': 'Open-source web browser focused on privacy',
            'google-chrome': 'Fast and secure web browser from Google',
            'visual-studio-code': 'Lightweight but powerful source code editor',
            'zoom': 'Video conferencing and online meeting platform'
        },
        'mas': {
            'Fantastical': 'Premium calendar app with natural language event creation',
            'Xcode': "Apple's integrated development environment for iOS/macOS apps"
        },
        'tap': {
            'homebrew/bundle': 'Homebrew tap for managing dependencies with Brewfiles',
            'homebrew/services': 'Homebrew tap for managing background services'
        }
    }

    # Check for known enhanced descriptions
    type_fallbacks = fallbacks.get(item_type, {})
    if name in type_fallbacks:
        return type_fallbacks[name]

    # Generic fallbacks
    if item_type == 'brew':
        return f"Command-line tool: {name.replace('-', ' ').replace('_', ' ')}"
    elif item_type == 'cask':
        return f"macOS application: {name.replace('-', ' ').replace('_', ' ')}"
    elif item_type == 'mas':
        suffix = f" (ID: {mas_id})" if mas_id else ""
        return f"Mac App Store application{suffix}"
    elif item_type == 'tap':
        return "Homebrew tap providing additional software packages"

    return f"{item_type.title()}: {name}"


def _get_example_for_type(name: str, item_type: str, mas_id: str = '') -> str:
    """Generate appropriate example for item type."""
    if item_type == 'brew':
        return KNOWN_EXAMPLES.get(name, f"{name} --help")
    elif item_type == 'cask':
        return f"Open {name} from Applications folder"
    elif item_type == 'mas':
        if mas_id:
            return f"mas install {mas_id}"
        else:
            return f"Install {name} from Mac App Store"
    elif item_type == 'tap':
        return f"brew tap {name}"
    else:
        return f"{name} --help"


def _initialize_ai_generator(use_ai, ai_provider):
    """Initialize AI generator with proper error handling."""
    if not use_ai:
        return None

    if not AI_AVAILABLE:
        print("WARNING: AI descriptions requested but not available")
        return None

    if load_ai_config is None or AIDescriptionGenerator is None:
        print("WARNING: AI modules not properly imported")
        return None

    try:
        ai_config = load_ai_config()
        ai_generator = AIDescriptionGenerator(provider=ai_provider, config=ai_config)

        status = ai_generator.get_status()
        if status is None:
            return None

        providers = status.get("available_providers", [])
        if not providers:
            return None

        return ai_generator
    except Exception:
        return None


def _ensure_api_key_interactive(provider: str) -> None:
    """If running in an interactive TTY and the selected provider lacks an API key, prompt for it.

    This sets the key only for the current process (no persistence).
    """
    try:
        if not sys.stdin.isatty():
            return
    except Exception:
        return

    provider = (provider or "auto").lower()
    if provider not in {"claude", "gemini", "openai"}:
        return

    if provider == "claude":
        if os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
            return
        try:
            key = getpass.getpass("Enter Claude (Anthropic) API key: ")
        except Exception:
            return
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
    elif provider == "gemini":
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            return
        try:
            key = getpass.getpass("Enter Gemini API key: ")
        except Exception:
            return
        if key:
            os.environ["GEMINI_API_KEY"] = key
    elif provider == "openai":
        if os.getenv("OPENAI_API_KEY"):
            return
        try:
            key = getpass.getpass("Enter OpenAI API key: ")
        except Exception:
            return
        if key:
            os.environ["OPENAI_API_KEY"] = key


def generate_data(config, use_ai=False, ai_provider="auto"):
    """Generate JSON and CSV data files with optional AI enhancement."""
    items = collect_items(config)

    if not items:
        print("No items to process. Exiting.")
        return False

    rows = []
    db_con = None
    if dbmod is not None:
        try:
            db_con = dbmod.ensure_db(config)
        except Exception:
            db_con = None

    # Initialize AI generator if requested and available
    ai_generator = _initialize_ai_generator(use_ai, ai_provider)

# Generate descriptions (AI-enhanced or fallback)
    ai_lookup = {}
    if ai_generator:
        print("Generating AI-enhanced descriptions...")
        # Convert items to format expected by AI generator
        ai_tools = [{'name': item['name'], 'type': item['type']} for item in items]
        enhanced_tools = ai_generator.batch_generate(ai_tools)
        # Create lookup dict for AI descriptions
        ai_lookup = {tool['name']: tool for tool in enhanced_tools}
    else:
        print("Generating enhanced descriptions...")

    # Process each item
    for item in items:
        name = item['name']
        item_type = item['type']
        mas_id = item.get('mas_id', '')

        # Try AI description first, then fallback
        ai_generated = False
        if ai_generator and name in ai_lookup:
            ai_tool = ai_lookup[name]
            desc = ai_tool.get('ai_description')
            example = ai_tool.get('ai_example')
            if desc and example:
                ai_generated = True
            else:
                desc = desc or get_enhanced_description(name, item_type, mas_id)
                example = example or KNOWN_EXAMPLES.get(name, f"{name} --help")
        else:
            desc = get_enhanced_description(name, item_type, mas_id)
            example = _get_example_for_type(name, item_type, mas_id)

        row = {
            'name': name,
            'description': desc,
            'example': example,
            'type': item_type
        }

        if mas_id:
            row['mas_id'] = mas_id

        if ai_generated:
            row['ai_generated'] = True

        rows.append(row)
        # If DB is available, upsert/merge preserving user edits
        if db_con is not None:
            try:
                db_row = {
                    'name': name,
                    'type': item_type,
                    'description': desc,
                    'example': example,
                }
                if mas_id:
                    db_row['mas_id'] = mas_id
                dbmod.upsert_tool_merged(db_con, db_row)
            except Exception as e:
                print(f"Warning: DB upsert failed for {name}: {e}")

    # Export snapshots from DB if available, else write from rows
    if db_con is not None:
        print("DuckDB updated. Skipping JSON/CSV snapshot (API-only mode).")
    else:
        # Write JSON
        print(f"Writing {len(rows)} items to {config.json_file}")
        config.json_file.write_text(json.dumps(rows, indent=2), encoding='utf-8')

        # CSV disabled (DuckDB-only mode)

    # Summary
    from collections import Counter
    type_counts = Counter(item['type'] for item in items)
    print("\nSummary:")
    for item_type, count in sorted(type_counts.items()):
        print(f"  {item_type}: {count}")

    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate comprehensive documentation from Brewfiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
AI Description Options:
  --ai                     Enable AI description generation (auto-detect provider)
  --ai-provider ollama     Use specific AI provider (ollama, claude, gemini, openai)
  --ai-status              Show AI provider status and exit

Examples:
  %(prog)s                           # Generate with standard descriptions
  %(prog)s --ai                      # Generate with AI descriptions (auto-detect)
  %(prog)s --ai-provider ollama      # Generate with Ollama AI descriptions
  %(prog)s --ai-status               # Check AI provider availability
        """
    )

    parser.add_argument('--ai', action='store_true',
                       help='Enable AI description generation')
    parser.add_argument('--ai-provider',
                       choices=['auto', 'ollama', 'claude', 'gemini', 'openai'],
                       default='auto',
                       help='AI provider to use (default: auto)')
    parser.add_argument('--ai-status', action='store_true',
                       help='Show AI provider status')
    parser.add_argument('--root', help='Custom project root directory')

    args = parser.parse_args()

    config = get_config(args.root)

    # Handle AI status check
    if args.ai_status:
        if AI_AVAILABLE and load_ai_config is not None and AIDescriptionGenerator is not None:
            try:
                ai_config = load_ai_config()
                ai_generator = AIDescriptionGenerator(config=ai_config)
                status = ai_generator.get_status()

                print("AI Description Generator Status:")
                print("=" * 40)
                print(f"Selected Provider: {status['selected_provider']}")
                print(f"Available Providers: {', '.join(status['available_providers']) or 'None'}")
                print("\nProvider Status:")
                for provider, available in status['provider_status'].items():
                    status_icon = "✅" if available else "❌"
                    print(f"  {status_icon} {provider.title()}: {'Available' if available else 'Not available'}")

                print("\nConfiguration:")
                for key, value in status['config'].items():
                    print(f"  {key}: {value}")

                return 0
            except Exception as e:
                print(f"❌ Error checking AI status: {e}")
                return 1
        else:
            print("❌ AI description generation not available")
            print("Install AI dependencies or check provider setup")
            return 1

    # Show configuration
    print("Brewfile Analyzer")
    print("=" * 50)
    print(f"Project root: {config.root}")
    print(f"Output directory: {config.output_dir}")

    if args.ai:
        if AI_AVAILABLE:
            print(f"AI descriptions: Enabled ({args.ai_provider})")
        else:
            print("AI descriptions: Requested but not available")
    else:
        print("AI descriptions: Disabled")

    # If user explicitly selected a cloud provider and no key is set, prompt interactively
    if args.ai and args.ai_provider in {"claude", "gemini", "openai"}:
        _ensure_api_key_interactive(args.ai_provider)

    if not config.has_brewfiles():
        print("\n❌ No Brewfiles found!")
        print("\nPlease ensure you have either:")
        print("  • Split files: Brewfile.Brew, Brewfile.Cask, "
              "Brewfile.Mas, Brewfile.Tap")
        print("  • Single file: Brewfile")
        print(f"\nIn directory: {config.root}")
        return 1

    print(f"Found Brewfiles: {', '.join(config.get_available_types())}")
    print()

    # Generate data
    success = generate_data(config, use_ai=args.ai, ai_provider=args.ai_provider)

    if success:
        print("\n✅ Success! View your data at:")
        print(f"   JSON: {config.json_file}")
        print(f"   CSV:  {config.csv_file}")
        print("\n🌐 Start the web server:")
        if args.ai:
            print("   python3 scripts/serve_combined.py  # With editing capabilities")
        else:
            print("   python3 scripts/serve_static.py")
        return 0
    else:
        print("\n❌ Failed to generate data")
        return 1


if __name__ == '__main__':
    exit(main())
