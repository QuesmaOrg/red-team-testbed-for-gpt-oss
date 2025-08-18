"""Settings manager for handling YAML configuration files."""

import os
from pathlib import Path
from typing import Any

import yaml


class SettingsManager:
    """Manages settings.yaml configuration file with environment variable overrides."""

    def __init__(self, settings_path: str = "settings.yaml") -> None:
        self.settings_path = Path(settings_path)
        self._settings: dict[str, Any] | None = None

    def load_settings(self) -> dict[str, Any]:
        """Load settings from YAML file with environment variable overrides."""
        if not self.settings_path.exists():
            raise FileNotFoundError(f"Settings file not found: {self.settings_path}")

        with open(self.settings_path) as f:
            settings = yaml.safe_load(f) or {}

        # Apply environment variable overrides
        settings = self._apply_env_overrides(settings)
        
        self._settings = settings
        return settings

    def save_settings(self, settings: dict[str, Any]) -> None:
        """Save settings to YAML file."""
        # Backup existing file
        if self.settings_path.exists():
            backup_path = self.settings_path.with_suffix('.yaml.bak')
            self.settings_path.rename(backup_path)

        with open(self.settings_path, 'w') as f:
            yaml.dump(settings, f, default_flow_style=False, indent=2)
        
        self._settings = settings

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value using dot notation (e.g., 'backend.provider')."""
        if self._settings is None:
            self.load_settings()
        
        keys = key.split('.')
        value = self._settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a setting value using dot notation and save to file."""
        if self._settings is None:
            self.load_settings()
        
        keys = key.split('.')
        settings_ref = self._settings
        
        # Navigate to the parent of the final key
        for k in keys[:-1]:
            if k not in settings_ref:
                settings_ref[k] = {}
            settings_ref = settings_ref[k]
        
        # Set the final value
        settings_ref[keys[-1]] = value
        
        # Save to file
        self.save_settings(self._settings)

    def _apply_env_overrides(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides with TESTBED_ prefix."""
        def override_nested(obj: dict[str, Any], prefix: str) -> dict[str, Any]:
            result = obj.copy()
            
            for key, value in obj.items():
                env_key = f"TESTBED_{prefix}_{key.upper()}"
                
                if isinstance(value, dict):
                    # Recursively handle nested dictionaries
                    result[key] = override_nested(value, f"{prefix}_{key.upper()}")
                elif env_key in os.environ:
                    # Override with environment variable
                    env_value = os.environ[env_key]
                    
                    # Try to convert to appropriate type
                    if isinstance(value, bool):
                        result[key] = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif isinstance(value, int):
                        try:
                            result[key] = int(env_value)
                        except ValueError:
                            result[key] = env_value
                    elif isinstance(value, float):
                        try:
                            result[key] = float(env_value)
                        except ValueError:
                            result[key] = env_value
                    else:
                        result[key] = env_value
            
            return result

        # Apply overrides for each top-level section
        result = {}
        for section, section_data in settings.items():
            if isinstance(section_data, dict):
                result[section] = override_nested(section_data, section.upper())
            else:
                # Handle top-level non-dict values
                env_key = f"TESTBED_{section.upper()}"
                if env_key in os.environ:
                    env_value = os.environ[env_key]
                    if isinstance(section_data, bool):
                        result[section] = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif isinstance(section_data, int):
                        try:
                            result[section] = int(env_value)
                        except ValueError:
                            result[section] = env_value
                    elif isinstance(section_data, float):
                        try:
                            result[section] = float(env_value)
                        except ValueError:
                            result[section] = env_value
                    else:
                        result[section] = env_value
                else:
                    result[section] = section_data

        return result

    def get_backend_config(self) -> dict[str, Any]:
        """Get the complete backend configuration."""
        if self._settings is None:
            self.load_settings()
        
        provider = self.get("backend.provider", "ollama")
        backend_config = {
            "backend": {"provider": provider}
        }
        
        if provider == "ollama":
            backend_config["ollama"] = self.get("ollama", {})
        elif provider == "openrouter":
            backend_config["openrouter"] = self.get("openrouter", {})
        
        return backend_config

    def create_default_settings(self) -> None:
        """Create default settings.yaml file."""
        default_settings = {
            "backend": {"provider": "ollama"},
            "ollama": {
                "host": "localhost",
                "port": 11434,
                "model": "gpt-oss:20b",
                "timeout": 180,
            },
            "openrouter": {
                "api_key": "",
                "model": "meta-llama/llama-3.1-70b-instruct", 
                "base_url": "https://openrouter.ai/api/v1",
                "timeout": 180,
                "site_url": "",
                "site_name": "Red Team Testbed",
            },
        }
        
        self.save_settings(default_settings)


# Global settings manager instance
settings_manager = SettingsManager()