#!/usr/bin/env python3
"""
AI Description Generation for Brewfile Analyzer
Supports multiple AI providers: Ollama, Claude, Gemini, OpenAI
"""

import json
import subprocess
import sys
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class AIDescriptionGenerator:
    """Main class for generating AI descriptions of tools"""

    def __init__(self, provider: str = "auto", config: Optional[Dict] = None):
        """
        Initialize AI description generator

        Args:
            provider: AI provider ('ollama', 'claude', 'gemini', 'openai', 'auto')
            config: Configuration dictionary with provider settings
        """
        self.provider = provider
        self.config = config or {}
        self.available_providers = []
        self._detect_available_providers()

        if provider == "auto":
            self.provider = self._select_best_provider()

    def _detect_available_providers(self):
        """Detect which AI providers are available"""
        # Check Ollama
        if self._check_ollama():
            self.available_providers.append("ollama")

        # Check Claude CLI
        if self._check_claude_cli():
            self.available_providers.append("claude")

        # Check Gemini CLI
        if self._check_gemini_cli():
            self.available_providers.append("gemini")

        # Check OpenAI (via environment variables)
        if self._check_openai():
            self.available_providers.append("openai")

    def _check_ollama(self) -> bool:
        """Check if Ollama is available"""
        try:
            # Try to connect to Ollama API
            ollama_url = self.config.get("ollama_url", "http://localhost:11434")

            # Check if Ollama service is running
            health_url = f"{ollama_url}/api/tags"
            req = urllib.request.Request(health_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    return True
        except:
            pass

        # Also check for ollama command
        try:
            result = subprocess.run(["ollama", "list"],
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    def _check_claude_cli(self) -> bool:
        """Check if Claude CLI is available"""
        try:
            # Check for claude command
            result = subprocess.run(["claude", "--version"],
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            # Check for environment variables
            return bool(os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

    def _check_gemini_cli(self) -> bool:
        """Check if Gemini CLI is available"""
        try:
            # Check for gemini command
            result = subprocess.run(["gemini", "--version"],
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            # Check for environment variables
            return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    def _check_openai(self) -> bool:
        """Check if OpenAI is available"""
        return bool(os.getenv("OPENAI_API_KEY"))

    def _select_best_provider(self) -> str:
        """Select the best available provider"""
        if not self.available_providers:
            return "fallback"

        # Priority order: Ollama (local) > Claude > Gemini > OpenAI
        priority = ["ollama", "claude", "gemini", "openai"]
        for provider in priority:
            if provider in self.available_providers:
                return provider

        return "fallback"

    def generate_description(self, tool_name: str, tool_type: str,
                           existing_description: str = "") -> Tuple[str, str]:
        """
        Generate AI description for a tool

        Args:
            tool_name: Name of the tool
            tool_type: Type of tool (brew, cask, mas, tap)
            existing_description: Current description if any

        Returns:
            Tuple of (description, example_usage)
        """
        if self.provider == "ollama":
            return self._generate_ollama(tool_name, tool_type, existing_description)
        elif self.provider == "claude":
            return self._generate_claude(tool_name, tool_type, existing_description)
        elif self.provider == "gemini":
            return self._generate_gemini(tool_name, tool_type, existing_description)
        elif self.provider == "openai":
            return self._generate_openai(tool_name, tool_type, existing_description)
        else:
            # Fallback to enhanced static descriptions
            return self._generate_fallback(tool_name, tool_type, existing_description)

    def _create_prompt(self, tool_name: str, tool_type: str, existing_description: str = "") -> str:
        """Create prompt for AI description generation"""
        type_context = {
            "brew": "command-line tool installable via Homebrew",
            "cask": "macOS desktop application installable via Homebrew Cask",
            "mas": "Mac App Store application",
            "tap": "Homebrew tap (additional package repository)"
        }

        context = type_context.get(tool_type, "software tool")

        prompt = f"""You are helping document Homebrew packages for developers.

Tool: {tool_name}
Type: {context}
Current description: {existing_description or "None"}

Please provide:
1. A concise, helpful description (1-2 sentences) that explains what this tool does
2. A practical usage example command

Requirements:
- Be specific and practical
- Focus on what developers actually use this tool for
- Keep descriptions under 100 words
- For command-line tools, provide realistic command examples
- For applications, mention key use cases
- If it's a development tool, mention the programming languages or frameworks it supports

Format your response as JSON:
{{
  "description": "Your description here",
  "example": "Your example command or usage here"
}}

Only respond with valid JSON, no additional text."""

        return prompt

    def _generate_ollama(self, tool_name: str, tool_type: str, existing_description: str) -> Tuple[str, str]:
        """Generate description using Ollama"""
        try:
            ollama_url = self.config.get("ollama_url", "http://localhost:11434")
            model = self.config.get("ollama_model", "llama2")

            prompt = self._create_prompt(tool_name, tool_type, existing_description)

            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            }

            req = urllib.request.Request(
                f"{ollama_url}/api/generate",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                ai_response = result.get("response", "")

                # Try to parse JSON from response
                try:
                    parsed = json.loads(ai_response)
                    return parsed.get("description", ""), parsed.get("example", "")
                except json.JSONDecodeError:
                    # If JSON parsing fails, extract manually
                    return self._extract_from_text(ai_response, tool_name, tool_type)

        except Exception as e:
            print(f"Ollama generation failed for {tool_name}: {e}")
            return self._generate_fallback(tool_name, tool_type, existing_description)

    def _generate_claude(self, tool_name: str, tool_type: str, existing_description: str) -> Tuple[str, str]:
        """Generate description using Claude CLI or API"""
        try:
            prompt = self._create_prompt(tool_name, tool_type, existing_description)

            # Try Claude CLI first
            try:
                result = subprocess.run([
                    "claude", "chat", "--message", prompt
                ], capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    ai_response = result.stdout.strip()
                else:
                    raise Exception("Claude CLI failed")
            except:
                # Fallback to direct API call if available
                api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise Exception("No Claude API key available")

                ai_response = self._call_claude_api(prompt, api_key)

            # Parse JSON response
            try:
                parsed = json.loads(ai_response)
                return parsed.get("description", ""), parsed.get("example", "")
            except json.JSONDecodeError:
                return self._extract_from_text(ai_response, tool_name, tool_type)

        except Exception as e:
            print(f"Claude generation failed for {tool_name}: {e}")
            return self._generate_fallback(tool_name, tool_type, existing_description)

    def _generate_gemini(self, tool_name: str, tool_type: str, existing_description: str) -> Tuple[str, str]:
        """Generate description using Gemini CLI or API"""
        try:
            prompt = self._create_prompt(tool_name, tool_type, existing_description)

            # Try Gemini CLI first
            try:
                result = subprocess.run([
                    "gemini", "generate", "--prompt", prompt
                ], capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    ai_response = result.stdout.strip()
                else:
                    raise Exception("Gemini CLI failed")
            except:
                # Fallback to direct API call if available
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    raise Exception("No Gemini API key available")

                ai_response = self._call_gemini_api(prompt, api_key)

            # Parse JSON response
            try:
                parsed = json.loads(ai_response)
                return parsed.get("description", ""), parsed.get("example", "")
            except json.JSONDecodeError:
                return self._extract_from_text(ai_response, tool_name, tool_type)

        except Exception as e:
            print(f"Gemini generation failed for {tool_name}: {e}")
            return self._generate_fallback(tool_name, tool_type, existing_description)

    def _generate_openai(self, tool_name: str, tool_type: str, existing_description: str) -> Tuple[str, str]:
        """Generate description using OpenAI API"""
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise Exception("No OpenAI API key available")

            prompt = self._create_prompt(tool_name, tool_type, existing_description)

            payload = {
                "model": self.config.get("openai_model", "gpt-3.5-turbo"),
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 200
            }

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                }
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                ai_response = result["choices"][0]["message"]["content"]

                # Parse JSON response
                try:
                    parsed = json.loads(ai_response)
                    return parsed.get("description", ""), parsed.get("example", "")
                except json.JSONDecodeError:
                    return self._extract_from_text(ai_response, tool_name, tool_type)

        except Exception as e:
            print(f"OpenAI generation failed for {tool_name}: {e}")
            return self._generate_fallback(tool_name, tool_type, existing_description)

    def _call_claude_api(self, prompt: str, api_key: str) -> str:
        """Direct API call to Claude"""
        payload = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 200,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': api_key,
                'anthropic-version': '2023-06-01'
            }
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result["content"][0]["text"]

    def _call_gemini_api(self, prompt: str, api_key: str) -> str:
        """Direct API call to Gemini"""
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 200
            }
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result["candidates"][0]["content"]["parts"][0]["text"]

    def _extract_from_text(self, text: str, tool_name: str, tool_type: str) -> Tuple[str, str]:
        """Extract description and example from free-form text"""
        lines = text.strip().split('\n')
        description = ""
        example = ""

        # Try to find description and example in the text
        for line in lines:
            line = line.strip()
            if line and not description:
                # First substantial line becomes description
                if len(line) > 10 and not line.startswith(('#', '//', '--')):
                    description = line
            elif tool_type == 'brew' and (
                line.startswith(tool_name) or
                any(cmd in line for cmd in ['$', '>', tool_name])
            ):
                example = line.lstrip('$> ')
                break

        # Fallback if extraction failed
        if not description:
            description = self._generate_fallback(tool_name, tool_type, "")[0]
        if not example:
            example = self._generate_fallback(tool_name, tool_type, "")[1]

        return description, example

    def _generate_fallback(self, tool_name: str, tool_type: str, existing_description: str) -> Tuple[str, str]:
        """Fallback to enhanced static descriptions"""
        # Enhanced fallback descriptions
        fallbacks = {
            'brew': {
                'git': ('Distributed version control system for tracking changes', 'git status'),
                'node': ('JavaScript runtime built on Chrome V8 engine', 'node --version'),
                'python': ('Interpreted programming language', 'python3 --version'),
                'docker': ('Platform for developing and running containerized applications', 'docker --version'),
                'kubectl': ('Command-line tool for controlling Kubernetes clusters', 'kubectl get pods'),
                'terraform': ('Infrastructure as code tool for building and managing resources', 'terraform --version'),
                'jq': ('Lightweight command-line JSON processor', 'jq \'.name\' package.json'),
                'curl': ('Command-line tool for transferring data with URLs', 'curl -I https://example.com'),
                'wget': ('Command-line utility for downloading files from web', 'wget https://example.com/file.zip'),
                'htop': ('Interactive process viewer and system monitor', 'htop'),
                'tree': ('Recursive directory listing command', 'tree -L 2'),
                'ripgrep': ('Fast text search tool that recursively searches directories', 'rg "pattern" src/'),
                'fd': ('Simple and fast alternative to find command', 'fd "*.py" src/'),
                'bat': ('Syntax-highlighted cat command with Git integration', 'bat README.md'),
                'eza': ('Modern ls replacement with colors and Git status', 'eza -la'),
                'fzf': ('Command-line fuzzy finder for interactive selections', 'find . | fzf'),
                'tmux': ('Terminal multiplexer for managing multiple sessions', 'tmux new -s work'),
                'neovim': ('Modern Vim-based text editor with extensibility', 'nvim file.txt'),
                'awscli': ('Official Amazon Web Services command-line interface', 'aws s3 ls'),
                'gh': ('GitHub command-line tool for repository management', 'gh repo list'),
            },
            'cask': {
                'visual-studio-code': ('Lightweight but powerful source code editor', 'Open from Applications'),
                'google-chrome': ('Fast and secure web browser from Google', 'Open from Applications'),
                'firefox': ('Open-source web browser focused on privacy', 'Open from Applications'),
                'docker': ('Desktop application for container development', 'Open from Applications'),
                'slack': ('Team collaboration and messaging platform', 'Open from Applications'),
                'zoom': ('Video conferencing and online meeting platform', 'Open from Applications'),
                'spotify': ('Music streaming service and player', 'Open from Applications'),
                '1password': ('Password manager for storing secure credentials', 'Open from Applications'),
                'alfred': ('Productivity app for macOS with hotkeys and workflows', 'Cmd+Space to open'),
                'raycast': ('Extensible launcher with powerful commands', 'Cmd+Space to open'),
                'iterm2': ('Terminal emulator replacement for macOS', 'Open from Applications'),
                'notion': ('All-in-one workspace for notes and project management', 'Open from Applications'),
                'figma': ('Collaborative interface design and prototyping tool', 'Open from Applications'),
                'postman': ('API development and testing platform', 'Open from Applications'),
            },
            'mas': {
                'Xcode': ('Apple\'s integrated development environment for iOS/macOS', 'mas install 497799835'),
                'Keynote': ('Apple\'s presentation software', 'mas install 409183694'),
                'Numbers': ('Apple\'s spreadsheet application', 'mas install 409203825'),
                'Pages': ('Apple\'s word processing software', 'mas install 409201541'),
            },
            'tap': {
                'homebrew/bundle': ('Homebrew tap for managing dependencies with Brewfiles', 'brew tap homebrew/bundle'),
                'homebrew/services': ('Homebrew tap for managing background services', 'brew tap homebrew/services'),
                'homebrew/cask-fonts': ('Homebrew tap for installing fonts via Cask', 'brew tap homebrew/cask-fonts'),
            }
        }

        # Get specific fallback or generate generic one
        type_fallbacks = fallbacks.get(tool_type, {})
        if tool_name in type_fallbacks:
            return type_fallbacks[tool_name]

        # Generate generic fallback
        if tool_type == 'brew':
            description = f"Command-line tool: {tool_name.replace('-', ' ').replace('_', ' ')}"
            example = f"{tool_name} --help"
        elif tool_type == 'cask':
            description = f"macOS application: {tool_name.replace('-', ' ').replace('_', ' ')}"
            example = "Open from Applications folder"
        elif tool_type == 'mas':
            description = f"Mac App Store application: {tool_name}"
            example = f"Install {tool_name} from Mac App Store"
        elif tool_type == 'tap':
            description = f"Homebrew tap providing additional packages: {tool_name}"
            example = f"brew tap {tool_name}"
        else:
            description = existing_description or f"{tool_type.title()}: {tool_name}"
            example = f"{tool_name} --help"

        return description, example

    def batch_generate(self, tools: List[Dict], max_concurrent: int = 5) -> List[Dict]:
        """
        Generate descriptions for multiple tools with rate limiting

        Args:
            tools: List of tool dictionaries with 'name' and 'type' keys
            max_concurrent: Maximum concurrent requests (for API providers)

        Returns:
            List of tools with added 'ai_description' and 'ai_example' keys
        """
        print(f"🤖 Generating AI descriptions using {self.provider}")

        enhanced_tools = []
        for i, tool in enumerate(tools):
            print(f"Processing {i+1}/{len(tools)}: {tool['name']}")

            try:
                description, example = self.generate_description(
                    tool['name'],
                    tool['type'],
                    tool.get('description', '')
                )

                enhanced_tool = tool.copy()
                enhanced_tool['ai_description'] = description
                enhanced_tool['ai_example'] = example
                enhanced_tools.append(enhanced_tool)

                # Rate limiting for API providers
                if self.provider in ['openai', 'claude', 'gemini'] and i < len(tools) - 1:
                    time.sleep(1)  # 1 second delay between API calls

            except Exception as e:
                print(f"Error processing {tool['name']}: {e}")
                enhanced_tools.append(tool)  # Add original tool without AI enhancement

        return enhanced_tools

    def get_status(self) -> Dict:
        """Get status information about AI providers"""
        return {
            "selected_provider": self.provider,
            "available_providers": self.available_providers,
            "config": {k: v for k, v in self.config.items() if 'key' not in k.lower()},
            "provider_status": {
                "ollama": self._check_ollama(),
                "claude": self._check_claude_cli(),
                "gemini": self._check_gemini_cli(),
                "openai": self._check_openai()
            }
        }


def load_ai_config() -> Dict:
    """Load AI configuration from environment variables and config files"""
    config = {}

    # Ollama configuration
    config["ollama_url"] = os.getenv("OLLAMA_URL", "http://localhost:11434")
    config["ollama_model"] = os.getenv("OLLAMA_MODEL", "llama2")

    # OpenAI configuration
    config["openai_model"] = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    # Try to load from config file
    config_file = Path.cwd() / "ai_config.json"
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception:
            pass

    return config


def main():
    """CLI interface for AI description generation"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate AI descriptions for Homebrew tools")
    parser.add_argument("--provider", choices=["auto", "ollama", "claude", "gemini", "openai"],
                       default="auto", help="AI provider to use")
    parser.add_argument("--tool", help="Single tool to generate description for")
    parser.add_argument("--type", choices=["brew", "cask", "mas", "tap"],
                       help="Tool type (required if --tool is used)")
    parser.add_argument("--status", action="store_true", help="Show provider status")
    parser.add_argument("--config", help="Path to AI configuration file")

    args = parser.parse_args()

    # Load configuration
    config = load_ai_config()
    if args.config:
        with open(args.config, 'r') as f:
            config.update(json.load(f))

    # Create generator
    generator = AIDescriptionGenerator(provider=args.provider, config=config)

    if args.status:
        status = generator.get_status()
        print("AI Description Generator Status:")
        print("=" * 40)
        print(f"Selected Provider: {status['selected_provider']}")
        print(f"Available Providers: {', '.join(status['available_providers'])}")
        print("\nProvider Status:")
        for provider, available in status['provider_status'].items():
            status_icon = "✅" if available else "❌"
            print(f"  {status_icon} {provider}: {'Available' if available else 'Not available'}")

        if status['config']:
            print("\nConfiguration:")
            for key, value in status['config'].items():
                print(f"  {key}: {value}")
        return

    if args.tool and args.type:
        description, example = generator.generate_description(args.tool, args.type)
        print(f"Tool: {args.tool}")
        print(f"Description: {description}")
        print(f"Example: {example}")
        return

    print("Use --status to check provider availability or --tool and --type to generate single description")


if __name__ == "__main__":
    main()
