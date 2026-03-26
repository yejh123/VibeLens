"""Application configuration package.

Provides YAML-first configuration with environment variable overrides.
Priority (highest to lowest): env vars → .env file → YAML config → defaults.
"""

from vibelens.config.llm_config import LLMConfig, load_llm_config, mask_api_key, save_llm_config
from vibelens.config.loader import discover_config_path
from vibelens.config.settings import Settings, load_settings

__all__ = [
    "LLMConfig",
    "Settings",
    "discover_config_path",
    "load_llm_config",
    "load_settings",
    "mask_api_key",
    "save_llm_config",
]
