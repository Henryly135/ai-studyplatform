from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.repositories.ai_knowledge_chunks_repository import SimilarChunkResult
from app.services.chat.rag_retrieval_service import RagRetrievalService
from app.services.retrieval_readiness_service import RetrievalReadinessSnapshot


def _match(chunk_id: int, *, score: float = 0.9) -> SimilarChunkResult:
    return SimilarChunkResult(
        chunk=SimpleNamespace(
            chunk_id=chunk_id,
            source_id=100 + chunk_id,
            material_id=200 + chunk_id,
            module_id=300 + chunk_id,
            course_id=400 + chunk_id,
            chunk_index=chunk_id,
            chunk_text=f"chunk {chunk_id}",
            heading_path=f"heading {chunk_id}",
            metadata_json={"rank": chunk_id},
        ),
        distance=1 - score,
    )


def test_merge_matches_prefers_title_matches_and_deduplicates() -> None:
    # Tests retrieval merge keeps title matches first and removes duplicates.
    service = RagRetrievalService.__new__(RagRetrievalService)

    merged = service._merge_matches(
        title_matches=[_match(1), _match(2)],
        vector_matches=[_match(2), _match(3), _match(4)],
        top_k=3,
    )

    assert [match.chunk.chunk_id for match in merged] == [1, 2, 3]


def test_serialize_match_converts_repository_result_to_retrieved_chunk() -> None:
    # Tests repository match rows serialize into RetrievedChunk objects.
    service = RagRetrievalService.__new__(RagRetrievalService)

    retrieved = service._serialize_match(_match(7, score=0.8123456))

    assert retrieved.chunk_id == 7
    assert retrieved.source_id == 107
    assert retrieved.material_id == 207
    assert retrieved.module_id == 307
    assert retrieved.course_id == 407
    assert retrieved.chunk_text == "chunk 7"
    assert retrieved.heading_path == "heading 7"
    assert retrieved.score == pytest.approx(0.8123456)
    assert retrieved.distance == pytest.approx(0.1876544)
    assert retrieved.metadata_json == {"rank": 7}


def test_retrieve_uses_the_exact_embedding_model_and_version_from_chat_pair() -> None:
    service = RagRetrievalService.__new__(RagRetrievalService)
    search_calls = []
    retrieval_log_calls = []

    embedding_calls = []
    service.readiness_service = SimpleNamespace(
        resolve=lambda **_: RetrievalReadinessSnapshot(
            chat_model_id="glm:glm-4.7",
            embedding_model_id="glm:embedding-3",
            embedding_version="glm:embedding-3@1024",
            index_status="ready",
            indexed_chunk_count=8,
            total_chunk_count=8,
            index_coverage=1.0,
            allow_plain_chat=False,
        )
    )
    service.embedding_service = SimpleNamespace(
        embed_query=lambda **kwargs: (
            embedding_calls.append(kwargs)
            or SimpleNamespace(
            vector=[0.03125] * 1024,
            embedding_model_id="glm:embedding-3",
            embedding_version="glm:embedding-3@1024",
        )
        )
    )

    class FakeChunkRepository:
        def list_title_matched_chunks(self, **kwargs):
            search_calls.append({"title": kwargs})
            return []

        def search_similar_chunks(self, **kwargs):
            search_calls.append(kwargs)
            return []

    service.chunk_repository = FakeChunkRepository()
    service.retrieval_logs = SimpleNamespace(
        create=lambda **kwargs: retrieval_log_calls.append(kwargs)
    )

    result = service.retrieve(
        user_id=7,
        query_text="What is a vector index?",
        course_id=11,
        module_id=13,
        session_id=17,
        message_id=19,
        top_k=5,
        chat_model_id="glm:glm-4.7",
        model_user_id=7,
        readiness_purpose="chat",
    )

    assert embedding_calls == [
        {
            "text": "What is a vector index?",
            "embedding_model_id": "glm:embedding-3",
        }
    ]
    assert search_calls[0]["title"]["embedding_model_id"] == "glm:embedding-3"
    assert search_calls[0]["title"]["embedding_version"] == "glm:embedding-3@1024"
    assert search_calls[1]["embedding_model_id"] == "glm:embedding-3"
    assert search_calls[1]["embedding_version"] == "glm:embedding-3@1024"
    assert search_calls[1]["course_id"] == 11
    assert search_calls[1]["module_id"] == 13
    assert result.query_embedding_model == "glm:embedding-3"
    assert result.query_embedding_version == "glm:embedding-3@1024"
    assert result.chat_model_id == "glm:glm-4.7"
    assert retrieval_log_calls[0]["query_embedding_model"] == "glm:embedding-3"


