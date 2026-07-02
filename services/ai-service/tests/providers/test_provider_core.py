from __future__ import annotations

from io import BytesIO
import json
import urllib.error
from types import SimpleNamespace

from app.services.providers.adapters import OpenAICompatibleChatAdapter
from app.services.providers.credentials import ProviderCredentialCipher, api_key_hint, redact_secret_text
from app.services.providers.types import ProviderInvocationError, TextGenerationRequest


def test_provider_credential_cipher_encrypts_and_decrypts_key() -> None:
    cipher = ProviderCredentialCipher("x" * 32)

    encrypted = cipher.encrypt("sk-test-secret")

    assert encrypted != "sk-test-secret"
    assert cipher.decrypt(encrypted) == "sk-test-secret"
    assert api_key_hint("sk-test-secret") == "****cret"


def test_redact_secret_text_masks_api_key_and_bearer_tokens() -> None:
    redacted = redact_secret_text("api_key=abc123 Authorization: Bearer secret-token")

    assert "abc123" not in redacted
    assert "secret-token" not in redacted
    assert "[REDACTED]" in redacted


def test_openai_compatible_adapter_parses_chat_completion(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.providers.adapters.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.providers.adapters.settings", SimpleNamespace(ai_chat_timeout_seconds=12))

    result = OpenAICompatibleChatAdapter().generate_text(
        TextGenerationRequest(
            provider_key="deepseek",
            model_name="deepseek-v4-flash",
            api_key="secret-key",
            base_url="https://api.deepseek.com",
            prompt="hi",
            system_instruction="system",
            json_mode=True,
        )
    )

    assert result.text == "hello"
    assert result.usage.total_tokens == 5
    assert captured["payload"]["model"] == "deepseek-v4-flash"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert "secret-key" not in str(result.request_json)
    assert captured["timeout"] == 12


def test_openai_compatible_adapter_uses_safe_error_summary(monkeypatch) -> None:
    def fake_urlopen(_request, timeout):
        assert timeout == 12
        raise urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions",
            401,
            "Unauthorized secret-key",
            {},
            BytesIO(b'{"error":"secret-key leaked back"}'),
        )

    monkeypatch.setattr("app.services.providers.adapters.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.providers.adapters.settings", SimpleNamespace(ai_chat_timeout_seconds=12))

    try:
        OpenAICompatibleChatAdapter().generate_text(
            TextGenerationRequest(
                provider_key="deepseek",
                model_name="deepseek-v4-flash",
                api_key="secret-key",
                base_url="https://api.deepseek.com",
                prompt="hi",
            )
        )
    except ProviderInvocationError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected provider invocation error")

    assert "secret-key" not in message
    assert "leaked back" not in message
    assert "HTTP 401" in message
