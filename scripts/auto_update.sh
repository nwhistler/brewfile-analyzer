#!/usr/bin/env zsh
# Auto update helper for Brewfile Analyzer
# - Runs a silent background update check and applies updates if available
# - On first run, optionally sets up a launchd task to check periodically (with a concise prompt)

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

# First-run prompt (concise) with optional Details…
prompt_schedule_setup() {
  # Returns 0 to enable, 1 to skip
  local title="Brewfile Analyzer"
  local msg_main
  msg_main=$(cat <<MSG
Enable automatic update checks?

Brewfile Analyzer will check for updates every 6 hours in the background.
You can turn this off anytime.
MSG
)
  local msg_details
  msg_details=$(cat <<DET
What this does:

• Creates a per-user LaunchAgent:
  $PLIST_PATH
• Runs every 6 hours and at login
• Executes:
  $SCRIPT_DIR/auto_update.sh scheduled
• Logs:
  $HOME/Library/Logs/brewfile-analyzer-updatecheck.out.log
  $HOME/Library/Logs/brewfile-analyzer-updatecheck.err.log
• Disable anytime:
  launchctl unload -w $PLIST_PATH && rm -f $PLIST_PATH
DET
)

  if is_macos && have_osascript; then
    while true; do
      local osa
      if osa=$(osascript -e "display dialog \"${msg_main}\" buttons {\"Not now\",\"Details…\",\"Enable\"} default button \"Enable\" with title \"${title}\" with icon note giving up after 60"); then
        case "$osa" in
          *"button returned:Enable"*) return 0 ;;
          *"button returned:Details…"*)
            osascript -e "display dialog \"${msg_details}\" buttons {\"OK\"} default button \"OK\" with title \"${title}\" with icon note" || true
            continue ;;
          *) return 1 ;;
        esac
      else
        return 1
      fi
    done
  else
    # Fallback to tty prompt (if interactive)
    if [ -t 0 ]; then
      printf "Enable automatic update checks? [Y/n]: "
      read -r ans || true
      case "${ans:-Y}" in
        Y|y|Yes|yes) return 0;;
        *) return 1;;
      esac
    fi
    return 1
  fi
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
  # First-run prompt (concise). Skip in scheduled runs or if already set up.
  if [[ "${1:-}" == "scheduled" ]]; then
    return 0
  fi
  if [[ -f "$MARKER_PROMPTED" ]]; then
    return 0
  fi

  if prompt_schedule_setup; then
    if is_macos; then
      install_launchagent
    else
      echo "Non-macOS: periodic scheduling not supported by this script." >&2
    fi
  fi

  # Mark so we don't prompt again on future runs
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

