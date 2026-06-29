from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.ai_knowledge_sources import (
    AIKnowledgeSource,
    AIKnowledgeSourceType,
    AIPublishStatus,
    AIVisibilityScope,
)
from app.repositories.ai_knowledge_chunks_repository import AIKnowledgeChunksRepository, ChunkCreate
from app.repositories.ai_knowledge_sources_repository import AIKnowledgeSourcesRepository
from platform_common.errors import invalid_request_error


@dataclass(frozen=True)
class SourceUpsert:
    source_type: AIKnowledgeSourceType
    source_ref_id: str
    course_id: int | None
    module_id: int | None
    material_id: int | None
    title: str | None
    content_text: str
    content_markdown: str | None
    language_code: str | None
    visibility_scope: AIVisibilityScope
    publish_status: AIPublishStatus
    content_hash: str
    embedding_model: str | None
    embedding_version: str | None
    source_version: str | None
    metadata_json: dict | list | None
    created_by: int | None
    updated_by: int | None
    origin_event_id: str | None


@dataclass(frozen=True)
class KnowledgeIndexingResult:
    source: AIKnowledgeSource
    source_created: bool
    deleted_chunk_count: int
    chunk_count: int


@dataclass(frozen=True)
class KnowledgeDeleteResult:
    deleted_source_count: int
    deleted_chunk_count: int


@dataclass(frozen=True)
class KnowledgePublishSyncResult:
    updated_source_count: int
    updated_chunk_count: int


class KnowledgeIndexingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sources = AIKnowledgeSourcesRepository(session)
        self.chunks = AIKnowledgeChunksRepository(session)

    def replace_source_chunks(
        self,
        *,
        source_data: SourceUpsert,
        chunks: list[ChunkCreate],
    ) -> KnowledgeIndexingResult:
        self._validate_source_data(source_data=source_data)
        self._validate_chunks(chunks=chunks)

        source, source_created = self._upsert_source(source_data=source_data)
        deleted_chunk_count = self.chunks.delete_by_source_id(source.source_id)

        prepared_chunks = [
            self._bind_chunk_to_source(source=source, chunk=chunk)
            for chunk in chunks
        ]
        created_chunks = self.chunks.create_many(prepared_chunks)

        self.session.flush()
        return KnowledgeIndexingResult(
            source=source,
            source_created=source_created,
            deleted_chunk_count=deleted_chunk_count,
            chunk_count=len(created_chunks),
        )

    def delete_source(
        self,
        *,
        source_type: AIKnowledgeSourceType,
        source_ref_id: str,
    ) -> int:
        return self.sources.delete_by_type_and_ref(
            source_type=source_type,
            source_ref_id=source_ref_id,
        )

    def delete_material_source(self, *, material_id: int) -> KnowledgeDeleteResult:
        sources = self.sources.list_by_material_id(material_id)
        deleted_source_count = 0
        deleted_chunk_count = 0

        for source in sources:
            deleted_chunk_count += self.chunks.delete_by_source_id(source.source_id)
            self.sources.delete(source)
            deleted_source_count += 1

        self.session.flush()
        return KnowledgeDeleteResult(
            deleted_source_count=deleted_source_count,
            deleted_chunk_count=deleted_chunk_count,
        )

    def publish_module_sources(self, *, module_ids: list[int]) -> KnowledgePublishSyncResult:
        updated_source_count = 0
        updated_chunk_count = 0

        for module_id in module_ids:
            for source in self.sources.list_by_module_id(module_id):
                if source.publish_status != AIPublishStatus.PUBLISHED:
                    source.publish_status = AIPublishStatus.PUBLISHED
                    updated_source_count += 1

                for chunk in self.chunks.list_by_source_id(source.source_id):
                    if chunk.publish_status != AIPublishStatus.PUBLISHED:
                        chunk.publish_status = AIPublishStatus.PUBLISHED
                        updated_chunk_count += 1

        self.session.flush()
        return KnowledgePublishSyncResult(
            updated_source_count=updated_source_count,
            updated_chunk_count=updated_chunk_count,
        )

    def _validate_source_data(self, *, source_data: SourceUpsert) -> None:
        if not source_data.source_ref_id.strip():
            raise invalid_request_error("source_ref_id is required")
        if not source_data.content_text.strip():
            raise invalid_request_error("content_text is required")
        if not source_data.content_hash.strip():
            raise invalid_request_error("content_hash is required")

    def _validate_chunks(self, *, chunks: list[ChunkCreate]) -> None:
        seen_indexes: set[int] = set()
        for chunk in chunks:
            if chunk.chunk_index < 0:
                raise invalid_request_error("chunk_index must be greater than or equal to 0")
            if chunk.chunk_index in seen_indexes:
                raise invalid_request_error("chunk_index values must be unique within a source")
            seen_indexes.add(chunk.chunk_index)

            if not chunk.chunk_text.strip():
                raise invalid_request_error("chunk_text is required for every chunk")
            if not chunk.chunk_hash.strip():
                raise invalid_request_error("chunk_hash is required for every chunk")
            if not chunk.embedding_model.strip():
                raise invalid_request_error("embedding_model is required for every chunk")
            if not chunk.embedding:
                raise invalid_request_error("embedding must contain at least one dimension for every chunk")

    def _upsert_source(
        self,
        *,
        source_data: SourceUpsert,
    ) -> tuple[AIKnowledgeSource, bool]:
        existing_source = self.sources.get_by_type_and_ref(
            source_type=source_data.source_type,
            source_ref_id=source_data.source_ref_id,
        )
        if existing_source is None:
            return (
                self.sources.create(
                    source_type=source_data.source_type,
                    source_ref_id=source_data.source_ref_id,
                    course_id=source_data.course_id,
                    module_id=source_data.module_id,
                    material_id=source_data.material_id,
                    title=source_data.title,
                    content_text=source_data.content_text,
                    content_markdown=source_data.content_markdown,
                    language_code=source_data.language_code,
                    visibility_scope=source_data.visibility_scope,
                    publish_status=source_data.publish_status,
                    content_hash=source_data.content_hash,
                    embedding_model=source_data.embedding_model,
                    embedding_version=source_data.embedding_version,
                    source_version=source_data.source_version,
                    metadata_json=source_data.metadata_json,
                    created_by=source_data.created_by,
                    updated_by=source_data.updated_by,
                    origin_event_id=source_data.origin_event_id,
                ),
                True,
            )

        updated_source = self.sources.update(
            existing_source,
            title=source_data.title,
            content_text=source_data.content_text,
            content_markdown=source_data.content_markdown,
            language_code=source_data.language_code,
            visibility_scope=source_data.visibility_scope,
            publish_status=source_data.publish_status,
            content_hash=source_data.content_hash,
            embedding_model=source_data.embedding_model,
            embedding_version=source_data.embedding_version,
            source_version=source_data.source_version,
            metadata_json=source_data.metadata_json,
            updated_by=source_data.updated_by,
            origin_event_id=source_data.origin_event_id,
        )
        return updated_source, False

    def _bind_chunk_to_source(
        self,
        *,
        source: AIKnowledgeSource,
        chunk: ChunkCreate,
    ) -> ChunkCreate:
        return ChunkCreate(
            source_id=source.source_id,
            course_id=source.course_id,
            module_id=source.module_id,
            material_id=source.material_id,
            chunk_index=chunk.chunk_index,
            chunk_text=chunk.chunk_text,
            token_count=chunk.token_count,
            heading_path=chunk.heading_path,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            chunk_hash=chunk.chunk_hash,
            language_code=chunk.language_code,
            visibility_scope=source.visibility_scope,
            publish_status=source.publish_status,
            is_active=chunk.is_active,
            embedding_model=chunk.embedding_model,
            embedding_version=chunk.embedding_version,
            embedding=chunk.embedding,
            metadata_json=chunk.metadata_json,
        )
