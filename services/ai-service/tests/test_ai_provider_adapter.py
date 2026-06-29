from __future__ import annotations

import json
import socket
from io import BytesIO
from types import SimpleNamespace
from urllib import error

import pytest

from app.services.providers.factory import get_chat_provider, resolve_gemini_chat_api_key
from app.services.providers.gemini import GeminiChatProvider
from app.services.providers.openai_compatible import OpenAICompatibleChatProvider
from app.services.providers.types import (
    AIProviderConfigurationError,
    AIProviderError,
    ChatGenerationMessage,
    ChatGenerationRequest,
)


def _request(**overrides) -> ChatGenerationRequest:
    values = {
        "model": "chat-model",
        "system_instruction": "Be helpful.",
        "contents": "Hello",
        "temperature": 0.2,
        "max_output_tokens": 128,
        "response_mime_type": None,
    }
    values.update(overrides)
    return ChatGenerationRequest(**values)


def test_factory_keeps_gemini_default_and_uses_legacy_key(monkeypatch) -> None:
    # Tests default provider remains Gemini and can use GEMINI_API_KEY compatibility.
    created: dict[str, str] = {}

    class FakeGeminiProvider:
        provider_name = "gemini"

        def __init__(self, *, api_key: str) -> None:
            created["api_key"] = api_key

    monkeypatch.setattr("app.services.providers.factory.GeminiChatProvider", FakeGeminiProvider)

    provider = get_chat_provider(SimpleNamespace(gemini_api_key="legacy-key"))

    assert provider.provider_name == "gemini"
    assert created["api_key"] == "legacy-key"


def test_factory_keeps_deepseek_alias_out_of_gemini_key(monkeypatch) -> None:
    # Tests DEEPSEEK_API_KEY fallback cannot accidentally become the Gemini key.
    created: dict[str, str] = {}

    class FakeGeminiProvider:
        provider_name = "gemini"

        def __init__(self, *, api_key: str) -> None:
            created["api_key"] = api_key

    monkeypatch.setattr("app.services.providers.factory.GeminiChatProvider", FakeGeminiProvider)

    config = SimpleNamespace(
        ai_chat_provider="gemini",
        ai_chat_api_key="deepseek-key",
        deepseek_api_key="deepseek-key",
        gemini_api_key="gemini-key",
    )
    provider = get_chat_provider(config)

    assert provider.provider_name == "gemini"
    assert created["api_key"] == "gemini-key"
    assert resolve_gemini_chat_api_key(config) == "gemini-key"


def test_factory_rejects_gemini_when_only_deepseek_alias_is_configured() -> None:
    # Tests a DeepSeek alias alone does not make the default Gemini provider configured.
    config = SimpleNamespace(
        ai_chat_provider="gemini",
        ai_chat_api_key="deepseek-key",
        deepseek_api_key="deepseek-key",
        gemini_api_key="",
    )

    with pytest.raises(AIProviderConfigurationError) as exc_info:
        get_chat_provider(config)

    assert "Gemini chat provider requires" in str(exc_info.value)


def test_factory_builds_deepseek_as_openai_compatible_provider() -> None:
    # Tests DeepSeek is reserved through the shared OpenAI-compatible adapter shape.
    provider = get_chat_provider(
        SimpleNamespace(
            ai_chat_provider="deepseek",
            ai_chat_api_key="chat-key",
            ai_chat_base_url="https://api.deepseek.com",
        )
    )

    assert provider.provider_name == "deepseek"
    assert provider.endpoint == "https://api.deepseek.com/chat/completions"


def test_openai_compatible_provider_requires_api_key() -> None:
    # Tests OpenAI-compatible providers fail before any network call when no key is configured.
    with pytest.raises(AIProviderConfigurationError) as exc_info:
        OpenAICompatibleChatProvider(
            provider_name="deepseek",
            api_key="",
            base_url="https://api.deepseek.com",
        )

    assert "requires AI_CHAT_API_KEY" in str(exc_info.value)


def test_factory_rejects_unknown_provider() -> None:
    # Tests unsupported provider names fail before any network call.
    with pytest.raises(AIProviderConfigurationError) as exc_info:
        get_chat_provider(SimpleNamespace(ai_chat_provider="mystery"))

    assert "Unsupported AI_CHAT_PROVIDER" in str(exc_info.value)


