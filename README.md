# Brewfile Analyzer

Beautiful, editable documentation for your Homebrew setup — powered by a fast DuckDB backend and a simple local web UI.

[Download latest (.zip)](https://github.com/nwhistler/brewfile-analyzer/archive/refs/heads/main.zip) • [Raw installer script](https://raw.githubusercontent.com/nwhistler/brewfile-analyzer/main/install.sh)

## ✨ Features
- 🔍 Smart parsing of Brewfile (single or split) with optional brew info enrichment
- ✏️ Live editing in the browser (description + example)
- 💾 Edits persist in DuckDB and survive regeneration
- 🔎 API-first search: name, description, example, and type filters (brew/cask/mas/tap)
- 🕘 “Recent edits” view and counts by type
- 🧱 Zero external services required; optional AI providers supported

## 🚀 Quick Start (2 minutes)

One-liner (no clone needed):
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/nwhistler/brewfile-analyzer/main/install.sh)"
```

Or run the installer from a local clone:
```bash
# 1) Run the one-command installer
./install.sh

# 2) Generate data into the deployed app (DB-first)
BREWFILE_PROJECT_ROOT=~/brewfile \
BREWFILE_OUTPUT_ROOT=~/brewfile/web_app \
python3 scripts/gen_tools_data.py

# 3) Start the combined server (UI + API)
python3 scripts/serve_combined.py
# Open: http://127.0.0.1:8000/docs/tools/
```

Requirements
- macOS
- Python 3.7+ (Python 3.11/3.12 recommended)
- Homebrew (optional, for brew info enrichment)
- Python package: duckdb (offered during install as an optional dependency)

## 📂 Brewfile Formats
Place your Brewfiles under BREWFILE_PROJECT_ROOT (default: ~/brewfile):

Single Brewfile
```ruby
# Brewfile
tap "homebrew/bundle"
brew "git"
brew "node"
cask "visual-studio-code"
mas "Xcode", id: 497799835
```

Split Brewfiles
- Brewfile.Brew — CLI tools
- Brewfile.Cask — desktop apps
- Brewfile.Mas — Mac App Store apps
- Brewfile.Tap — taps

## 🖥️ Live Editing
- Click a tool card → click “Edit” → change text → click outside to save
- Saved changes are written to DuckDB; the web UI reflects live API data

## 🌐 API Overview
Base URL: http://127.0.0.1:8000

- GET /api/health
  - Server info and DB mode/path
- GET /api/tools
  - List all tools
- GET /api/tools/<name>
  - Fetch a single tool by name
- PATCH /api/tools/<name>
  - Update description/example
  - JSON body: {"description": "...", "example": "..."}
- GET /api/tools/search?q=term[&type=brew|cask|mas|tap][&limit=200]
  - Server-side, case-insensitive search across name/description/example
- GET /api/tools/types
  - Counts by type
- GET /api/tools/recent?limit=50
  - Recently edited tools
- GET /api/query?sql=SELECT ...
  - Read-only SELECT queries for advanced usage (Raycast integrations, etc.)

Examples
```bash
# Search
curl 'http://127.0.0.1:8000/api/tools/search?q=password&type=cask&limit=20'

# Edit one tool
curl -X PATCH 'http://127.0.0.1:8000/api/tools/1password' \
  -H 'Content-Type: application/json' \
  -d '{"description":"Password manager with strong vaults","example":"Open from Applications"}'
```

## 🔧 Configuration
Environment variables (optional):
- BREWFILE_PROJECT_ROOT — directory holding your Brewfile(s) (default set by installer)
- BREWFILE_OUTPUT_ROOT — directory where the web app lives (defaults to app root)
- BREWFILE_INCLUDE_LOCAL — include repo-local Brewfiles when running in the repo (true/false)

AI (optional):
- Providers: ollama, claude (Anthropic), gemini, openai
- The generator can auto-detect available providers and prompt for missing keys

## 🧱 Architecture
- DuckDB is the source of truth (no CSV/JSON snapshots required)
- The generator parses Brewfiles and upserts into DuckDB, preserving user edits
- The server reads/writes to DuckDB; the web UI fetches via API

Project Structure
```
brewfile-analyzer/
├── install.sh                 # One-command setup
├── config.py                  # Smart configuration (output defaults to app root)
├── scripts/
│   ├── gen_tools_data.py      # Parses Brewfiles, writes into DuckDB
│   ├── serve_combined.py      # UI + REST API (DuckDB-backed)
│   ├── serve_static.py        # Static-only server (rarely needed)
│   ├── update_brewfile_data.py# Optional watcher/integration
│   ├── db.py                  # DuckDB persistence layer
│   └── ai_descriptions.py     # Optional AI enrichment
├── docs/tools/                # Web UI (static)
│   └── index.html             # Fetches from /api endpoints
├── examples/                  # Example Brewfiles
├── CHANGELOG.md               # Changes
└── LICENSE                    # MIT
```

## ❓ Troubleshooting
- 404 for /docs/tools/index.html
  - Ensure BREWFILE_OUTPUT_ROOT points at the deployed app (~/brewfile/web_app) or leave unset (defaults to app root). The server prefers the app root.
- PATCH returns 501
  - Make sure you’re running the combined server (scripts/serve_combined.py), not the static server.
- Search/types previously 404
  - Fixed via route ordering. Ensure you’re on the latest server script.

## 📜 License
MIT

