from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.ai_knowledge_sources import AIKnowledgeSourceType, AIPublishStatus, AIVisibilityScope
from app.repositories.ai_knowledge_chunks_repository import ChunkCreate
from app.services.indexing.knowledge_indexing_service import KnowledgeIndexingService, SourceUpsert


class FakeSession:
    def __init__(self) -> None:
        self.flush_calls = 0

    def flush(self) -> None:
        self.flush_calls += 1


def _source_data(source_ref_id: str = "material-1", content_text: str = "content", content_hash: str = "hash") -> SourceUpsert:
    return SourceUpsert(
        source_type=AIKnowledgeSourceType.MATERIAL,
        source_ref_id=source_ref_id,
        course_id=1,
        module_id=2,
        material_id=3,
        title="Lesson",
        content_text=content_text,
        content_markdown=None,
        language_code=None,
        visibility_scope=AIVisibilityScope.COURSE_ONLY,
        publish_status=AIPublishStatus.DRAFT,
        content_hash=content_hash,
        embedding_model="embedding",
        embedding_version="v1",
        source_version="object-key",
        metadata_json={},
        created_by=None,
        updated_by=None,
        origin_event_id=None,
    )


def _chunk(index: int = 0, text: str = "chunk", chunk_hash: str = "hash") -> ChunkCreate:
    return ChunkCreate(
        source_id=0,
        course_id=None,
        module_id=None,
        material_id=None,
        chunk_index=index,
        chunk_text=text,
        token_count=None,
        heading_path=None,
        start_char=0,
        end_char=5,
        chunk_hash=chunk_hash,
        language_code=None,
        visibility_scope=AIVisibilityScope.COURSE_ONLY,
        publish_status=AIPublishStatus.DRAFT,
        is_active=True,
        metadata_json={},
    )


def test_replace_source_chunks_creates_source_binds_chunks_and_flushes() -> None:
    # Tests source replacement validates data, creates source, binds chunks, and flushes.
    session = FakeSession()
    service = KnowledgeIndexingService(session)
    source = SimpleNamespace(
        source_id=99,
        course_id=1,
        module_id=2,
        material_id=3,
        visibility_scope=AIVisibilityScope.COURSE_ONLY,
        publish_status=AIPublishStatus.PUBLISHED,
    )
    service.sources = SimpleNamespace(
        get_by_type_and_ref=lambda **_: None,
        create=lambda **_: source,
    )
    service.chunks = SimpleNamespace(
        delete_by_source_id=lambda source_id: 2,
        create_many=lambda chunks: chunks,
    )
    service.embedding_statuses = SimpleNamespace(delete_by_source_id=lambda source_id: 1)

    result = service.replace_source_chunks(source_data=_source_data(), chunks=[_chunk()])

    assert result.source is source
    assert result.source_created is True
    assert result.deleted_chunk_count == 2
    assert result.chunk_count == 1
    assert result.created_chunks[0].source_id == 99
    assert session.flush_calls == 1


def test_replace_source_chunks_updates_existing_source() -> None:
    # Tests source replacement updates an existing source instead of creating one.
    service = KnowledgeIndexingService(FakeSession())
    existing = SimpleNamespace(
        source_id=99,
        course_id=1,
        module_id=2,
        material_id=3,
        visibility_scope=AIVisibilityScope.COURSE_ONLY,
        publish_status=AIPublishStatus.PUBLISHED,
    )
    service.sources = SimpleNamespace(
        get_by_type_and_ref=lambda **_: existing,
        update=lambda source, **_: source,
    )
    service.chunks = SimpleNamespace(delete_by_source_id=lambda source_id: 0, create_many=lambda chunks: chunks)
    service.embedding_statuses = SimpleNamespace(delete_by_source_id=lambda source_id: 0)

    result = service.replace_source_chunks(source_data=_source_data(), chunks=[_chunk()])

    assert result.source is existing
    assert result.source_created is False


@pytest.mark.parametrize(
    "source_data",
    [_source_data(source_ref_id=" "), _source_data(content_text=" "), _source_data(content_hash=" ")],
)
def test_validate_source_data_rejects_required_blank_fields(source_data) -> None:
    # Tests source validation rejects blank ref id, content text, and content hash.
    service = KnowledgeIndexingService(FakeSession())

    with pytest.raises(Exception):
        service._validate_source_data(source_data=source_data)


@pytest.mark.parametrize(
    "chunk",
    [_chunk(index=-1), _chunk(text=" "), _chunk(chunk_hash=" ")],
)
def test_validate_chunks_rejects_invalid_chunk_fields(chunk) -> None:
    # Tests chunk validation rejects negative indexes, blanks, and empty embeddings.
    service = KnowledgeIndexingService(FakeSession())

    with pytest.raises(Exception):
        service._validate_chunks(chunks=[chunk])


def test_validate_chunks_rejects_duplicate_indexes() -> None:
    # Tests chunk validation rejects duplicate chunk indexes in one source.
    service = KnowledgeIndexingService(FakeSession())

    with pytest.raises(Exception):
        service._validate_chunks(chunks=[_chunk(index=1), _chunk(index=1)])


