# Contributing to Brewfile Analyzer

Thanks for contributing! This guide explains how to develop, test, and maintain the project. Everything uses the Python standard library unless noted.

## Dev Setup
```bash
# Optional: use a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Optional dependencies
pip install duckdb orjson click rich
```

## Common Commands
```bash
# Generate/update data (writes into DuckDB)
BREWFILE_PROJECT_ROOT=~/brewfile \
BREWFILE_OUTPUT_ROOT=~/brewfile/web_app \
python3 scripts/gen_tools_data.py

# Start combined server (UI + API)
python3 scripts/serve_combined.py
# Open: http://127.0.0.1:8000/docs/tools/

# Static-only server (rarely needed)
python3 scripts/serve_static.py

# Health check
curl http://127.0.0.1:8000/api/health | jq

# Search
curl 'http://127.0.0.1:8000/api/tools/search?q=git&type=brew'

# Update one tool
curl -X PATCH 'http://127.0.0.1:8000/api/tools/git' \
  -H 'Content-Type: application/json' \
  -d '{"description":"VCS","example":"git status"}'
```

## Architecture Overview
- scripts/gen_tools_data.py
  - Parses Brewfiles, enriches descriptions, stores tools in DuckDB.
  - AI providers optional (ollama/claude/gemini/openai). Prompts for API key if missing.
- scripts/serve_combined.py
  - Serves static UI and a REST API.
  - Reads/writes tools from DuckDB. Supports search, types, recent, and read-only SQL (/api/query).
- scripts/db.py
  - Thin DuckDB layer (ensure schema, upsert preserving user edits, list/export).
- config.py
  - Auto-detects project and defaults output_root to the app root. BREWFILE_OUTPUT_ROOT can override.
- docs/tools/index.html
  - Fetches data from API (no JSON snapshots required) and performs live edits via PATCH.

## Coding Style
- Prefer standard library.
- Keep new endpoints simple, documented, and read-only unless there is a strong reason.
- Preserve user edits during regeneration.

## Testing
- Manual tests via curl, browser, and small datasets in examples/.
- Optional: add Python unit tests (unittest or pytest) for new modules.

## Releasing
- Update CHANGELOG.md
- Bump VERSION

## Notes
- Avoid writing tools.json/tools.csv in DuckDB mode. The UI is API-only.
- If you add new env variables or endpoints, reflect them in README and this file.

