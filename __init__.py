"""
Brewfile Analyzer - A portable tool for analyzing Homebrew Brewfiles

This package provides tools to analyze and document Homebrew Brewfiles
with web-based visualization and automated update capabilities.

Main modules:
- config: Configuration management and Brewfile detection
- scripts.gen_tools_data: Main data generator
- scripts.serve_static: Web server for viewing results
- scripts.update_brewfile_data: Periodic update system

Usage:
    from brewfile_analyzer.config import get_config
    from brewfile_analyzer.scripts.gen_tools_data import main as generate_data

    # Get configuration
    config = get_config()

    # Generate data
    generate_data()
"""

__version__ = "1.0.0"
__author__ = "Brewfile Analyzer Team"
__email__ = ""
__description__ = "Analyze and document Homebrew Brewfiles with web interface"

# Package metadata
__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__description__",
]

# Import main functions for convenience
try:
    from .config import get_config, BrewfileConfig
    __all__.extend(["get_config", "BrewfileConfig"])
    # Make imports available at package level
    globals()['get_config'] = get_config
    globals()['BrewfileConfig'] = BrewfileConfig
except ImportError:
    # Handle cases where the package structure might be different
    pass
