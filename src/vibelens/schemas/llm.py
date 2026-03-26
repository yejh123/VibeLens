"""LLM configuration request schemas."""

from pydantic import BaseModel, Field


class LLMConfigureRequest(BaseModel):
    """Request body for runtime LLM backend configuration."""

    backend: str = Field(
        default="litellm",
        description="Backend type: 'litellm', 'claude-cli', 'codex-cli', 'disabled'.",
    )
    api_key: str = Field(
        default="",
        description="API key for the LLM provider. Empty to keep existing key.",
    )
    model: str = Field(
        default="anthropic/claude-sonnet-4-5",
        description="Model in litellm format (e.g. 'anthropic/claude-sonnet-4-5').",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom base URL (auto-resolved from provider if None).",
    )
    timeout: int = Field(
        default=120,
        description="Timeout in seconds.",
    )
    max_tokens: int = Field(
        default=4096,
        description="Max output tokens.",
    )