def test_openai_compatible_success_uses_chat_completions_shape(monkeypatch) -> None:
    # Tests OpenAI-compatible success parsing and request payload mapping without real API keys.
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [{"message": {"content": "Hello back"}}],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                }
            ).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["timeout"] = timeout
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        captured["authorization"] = req.headers["Authorization"]
        return FakeResponse()

    monkeypatch.setattr("app.services.providers.openai_compatible.urllib_request.urlopen", fake_urlopen)

    provider = OpenAICompatibleChatProvider(
        provider_name="deepseek",
        api_key="test-key",
        base_url="https://api.deepseek.com",
        timeout_seconds=4,
    )
    result = provider.generate(_request(response_mime_type="application/json"))

    assert result.text == "Hello back"
    assert result.usage_metadata["prompt_tokens"] == 2
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["messages"][0] == {"role": "system", "content": "Be helpful."}


def test_openai_compatible_request_includes_conversation_history(monkeypatch) -> None:
    # Tests non-Gemini chat providers receive prior turns instead of only the latest user message.
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "Next answer"}}]}).encode("utf-8")

    def fake_urlopen(req, timeout):
        _ = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("app.services.providers.openai_compatible.urllib_request.urlopen", fake_urlopen)

    provider = OpenAICompatibleChatProvider(
        provider_name="deepseek",
        api_key="test-key",
        base_url="https://api.deepseek.com",
    )
    provider.generate(
        _request(
            messages=(
                ChatGenerationMessage(role="user", content="Earlier question"),
                ChatGenerationMessage(role="assistant", content="Earlier answer"),
            )
        )
    )

    assert captured["payload"]["messages"] == [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
        {"role": "user", "content": "Hello"},
    ]


@pytest.mark.parametrize(
    ("status_code", "body", "expected"),
    [
        (401, {"error": {"message": "invalid api key"}}, "invalid_api_key"),
        (408, {"error": {"message": "request timeout"}}, "provider_timeout"),
        (429, {"error": {"message": "quota exceeded"}}, "quota"),
        (503, {"error": {"message": "temporarily unavailable"}}, "transient_network_error"),
    ],
)
def test_openai_compatible_http_errors_are_classified(monkeypatch, status_code, body, expected) -> None:
    # Tests provider HTTP failures become stable adapter error categories.
    def fake_urlopen(*_, **__):
        raise error.HTTPError(
            url="https://provider.test/chat/completions",
            code=status_code,
            msg="failed",
            hdrs={},
            fp=BytesIO(json.dumps(body).encode("utf-8")),
        )

    monkeypatch.setattr("app.services.providers.openai_compatible.urllib_request.urlopen", fake_urlopen)
    provider = OpenAICompatibleChatProvider(
        provider_name="deepseek",
        api_key="test-key",
        base_url="https://provider.test",
    )

    with pytest.raises(AIProviderError) as exc_info:
        provider.generate(_request())

    assert exc_info.value.error_type == expected


def test_openai_compatible_timeout_is_classified(monkeypatch) -> None:
    # Tests transport timeouts become stable provider_timeout errors.
    def fake_urlopen(*_, **__):
        raise socket.timeout("timed out")

    monkeypatch.setattr("app.services.providers.openai_compatible.urllib_request.urlopen", fake_urlopen)
    provider = OpenAICompatibleChatProvider(
        provider_name="deepseek",
        api_key="test-key",
        base_url="https://provider.test",
    )

    with pytest.raises(AIProviderError) as exc_info:
        provider.generate(_request())

    assert exc_info.value.error_type == "provider_timeout"


def test_openai_compatible_invalid_json_is_classified(monkeypatch) -> None:
    # Tests malformed provider responses become classified adapter errors.
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setattr(
        "app.services.providers.openai_compatible.urllib_request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    provider = OpenAICompatibleChatProvider(
        provider_name="deepseek",
        api_key="test-key",
        base_url="https://provider.test",
    )

    with pytest.raises(AIProviderError) as exc_info:
        provider.generate(_request())

    assert exc_info.value.error_type == "unknown_provider_error"


def test_gemini_provider_wraps_client_response(monkeypatch) -> None:
    # Tests Gemini provider success path without calling the real google-genai client.
    class FakeModels:
        def generate_content(self, **_):
            return SimpleNamespace(
                text="Gemini reply",
                usage_metadata=SimpleNamespace(
                    prompt_token_count=1,
                    candidates_token_count=2,
                    total_token_count=3,
                ),
            )

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "gemini-key"
            self.models = FakeModels()

    monkeypatch.setattr("app.services.providers.gemini.genai.Client", FakeClient)

    result = GeminiChatProvider(api_key="gemini-key").generate(_request())

    assert result.text == "Gemini reply"
    assert result.usage_metadata["total_token_count"] == 3
