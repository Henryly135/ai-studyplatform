from __future__ import annotations

from io import BytesIO
import json
import urllib.error
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors

from app.services.providers.adapters import (
    GeminiChatAdapter,
    GeminiEmbeddingAdapter,
    OpenAICompatibleChatAdapter,
    OpenAICompatibleEmbeddingAdapter,
    build_chat_adapter,
    build_embedding_adapter,
    classify_provider_error,
)
from app.services.providers.credentials import (
    ProviderCredentialCipher,
    ProviderCredentialService,
    api_key_hint,
    redact_secret_text,
)
from app.services.providers.model_registry import (
    MODEL_DEFINITION_BY_ID,
    MODEL_DEFINITIONS,
    PROVIDER_DEFINITIONS,
    SUPPORTED_PROVIDER_KEYS,
)
from app.services.providers.types import (
    EmbeddingRequest,
    ProviderConfigurationError,
    ProviderInvocationError,
    ProviderQuotaError,
    TextGenerationRequest,
)


def test_registry_only_exposes_supported_paired_providers() -> None:
    assert SUPPORTED_PROVIDER_KEYS == {"gemini", "glm", "openrouter"}
    assert {provider.provider_key for provider in PROVIDER_DEFINITIONS} == SUPPORTED_PROVIDER_KEYS
    assert all(model.provider_key != "deepseek" for model in MODEL_DEFINITIONS)

    expected_pairs = {
        "gemini": "gemini:gemini-embedding-2",
        "glm": "glm:embedding-3",
        "openrouter": "openrouter:openai/text-embedding-3-small",
    }
    for model in MODEL_DEFINITIONS:
        if model.supports_chat:
            assert model.paired_embedding_model_id == expected_pairs[model.provider_key]
            paired = MODEL_DEFINITION_BY_ID[model.paired_embedding_model_id]
            assert paired.supports_embedding is True
            assert paired.embedding_dimension == 1024

    assert {
        model.model_id
        for model in MODEL_DEFINITIONS
        if model.provider_key == "gemini" and model.supports_chat
    } == {
        "gemini:gemini-3.5-flash-lite",
        "gemini:gemini-3.6-flash",
    }
    assert MODEL_DEFINITION_BY_ID[
        "gemini:gemini-3.5-flash-lite"
    ].display_name == "Gemini 3.5 Flash-Lite"
    assert {
        model.model_id
        for model in MODEL_DEFINITIONS
        if model.provider_key == "glm" and model.supports_chat
    } == {"glm:glm-4.7"}
    assert {
        model.model_id
        for model in MODEL_DEFINITIONS
        if model.provider_key == "openrouter" and model.supports_chat
    } == {"openrouter:openrouter/auto"}


def test_adapter_factories_use_adapter_type_not_provider_key() -> None:
    assert isinstance(build_chat_adapter("gemini"), GeminiChatAdapter)
    assert isinstance(build_chat_adapter("openai_compatible"), OpenAICompatibleChatAdapter)
    assert isinstance(build_embedding_adapter("gemini"), GeminiEmbeddingAdapter)
    assert isinstance(build_embedding_adapter("openai_compatible"), OpenAICompatibleEmbeddingAdapter)

    with pytest.raises(ProviderInvocationError):
        build_chat_adapter("deepseek")


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
            provider_key="glm",
            model_name="glm-4.7",
            api_key="secret-key",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            prompt="hi",
            system_instruction="system",
            json_mode=True,
        )
    )

    assert result.text == "hello"
    assert result.usage.total_tokens == 5
    assert captured["payload"]["model"] == "glm-4.7"
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert result.request_json["thinkingDisabled"] is True
    assert "secret-key" not in str(result.request_json)
    assert captured["timeout"] == 12


