from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.ai_prompt_logs import AIPromptStatus
from app.services.indexing.embedding_service import EmbeddingService
from app.services.providers.types import (
    ProviderConfigurationError,
    ProviderInvocationError,
    ProviderQuotaError,
)


def _invocation_result(model_id: str = "glm:embedding-3"):
    return SimpleNamespace(
        model_id=model_id,
        embedding_version=f"{model_id}@1024",
        vector=[0.5] * 1024,
        task_type="RETRIEVAL_QUERY",
        output_dimension=1024,
        latency_ms=12,
        request_json={"modelId": model_id},
        response_json={"embeddingDimension": 1024},
        trace_id="trace",
        input_tokens=7,
        total_tokens=7,
    )


def test_list_available_embedding_models_exposes_catalog_identity_and_version() -> None:
    service = EmbeddingService.__new__(EmbeddingService)
    service.catalog = SimpleNamespace(
        list_available_embedding_models=lambda: [
            SimpleNamespace(
                model=SimpleNamespace(
                    model_id="glm:embedding-3",
                    display_name="GLM Embedding-3",
                    embedding_dimension=1024,
                )
            )
        ]
    )

    targets = service.list_available_embedding_models()

    assert targets[0].model_id == "glm:embedding-3"
    assert targets[0].embedding_version == "glm:embedding-3@1024"
    assert targets[0].dimension == 1024


def test_count_document_tokens_is_provider_neutral() -> None:
    service = EmbeddingService.__new__(EmbeddingService)

    result = service.count_document_tokens(
        text="  hello  ",
        embedding_model_id="openrouter:openai/text-embedding-3-small",
    )

    assert result.provider_input_tokens is None
    assert result.provider_total_tokens is None
    assert result.request_json["modelId"] == "openrouter:openai/text-embedding-3-small"
    assert result.response_json["providerCountTokensSupported"] is False


def test_embed_query_resolves_chat_pair_and_invokes_that_embedding_model() -> None:
    service = EmbeddingService.__new__(EmbeddingService)
    pair_calls = []
    invocation_calls = []
    service.catalog = SimpleNamespace(
        resolve_model_pair=lambda **kwargs: (
            pair_calls.append(kwargs)
            or SimpleNamespace(
                embedding=SimpleNamespace(
                    model=SimpleNamespace(model_id="glm:embedding-3")
                )
            )
        )
    )
    service.invocation = SimpleNamespace(
        embed_text=lambda **kwargs: (
            invocation_calls.append(kwargs) or _invocation_result()
        )
    )

    result = service.embed_query(
        text="question",
        chat_model_id="glm:glm-4.7",
        user_id=9,
    )

    assert pair_calls == [
        {"user_id": 9, "requested_model_id": "glm:glm-4.7"}
    ]
    assert invocation_calls[0]["model_id"] == "glm:embedding-3"
    assert invocation_calls[0]["task_type"] == "RETRIEVAL_QUERY"
    assert result.embedding_model_id == "glm:embedding-3"
    assert result.embedding_model == "glm:embedding-3"
    assert result.status == AIPromptStatus.SUCCESS
    assert result.provider_input_tokens == 7


def test_embed_query_accepts_authoritative_embedding_model_id_directly() -> None:
    service = EmbeddingService.__new__(EmbeddingService)
    service.catalog = SimpleNamespace(
        resolve_model_pair=lambda **_: pytest.fail("pair should not be resolved")
    )
    calls = []
    service.invocation = SimpleNamespace(
        embed_text=lambda **kwargs: (
            calls.append(kwargs)
            or _invocation_result("gemini:gemini-embedding-2")
        )
    )

    result = service.embed_query(
        text="question",
        embedding_model_id="gemini:gemini-embedding-2",
    )

    assert calls[0]["model_id"] == "gemini:gemini-embedding-2"
    assert result.embedding_model_id == "gemini:gemini-embedding-2"


def test_embed_query_maps_unavailable_pair_to_stable_api_error() -> None:
    service = EmbeddingService.__new__(EmbeddingService)

    def _raise(**_):
        raise ProviderConfigurationError("missing credential")

    service.catalog = SimpleNamespace(resolve_model_pair=_raise)

    with pytest.raises(HTTPException) as exc_info:
        service.embed_query(text="question", chat_model_id="glm:glm-4.7")

    assert exc_info.value.status_code == 503
    assert (
        exc_info.value.detail["code"]
        == "AI_EMBEDDING_PROVIDER_UNAVAILABLE"
    )


@pytest.mark.parametrize(
    ("provider_error", "status_code", "error_code"),
    [
        (
            ProviderConfigurationError("missing credential"),
            503,
            "AI_EMBEDDING_PROVIDER_UNAVAILABLE",
        ),
        (
            ProviderInvocationError(
                "timeout",
                provider_error_type="provider_timeout",
            ),
            503,
            "AI_EMBEDDING_PROVIDER_UNAVAILABLE",
        ),
        (
            ProviderQuotaError("quota"),
            429,
            "AI_QUOTA_EXCEEDED",
        ),
    ],
)
def test_embed_query_preserves_provider_failure_classification(
    provider_error,
    status_code,
    error_code,
) -> None:
    service = EmbeddingService.__new__(EmbeddingService)

    def raise_provider_error(**_):
        raise provider_error

    service.invocation = SimpleNamespace(embed_text=raise_provider_error)

    with pytest.raises(HTTPException) as exc_info:
        service.embed_query(
            text="question",
            embedding_model_id="glm:embedding-3",
        )

    assert exc_info.value.status_code == status_code
    assert exc_info.value.detail["code"] == error_code


def test_embed_text_rejects_blank_content_before_provider_call() -> None:
    service = EmbeddingService.__new__(EmbeddingService)
    service.invocation = SimpleNamespace(
        embed_text=lambda **_: pytest.fail("provider should not be called")
    )

    with pytest.raises(Exception) as exc_info:
        service._embed_text(
            text=" ",
            title=None,
            task_type="RETRIEVAL_QUERY",
            embedding_model_id="glm:embedding-3",
        )

    assert "text is required for embedding" in str(exc_info.value)