def test_write_source_embeddings_requires_exact_chunk_indexes() -> None:
    service = KnowledgeIndexingService(FakeSession())
    service.chunks = SimpleNamespace(
        list_by_source_id=lambda source_id: [
            SimpleNamespace(chunk_id=10, chunk_index=0),
            SimpleNamespace(chunk_id=11, chunk_index=1),
        ],
    )

    with pytest.raises(Exception):
        service.write_source_embeddings(
            source_id=1,
            embedding_model_id="glm:embedding-3",
            embedding_version="glm:embedding-3@1024",
            embeddings_by_chunk_index={0: [0.1] * 1024},
        )


def test_write_source_embeddings_persists_model_specific_rows_and_success_status() -> None:
    session = FakeSession()
    service = KnowledgeIndexingService(session)
    created_rows = []
    statuses = []
    service.chunks = SimpleNamespace(
        list_by_source_id=lambda source_id: [
            SimpleNamespace(chunk_id=10, chunk_index=0),
            SimpleNamespace(chunk_id=11, chunk_index=1),
        ],
        create_many_embeddings=lambda rows: created_rows.extend(rows) or rows,
        delete_embeddings_by_source_and_model=lambda **_: 0,
    )
    service.embedding_statuses = SimpleNamespace(
        upsert=lambda **kwargs: statuses.append(kwargs),
    )

    written = service.write_source_embeddings(
        source_id=1,
        embedding_model_id="glm:embedding-3",
        embedding_version="glm:embedding-3@1024",
        embeddings_by_chunk_index={
            0: [0.1] * 1024,
            1: [0.2] * 1024,
        },
    )

    assert written == 2
    assert [row.chunk_id for row in created_rows] == [10, 11]
    assert all(row.embedding_model_id == "glm:embedding-3" for row in created_rows)
    assert statuses[0]["status"] == "success"
    assert statuses[0]["indexed_chunk_count"] == 2


def test_mark_source_index_stale_deactivates_old_chunks_and_records_pending_version() -> None:
    session = FakeSession()
    service = KnowledgeIndexingService(session)
    source = SimpleNamespace(
        source_id=9,
        metadata_json={"title": "Old lesson"},
    )
    active_chunk = SimpleNamespace(is_active=True)
    inactive_chunk = SimpleNamespace(is_active=False)
    service.chunks = SimpleNamespace(
        list_by_source_id=lambda source_id: [active_chunk, inactive_chunk]
    )
    stale_status_updates = []
    service.embedding_statuses = SimpleNamespace(
        list_by_source_id=lambda source_id: [
            SimpleNamespace(
                embedding_model_id="glm:embedding-3",
                embedding_version="glm:embedding-3@1024",
                expected_chunk_count=2,
                started_at="started",
            )
        ],
        upsert=lambda **kwargs: stale_status_updates.append(kwargs),
    )

    changed = service.mark_source_index_stale(
        source=source,
        pending_content_hash="new-content-hash",
        pending_source_version="materials/new.pdf",
    )

    assert changed == 1
    assert active_chunk.is_active is False
    assert inactive_chunk.is_active is False
    assert source.metadata_json["title"] == "Old lesson"
    assert source.metadata_json["indexStale"] is True
    assert source.metadata_json["pendingContentHash"] == "new-content-hash"
    assert source.metadata_json["pendingSourceVersion"] == "materials/new.pdf"
    assert stale_status_updates[0]["status"] == "failed"
    assert stale_status_updates[0]["indexed_chunk_count"] == 0
    assert session.flush_calls == 1


def test_delete_material_source_deletes_sources_and_chunks() -> None:
    # Tests material source deletion removes chunks before deleting each source.
    session = FakeSession()
    service = KnowledgeIndexingService(session)
    sources = [SimpleNamespace(source_id=1), SimpleNamespace(source_id=2)]
    deleted_sources = []
    service.sources = SimpleNamespace(list_by_material_id=lambda material_id: sources, delete=lambda source: deleted_sources.append(source))
    service.chunks = SimpleNamespace(delete_by_source_id=lambda source_id: source_id)

    result = service.delete_material_source(material_id=3)

    assert result.deleted_source_count == 2
    assert result.deleted_chunk_count == 3
    assert deleted_sources == sources
    assert session.flush_calls == 1


def test_publish_module_sources_updates_sources_and_chunks() -> None:
    # Tests publishing module sources promotes draft sources and chunks to published.
    session = FakeSession()
    service = KnowledgeIndexingService(session)
    source = SimpleNamespace(source_id=1, publish_status=AIPublishStatus.DRAFT)
    chunk = SimpleNamespace(publish_status=AIPublishStatus.DRAFT)
    service.sources = SimpleNamespace(list_by_module_id=lambda module_id: [source])
    service.chunks = SimpleNamespace(list_by_source_id=lambda source_id: [chunk])

    result = service.publish_module_sources(module_ids=[2])

    assert source.publish_status == AIPublishStatus.PUBLISHED
    assert chunk.publish_status == AIPublishStatus.PUBLISHED
    assert result.updated_source_count == 1
    assert result.updated_chunk_count == 1
