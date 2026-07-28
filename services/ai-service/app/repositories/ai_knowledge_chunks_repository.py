from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.ai_knowledge_chunk_embeddings import (
    MULTI_EMBEDDING_DIMENSION,
    AIKnowledgeChunkEmbedding,
)
from app.models.ai_knowledge_chunks import AIKnowledgeChunk
from app.models.ai_knowledge_sources import AIKnowledgeSource, AIPublishStatus, AIVisibilityScope
from platform_common.errors import invalid_request_error


class SimilarChunkResult:
    def __init__(self, *, chunk: AIKnowledgeChunk, distance: float) -> None:
        self.chunk = chunk
        self.distance = float(distance)

    @property
    def score(self) -> float:
        return max(0.0, 1.0 - self.distance)


@dataclass(frozen=True)
class ChunkCreate:
    source_id: int
    course_id: int | None
    module_id: int | None
    material_id: int | None
    chunk_index: int
    chunk_text: str
    token_count: int | None
    heading_path: str | None
    start_char: int | None
    end_char: int | None
    chunk_hash: str
    language_code: str | None
    visibility_scope: AIVisibilityScope
    publish_status: AIPublishStatus
    is_active: bool
    metadata_json: dict | list | None
    embedding_model: str | None = None
    embedding_version: str | None = None
    embedding: list[float] | None = None


@dataclass(frozen=True)
class ChunkEmbeddingCreate:
    chunk_id: int
    embedding_model_id: str
    embedding_version: str
    embedding: list[float]


class AIKnowledgeChunksRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, chunk_id: int) -> AIKnowledgeChunk | None:
        return self.session.get(AIKnowledgeChunk, chunk_id)

    def list_by_source_id(self, source_id: int) -> list[AIKnowledgeChunk]:
        stmt = (
            select(AIKnowledgeChunk)
            .where(AIKnowledgeChunk.source_id == source_id)
            .order_by(AIKnowledgeChunk.chunk_index.asc(), AIKnowledgeChunk.chunk_id.asc())
        )
        return list(self.session.scalars(stmt))

    def list_active_by_material_id(self, material_id: int) -> list[AIKnowledgeChunk]:
        stmt = (
            select(AIKnowledgeChunk)
            .where(
                AIKnowledgeChunk.material_id == material_id,
                AIKnowledgeChunk.is_active.is_(True),
            )
            .order_by(AIKnowledgeChunk.chunk_index.asc(), AIKnowledgeChunk.chunk_id.asc())
        )
        return list(self.session.scalars(stmt))

    def search_similar_chunks(
        self,
        *,
        query_embedding: list[float],
        embedding_model_id: str,
        embedding_version: str | None = None,
        course_id: int,
        module_id: int | None = None,
        top_k: int = 5,
    ) -> list[SimilarChunkResult]:
        if not query_embedding:
            raise invalid_request_error("query_embedding is required")
        if course_id <= 0:
            raise invalid_request_error("course_id must be greater than 0")
        if top_k <= 0:
            raise invalid_request_error("top_k must be greater than 0")
        if not embedding_model_id.strip():
            raise invalid_request_error("embedding_model_id is required")
        if len(query_embedding) != MULTI_EMBEDDING_DIMENSION:
            raise invalid_request_error(
                f"query_embedding must contain exactly {MULTI_EMBEDDING_DIMENSION} dimensions"
            )

        distance_expr = AIKnowledgeChunkEmbedding.embedding.cosine_distance(query_embedding)
        stmt = (
            select(AIKnowledgeChunk, distance_expr.label("distance"))
            .join(
                AIKnowledgeChunkEmbedding,
                AIKnowledgeChunkEmbedding.chunk_id == AIKnowledgeChunk.chunk_id,
            )
            .where(
                AIKnowledgeChunk.course_id == course_id,
                AIKnowledgeChunk.is_active.is_(True),
                AIKnowledgeChunk.publish_status == AIPublishStatus.PUBLISHED,
                AIKnowledgeChunkEmbedding.embedding_model_id == embedding_model_id,
            )
            .order_by(distance_expr.asc(), AIKnowledgeChunk.chunk_id.asc())
            .limit(top_k)
        )
        if embedding_version is not None:
            stmt = stmt.where(AIKnowledgeChunkEmbedding.embedding_version == embedding_version)
        if module_id is not None:
            stmt = stmt.where(AIKnowledgeChunk.module_id == module_id)

        rows = self.session.execute(stmt).all()
        return [
            SimilarChunkResult(chunk=chunk, distance=distance)
            for chunk, distance in rows
        ]

    def list_title_matched_chunks(
        self,
        *,
        query_text: str,
        embedding_model_id: str,
        embedding_version: str,
        course_id: int,
        module_id: int | None = None,
        top_k: int = 5,
    ) -> list[SimilarChunkResult]:
        if course_id <= 0:
            raise invalid_request_error("course_id must be greater than 0")
        if top_k <= 0:
            raise invalid_request_error("top_k must be greater than 0")
        if not embedding_model_id.strip() or not embedding_version.strip():
            raise invalid_request_error(
                "embedding_model_id and embedding_version are required"
            )

        normalized_query = _normalize_title_match_text(query_text)
        if not normalized_query:
            return []

        stmt = (
            select(AIKnowledgeChunk, AIKnowledgeSource)
            .join(AIKnowledgeSource, AIKnowledgeSource.source_id == AIKnowledgeChunk.source_id)
            .join(
                AIKnowledgeChunkEmbedding,
                AIKnowledgeChunkEmbedding.chunk_id == AIKnowledgeChunk.chunk_id,
            )
            .where(
                AIKnowledgeChunk.course_id == course_id,
                AIKnowledgeChunk.is_active.is_(True),
                AIKnowledgeChunk.publish_status == AIPublishStatus.PUBLISHED,
                AIKnowledgeChunkEmbedding.embedding_model_id
                == embedding_model_id,
                AIKnowledgeChunkEmbedding.embedding_version
                == embedding_version,
            )
            .order_by(AIKnowledgeChunk.chunk_index.asc(), AIKnowledgeChunk.chunk_id.asc())
        )
        if module_id is not None:
            stmt = stmt.where(AIKnowledgeChunk.module_id == module_id)

        matched: list[AIKnowledgeChunk] = []
        for chunk, source in self.session.execute(stmt).all():
            if _query_mentions_material(query_text=normalized_query, chunk=chunk, source=source):
                matched.append(chunk)
                if len(matched) >= top_k:
                    break

        return [SimilarChunkResult(chunk=chunk, distance=0.0) for chunk in matched]

    def create(
        self,
        *,
        chunk_data: ChunkCreate,
    ) -> AIKnowledgeChunk:
        chunk = AIKnowledgeChunk(
            source_id=chunk_data.source_id,
            course_id=chunk_data.course_id,
            module_id=chunk_data.module_id,
            material_id=chunk_data.material_id,
            chunk_index=chunk_data.chunk_index,
            chunk_text=chunk_data.chunk_text,
            token_count=chunk_data.token_count,
            heading_path=chunk_data.heading_path,
            start_char=chunk_data.start_char,
            end_char=chunk_data.end_char,
            chunk_hash=chunk_data.chunk_hash,
            language_code=chunk_data.language_code,
            visibility_scope=chunk_data.visibility_scope,
            publish_status=chunk_data.publish_status,
            is_active=chunk_data.is_active,
            embedding_model=chunk_data.embedding_model,
            embedding_version=chunk_data.embedding_version,
            embedding=chunk_data.embedding,
            metadata_json=chunk_data.metadata_json,
        )
        self.session.add(chunk)
        self.session.flush()
        return chunk

    def create_many(
        self,
        chunks: Sequence[ChunkCreate],
    ) -> list[AIKnowledgeChunk]:
        created_chunks: list[AIKnowledgeChunk] = []
        for chunk_data in chunks:
            chunk = AIKnowledgeChunk(
                source_id=chunk_data.source_id,
                course_id=chunk_data.course_id,
                module_id=chunk_data.module_id,
                material_id=chunk_data.material_id,
                chunk_index=chunk_data.chunk_index,
                chunk_text=chunk_data.chunk_text,
                token_count=chunk_data.token_count,
                heading_path=chunk_data.heading_path,
                start_char=chunk_data.start_char,
                end_char=chunk_data.end_char,
                chunk_hash=chunk_data.chunk_hash,
                language_code=chunk_data.language_code,
                visibility_scope=chunk_data.visibility_scope,
                publish_status=chunk_data.publish_status,
                is_active=chunk_data.is_active,
                embedding_model=chunk_data.embedding_model,
                embedding_version=chunk_data.embedding_version,
                embedding=chunk_data.embedding,
                metadata_json=chunk_data.metadata_json,
            )
            self.session.add(chunk)
            created_chunks.append(chunk)
        self.session.flush()
        return created_chunks

    def create_many_embeddings(
        self,
        embeddings: Sequence[ChunkEmbeddingCreate],
    ) -> list[AIKnowledgeChunkEmbedding]:
        created_embeddings: list[AIKnowledgeChunkEmbedding] = []
        for embedding_data in embeddings:
            if embedding_data.chunk_id <= 0:
                raise invalid_request_error("chunk_id must be greater than 0")
            if not embedding_data.embedding_model_id.strip():
                raise invalid_request_error("embedding_model_id is required")
            if not embedding_data.embedding_version.strip():
                raise invalid_request_error("embedding_version is required")
            if len(embedding_data.embedding) != MULTI_EMBEDDING_DIMENSION:
                raise invalid_request_error(
                    f"embedding must contain exactly {MULTI_EMBEDDING_DIMENSION} dimensions"
                )

            row = AIKnowledgeChunkEmbedding(
                chunk_id=embedding_data.chunk_id,
                embedding_model_id=embedding_data.embedding_model_id,
                embedding_version=embedding_data.embedding_version,
                embedding_dimension=MULTI_EMBEDDING_DIMENSION,
                embedding=embedding_data.embedding,
            )
            self.session.add(row)
            created_embeddings.append(row)

        self.session.flush()
        return created_embeddings

    def delete_embeddings_by_source_and_model(
        self,
        *,
        source_id: int,
        embedding_model_id: str,
    ) -> int:
        chunk_ids = select(AIKnowledgeChunk.chunk_id).where(
            AIKnowledgeChunk.source_id == source_id
        )
        stmt = delete(AIKnowledgeChunkEmbedding).where(
            AIKnowledgeChunkEmbedding.chunk_id.in_(chunk_ids),
            AIKnowledgeChunkEmbedding.embedding_model_id == embedding_model_id,
        )
        result = self.session.execute(stmt)
        self.session.flush()
        return int(result.rowcount or 0)

    def update(
        self,
        chunk: AIKnowledgeChunk,
        *,
        chunk_text: str,
        token_count: int | None,
        heading_path: str | None,
        start_char: int | None,
        end_char: int | None,
        chunk_hash: str,
        language_code: str | None,
        visibility_scope: AIVisibilityScope,
        publish_status: AIPublishStatus,
        is_active: bool,
        embedding_model: str | None,
        embedding_version: str | None,
        embedding: list[float] | None,
        metadata_json: dict | list | None,
    ) -> AIKnowledgeChunk:
        chunk.chunk_text = chunk_text
        chunk.token_count = token_count
        chunk.heading_path = heading_path
        chunk.start_char = start_char
        chunk.end_char = end_char
        chunk.chunk_hash = chunk_hash
        chunk.language_code = language_code
        chunk.visibility_scope = visibility_scope
        chunk.publish_status = publish_status
        chunk.is_active = is_active
        chunk.embedding_model = embedding_model
        chunk.embedding_version = embedding_version
        chunk.embedding = embedding
        chunk.metadata_json = metadata_json
        self.session.flush()
        return chunk

    def delete(self, chunk: AIKnowledgeChunk) -> None:
        self.session.delete(chunk)
        self.session.flush()

    def delete_by_source_id(self, source_id: int) -> int:
        stmt = delete(AIKnowledgeChunk).where(AIKnowledgeChunk.source_id == source_id)
        result = self.session.execute(stmt)
        self.session.flush()
        return int(result.rowcount or 0)


