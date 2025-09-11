#!/usr/bin/env zsh
# Auto update helper for Brewfile Analyzer
# - Runs a silent background update check and applies updates if available
# - On first run, silently sets up a launchd task to check periodically (no prompts)

set -euo pipefail

# Resolve paths relative to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SELF_UPDATE="$APP_DIR/scripts/self_update.py"
PY_BIN="${PY_BIN:-/usr/bin/python3}"

MARKER_PROMPTED="$APP_DIR/.auto_update_prompted"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_LABEL="com.nwhistler.brewfile-analyzer.updatecheck"
PLIST_PATH="$LAUNCH_AGENTS_DIR/${PLIST_LABEL}.plist"

is_macos() {
  [[ "$(uname -s)" == "Darwin" ]]
}

have_osascript() {
  command -v osascript >/dev/null 2>&1
}


install_launchagent() {
  mkdir -p "$LAUNCH_AGENTS_DIR"
  cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
      <string>${SCRIPT_DIR}/auto_update.sh</string>
      <string>scheduled</string>
    </array>

    <!-- Every 6 hours -->
    <key>StartInterval</key>
    <integer>21600</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/brewfile-analyzer-updatecheck.out.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/brewfile-analyzer-updatecheck.err.log</string>

    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
      <key>PY_BIN</key>
      <string>${PY_BIN}</string>
    </dict>
  </dict>
</plist>
PLIST

  # Load (reload if exists)
  launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl load -w "$PLIST_PATH"

  # Notify user on first setup (macOS only)
  if is_macos && have_osascript; then
    local title="Brewfile Analyzer"
    local subtitle="Auto-update enabled"
    local msg="Checks every 6h via LaunchAgent. Manage with: launchctl unload -w $PLIST_PATH. Logs: ~/Library/Logs/."
    osascript -e "display notification \"$msg\" with title \"$title\" subtitle \"$subtitle\"" || true
  fi
}

maybe_setup_schedule() {
  # Silent setup: no prompts.
  # Skip in scheduled runs or if we've already set up once
  if [[ "${1:-}" == "scheduled" ]]; then
    return 0
  fi
  if [[ -f "$MARKER_PROMPTED" ]]; then
    return 0
  fi

  if is_macos; then
    install_launchagent
  else
    echo "Non-macOS: periodic scheduling not supported by this script." >&2
  fi

  # Mark so we don't attempt setup again on future runs
  : > "$MARKER_PROMPTED"
}

run_check() {
  # Run silently in the background; apply updates if available, no prompts
  "$PY_BIN" "$SELF_UPDATE" --apply --repo nwhistler/brewfile-analyzer --ref main >/dev/null 2>&1 || true
}

main() {
  maybe_setup_schedule "${1:-}"
  run_check
}

main "$@"

