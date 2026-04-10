from __future__ import annotations

import logging
import os

from .base import BaseLLMProvider
from .gemini import GeminiProvider
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class ModelRouter:
    """Config-driven model selection."""

    def __init__(self, config: dict | None = None):
        self._providers: dict[str, BaseLLMProvider] = {}
        self._default: str = ""
        if config:
            self._init_from_config(config)
        else:
            self._init_from_env()

    def _init_from_env(self):
        """Initialize from environment variables (simple mode)."""
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            self._providers["gemini"] = GeminiProvider(api_key=gemini_key)
            self._default = self._default or "gemini"

        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            self._providers["openai"] = OpenAIProvider(
                api_key=openai_key,
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                base_url=os.environ.get("OPENAI_BASE_URL"),
            )
            self._default = self._default or "openai"

        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        if deepseek_key:
            self._providers["deepseek"] = OpenAIProvider(
                api_key=deepseek_key,
                model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
                base_url="https://api.deepseek.com",
                provider_name="deepseek",
            )
            self._default = self._default or "deepseek"

        # Override default if explicitly set
        env_default = os.environ.get("LLM_DEFAULT_PROVIDER")
        if env_default and env_default in self._providers:
            self._default = env_default

    def _init_from_config(self, config: dict):
        """Initialize from settings.yaml config. Env vars override config values."""
        llm_config = config.get("llm", {})
        self._default = os.environ.get("LLM_DEFAULT_PROVIDER") or llm_config.get("default_provider", "")

        gemini_cfg = llm_config.get("gemini", {})
        gemini_key = gemini_cfg.get("api_key") or os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            self._providers["gemini"] = GeminiProvider(
                api_key=gemini_key,
                model=gemini_cfg.get("model", "gemini-2.5-flash"),
            )
            self._default = self._default or "gemini"

        openai_cfg = llm_config.get("openai", {})
        openai_key = openai_cfg.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if openai_key:
            self._providers["openai"] = OpenAIProvider(
                api_key=openai_key,
                model=os.environ.get("OPENAI_MODEL") or openai_cfg.get("model", "gpt-4o-mini"),
                base_url=os.environ.get("OPENAI_BASE_URL") or openai_cfg.get("base_url"),
            )
            self._default = self._default or "openai"

        deepseek_cfg = llm_config.get("deepseek", {})
        deepseek_key = deepseek_cfg.get("api_key") or os.environ.get("DEEPSEEK_API_KEY")
        if deepseek_key:
            self._providers["deepseek"] = OpenAIProvider(
                api_key=deepseek_key,
                model=deepseek_cfg.get("model", "deepseek-chat"),
                base_url=deepseek_cfg.get("base_url", "https://api.deepseek.com"),
                provider_name="deepseek",
            )
            self._default = self._default or "deepseek"

    def get(self, name: str | None = None) -> BaseLLMProvider:
        """Get a provider by name, or the default. Falls back to any available provider."""
        target = name or self._default
        provider = self._providers.get(target)
        if not provider and not name:
            # Default not available, fall back to first available
            if self._providers:
                fallback = next(iter(self._providers))
                logger.warning("Default provider '%s' not available, falling back to '%s'", target, fallback)
                return self._providers[fallback]
        if not provider:
            available = list(self._providers.keys())
            raise ValueError(
                f"No LLM provider '{target}' available. "
                f"Configured: {available}. Set API keys via environment variables."
            )
        return provider

    @property
    def available(self) -> list[str]:
        return list(self._providers.keys())

    @property
    def default_name(self) -> str:
        return self._default
