from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.providers.gemini import GeminiChatProvider
from app.services.providers.openai_compatible import DEFAULT_BASE_URLS, OpenAICompatibleChatProvider
from app.services.providers.types import AIProviderConfigurationError, ChatProvider


OPENAI_COMPATIBLE_PROVIDERS = {"deepseek", "openrouter", "openai_compatible"}


def normalize_provider_name(provider_name: str | None) -> str:
    return (provider_name or "gemini").strip().lower().replace("-", "_")


def _get(config: Any, name: str, default: str = "") -> str:
    value = getattr(config, name, default)
    if value is None:
        return default
    return str(value)


def _config_or_settings(config: Any | None) -> Any:
    return settings if config is None else config


def resolve_gemini_chat_api_key(config: Any | None = None) -> str:
    config = _config_or_settings(config)
    chat_api_key = _get(config, "ai_chat_api_key")
    deepseek_api_key = _get(config, "deepseek_api_key")
    if chat_api_key and chat_api_key != deepseek_api_key:
        return chat_api_key
    return _get(config, "gemini_api_key")


def get_chat_provider(config: Any | None = None) -> ChatProvider:
    config = _config_or_settings(config)
    provider_name = normalize_provider_name(_get(config, "ai_chat_provider", "gemini"))
    if provider_name == "gemini":
        return GeminiChatProvider(
            api_key=resolve_gemini_chat_api_key(config)
        )

    if provider_name in OPENAI_COMPATIBLE_PROVIDERS:
        base_url = _get(config, "ai_chat_base_url") or DEFAULT_BASE_URLS.get(provider_name, "")
        return OpenAICompatibleChatProvider(
            provider_name=provider_name,
            api_key=_get(config, "ai_chat_api_key"),
            base_url=base_url,
        )

    raise AIProviderConfigurationError(f"Unsupported AI_CHAT_PROVIDER '{_get(config, 'ai_chat_provider')}'")


def is_chat_provider_configured(config: Any | None = None) -> bool:
    try:
        get_chat_provider(config)
    except AIProviderConfigurationError:
        return False
    return True
