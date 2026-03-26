"""Mutable LLM configuration with YAML persistence and provider URL registry.

Separated from Settings (which is immutable after startup) because LLM
config changes at runtime via ``POST /llm/configure`` and should persist
across restarts.
"""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from vibelens.utils.log import get_logger

logger = get_logger(__name__)

LLM_CONFIG_ENV_VAR = "VIBELENS_LLM_CONFIG"
LLM_ENV_PREFIX = "VIBELENS_LLM_"
DEFAULT_LLM_CONFIG_PATH = Path("config/llm.yaml")

PROVIDER_BASE_URLS: dict[str, str] = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "openrouter": "https://openrouter.ai/api/v1",
    "mistral": "https://api.mistral.ai/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com",
    "minimax": "https://api.minimax.chat/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "together": "https://api.together.xyz/v1",
    "fireworks": "https://api.fireworks.ai/inference/v1",
}

# Env var name → LLMConfig field name
_ENV_FIELD_MAP: dict[str, str] = {
    "VIBELENS_LLM_BACKEND": "backend",
    "VIBELENS_LLM_API_KEY": "api_key",
    "VIBELENS_LLM_BASE_URL": "base_url",
    "VIBELENS_LLM_MODEL": "model",
    "VIBELENS_LLM_TIMEOUT": "timeout",
    "VIBELENS_LLM_MAX_TOKENS": "max_tokens",
}

API_KEY_MASK_SUFFIX_LEN = 4
API_KEY_MASK = "***"


class LLMConfig(BaseModel):
    """Mutable LLM configuration. Can be changed at runtime and persisted."""

    backend: str = Field(
        default="disabled",
        description="Backend: 'litellm', 'claude-cli', 'codex-cli', 'disabled'.",
    )
    api_key: str = Field(
        default="",
        description="API key for the LLM provider.",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom base URL. Auto-resolved from PROVIDER_BASE_URLS if None.",
    )
    model: str = Field(
        default="anthropic/claude-sonnet-4-5",
        description="Model in litellm format.",
    )
    timeout: int = Field(
        default=120,
        description="Inference timeout in seconds.",
    )
    max_tokens: int = Field(
        default=4096,
        description="Max output tokens.",
    )


def discover_llm_config_path() -> Path | None:
    """Find the LLM config file path.

    Checks (in order):
        1. ``VIBELENS_LLM_CONFIG`` environment variable
        2. ``config/llm.yaml`` in the current directory

    Returns:
        Path if found, else None.
    """
    env_value = os.environ.get(LLM_CONFIG_ENV_VAR)
    if env_value:
        path = Path(env_value)
        if path.exists():
            return path
        logger.warning("%s points to missing file: %s", LLM_CONFIG_ENV_VAR, path)
        return None

    if DEFAULT_LLM_CONFIG_PATH.exists():
        return DEFAULT_LLM_CONFIG_PATH
    return None


def load_llm_config(config_path: Path | None = None) -> LLMConfig:
    """Load LLM config from YAML file, then apply env var overrides.

    Priority (highest to lowest):
        1. Environment variables (``VIBELENS_LLM_*``)
        2. YAML config file values
        3. Field defaults

    Args:
        config_path: Explicit path. Auto-discovered if None.

    Returns:
        Populated LLMConfig.
    """
    resolved = config_path or discover_llm_config_path()
    yaml_values = _load_yaml_values(resolved) if resolved else {}

    # Apply env var overrides on top of YAML values
    merged = _apply_env_overrides(yaml_values)

    config = LLMConfig(**merged)
    if resolved:
        logger.info("Loaded LLM config from %s (backend=%s)", resolved, config.backend)
    return config


def save_llm_config(config: LLMConfig, config_path: Path) -> None:
    """Persist LLM config to a YAML file.

    The API key is saved as-is so it can be reloaded on restart.

    Args:
        config: Current LLM configuration.
        config_path: Target file path.
    """
    data = {
        "llm": {
            "backend": config.backend,
            "model": config.model,
            "api_key": config.api_key,
            "base_url": config.base_url,
            "timeout": config.timeout,
            "max_tokens": config.max_tokens,
        }
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    logger.info("Saved LLM config to %s", config_path)


def resolve_base_url(config: LLMConfig) -> str | None:
    """Resolve base URL from config or provider registry.

    If ``config.base_url`` is set, returns it. Otherwise extracts the
    provider prefix from the model name and looks up PROVIDER_BASE_URLS.

    Args:
        config: LLM configuration.

    Returns:
        Resolved base URL, or None if provider is unknown.
    """
    if config.base_url:
        return config.base_url

    provider = _extract_provider(config.model)
    if not provider:
        return None
    return PROVIDER_BASE_URLS.get(provider)


def _extract_provider(model: str) -> str | None:
    """Extract provider prefix from a litellm model name (e.g. 'anthropic/...' → 'anthropic')."""
    if "/" not in model:
        return None
    return model.split("/", 1)[0].lower()


def _load_yaml_values(config_path: Path) -> dict:
    """Read the ``llm:`` section from a YAML config file.

    Args:
        config_path: Path to YAML file.

    Returns:
        Dict of field name → value from the llm section.
    """
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    llm_section = raw.get("llm")
    if not isinstance(llm_section, dict):
        return {}
    return {k: v for k, v in llm_section.items() if v is not None}


def _apply_env_overrides(yaml_values: dict) -> dict:
    """Overlay environment variables onto YAML-loaded values.

    Args:
        yaml_values: Values from YAML file.

    Returns:
        Merged dict with env vars taking priority.
    """
    merged = dict(yaml_values)
    for env_key, field_name in _ENV_FIELD_MAP.items():
        env_value = os.environ.get(env_key)
        if env_value is not None:
            # Coerce integer fields
            if field_name in ("timeout", "max_tokens"):
                merged[field_name] = int(env_value)
            else:
                merged[field_name] = env_value
    return merged


def mask_api_key(api_key: str) -> str:
    """Mask an API key for display, preserving the last 4 chars."""
    if not api_key or len(api_key) <= API_KEY_MASK_SUFFIX_LEN:
        return API_KEY_MASK
    return f"{API_KEY_MASK}{api_key[-API_KEY_MASK_SUFFIX_LEN:]}"