def test_openrouter_json_request_requires_parameter_support(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {"content": '{"ok":true}'},
                            "finish_reason": "stop",
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        assert timeout == 12
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(
        "app.services.providers.adapters.urllib.request.urlopen",
        fake_urlopen,
    )
    monkeypatch.setattr(
        "app.services.providers.adapters.settings",
        SimpleNamespace(ai_chat_timeout_seconds=12),
    )

    result = OpenAICompatibleChatAdapter().generate_text(
        TextGenerationRequest(
            provider_key="openrouter",
            model_name="openrouter/auto",
            api_key="secret-key",
            base_url="https://openrouter.ai/api/v1",
            prompt="return json",
            json_mode=True,
            require_parameter_support=True,
        )
    )

    assert captured["payload"]["response_format"] == {
        "type": "json_object"
    }
    assert captured["payload"]["provider"] == {
        "require_parameters": True
    }
    assert "thinking" not in captured["payload"]
    assert result.request_json["thinkingDisabled"] is False


def test_openai_compatible_adapter_uses_safe_error_summary(monkeypatch) -> None:
    def fake_urlopen(_request, timeout):
        assert timeout == 12
        raise urllib.error.HTTPError(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
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
                provider_key="glm",
                model_name="glm-4.7",
                api_key="secret-key",
                base_url="https://open.bigmodel.cn/api/paas/v4",
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


def test_openai_compatible_chat_adapter_rejects_http_200_error_payload(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {"error": {"code": "rate_limit_exceeded", "message": "provider quota reached"}}
            ).encode("utf-8")

    monkeypatch.setattr(
        "app.services.providers.adapters.urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    monkeypatch.setattr("app.services.providers.adapters.settings", SimpleNamespace(ai_chat_timeout_seconds=12))

    with pytest.raises(ProviderQuotaError):
        OpenAICompatibleChatAdapter().generate_text(
            TextGenerationRequest(
                provider_key="openrouter",
                model_name="openrouter/auto",
                api_key="secret-key",
                base_url="https://openrouter.ai/api/v1",
                prompt="hi",
            )
        )


def test_openai_compatible_chat_adapter_classifies_nested_numeric_error(
    monkeypatch,
) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {"content": "partial"},
                            "finish_reason": "error",
                            "error": {
                                "code": 429,
                                "message": "upstream failed",
                                "metadata": {
                                    "error_type": "rate_limit_exceeded"
                                },
                            },
                        }
                    ]
                }
            ).encode("utf-8")

    monkeypatch.setattr(
        "app.services.providers.adapters.urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    monkeypatch.setattr(
        "app.services.providers.adapters.settings",
        SimpleNamespace(ai_chat_timeout_seconds=12),
    )

    with pytest.raises(ProviderQuotaError):
        OpenAICompatibleChatAdapter().generate_text(
            TextGenerationRequest(
                provider_key="openrouter",
                model_name="openrouter/auto",
                api_key="secret-key",
                base_url="https://openrouter.ai/api/v1",
                prompt="hi",
            )
        )


def test_gemini_chat_adapter_omits_deprecated_temperature(
    monkeypatch,
) -> None:
    captured = {}

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(
                text="OK",
                usage_metadata=SimpleNamespace(
                    prompt_token_count=2,
                    candidates_token_count=1,
                    total_token_count=3,
                ),
            )

    monkeypatch.setattr(
        "app.services.providers.adapters.genai.Client",
        lambda **_: SimpleNamespace(models=FakeModels()),
    )

    result = GeminiChatAdapter().generate_text(
        TextGenerationRequest(
            provider_key="gemini",
            model_name="gemini-3.5-flash-lite",
            api_key="secret-key",
            base_url=None,
            prompt="Reply with OK.",
            temperature=0.8,
            max_output_tokens=16,
        )
    )

    assert result.text == "OK"
    assert captured["model"] == "gemini-3.5-flash-lite"
    assert "temperature" not in captured["config"].model_dump(
        exclude_none=True
    )
    assert "temperature" not in result.request_json


@pytest.mark.parametrize("adapter_kind", ["chat", "embedding"])
@pytest.mark.parametrize(
    ("status_code", "status_name", "expected_exception", "expected_error_type"),
    [
        (429, "RESOURCE_EXHAUSTED", ProviderQuotaError, None),
        (
            401,
            "UNAUTHENTICATED",
            ProviderInvocationError,
            "provider_authentication_error",
        ),
        (
            503,
            "UNAVAILABLE",
            ProviderInvocationError,
            "transient_network_error",
        ),
    ],
)
def test_gemini_adapters_classify_client_error_metadata(
    monkeypatch,
    adapter_kind,
    status_code,
    status_name,
    expected_exception,
    expected_error_type,
) -> None:
    provider_error = genai_errors.ClientError(
        status_code,
        {
            "error": {
                "code": status_code,
                "status": status_name,
                "message": "provider request failed",
            }
        },
    )

    class FakeModels:
        def generate_content(self, **_kwargs):
            raise provider_error

        def embed_content(self, **_kwargs):
            raise provider_error

    monkeypatch.setattr(
        "app.services.providers.adapters.genai.Client",
        lambda **_: SimpleNamespace(models=FakeModels()),
    )

    with pytest.raises(expected_exception) as exc_info:
        if adapter_kind == "chat":
            GeminiChatAdapter().generate_text(
                TextGenerationRequest(
                    provider_key="gemini",
                    model_name="gemini-3.5-flash-lite",
                    api_key="secret-key",
                    base_url=None,
                    prompt="Reply with OK.",
                )
            )
        else:
            GeminiEmbeddingAdapter().embed(
                EmbeddingRequest(
                    provider_key="gemini",
                    model_name="gemini-embedding-2",
                    api_key="secret-key",
                    base_url=None,
                    text="document",
                    output_dimension=2,
                    task_type="RETRIEVAL_QUERY",
                )
            )

    if expected_error_type is not None:
        assert (
            exc_info.value.provider_error_type
            == expected_error_type
        )


