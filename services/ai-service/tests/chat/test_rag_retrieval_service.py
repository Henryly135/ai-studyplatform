from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.repositories.ai_knowledge_chunks_repository import SimilarChunkResult
from app.services.chat.rag_retrieval_service import RagRetrievalService


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
