#!/bin/bash
# Brewfile Analyzer - One-Command Installation Script
# Portable setup for analyzing and documenting Homebrew Brewfiles

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_MIN_VERSION="3.7"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_BREW_DIR="$HOME/brewfile"
TARGET_DIR="$HOME_BREW_DIR/web_app"

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Fancy spinner (ASCII beach ball homage) wrapper
# Usage: run_with_spinner "Message" <cmd> [args...]
run_with_spinner() {
    local msg="$1"; shift
    local tmp_log
    tmp_log=$(mktemp -t brewfile-installer.XXXXXX)

    # Run the command in background with output captured to a temp log
    ("$@") >"$tmp_log" 2>&1 &
    local pid=$!

    # Spinner frames and rotating colors (beach-ball vibes)
    local frames=("◐" "◓" "◑" "◒")
    local colors=("\033[0;31m" "\033[1;33m" "\033[0;32m" "\033[0;34m" "\033[0;35m")
    local i=0

    printf "${BLUE}⏳ %s${NC}  " "$msg"
    while kill -0 "$pid" 2>/dev/null; do
        local frame=${frames[$((i % ${#frames[@]}))]}
        local color=${colors[$((i % ${#colors[@]}))]}
        printf "\r${BLUE}⏳ %s${NC}  ${color}%s${NC}  " "$msg" "$frame"
        sleep 0.1
        i=$((i+1))
    done

    wait "$pid"
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        printf "\r${GREEN}✅ %s${NC}                                          \n" "$msg"
        rm -f "$tmp_log" 2>/dev/null || true
    else
        printf "\r${RED}❌ %s (failed)${NC}\n" "$msg"
        log_warning "Last 20 lines of output:"
        tail -n 20 "$tmp_log" 2>/dev/null || true
        log_info "Full log: $tmp_log"
    fi
    return $exit_code
}

prompt_api_key() {
    # Usage: prompt_api_key <provider>
    # Supports: claude | gemini | openai
    local provider="$1"
    local key_var=""
    local alt_var=""
    local provider_name=""

    case "$provider" in
        claude)
            provider_name="Claude (Anthropic)"
            # Accept either CLAUDE_API_KEY or ANTHROPIC_API_KEY; prefer ANTHROPIC_API_KEY
            if [ -n "$CLAUDE_API_KEY" ] || [ -n "$ANTHROPIC_API_KEY" ]; then
                return 0
            fi
            key_var="ANTHROPIC_API_KEY"
            alt_var="CLAUDE_API_KEY"
            ;;
        gemini)
            provider_name="Gemini"
            if [ -n "$GEMINI_API_KEY" ] || [ -n "$GOOGLE_API_KEY" ]; then
                return 0
            fi
            key_var="GEMINI_API_KEY"
            ;;
        openai)
            provider_name="OpenAI"
            if [ -n "$OPENAI_API_KEY" ]; then
                return 0
            fi
            key_var="OPENAI_API_KEY"
            ;;
        *)
            return 0
            ;;
    esac

    echo
    log_warning "No API key detected for $provider_name."
    printf "Enter $provider_name API key (input hidden): "
    # Use silent read to avoid echoing the key
    stty -echo 2>/dev/null || true
    IFS= read -r api_key
    stty echo 2>/dev/null || true
    echo

    if [ -z "$api_key" ]; then
        log_warning "No key entered. Continuing without $provider_name (fallback descriptions will be used)."
        return 1
    fi

    # Export for current process so initial generation works
    export ${key_var}="$api_key"
    if [ -n "$alt_var" ]; then
        export ${alt_var}="$api_key"
    fi
    log_success "$provider_name API key configured for this session."

    # Offer to persist to ~/.zshrc
    if [[ "$OSTYPE" == "darwin"* ]]; then
        read -p "Persist this key to ~/.zshrc for future runs? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ZSHRC="$HOME/.zshrc"
            {
                echo "# Brewfile Analyzer - ${provider_name} API key"
                echo "export ${key_var}=\"$api_key\""
                if [ -n "$alt_var" ]; then
                    echo "export ${alt_var}=\"$api_key\""
                fi
            } >> "$ZSHRC"
            log_success "Saved ${provider_name} API key to ~/.zshrc (restart your shell to apply)."
        fi
    fi

    # Clear local variable
    unset api_key

    return 0
}

check_python() {
    log_info "Checking Python installation..."

    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed or not in PATH"
        log_info "Please install Python 3.7+ from https://python.org or via Homebrew:"
        log_info "  brew install python"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    log_info "Found Python $PYTHON_VERSION"

    # Simple version comparison (works for x.y format)
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)"; then
        log_success "Python version requirement met (>= $PYTHON_MIN_VERSION)"
    else
        log_error "Python $PYTHON_VERSION is too old. Minimum required: $PYTHON_MIN_VERSION"
        exit 1
    fi
}

check_homebrew() {
    log_info "Checking Homebrew installation..."

    if command -v brew &> /dev/null; then
        BREW_VERSION=$(brew --version | head -n1)
        log_success "Found $BREW_VERSION"
    else
        log_warning "Homebrew not found - some features may not work"
        log_info "Install Homebrew from https://brew.sh"
        log_info "The tool will still work but won't fetch package descriptions"
    fi
}

check_brewfiles() {
    log_info "Setting up Brewfile location in your home directory..."

    if [ ! -d "$HOME_BREW_DIR" ]; then
        log_info "Creating Brewfile directory: $HOME_BREW_DIR"
        mkdir -p "$HOME_BREW_DIR"
    fi

    # Determine a potential source of existing Brewfiles (for messaging only)
    PROJECT_ROOT="${BREWFILE_PROJECT_ROOT:-$SCRIPT_DIR}"

    # Detect if this looks like the analyzer repo root
    IS_REPO_ROOT=false
    if [ -f "$PROJECT_ROOT/install.sh" ] && [ -d "$PROJECT_ROOT/scripts" ] && [ -f "$PROJECT_ROOT/README.md" ]; then
        IS_REPO_ROOT=true
    fi

    # Never auto-copy Brewfiles from the installer repo to the user's home brewfile dir.
    # This avoids bringing over examples or local repo files unintentionally.
    if [ "$IS_REPO_ROOT" = true ]; then
        log_info "Detected analyzer repository root. Repo-local Brewfiles will be ignored."
        log_info "Set BREWFILE_PROJECT_ROOT to point to your actual Brewfile directory if needed."
    fi

    # Check if we now have Brewfiles in $HOME_BREW_DIR
    HAS_BREWFILES=false
    for f in Brewfile Brewfile.Brew Brewfile.Cask Brewfile.Mas Brewfile.Tap; do
        if [ -f "$HOME_BREW_DIR/$f" ]; then
            HAS_BREWFILES=true
        fi
    done

    if [ "$HAS_BREWFILES" != true ]; then
        echo
        read -p "No Brewfiles found. Enter path to directory containing your Brewfile(s), or press Enter to create a starter Brewfile in $HOME_BREW_DIR: " USER_PATH
        # Expand ~ if used
        USER_PATH=${USER_PATH/#\~/$HOME}
        if [ -n "$USER_PATH" ] && [ -d "$USER_PATH" ]; then
            COPIED=false
            for f in Brewfile Brewfile.Brew Brewfile.Cask Brewfile.Mas Brewfile.Tap; do
                if [ -f "$USER_PATH/$f" ]; then
                    if [ -f "$HOME_BREW_DIR/$f" ]; then
                        log_warning "$f already exists in $HOME_BREW_DIR; keeping existing copy"
                    else
                        cp "$USER_PATH/$f" "$HOME_BREW_DIR/$f"
                        log_success "Copied $f from $USER_PATH"
                        COPIED=true
                    fi
                fi
            done
            if [ "$COPIED" != true ]; then
                log_warning "Did not find Brewfile(s) at: $USER_PATH"
            fi
        fi

        # Re-check after potential copy
        HAS_BREWFILES=false
        for f in Brewfile Brewfile.Brew Brewfile.Cask Brewfile.Mas Brewfile.Tap; do
            if [ -f "$HOME_BREW_DIR/$f" ]; then
                HAS_BREWFILES=true
            fi
        done

        if [ "$HAS_BREWFILES" != true ]; then
            read -p "Create a starter Brewfile in $HOME_BREW_DIR? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                cat > "$HOME_BREW_DIR/Brewfile" << 'EOF'
# Brewfile - starter template
# Learn more: https://github.com/Homebrew/homebrew-bundle

tap "homebrew/bundle"
# brew "git"
# brew "node"
# cask "visual-studio-code"
# mas "Xcode", id: 497799835
EOF
                log_success "Created starter Brewfile at $HOME_BREW_DIR/Brewfile"
                HAS_BREWFILES=true
            else
                log_warning "Continuing without Brewfiles. You can add them later to $HOME_BREW_DIR."
            fi
        fi
    fi

    # Use the home Brewfile directory as the project root for subsequent steps
    export BREWFILE_PROJECT_ROOT="$HOME_BREW_DIR"
    log_info "Using BREWFILE_PROJECT_ROOT=$BREWFILE_PROJECT_ROOT"
    return 0
}

run_setup() {
    log_info "Preparing environment..."
    log_success "Environment ready"
}

test_installation() {
    log_info "Testing installation..."
    cd "$SCRIPT_DIR"

    # Test configuration
    if python3 -c "from config import get_config; get_config()" 2>/dev/null; then
        log_success "Configuration module working"
    else
        log_error "Configuration module test failed"
        exit 1
    fi

    # Test scripts
    if python3 scripts/gen_tools_data.py --help >/dev/null 2>&1; then
        log_success "Data generator script accessible"
    else
        log_error "Data generator script test failed"
        exit 1
    fi

    if python3 scripts/serve_static.py --help >/dev/null 2>&1; then
        log_success "Web server script accessible"
    else
        log_error "Web server script test failed"
        exit 1
    fi

    if python3 scripts/update_brewfile_data.py --help >/dev/null 2>&1; then
        log_success "Update script accessible"
    else
        log_error "Update script test failed"
        exit 1
    fi
}

generate_initial_data() {
    log_info "Generating initial data (if Brewfiles present)..."

    # Run generator from installed app location, reading Brewfiles from $HOME_BREW_DIR
    # and writing output to the app's docs directory via BREWFILE_OUTPUT_ROOT
if run_with_spinner "Generating initial data (if Brewfiles present)" \
       env BREWFILE_PROJECT_ROOT="$HOME_BREW_DIR" BREWFILE_OUTPUT_ROOT="$TARGET_DIR" \
       python3 "$TARGET_DIR/scripts/gen_tools_data.py" $AI_ARGS; then
        log_success "Initial data generated successfully"

        # Check output files at target
        if [ -f "$TARGET_DIR/docs/tools/tools.json" ]; then
            TOOL_COUNT=$(python3 -c "import json; data=json.load(open('$TARGET_DIR/docs/tools/tools.json')); print(len(data))" 2>/dev/null || echo "unknown")
            log_success "Generated data for $TOOL_COUNT packages"
        fi
    else
        log_warning "Could not generate initial data (no Brewfiles or other issue)"
        log_info "You can run 'python3 scripts/gen_tools_data.py' later from $TARGET_DIR when you have Brewfiles"
    fi
}

show_next_steps() {
    echo
    echo -e "${BLUE}🎉 Installation Complete!${NC}"
    echo "=========================="
    echo
    echo "📁 App location: $TARGET_DIR"
    echo "📦 Brewfile directory: ${BREWFILE_PROJECT_ROOT:-$HOME_BREW_DIR}"
    echo "📂 Installer repository (can be removed): $SCRIPT_DIR"
    echo
    echo "🚀 Next steps:"
    echo
    echo "1. Ensure you have Brewfiles in the project directory:"
    echo "   - Single file: Brewfile"
    echo "   - Or split files: Brewfile.Brew, Brewfile.Cask, etc."
    echo
    echo "2. Generate/update documentation:"
    echo "   cd '$TARGET_DIR'"
    echo "   python3 scripts/gen_tools_data.py [--ai --ai-provider auto]"
    echo
    echo "3. Start web server to view results:"
    echo "   cd '$TARGET_DIR'"
    echo "   python3 scripts/serve_static.py"
    echo "   Then open: http://localhost:8000"
    echo
    echo "4. Set up periodic updates:"
    echo "   cd '$TARGET_DIR'"
    echo "   python3 scripts/update_brewfile_data.py --setup-hook"
    echo
    echo "🔧 Useful commands (run from $TARGET_DIR):"
    echo "   python3 scripts/gen_tools_data.py   # Generate/update docs"
    echo "   python3 scripts/serve_combined.py   # Start server with editing"
    echo "   python3 scripts/update_brewfile_data.py --watch   # Watch for changes"
    echo "   python3 scripts/update_brewfile_data.py --status  # Check update status"
    echo
    echo "📚 Documentation: README.md"
    echo "🐛 Issues: Check the troubleshooting section in README.md"
    echo
}

install_requirements() {
    log_info "Checking requirements.txt..."

    REQ_FILE="$SCRIPT_DIR/requirements.txt"
    if [ ! -f "$REQ_FILE" ]; then
        log_info "No requirements.txt found - skipping"
        return
    fi

    # Extract non-comment, non-empty lines
    ACTIVE_REQS=$(grep -E '^[[:space:]]*[^#[:space:]].*' "$REQ_FILE" || true)
    if [ -z "$ACTIVE_REQS" ]; then
        log_info "requirements.txt has no active requirements - skipping"
        return
    fi

    echo
    echo "The following packages are listed in requirements.txt:" >&2
    echo "$ACTIVE_REQS" >&2

    # Check for pip
    if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
        log_warning "pip not found - cannot install requirements"
        log_info "Install pip or Python from Homebrew: brew install python"
        return
    fi

    # Prefer venv pip if available
if [ -x "$TARGET_DIR/.venv/bin/pip" ]; then
        PIP_CMD="$TARGET_DIR/.venv/bin/pip"
    else
        PIP_CMD="pip3"
        if ! command -v pip3 &> /dev/null; then
            PIP_CMD="pip"
        fi
    fi

    echo
    read -p "Install requirements with '$PIP_CMD install --user -r requirements.txt'? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log_info "Skipping requirements installation"
        return
    fi

    if run_with_spinner "Installing Python requirements" "$PIP_CMD" install --user -r "$REQ_FILE"; then
        log_success "Requirements installed successfully"
    else
        log_warning "Failed to install some requirements. You can retry later with: $PIP_CMD install --user -r $REQ_FILE"
    fi
}

install_optional_deps() {
    log_info "Checking for optional enhancements..."

    # Check if pip is available
    if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
        log_warning "pip not found - skipping optional dependencies"
        return
    fi

    # Prefer venv pip if available
    if [ -x "$TARGET_DIR/.venv/bin/pip" ]; then
        PIP_CMD="$TARGET_DIR/.venv/bin/pip"
    else
        PIP_CMD="pip3"
        if ! command -v pip3 &> /dev/null; then
            PIP_CMD="pip"
        fi
    fi

    echo
    read -p "Install optional dependencies for enhanced features? (y/N) " -n 1 -r
    echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installing optional dependencies..."

        # Try to install optional packages with spinner
        for package in "orjson" "click" "rich" "duckdb"; do
            if run_with_spinner "Installing $package" "$PIP_CMD" install "$package"; then
                log_success "Installed $package"
            else
                log_warning "Failed to install $package (continuing anyway)"
            fi
        done

        log_success "Optional dependencies installation completed"
    else
        log_info "Skipping optional dependencies (can install later)"
    fi
}

create_desktop_shortcut() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if [ "$SKIP_SHORTCUT" = true ]; then
            log_info "Skipping desktop shortcut creation (--no-shortcut)"
            return
        fi
        echo
        read -p "Create desktop shortcut for easy access? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            SHORTCUT_PATH="$HOME/Desktop/Brewfile Analyzer.command"
            PY_CMD="python3"
            if [ -x "$TARGET_DIR/.venv/bin/python" ]; then
                PY_CMD="$TARGET_DIR/.venv/bin/python"
            fi
            cat > "$SHORTCUT_PATH" << EOF
#!/bin/bash
cd "$TARGET_DIR"
echo "Starting Brewfile Analyzer..."
"$PY_CMD" scripts/gen_tools_data.py && "$PY_CMD" scripts/serve_static.py
EOF
            chmod +x "$SHORTCUT_PATH"
            log_success "Created desktop shortcut: $SHORTCUT_PATH"
        fi
    fi
}

install_web_app() {
    log_info "Deploying Brewfile Analyzer web app to: $TARGET_DIR"

    mkdir -p "$TARGET_DIR"
    mkdir -p "$TARGET_DIR/docs"

    # Copy runtime files
    cp -R "$SCRIPT_DIR/scripts" "$TARGET_DIR/" 2>/dev/null || {
        log_error "Failed to copy scripts directory"; exit 1;
    }
    cp "$SCRIPT_DIR/config.py" "$TARGET_DIR/" 2>/dev/null || {
        log_error "Failed to copy config.py"; exit 1;
    }
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        cp "$SCRIPT_DIR/requirements.txt" "$TARGET_DIR/" 2>/dev/null || true
    fi
    # Copy web assets
    if [ -d "$SCRIPT_DIR/docs/tools" ]; then
        cp -R "$SCRIPT_DIR/docs/tools" "$TARGET_DIR/docs/" 2>/dev/null || log_warning "Could not copy docs/tools (will be created on first run)"
    fi

# Generate initial data at target (if Brewfiles exist)
    if run_with_spinner "Generating data in $TARGET_DIR (if Brewfiles present)" \
       env BREWFILE_PROJECT_ROOT="$HOME_BREW_DIR" python3 "$TARGET_DIR/scripts/gen_tools_data.py"; then
        log_success "Initial data generated in $TARGET_DIR/docs/tools"
    else
        log_warning "Could not generate data at $TARGET_DIR (no Brewfiles yet or other issue)"
    fi
}

setup_venv() {
    echo
    if [ "$SKIP_VENV" = true ]; then
        log_info "Skipping virtual environment creation (--no-venv)"
        return
    fi
    log_info "Checking for Python venv module..."
    if python3 -c "import venv" >/dev/null 2>&1; then
        if [ -d "$TARGET_DIR/.venv" ]; then
            log_info "Virtual environment already exists at $TARGET_DIR/.venv"
            return
        fi
        log_info "Creating virtual environment at $TARGET_DIR/.venv"
if run_with_spinner "Creating virtual environment at $TARGET_DIR/.venv" python3 -m venv "$TARGET_DIR/.venv"; then
            log_success "Virtual environment created"
            echo "To activate: source $TARGET_DIR/.venv/bin/activate"
        else
            log_warning "Failed to create virtual environment (continuing without venv)"
        fi
    else
        log_info "venv module not available; skipping virtual environment creation"
    fi
}

setup_brew_bundle_integration() {
    echo
    read -p "Set up automatic 'brew bundle' integration (run analyzer update before bundling)? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Skipping brew bundle integration (can set up later with: python3 scripts/update_brewfile_data.py --setup-hook)"
        return
    fi

    # Create or update the hook script in repo root
    # Generate hook using the installed app location so paths are correct
    if python3 "$TARGET_DIR/scripts/update_brewfile_data.py" --setup-hook >/dev/null 2>&1; then
        log_success "Created/updated brew bundle hook script"
    else
        log_warning "Failed to create hook script automatically. You can run it later: python3 scripts/update_brewfile_data.py --setup-hook"
        return
    fi

    HOOK_PATH="$TARGET_DIR/brewfile_update_hook.sh"

    # Offer to configure zsh function to run hook before 'brew bundle'
    echo
    read -p "Configure your zsh so 'brew bundle' automatically runs the update hook? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ZSHRC="$HOME/.zshrc"
        MARK_START="# >>> Brewfile Analyzer brew bundle hook >>>"
        MARK_END="# <<< Brewfile Analyzer brew bundle hook <<<"

        # Remove existing block if present
        if [ -f "$ZSHRC" ] && grep -q "$MARK_START" "$ZSHRC"; then
            awk -v start="$MARK_START" -v end="$MARK_END" '
                $0 ~ start {flag=1; next}
                $0 ~ end {flag=0; next}
                !flag {print}
            ' "$ZSHRC" > "$ZSHRC.tmp" && mv "$ZSHRC.tmp" "$ZSHRC"
        fi

        cat >> "$ZSHRC" << EOF
$MARK_START
# Automatically run Brewfile Analyzer update before 'brew bundle'
brew() {
  if [ "\$1" = "bundle" ]; then
    "$HOOK_PATH" || { echo "Brewfile Analyzer update failed" >&2; return 1; }
  fi
  command brew "\$@"
}
$MARK_END
EOF
        log_success "Configured ~/.zshrc to run analyzer update before 'brew bundle'"
        log_info "Restart your terminal or run: source ~/.zshrc"
    else
        log_info "Skipping zsh configuration. You can use the hook manually: $HOOK_PATH && brew bundle"
    fi
}

offer_ai_descriptions() {
    echo
    log_info "AI-generated descriptions"
    echo "This tool can optionally generate enhanced descriptions using local/remote AI providers."
    echo "We'll scan for available providers and you can choose one (or skip)."
    echo

    # Show provider status using the installed app's environment
    if python3 "$TARGET_DIR/scripts/gen_tools_data.py" --ai-status >/dev/null 2>&1; then
        python3 "$TARGET_DIR/scripts/gen_tools_data.py" --ai-status
    else
        log_info "AI status check unavailable (optional module). You can still proceed without AI."
    fi

    echo
    read -p "Enable AI-enhanced descriptions during initial generation? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Choose provider: [auto/ollama/claude/gemini/openai] (default: auto)"
        read -r -p "> " CHOSEN
        CHOSEN=${CHOSEN:-auto}
        case "$CHOSEN" in
            auto|ollama|claude|gemini|openai)
                AI_ARGS="--ai --ai-provider $CHOSEN"
                # If a cloud provider was explicitly chosen but no API key is present, prompt for it
                if [[ "$CHOSEN" == "claude" || "$CHOSEN" == "gemini" || "$CHOSEN" == "openai" ]]; then
                    prompt_api_key "$CHOSEN" || true
                fi
                log_success "AI descriptions enabled ($CHOSEN)"
                ;;
            *)
                log_warning "Unknown provider '$CHOSEN'. Using auto."
                AI_ARGS="--ai --ai-provider auto"
                ;;
        esac
    else
        AI_ARGS=""
        log_info "Proceeding without AI-enhanced descriptions"
    fi
}

# Main installation process
main() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════╗"
    echo "║        Brewfile Analyzer Setup        ║"
    echo "║     One-Command Installation Tool     ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
    echo

    log_info "Starting installation process..."
    echo

    # System checks
    check_python
    check_homebrew
    check_brewfiles
    echo

    # Prepare target app first to avoid duplicate output locations
    install_web_app

    # Installation steps
    run_setup
    test_installation

    # Offer AI and then generate data into the app's docs
    offer_ai_descriptions
    generate_initial_data
    echo

    # Python dependencies
    install_requirements

    # Virtual environment (if available)
    setup_venv

    # Optional enhancements
    install_optional_deps

    # Deploy app to home directory target
    install_web_app

    # Offer brew bundle integration
    setup_brew_bundle_integration

    # Success message
    show_next_steps

    # Offer to create desktop shortcut now that app is deployed
    create_desktop_shortcut

    # Offer to remove the installer repository directory
    offer_cleanup
}

offer_cleanup() {
    echo
    read -p "Remove the original installer repository at $SCRIPT_DIR? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ "$SCRIPT_DIR" = "$TARGET_DIR" ]; then
            log_warning "Installer path and target path are the same. Skipping removal."
            return
        fi
        # Move away from SCRIPT_DIR before deletion
        cd "$HOME" || true
        rm -rf "$SCRIPT_DIR"
        log_success "Removed installer repository at: $SCRIPT_DIR"
    else
        log_info "Keeping installer repository. You can remove it later manually."
    fi
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Brewfile Analyzer Installation Script"
        echo
        echo "Usage: $0 [OPTIONS]"
        echo
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --check-only   Only run system checks, don't install"
        echo "  --no-deps      Skip optional dependency installation"
        echo "  --no-venv      Do not create a Python virtual environment"
        echo "  --no-shortcut  Do not prompt to create a desktop shortcut (macOS only)"
        echo "  --quiet        Reduce output verbosity"
        echo
        echo "This script will:"
        echo "  1. Check Python 3.7+ and Homebrew"
        echo "  2. Prepare the environment"
        echo "  3. Test the installation"
        echo "  4. Generate initial data (if Brewfiles present)"
        echo "  5. Install the web app to ~/brewfile/web_app"
        echo "  6. Create a Python venv unless --no-venv is specified"
        echo "  7. Offer optional enhancements and brew bundle integration"
        echo
        exit 0
        ;;
    --check-only)
        echo "System Check Mode"
        echo "=================="
        check_python
        check_homebrew
        check_brewfiles
        log_success "System check completed"
        exit 0
        ;;
    --no-deps)
        # Skip optional deps by setting a flag
        SKIP_DEPS=true
        ;;
    --no-venv)
        # Skip virtual environment creation
        SKIP_VENV=true
        ;;
    --no-shortcut)
        # Skip desktop shortcut prompt
        SKIP_SHORTCUT=true
        ;;
    --quiet)
        # Redirect some output for quieter installation
        exec 3>&1 4>&2 1>/dev/null 2>&1
        ;;
esac

# Run main installation
main "$@"

# Restore output if quiet mode was used
if [[ "${1:-}" == "--quiet" ]]; then
    exec 1>&3 2>&4
    log_success "Installation completed (quiet mode)"
fi

exit 0
