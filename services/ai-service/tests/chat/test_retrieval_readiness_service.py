from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.repositories.ai_knowledge_source_embedding_statuses_repository import (
    EmbeddingIndexCoverage,
)
from app.services.retrieval_readiness_service import RetrievalReadinessService


def _model(
    model_id: str,
    *,
    paired_embedding_model_id: str | None = None,
    embedding_dimension: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        model_id=model_id,
        paired_embedding_model_id=paired_embedding_model_id,
        embedding_dimension=embedding_dimension,
        supports_embedding=embedding_dimension is not None,
        supports_rag_indexing=embedding_dimension is not None,
    )


def _service(
    coverage: EmbeddingIndexCoverage,
) -> tuple[RetrievalReadinessService, dict[str, object]]:
    calls: dict[str, object] = {}
    chat_model = _model(
        "glm:glm-4.7",
        paired_embedding_model_id="glm:embedding-3",
    )
    embedding_model = _model(
        "glm:embedding-3",
        embedding_dimension=1024,
    )

    class FakeCatalog:
        repo = SimpleNamespace(
            get_model=lambda model_id: (
                embedding_model
                if model_id == embedding_model.model_id
                else None
            )
        )

        def resolve_chat_model(self, **kwargs):
            calls["chat"] = kwargs
            return SimpleNamespace(model=chat_model)

        def resolve_embedding_model(self, **kwargs):
            calls["embedding"] = kwargs
            return SimpleNamespace(model=embedding_model)

    class FakeCoverageRepository:
        def get_coverage(self, **kwargs):
            calls["coverage"] = kwargs
            return coverage

    service = RetrievalReadinessService.__new__(RetrievalReadinessService)
    service.catalog = FakeCatalog()
    service.coverage_repository = FakeCoverageRepository()
    return service, calls


def test_ready_snapshot_checks_the_exact_paired_embedding_version() -> None:
    service, calls = _service(
        EmbeddingIndexCoverage(
            indexed_chunk_count=8,
            total_chunk_count=8,
            coverage=1.0,
            status="ready",
        )
    )

    snapshot = service.resolve(
        model_user_id=7,
        requested_chat_model_id="glm:glm-4.7",
        course_id=11,
        module_id=22,
        purpose="chat",
    )

    assert calls["chat"] == {
        "user_id": 7,
        "requested_model_id": "glm:glm-4.7",
    }
    assert calls["coverage"] == {
        "embedding_model_id": "glm:embedding-3",
        "embedding_version": "glm:embedding-3@1024",
        "course_id": 11,
        "module_id": 22,
    }
    assert calls["embedding"] == {
        "embedding_model_id": "glm:embedding-3",
    }
    assert snapshot.chat_model_id == "glm:glm-4.7"
    assert snapshot.embedding_model_id == "glm:embedding-3"
    assert snapshot.embedding_version == "glm:embedding-3@1024"
    assert snapshot.index_status == "ready"
    assert snapshot.allow_plain_chat is False


def test_chat_allows_plain_fallback_only_when_scope_is_empty() -> None:
    service, calls = _service(
        EmbeddingIndexCoverage(
            indexed_chunk_count=0,
            total_chunk_count=0,
            coverage=0.0,
            status="empty",
        )
    )

    snapshot = service.resolve(
        model_user_id=7,
        requested_chat_model_id=None,
        course_id=11,
        module_id=None,
        purpose="chat",
    )

    assert snapshot.allow_plain_chat is True
    assert "embedding" not in calls


@pytest.mark.parametrize("status", ["building", "partial", "not_indexed", "failed"])
def test_chat_blocks_every_non_ready_non_empty_index_status(status: str) -> None:
    service, _ = _service(
        EmbeddingIndexCoverage(
            indexed_chunk_count=2 if status == "partial" else 0,
            total_chunk_count=8,
            coverage=0.25 if status == "partial" else 0.0,
            status=status,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        service.resolve(
            model_user_id=7,
            requested_chat_model_id=None,
            course_id=11,
            module_id=22,
            purpose="chat",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "AI_RAG_INDEX_NOT_READY"
    assert status in exc_info.value.detail["message"]


def test_quiz_rejects_an_empty_material_scope_with_a_clear_error() -> None:
    service, _ = _service(
        EmbeddingIndexCoverage(
            indexed_chunk_count=0,
            total_chunk_count=0,
            coverage=0.0,
            status="empty",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        service.resolve(
            model_user_id=None,
            requested_chat_model_id=None,
            course_id=11,
            module_id=22,
            purpose="quiz",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "AI_RAG_NO_MATERIALS"
