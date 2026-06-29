from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.ai_prompt_logs import AIPromptStatus
from app.services.indexing.embedding_service import EmbeddingService


def _settings(**overrides):
    values = {
        "ai_embedding_provider": "gemini",
        "ai_embedding_api_key": "embedding-key",
        "ai_embedding_orchestrator": "direct",
        "ai_embedding_model": "embedding-model",
        "ai_embedding_version": "embedding-v1",
        "ai_embedding_output_dimension": 2,
        "ai_embedding_dimension": 2,
        "ai_embedding_task_type": "RETRIEVAL_DOCUMENT",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_extract_token_count_supports_object_dict_and_serializers() -> None:
    # Tests all supported provider token-count response shapes.
    service = EmbeddingService.__new__(EmbeddingService)

    assert service._extract_token_count(SimpleNamespace(total_tokens=7)) == 7
    assert service._extract_token_count({"total_tokens": 8}) == 8
    assert service._extract_token_count(SimpleNamespace(to_dict=lambda: {"total_tokens": 9})) == 9
    assert service._extract_token_count(SimpleNamespace(to_json_dict=lambda: {"total_tokens": 10})) == 10
    assert service._extract_token_count(None) is None


def test_embedding_service_rejects_non_gemini_provider_with_reindex_guidance(monkeypatch) -> None:
    # Tests unsupported embedding providers fail clearly and tell operators to reindex after configuration.
    monkeypatch.setattr(
        "app.services.indexing.embedding_service.settings",
        _settings(ai_embedding_provider="deepseek"),
    )

    with pytest.raises(Exception) as exc_info:
        EmbeddingService()

    assert "Unsupported AI_EMBEDDING_PROVIDER 'deepseek'" in str(exc_info.value)
    assert "reindexing materials" in str(exc_info.value)


def test_normalize_vector_returns_unit_vector_and_rejects_zero() -> None:
    # Tests vector normalization and zero-vector validation.
    service = EmbeddingService.__new__(EmbeddingService)

    assert service._normalize_vector([3.0, 4.0]) == [0.6, 0.8]
    with pytest.raises(Exception) as exc_info:
        service._normalize_vector([0.0, 0.0])
    assert "Embedding vector magnitude is zero" in str(exc_info.value)


def test_count_document_tokens_returns_provider_count(monkeypatch) -> None:
    # Tests successful Gemini token counting with request/response metadata.
    service = EmbeddingService.__new__(EmbeddingService)
    service.client = SimpleNamespace(
        models=SimpleNamespace(count_tokens=lambda **_: SimpleNamespace(total_tokens=12))
    )
    monkeypatch.setattr("app.services.indexing.embedding_service.settings", _settings())

    result = service.count_document_tokens(text="  hello  ")

    assert result.provider_input_tokens == 12
    assert result.provider_total_tokens == 12
    assert result.request_json["contents_preview"] == "hello"
    assert result.response_json["provider_count_tokens_supported"] is True


def test_count_document_tokens_records_provider_error(monkeypatch) -> None:
    # Tests that token-count provider failures are returned as metadata, not raised.
    service = EmbeddingService.__new__(EmbeddingService)

    def _raise(**_):
        raise RuntimeError("provider down")

    service.client = SimpleNamespace(models=SimpleNamespace(count_tokens=_raise))
    monkeypatch.setattr("app.services.indexing.embedding_service.settings", _settings())

    result = service.count_document_tokens(text="hello")

    assert result.provider_input_tokens is None
    assert result.provider_total_tokens is None
    assert result.response_json["provider_count_tokens_supported"] is False
    assert "provider down" in result.response_json["provider_error"]


def test_embed_text_direct_normalizes_provider_embedding(monkeypatch) -> None:
    # Tests direct provider embedding path with dimension validation and normalization.
    service = EmbeddingService.__new__(EmbeddingService)
    service.client = SimpleNamespace(
        models=SimpleNamespace(
            embed_content=lambda **_: SimpleNamespace(
                embeddings=[SimpleNamespace(values=[3.0, 4.0])]
            )
        )
    )
    monkeypatch.setattr("app.services.indexing.embedding_service.settings", _settings())

    result = service._embed_text(text=" hello ", title="Doc", task_type="RETRIEVAL_DOCUMENT")

    assert result.vector == [0.6, 0.8]
    assert result.embedding_model == "embedding-model"
    assert result.status == AIPromptStatus.SUCCESS
    assert result.request_json["config"]["title"] == "Doc"


def test_embed_text_rejects_blank_and_dimension_mismatch(monkeypatch) -> None:
    # Tests blank embedding input and provider dimension mismatch errors.
    service = EmbeddingService.__new__(EmbeddingService)
    service.client = SimpleNamespace(
        models=SimpleNamespace(embed_content=lambda **_: SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0])]))
    )
    monkeypatch.setattr("app.services.indexing.embedding_service.settings", _settings())

    with pytest.raises(Exception) as blank_error:
        service._embed_text(text=" ", title=None, task_type="RETRIEVAL_QUERY")
    with pytest.raises(Exception) as dimension_error:
        service._embed_text(text="hello", title=None, task_type="RETRIEVAL_QUERY")

    assert "text is required for embedding" in str(blank_error.value)
    assert "Embedding dimension mismatch" in str(dimension_error.value)


def test_embed_text_via_langchain_uses_query_or_document_method(monkeypatch) -> None:
    # Tests langchain embedding path chooses query/document methods and normalizes vectors.
    service = EmbeddingService.__new__(EmbeddingService)
    calls: list[str] = []
    service.langchain_embeddings = SimpleNamespace(
        embed_query=lambda text: calls.append(f"query:{text}") or SimpleNamespace(
            vector=[0.0, 2.0],
            request_json={"mode": "query"},
            response_json={"ok": True},
        ),
        embed_document=lambda **kwargs: calls.append(f"document:{kwargs['title']}") or SimpleNamespace(
            vector=[2.0, 0.0],
            request_json={"mode": "document"},
            response_json={"ok": True},
        ),
    )
    monkeypatch.setattr(
        "app.services.indexing.embedding_service.settings",
        _settings(ai_embedding_orchestrator="langchain"),
    )

    query_result = service._embed_text(text="query", title=None, task_type="RETRIEVAL_QUERY")
    document_result = service._embed_text(text="doc", title="Doc", task_type="RETRIEVAL_DOCUMENT")

    assert query_result.vector == [0.0, 1.0]
    assert document_result.vector == [1.0, 0.0]
    assert calls == ["query:query", "document:Doc"]
