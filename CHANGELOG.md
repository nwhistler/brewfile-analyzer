# Changelog

All notable changes to Brewfile Analyzer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2025-09-11

### Added
- Silent background updates: `scripts/auto_update.sh` applies updates without prompts; first-run shows a concise, one-time prompt to enable the LaunchAgent.
- Update banner in UI: on next load after an update, a small banner appears and fades away.
- Installer options (macOS):
  - Enable automatic update checks (LaunchAgent, every 6h)
  - Optionally run the combined server in the background at login (LaunchAgent, KeepAlive)
- API: `/api/tools/recent` now accepts a `days` query parameter (default 30) to scope "Recent" to a time window.

### Changed
- New DuckDB insert behavior sets `last_edited = CURRENT_TIMESTAMP` for newly added tools, so they appear in "Recent" immediately.
- LaunchAgent labels no longer include the author handle; renamed to `com.brewfile-analyzer.updatecheck` and `com.brewfile-analyzer.server`.
- WARP.md updated with Ruff/CI rules; WARP.md added to .gitignore.

### Removed
- Developer-only `repo_update.py` (use `scripts/self_update.py` for installed app updates).

### Added
- Future enhancements will be listed here

### Changed
- Future changes will be listed here

### Fixed
- (none)

## [1.0.1] - 2025-09-08

### Fixed
- Brewfile parsing now supports single- and double-quoted entries, optional whitespace after keywords, and case-insensitive matching for brew/cask/mas/tap lines (e.g., handles lines like `cask'hovrly'`).
- Detection now includes lowercase `brewfile` (and lowercase split variants) in addition to `Brewfile`.

## [1.0.0] - 2024-01-15

### Added
- 🎉 Initial release of Brewfile Analyzer
- **Core Features**:
  - Automatic Brewfile detection (single or split format)
  - JSON and CSV data generation with package descriptions
  - Interactive web interface with secure static file serving
  - Periodic update system with file change detection
- **Scripts**:
  - `gen_tools_data.py` - Main data generator with enhanced descriptions
  - `serve_static.py` - Secure web server with path traversal protection
  - `update_brewfile_data.py` - Automated update system with brew bundle integration
  - `tools_api.py` - API utilities for data processing
- **Configuration**:
  - Smart project root detection
  - Automatic Brewfile discovery
  - Configurable output directories
- **Web Interface**:
  - Clean, responsive HTML interface
  - Real-time data visualization
  - Package search and filtering capabilities
- **Automation**:
  - File watching for automatic updates
  - Brew bundle hook integration
  - Lock file system to prevent concurrent updates
- **Documentation**:
  - Comprehensive README with usage examples
  - Inline code documentation
  - Installation and setup guides

### Security
- Path traversal protection in web server
- Symlink confinement to project root
- No directory listing for security
- Process isolation for server requests

### Developer Experience
- **Portable Design**: Uses only Python standard library
- **One-Command Setup**: `install.sh` script for easy installation
- **Git Integration**: Pre-commit hooks and workflow examples
- **Comprehensive Testing**: System checks and validation
- Single Installation Method: install.sh

### Package Management
- Standard `requirements.txt` with optional enhancements
- VERSION file for version tracking
- Optional dependencies for enhanced features

### Supported Formats
- **Brewfile Types**: brew, cask, mas, tap
- **Input Formats**: Single Brewfile or split files
- **Output Formats**: JSON, CSV, HTML
- **Integration**: GitHub Actions, shell aliases, pre-commit hooks

## [0.9.0] - Development Phase

### Added
- Initial development and testing
- Core functionality implementation
- Basic web interface
- Configuration management system

---

## Version History

- **1.0.0** - First stable release with full feature set
- **0.9.0** - Development and testing phase

## Upgrade Notes

### From Development to 1.0.0
- Project now uses install.sh and Python scripts directly; setup.py and Makefile are not required.
- Regenerate data files with `python3 scripts/gen_tools_data.py`.

## Contributing

When contributing to this project, please:
1. Update the [Unreleased] section with your changes
2. Follow the format: `### Added/Changed/Deprecated/Removed/Fixed/Security`
3. Include relevant details and breaking changes
4. Update version numbers according to semantic versioning

## Support

For issues, questions, or feature requests, please check:
1. The troubleshooting section in README.md
2. Existing issues in the project repository
3. The documentation and examples provided