def _normalize_title_match_text(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _candidate_material_names(*, chunk: AIKnowledgeChunk, source: AIKnowledgeSource) -> set[str]:
    candidates: set[str] = set()
    if source.title:
        candidates.add(source.title)
        candidates.add(source.title.rsplit(".", 1)[0])
    if source.source_ref_id:
        candidates.add(source.source_ref_id)

    for metadata in (source.metadata_json, chunk.metadata_json):
        if not isinstance(metadata, dict):
            continue
        for key in ("title", "objectKey", "storagePath", "resourceUrl"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                candidates.add(value)
                candidates.add(value.rsplit("/", 1)[-1])
                candidates.add(value.rsplit("\\", 1)[-1])
                candidates.add(value.rsplit("/", 1)[-1].rsplit(".", 1)[0])
                candidates.add(value.rsplit("\\", 1)[-1].rsplit(".", 1)[0])

    return candidates


def _query_mentions_material(
    *,
    query_text: str,
    chunk: AIKnowledgeChunk,
    source: AIKnowledgeSource,
) -> bool:
    for candidate in _candidate_material_names(chunk=chunk, source=source):
        normalized_candidate = _normalize_title_match_text(candidate)
        if len(normalized_candidate) >= 4 and normalized_candidate in query_text:
            return True
    return False
