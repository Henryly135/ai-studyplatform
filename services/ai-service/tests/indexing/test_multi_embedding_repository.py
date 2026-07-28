from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.repositories.ai_knowledge_chunks_repository import (
    AIKnowledgeChunksRepository,
    ChunkEmbeddingCreate,
)
from app.repositories.ai_knowledge_source_embedding_statuses_repository import (
    AIKnowledgeSourceEmbeddingStatusesRepository,
)


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.flush_calls = 0

    def add(self, row) -> None:
        self.added.append(row)

    def flush(self) -> None:
        self.flush_calls += 1


class CoverageFakeSession:
    def __init__(
        self,
        *,
        total_chunks: int,
        indexed_chunks: int | None = None,
        published_sources: int | None = None,
        status_rows: list[tuple[str, int, int]],
    ) -> None:
        inferred_published_sources = (
            published_sources
            if published_sources is not None
            else (
                sum(source_count for _, _, source_count in status_rows)
                if status_rows
                else (1 if total_chunks > 0 else 0)
            )
        )
        self.scalar_values = iter(
            [
                total_chunks,
                total_chunks if indexed_chunks is None else indexed_chunks,
                inferred_published_sources,
            ]
        )
        self.status_rows = status_rows

    def scalar(self, _statement):
        return next(self.scalar_values)

    def execute(self, _statement):
        return SimpleNamespace(all=lambda: self.status_rows)


def test_create_many_embeddings_writes_full_model_id_and_fixed_dimension() -> None:
    session = FakeSession()
    repository = AIKnowledgeChunksRepository(session)

    rows = repository.create_many_embeddings(
        [
            ChunkEmbeddingCreate(
                chunk_id=1,
                embedding_model_id="glm:embedding-3",
                embedding_version="glm:embedding-3@1024",
                embedding=[0.1] * 1024,
            )
        ]
    )

    assert rows == session.added
    assert rows[0].embedding_model_id == "glm:embedding-3"
    assert rows[0].embedding_dimension == 1024
    assert len(rows[0].embedding) == 1024
    assert session.flush_calls == 1


@pytest.mark.parametrize(
    "payload",
    [
        ChunkEmbeddingCreate(
            chunk_id=0,
            embedding_model_id="glm:embedding-3",
            embedding_version="glm:embedding-3@1024",
            embedding=[0.1] * 1024,
        ),
        ChunkEmbeddingCreate(
            chunk_id=1,
            embedding_model_id=" ",
            embedding_version="glm:embedding-3@1024",
            embedding=[0.1] * 1024,
        ),
        ChunkEmbeddingCreate(
            chunk_id=1,
            embedding_model_id="glm:embedding-3",
            embedding_version=" ",
            embedding=[0.1] * 1024,
        ),
        ChunkEmbeddingCreate(
            chunk_id=1,
            embedding_model_id="glm:embedding-3",
            embedding_version="glm:embedding-3@1024",
            embedding=[0.1] * 1536,
        ),
    ],
)
def test_create_many_embeddings_rejects_invalid_identity_or_dimension(payload) -> None:
    repository = AIKnowledgeChunksRepository(FakeSession())

    with pytest.raises(Exception):
        repository.create_many_embeddings([payload])


def test_embedding_status_upsert_preserves_running_start_time_on_success() -> None:
    session = FakeSession()
    repository = AIKnowledgeSourceEmbeddingStatusesRepository(session)
    existing = SimpleNamespace(
        embedding_version="old",
        status="running",
        expected_chunk_count=2,
        indexed_chunk_count=0,
        last_error=None,
        started_at="started",
        finished_at=None,
    )
    repository.get = lambda **_: existing

    row = repository.upsert(
        source_id=1,
        embedding_model_id="gemini:gemini-embedding-001",
        embedding_version="gemini:gemini-embedding-001@1024",
        status="success",
        expected_chunk_count=2,
        indexed_chunk_count=2,
        finished_at="finished",
    )

    assert row.started_at == "started"
    assert row.finished_at == "finished"
    assert row.status == "success"


def test_embedding_coverage_reports_empty_scope_as_chat_safe() -> None:
    repository = AIKnowledgeSourceEmbeddingStatusesRepository(
        CoverageFakeSession(total_chunks=0, status_rows=[])
    )

    coverage = repository.get_coverage(
        embedding_model_id="glm:embedding-3",
        course_id=1,
        module_id=2,
    )

    assert coverage.total_chunk_count == 0
    assert coverage.coverage == 0
    assert coverage.status == "empty"


def test_embedding_coverage_keeps_zero_chunk_failed_source_unavailable() -> None:
    repository = AIKnowledgeSourceEmbeddingStatusesRepository(
        CoverageFakeSession(total_chunks=0, status_rows=[("failed", 0, 1)])
    )

    coverage = repository.get_coverage(
        embedding_model_id="glm:embedding-3",
        course_id=1,
        module_id=2,
    )

    assert coverage.status == "failed"
    assert coverage.ready is False


def test_embedding_coverage_does_not_treat_unindexed_published_source_as_empty() -> None:
    repository = AIKnowledgeSourceEmbeddingStatusesRepository(
        CoverageFakeSession(
            total_chunks=0,
            published_sources=1,
            status_rows=[],
        )
    )

    coverage = repository.get_coverage(
        embedding_model_id="glm:embedding-3",
        embedding_version="glm:embedding-3@1024",
        course_id=1,
        module_id=2,
    )

    assert coverage.status == "not_indexed"
    assert coverage.ready is False


def test_embedding_coverage_is_not_ready_when_any_source_failed() -> None:
    repository = AIKnowledgeSourceEmbeddingStatusesRepository(
        CoverageFakeSession(
            total_chunks=2,
            indexed_chunks=2,
            status_rows=[("success", 2, 1), ("failed", 0, 1)],
        )
    )

    coverage = repository.get_coverage(
        embedding_model_id="glm:embedding-3",
        course_id=1,
    )

    assert coverage.coverage == 1
    assert coverage.status == "partial"
    assert coverage.ready is False


def test_embedding_coverage_counts_actual_active_vectors_not_status_totals() -> None:
    repository = AIKnowledgeSourceEmbeddingStatusesRepository(
        CoverageFakeSession(
            total_chunks=10,
            indexed_chunks=0,
            status_rows=[("success", 10, 1)],
        )
    )

    coverage = repository.get_coverage(
        embedding_model_id="glm:embedding-3",
        embedding_version="glm:embedding-3@1024",
        course_id=1,
    )

    assert coverage.indexed_chunk_count == 0
    assert coverage.coverage == 0
    assert coverage.status == "not_indexed"
    assert coverage.ready is False