def test_retrieve_skips_embedding_and_search_for_empty_chat_scope() -> None:
    service = RagRetrievalService.__new__(RagRetrievalService)
    service.readiness_service = SimpleNamespace(
        resolve=lambda **_: RetrievalReadinessSnapshot(
            chat_model_id="glm:glm-4.7",
            embedding_model_id="glm:embedding-3",
            embedding_version="glm:embedding-3@1024",
            index_status="empty",
            indexed_chunk_count=0,
            total_chunk_count=0,
            index_coverage=0.0,
            allow_plain_chat=True,
        )
    )
    service.embedding_service = SimpleNamespace(
        embed_query=lambda **_: pytest.fail("empty scope must not invoke embeddings")
    )
    service.chunk_repository = SimpleNamespace(
        list_title_matched_chunks=lambda **_: pytest.fail("empty scope must not search"),
        search_similar_chunks=lambda **_: pytest.fail("empty scope must not search"),
    )
    retrieval_log_calls = []
    service.retrieval_logs = SimpleNamespace(
        create=lambda **kwargs: retrieval_log_calls.append(kwargs)
    )

    result = service.retrieve(
        user_id=7,
        model_user_id=7,
        query_text="What is covered?",
        course_id=11,
        module_id=13,
        session_id=17,
        message_id=19,
        top_k=5,
        readiness_purpose="chat",
    )

    assert result.retrieved_chunks == []
    assert result.index_status == "empty"
    assert result.retrieval_trace_json["retrievalMode"] == "ordinary_chat_fallback"
    assert retrieval_log_calls[0]["retrieval_mode"] == "ordinary_chat_fallback"


@pytest.mark.parametrize("readiness_purpose", ["chat", "quiz"])
def test_query_embedding_runtime_failure_is_a_stable_rag_provider_error(
    readiness_purpose,
) -> None:
    service = RagRetrievalService.__new__(RagRetrievalService)
    service.readiness_service = SimpleNamespace(
        resolve=lambda **_: RetrievalReadinessSnapshot(
            chat_model_id="glm:glm-4.7",
            embedding_model_id="glm:embedding-3",
            embedding_version="glm:embedding-3@1024",
            index_status="ready",
            indexed_chunk_count=8,
            total_chunk_count=8,
            index_coverage=1.0,
            allow_plain_chat=False,
        )
    )

    def raise_runtime_failure(**_):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AI_EMBEDDING_PROVIDER_UNAVAILABLE",
                "message": "provider timeout",
            },
        )

    service.embedding_service = SimpleNamespace(
        embed_query=raise_runtime_failure
    )
    service.chunk_repository = SimpleNamespace(
        list_title_matched_chunks=lambda **_: pytest.fail(
            "provider failure must stop before retrieval"
        ),
        search_similar_chunks=lambda **_: pytest.fail(
            "provider failure must stop before retrieval"
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.retrieve(
            user_id=7,
            model_user_id=(
                7 if readiness_purpose == "chat" else None
            ),
            query_text="What is covered?",
            course_id=11,
            module_id=13,
            session_id=17,
            message_id=19,
            top_k=5,
            readiness_purpose=readiness_purpose,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "AI_RAG_PROVIDER_UNAVAILABLE"


def test_query_embedding_quota_error_preserves_429() -> None:
    service = RagRetrievalService.__new__(RagRetrievalService)
    service.readiness_service = SimpleNamespace(
        resolve=lambda **_: RetrievalReadinessSnapshot(
            chat_model_id="glm:glm-4.7",
            embedding_model_id="glm:embedding-3",
            embedding_version="glm:embedding-3@1024",
            index_status="ready",
            indexed_chunk_count=8,
            total_chunk_count=8,
            index_coverage=1.0,
            allow_plain_chat=False,
        )
    )
    service.embedding_service = SimpleNamespace(
        embed_query=lambda **_: (_ for _ in ()).throw(
            HTTPException(
                status_code=429,
                detail={
                    "code": "AI_QUOTA_EXCEEDED",
                    "message": "embedding quota exceeded",
                },
            )
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        service.retrieve(
            user_id=7,
            model_user_id=7,
            query_text="What is covered?",
            course_id=11,
            module_id=13,
            session_id=17,
            message_id=19,
            top_k=5,
            readiness_purpose="chat",
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["code"] == "AI_QUOTA_EXCEEDED"
