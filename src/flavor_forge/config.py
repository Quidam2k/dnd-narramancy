"""Configuration management for Flavor Forge."""

import os
from pathlib import Path
from typing import Optional


class ConfigManager:
    """Simple configuration manager using env vars with optional YAML fallback."""

    def __init__(self, config_path: Optional[Path] = None):
        self._yaml_config = {}
        if config_path and config_path.exists():
            self._load_yaml(config_path)
        elif config_path is None:
            # Try default location
            default = Path("config.yaml")
            if default.exists():
                self._load_yaml(default)

    def _load_yaml(self, path: Path):
        try:
            import yaml
            with open(path) as f:
                self._yaml_config = yaml.safe_load(f) or {}
        except ImportError:
            pass  # YAML support is optional

    def get(self, section: str, key: str, fallback=None):
        """Get a config value. Checks env vars first, then YAML, then fallback.

        Env var format: FLAVOR_FORGE_{SECTION}_{KEY} (uppercased).
        """
        env_key = f"FLAVOR_FORGE_{section}_{key}".upper()
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return env_val

        # Check YAML: section.key
        if section in self._yaml_config and isinstance(self._yaml_config[section], dict):
            val = self._yaml_config[section].get(key)
            if val is not None:
                return val

        return fallback

    def validate(self) -> list[str]:
        """Check for common misconfiguration. Returns a list of warnings."""
        warnings = []

        # Check if any API keys are set
        has_gemini = bool(os.environ.get('GEMINI_API_KEY'))
        has_anthropic = bool(os.environ.get('ANTHROPIC_API_KEY'))
        has_ollama = bool(os.environ.get('OLLAMA_BASE_URL'))

        has_groq = bool(os.environ.get('GROQ_API_KEY'))
        has_openrouter = bool(os.environ.get('OPENROUTER_API_KEY'))
        has_together = bool(os.environ.get('TOGETHER_API_KEY'))

        if not any([has_gemini, has_anthropic, has_ollama, has_groq, has_openrouter, has_together]):
            warnings.append(
                "No API keys configured. Set GEMINI_API_KEY, ANTHROPIC_API_KEY, "
                "GROQ_API_KEY, OPENROUTER_API_KEY, TOGETHER_API_KEY, "
                "or OLLAMA_BASE_URL to use a provider."
            )

        # Check if config.yaml exists but failed to parse
        if not self._yaml_config:
            from pathlib import Path
            if Path("config.yaml").exists():
                try:
                    import yaml
                    with open("config.yaml") as f:
                        data = yaml.safe_load(f)
                    if data is None:
                        warnings.append("config.yaml exists but is empty.")
                except ImportError:
                    pass  # No yaml module, already handled
                except Exception as e:
                    warnings.append(f"config.yaml exists but could not be parsed: {e}")

        return warnings

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider.

        Checks: GEMINI_API_KEY, ANTHROPIC_API_KEY, OLLAMA_BASE_URL
        """
        key_map = {
            'gemini': 'GEMINI_API_KEY',
            'google': 'GEMINI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'claude': 'ANTHROPIC_API_KEY',
            'ollama': 'OLLAMA_BASE_URL',
            'lmstudio': 'LMSTUDIO_BASE_URL',
            'groq': 'GROQ_API_KEY',
            'openrouter': 'OPENROUTER_API_KEY',
            'together': 'TOGETHER_API_KEY',
        }
        env_name = key_map.get(provider.lower())
        if env_name:
            return os.environ.get(env_name)
        return None
