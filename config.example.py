#!/usr/bin/env python3
"""
Example Configuration File for Brewfile Analyzer
Advanced configuration options and customization examples

This file demonstrates advanced configuration options for users who need
custom setups or want to override default behavior.

To use this file:
1. Copy to config.local.py or config_custom.py
2. Modify the settings as needed
3. Import in your scripts: from config_custom import get_custom_config

Note: The main config.py uses automatic detection and should work for
most users without modification.
"""
from pathlib import Path
from typing import Dict, Optional, List
import os


class CustomBrewfileConfig:
    """
    Advanced configuration class with custom options

    This extends the basic configuration with additional features:
    - Custom file locations
    - Multiple project support
    - Advanced filtering options
    - Custom description sources
    """

    def __init__(self,
                 project_name: str = "default",
                 custom_root: Optional[str] = None,
                 custom_brewfiles: Optional[Dict[str, str]] = None,
                 output_formats: Optional[List[str]] = None):
        """
        Initialize custom configuration

        Args:
            project_name: Name for this project configuration
            custom_root: Custom project root (overrides auto-detection)
            custom_brewfiles: Custom Brewfile locations
            output_formats: List of output formats to generate
        """
        self.project_name = project_name

        # Project root detection
        if custom_root:
            self.root = Path(custom_root).resolve()
        else:
            # Auto-detect from current script location
            self.root = Path(__file__).parent.resolve()

        # Custom directories
        self.scripts_dir = self.root / 'scripts'
        self.config_dir = self.root / '.brewfile_config'
        self.cache_dir = self.root / '.cache' / 'brewfile'
        self.logs_dir = self.root / 'logs'

        # Output configuration
        self.output_formats = output_formats or ['json', 'csv', 'html']
        self.output_dir = self.root / 'docs' / 'tools'

        # Custom output files
        self.json_file = self.output_dir / f'tools_{project_name}.json'
        self.csv_file = self.output_dir / f'tools_{project_name}.csv'
        self.html_file = self.output_dir / f'index_{project_name}.html'

        # Create directories
        for directory in [self.config_dir, self.cache_dir, self.logs_dir, self.output_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # Brewfile configuration
        if custom_brewfiles:
            self.brewfiles = {k: Path(v) for k, v in custom_brewfiles.items()}
        else:
            self._detect_brewfiles()

        # Advanced options
        self.enable_caching = True
        self.cache_duration_hours = 24
        self.parallel_processing = True
        self.max_workers = 4
        self.enable_logging = True
        self.log_level = 'INFO'

        # Package filtering
        self.include_patterns = []  # Regex patterns to include
        self.exclude_patterns = []  # Regex patterns to exclude
        self.package_types = ['brew', 'cask', 'mas', 'tap']  # Types to process

        # Description sources (in priority order)
        self.description_sources = [
            'brew_info',          # Official brew info command
            'homebrew_api',       # Homebrew API (if available)
            'custom_descriptions', # Custom description file
            'enhanced_fallbacks', # Enhanced fallback descriptions
            'basic_fallbacks'     # Basic fallbacks
        ]

        # Custom descriptions file
        self.custom_descriptions_file = self.config_dir / 'custom_descriptions.json'

        # Web server configuration
        self.server_host = '127.0.0.1'
        self.server_port = 8000
        self.server_debug = False
        self.enable_cors = False

        # Update system configuration
        self.auto_update = True
        self.update_interval_minutes = 60
        self.backup_before_update = True
        self.max_backups = 5

    def _detect_brewfiles(self):
        """Advanced Brewfile detection with custom patterns"""
        self.brewfiles = {}

        # Standard patterns
        patterns = {
            'brew': ['Brewfile.Brew', 'Brewfile.brew', 'brewfile.brew'],
            'cask': ['Brewfile.Cask', 'Brewfile.cask', 'brewfile.cask'],
            'mas': ['Brewfile.Mas', 'Brewfile.mas', 'brewfile.mas'],
            'tap': ['Brewfile.Tap', 'Brewfile.tap', 'brewfile.tap']
        }

        # Check for split files
        found_split = False
        for item_type, filenames in patterns.items():
            for filename in filenames:
                file_path = self.root / filename
                if file_path.exists():
                    self.brewfiles[item_type] = file_path
                    found_split = True
                    break

        # Check for single Brewfile if no split files found
        if not found_split:
            single_brewfile_names = ['Brewfile', 'brewfile', 'Brewfile.rb']
            for filename in single_brewfile_names:
                file_path = self.root / filename
                if file_path.exists():
                    # Use same file for all types
                    for item_type in ['brew', 'cask', 'mas', 'tap']:
                        self.brewfiles[item_type] = file_path
                    break

        # Custom Brewfile locations (environment variables)
        env_brewfiles = {
            'brew': os.getenv('BREWFILE_BREW_PATH'),
            'cask': os.getenv('BREWFILE_CASK_PATH'),
            'mas': os.getenv('BREWFILE_MAS_PATH'),
            'tap': os.getenv('BREWFILE_TAP_PATH')
        }

        for item_type, env_path in env_brewfiles.items():
            if env_path and Path(env_path).exists():
                self.brewfiles[item_type] = Path(env_path)

    def get_cache_file(self, cache_key: str) -> Path:
        """Get cache file path for a given key"""
        return self.cache_dir / f"{cache_key}.json"

    def get_log_file(self, log_type: str = 'main') -> Path:
        """Get log file path"""
        return self.logs_dir / f"brewfile_{log_type}.log"

    def load_custom_descriptions(self) -> Dict[str, Dict[str, str]]:
        """Load custom descriptions from JSON file"""
        if not self.custom_descriptions_file.exists():
            return {}

        try:
            import json
            with open(self.custom_descriptions_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def save_custom_descriptions(self, descriptions: Dict[str, Dict[str, str]]):
        """Save custom descriptions to JSON file"""
        try:
            import json
            with open(self.custom_descriptions_file, 'w') as f:
                json.dump(descriptions, f, indent=2)
        except Exception:
            pass

    def is_package_included(self, package_name: str, package_type: str) -> bool:
        """Check if package should be included based on filters"""
        import re

        # Check package type filter
        if package_type not in self.package_types:
            return False

        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if re.search(pattern, package_name, re.IGNORECASE):
                return False

        # Check include patterns (if any)
        if self.include_patterns:
            for pattern in self.include_patterns:
                if re.search(pattern, package_name, re.IGNORECASE):
                    return True
            return False  # No include patterns matched

        return True  # Include by default

    def get_config_dict(self) -> Dict:
        """Get configuration as dictionary for serialization"""
        return {
            'project_name': self.project_name,
            'root': str(self.root),
            'output_formats': self.output_formats,
            'package_types': self.package_types,
            'description_sources': self.description_sources,
            'server_host': self.server_host,
            'server_port': self.server_port,
            'auto_update': self.auto_update,
            'update_interval_minutes': self.update_interval_minutes,
            'enable_caching': self.enable_caching,
            'cache_duration_hours': self.cache_duration_hours,
            'brewfiles': {k: str(v) for k, v in self.brewfiles.items()},
            'has_brewfiles': len(self.brewfiles) > 0
        }

    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []

        # Check if root directory exists
        if not self.root.exists():
            issues.append(f"Project root does not exist: {self.root}")

        # Check if Brewfiles exist
        if not self.brewfiles:
            issues.append("No Brewfiles found")
        else:
            for item_type, file_path in self.brewfiles.items():
                if not file_path.exists():
                    issues.append(f"{item_type} Brewfile does not exist: {file_path}")

        # Check output directory is writable
        try:
            test_file = self.output_dir / '.test_write'
            test_file.write_text('test')
            test_file.unlink()
        except Exception:
            issues.append(f"Output directory not writable: {self.output_dir}")

        return issues


# Example configurations for different use cases

def get_development_config() -> CustomBrewfileConfig:
    """Configuration for development environment"""
    config = CustomBrewfileConfig(project_name="dev")
    config.enable_logging = True
    config.log_level = 'DEBUG'
    config.server_debug = True
    config.auto_update = True
    config.update_interval_minutes = 5  # Frequent updates for development
    return config


def get_production_config() -> CustomBrewfileConfig:
    """Configuration for production environment"""
    config = CustomBrewfileConfig(project_name="prod")
    config.enable_logging = True
    config.log_level = 'INFO'
    config.server_debug = False
    config.auto_update = False  # Manual updates in production
    config.backup_before_update = True
    return config


def get_minimal_config() -> CustomBrewfileConfig:
    """Minimal configuration with basic features only"""
    config = CustomBrewfileConfig(project_name="minimal")
    config.output_formats = ['json']  # Only JSON output
    config.enable_caching = False
    config.enable_logging = False
    config.description_sources = ['basic_fallbacks']  # Skip brew info calls
    return config


def get_multi_project_config(projects: List[str]) -> Dict[str, CustomBrewfileConfig]:
    """Configuration for managing multiple projects"""
    configs = {}
    for project in projects:
        config = CustomBrewfileConfig(project_name=project)
        config.custom_root = f"/path/to/{project}"
        configs[project] = config
    return configs


# Custom description examples
CUSTOM_DESCRIPTIONS = {
    "brew": {
        "my-custom-tool": "My custom description for this tool",
        "company-cli": "Internal company command-line tool"
    },
    "cask": {
        "my-app": "Custom application description",
        "company-software": "Internal company software"
    }
}

# Example usage patterns
def example_custom_setup():
    """Example of how to use custom configuration"""

    # Create custom config
    config = CustomBrewfileConfig(project_name="my_project")

    # Customize settings
    config.package_types = ['brew', 'cask']  # Only brew and cask
    config.exclude_patterns = [r'^test-', r'deprecated']  # Exclude test/deprecated packages
    config.include_patterns = [r'^my-company-']  # Include only company packages

    # Custom Brewfile locations
    config.brewfiles = {
        'brew': Path('/path/to/custom/Brewfile.brew'),
        'cask': Path('/path/to/custom/Brewfile.cask')
    }

    # Load and save custom descriptions
    custom_desc = config.load_custom_descriptions()
    custom_desc.update(CUSTOM_DESCRIPTIONS)
    config.save_custom_descriptions(custom_desc)

    # Validate configuration
    issues = config.validate_config()
    if issues:
        print("Configuration issues:", issues)

    return config


# Environment-based configuration
def get_config_from_env() -> CustomBrewfileConfig:
    """Load configuration from environment variables"""
    config = CustomBrewfileConfig()

    # Override with environment variables
    config.server_port = int(os.getenv('BREWFILE_SERVER_PORT', '8000'))
    config.enable_caching = os.getenv('BREWFILE_ENABLE_CACHING', 'true').lower() == 'true'
    config.log_level = os.getenv('BREWFILE_LOG_LEVEL', 'INFO')

    # Custom root from environment
    if os.getenv('BREWFILE_PROJECT_ROOT'):
        config.root = Path(os.getenv('BREWFILE_PROJECT_ROOT'))

    return config


# Main function for testing configuration
if __name__ == '__main__':
    # Test different configurations
    configs = {
        'default': CustomBrewfileConfig(),
        'development': get_development_config(),
        'production': get_production_config(),
        'minimal': get_minimal_config(),
        'env_based': get_config_from_env()
    }

    for name, config in configs.items():
        print(f"\n{name.upper()} Configuration:")
        print("=" * 50)

        config_dict = config.get_config_dict()
        for key, value in config_dict.items():
            print(f"  {key}: {value}")

        issues = config.validate_config()
        if issues:
            print(f"  Issues: {issues}")
        else:
            print("  Status: ✅ Valid")
