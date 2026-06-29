from __future__ import annotations

import importlib
import os
import sys

import platform_common.config as common_config


AI_CONFIG_ENV_KEYS = {
    "AI_CHAT_PROVIDER",
    "AI_CHAT_MODEL",
    "AI_CHAT_BASE_URL",
    "AI_CHAT_API_KEY",
    "AI_DEMO_MODEL_NAME",
    "AI_EMBEDDING_API_KEY",
    "AI_EMBEDDING_PROVIDER",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "MODEL_NAME",
    "REDIS_INTERNAL_PORT",
    "REDIS_PORT",
}

BASE_ENV = {
    "REDIS_INTERNAL_PORT": "6379",
}


def _reload_settings_with_env(**values):
    original_env = dict(os.environ)
    original_load_project_env = common_config.load_project_env
    try:
        for key in AI_CONFIG_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ.update(BASE_ENV)
        os.environ.update(values)
        common_config.load_project_env = lambda *_: None
        sys.modules.pop("app.core.config", None)
        module = importlib.import_module("app.core.config")
        return module.settings
    finally:
        os.environ.clear()
        os.environ.update(original_env)
        common_config.load_project_env = original_load_project_env
        sys.modules.pop("app.core.config", None)


def test_ai_chat_provider_defaults_keep_gemini_compatibility() -> None:
    # New provider settings are inert when no alternate provider is configured.
    settings = _reload_settings_with_env()

    assert settings.ai_chat_provider == "gemini"
    assert settings.ai_chat_model == "gemini-2.5-flash"
    assert settings.ai_chat_base_url == ""
    assert settings.ai_chat_api_key == ""
    assert settings.deepseek_api_key == ""
    assert settings.gemini_api_key == ""
    assert settings.ai_embedding_api_key == ""
    assert settings.ai_embedding_provider == "gemini"


def test_ai_chat_provider_reads_deepseek_without_polluting_gemini() -> None:
    # DeepSeek config is readable for the future adapter without changing Gemini key semantics.
    settings = _reload_settings_with_env(
        AI_CHAT_PROVIDER="deepseek",
        AI_CHAT_MODEL="deepseek-v4-flash",
        AI_CHAT_BASE_URL="https://api.deepseek.com",
        AI_CHAT_API_KEY="chat-key",
        DEEPSEEK_API_KEY="deepseek-key",
        GEMINI_API_KEY="gemini-key",
    )

    assert settings.ai_chat_provider == "deepseek"
    assert settings.ai_chat_model == "deepseek-v4-flash"
    assert settings.ai_chat_base_url == "https://api.deepseek.com"
    assert settings.ai_chat_api_key == "chat-key"
    assert settings.deepseek_api_key == "deepseek-key"
    assert settings.gemini_api_key == "gemini-key"


def test_ai_chat_api_key_can_fallback_to_deepseek_key() -> None:
    # Unified chat key can use the DeepSeek alias while current Gemini paths stay separate.
    settings = _reload_settings_with_env(
        AI_CHAT_PROVIDER="deepseek",
        DEEPSEEK_API_KEY="deepseek-key",
    )

    assert settings.ai_chat_api_key == "deepseek-key"
    assert settings.deepseek_api_key == "deepseek-key"
    assert settings.gemini_api_key == ""


def test_embedding_key_falls_back_to_gemini_not_deepseek() -> None:
    # DeepSeek is planned for chat only; embedding keeps a Gemini-compatible key path by default.
    settings = _reload_settings_with_env(
        DEEPSEEK_API_KEY="deepseek-key",
        GEMINI_API_KEY="gemini-key",
    )

    assert settings.ai_embedding_provider == "gemini"
    assert settings.ai_embedding_api_key == "gemini-key"
    assert settings.ai_embedding_api_key != settings.deepseek_api_key


def test_embedding_key_prefers_explicit_embedding_api_key() -> None:
    # Future embedding adapters can use their own explicit key without changing chat keys.
    settings = _reload_settings_with_env(
        AI_EMBEDDING_API_KEY="embedding-key",
        GEMINI_API_KEY="gemini-key",
        DEEPSEEK_API_KEY="deepseek-key",
    )

    assert settings.ai_embedding_api_key == "embedding-key"
    assert settings.gemini_api_key == "gemini-key"
    assert settings.deepseek_api_key == "deepseek-key"