@pytest.mark.parametrize(
    ("task_type", "title", "expected_contents"),
    [
        (
            "RETRIEVAL_QUERY",
            None,
            "task: search result | query: document",
        ),
        (
            "RETRIEVAL_DOCUMENT",
            "Lesson",
            "title: Lesson | text: document",
        ),
        (
            "RETRIEVAL_DOCUMENT",
            None,
            "title: none | text: document",
        ),
    ],
)
def test_gemini_embedding_2_adapter_formats_content_and_only_sends_dimension(
    monkeypatch,
    task_type,
    title,
    expected_contents,
) -> None:
    captured = {}

    class FakeModels:
        def embed_content(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[3.0, 4.0])],
                usage_metadata=SimpleNamespace(
                    prompt_token_count=2,
                    total_token_count=2,
                ),
            )

    monkeypatch.setattr(
        "app.services.providers.adapters.genai.Client",
        lambda **_: SimpleNamespace(models=FakeModels()),
    )

    result = GeminiEmbeddingAdapter().embed(
        EmbeddingRequest(
            provider_key="gemini",
            model_name="gemini-embedding-2",
            api_key="secret-key",
            base_url=None,
            text="document",
            output_dimension=2,
            task_type=task_type,
            title=title,
        )
    )

    assert result.vector == pytest.approx([0.6, 0.8])
    assert captured["model"] == "gemini-embedding-2"
    assert captured["contents"] == expected_contents
    assert captured["config"].model_dump(exclude_none=True) == {
        "output_dimensionality": 2
    }


def test_openai_compatible_embedding_adapter_parses_and_normalizes_vector(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {
                    "data": [{"index": 0, "embedding": [3, 4]}],
                    "usage": {"prompt_tokens": 2, "total_tokens": 2},
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.providers.adapters.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.providers.adapters.settings", SimpleNamespace(ai_chat_timeout_seconds=12))

    result = OpenAICompatibleEmbeddingAdapter().embed(
        EmbeddingRequest(
            provider_key="glm",
            model_name="embedding-3",
            api_key="secret-key",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            text="document",
            output_dimension=2,
        )
    )

    assert result.vector == pytest.approx([0.6, 0.8])
    assert result.usage.total_tokens == 2
    assert captured["url"].endswith("/embeddings")
    assert captured["payload"] == {
        "model": "embedding-3",
        "input": "document",
        "dimensions": 2,
    }
    assert captured["timeout"] == 12
    assert "secret-key" not in str(result.request_json)


def test_openai_compatible_embedding_adapter_rejects_invalid_payload(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"data":[{"embedding":[1]}]}'

    monkeypatch.setattr(
        "app.services.providers.adapters.urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    monkeypatch.setattr("app.services.providers.adapters.settings", SimpleNamespace(ai_chat_timeout_seconds=12))

    with pytest.raises(ProviderInvocationError, match="dimension mismatch"):
        OpenAICompatibleEmbeddingAdapter().embed(
            EmbeddingRequest(
                provider_key="openrouter",
                model_name="openai/text-embedding-3-small",
                api_key="secret-key",
                base_url="https://openrouter.ai/api/v1",
                text="document",
                output_dimension=2,
            )
        )


def test_openai_compatible_embedding_adapter_rejects_http_200_error_payload(
    monkeypatch,
) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {
                    "error": {
                        "code": 429,
                        "message": "upstream failed",
                        "metadata": {
                            "error_type": "rate_limit_exceeded"
                        },
                    }
                }
            ).encode("utf-8")

    monkeypatch.setattr(
        "app.services.providers.adapters.urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    monkeypatch.setattr(
        "app.services.providers.adapters.settings",
        SimpleNamespace(
            ai_chat_timeout_seconds=12,
            ai_embedding_timeout_seconds=12,
        ),
    )

    with pytest.raises(ProviderQuotaError):
        OpenAICompatibleEmbeddingAdapter().embed(
            EmbeddingRequest(
                provider_key="openrouter",
                model_name="openai/text-embedding-3-small",
                api_key="secret-key",
                base_url="https://openrouter.ai/api/v1",
                text="document",
                output_dimension=2,
            )
        )


def test_stale_database_provider_cannot_restore_removed_adapter() -> None:
    service = ProviderCredentialService(SimpleNamespace())
    service.repo = SimpleNamespace(
        get_provider=lambda _provider_key: SimpleNamespace(
            provider_key="deepseek",
            backend_supported=True,
            default_base_url="https://example.invalid",
        ),
        get_credential=lambda _provider_key: SimpleNamespace(
            is_enabled=True,
            encrypted_api_key="legacy-encrypted-key",
            base_url_override=None,
        ),
    )

    with pytest.raises(
        ProviderConfigurationError,
        match="not supported",
    ):
        service.get_credentials_for_provider("deepseek")

    with pytest.raises(
        ProviderConfigurationError,
        match="not supported",
    ):
        service.save_credentials(
            provider_key="deepseek",
            api_key="legacy-key",
            base_url_override=None,
            is_enabled=True,
        )


def test_error_classifier_does_not_treat_generate_as_rate_limit() -> None:
    assert classify_provider_error(RuntimeError("generate request failed")) != "quota"
