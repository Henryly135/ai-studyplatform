from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.ai_knowledge_chunk_embeddings import AIKnowledgeChunkEmbedding
from app.models.ai_knowledge_source_embedding_statuses import AIKnowledgeSourceEmbeddingStatus
from app.models.ai_knowledge_chunks import AIKnowledgeChunk
from app.models.ai_knowledge_sources import AIKnowledgeSource, AIPublishStatus
from platform_common.errors import invalid_request_error


VALID_EMBEDDING_INDEX_STATUSES = {"queued", "running", "success", "failed"}


@dataclass(frozen=True)
class EmbeddingIndexCoverage:
    indexed_chunk_count: int
    total_chunk_count: int
    coverage: float
    status: str

    @property
    def ready(self) -> bool:
        return (
            self.status == "ready"
            and self.total_chunk_count > 0
            and self.indexed_chunk_count >= self.total_chunk_count
        )


class AIKnowledgeSourceEmbeddingStatusesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(
        self,
        *,
        source_id: int,
        embedding_model_id: str,
    ) -> AIKnowledgeSourceEmbeddingStatus | None:
        return self.session.get(
            AIKnowledgeSourceEmbeddingStatus,
            {
                "source_id": source_id,
                "embedding_model_id": embedding_model_id,
            },
        )

    def list_by_source_id(self, source_id: int) -> list[AIKnowledgeSourceEmbeddingStatus]:
        stmt = (
            select(AIKnowledgeSourceEmbeddingStatus)
            .where(AIKnowledgeSourceEmbeddingStatus.source_id == source_id)
            .order_by(AIKnowledgeSourceEmbeddingStatus.embedding_model_id.asc())
        )
        return list(self.session.scalars(stmt))

    def delete_by_source_id(self, source_id: int) -> int:
        stmt = delete(AIKnowledgeSourceEmbeddingStatus).where(
            AIKnowledgeSourceEmbeddingStatus.source_id == source_id
        )
        result = self.session.execute(stmt)
        self.session.flush()
        return int(result.rowcount or 0)

    def get_coverage(
        self,
        *,
        embedding_model_id: str,
        embedding_version: str | None = None,
        course_id: int | None = None,
        module_id: int | None = None,
    ) -> EmbeddingIndexCoverage:
        chunk_filters = [
            AIKnowledgeChunk.is_active.is_(True),
            AIKnowledgeChunk.publish_status == AIPublishStatus.PUBLISHED,
        ]
        status_filters = [
            AIKnowledgeSourceEmbeddingStatus.embedding_model_id == embedding_model_id,
            AIKnowledgeSource.publish_status == AIPublishStatus.PUBLISHED,
        ]
        if embedding_version is not None:
            status_filters.append(
                AIKnowledgeSourceEmbeddingStatus.embedding_version
                == embedding_version
            )
        if course_id is not None:
            chunk_filters.append(AIKnowledgeChunk.course_id == course_id)
            status_filters.append(AIKnowledgeSource.course_id == course_id)
        if module_id is not None:
            chunk_filters.append(AIKnowledgeChunk.module_id == module_id)
            status_filters.append(AIKnowledgeSource.module_id == module_id)

        total_chunk_count = int(
            self.session.scalar(
                select(func.count(AIKnowledgeChunk.chunk_id)).where(*chunk_filters)
            )
            or 0
        )
        embedding_filters = [
            *chunk_filters,
            AIKnowledgeChunkEmbedding.embedding_model_id == embedding_model_id,
        ]
        if embedding_version is not None:
            embedding_filters.append(
                AIKnowledgeChunkEmbedding.embedding_version
                == embedding_version
            )
        indexed_chunk_count = min(
            int(
                self.session.scalar(
                    select(func.count(AIKnowledgeChunk.chunk_id))
                    .join(
                        AIKnowledgeChunkEmbedding,
                        AIKnowledgeChunkEmbedding.chunk_id
                        == AIKnowledgeChunk.chunk_id,
                    )
                    .where(*embedding_filters)
                )
                or 0
            ),
            total_chunk_count,
        )
        source_filters = [
            AIKnowledgeSource.publish_status == AIPublishStatus.PUBLISHED,
        ]
        if course_id is not None:
            source_filters.append(AIKnowledgeSource.course_id == course_id)
        if module_id is not None:
            source_filters.append(AIKnowledgeSource.module_id == module_id)
        published_source_count = int(
            self.session.scalar(
                select(func.count(AIKnowledgeSource.source_id)).where(
                    *source_filters
                )
            )
            or 0
        )

        status_stmt = (
            select(
                AIKnowledgeSourceEmbeddingStatus.status,
                func.coalesce(
                    func.sum(AIKnowledgeSourceEmbeddingStatus.indexed_chunk_count),
                    0,
                ),
                func.count(AIKnowledgeSourceEmbeddingStatus.source_id),
            )
            .join(
                AIKnowledgeSource,
                AIKnowledgeSource.source_id == AIKnowledgeSourceEmbeddingStatus.source_id,
            )
            .where(
                *status_filters,
            )
            .group_by(AIKnowledgeSourceEmbeddingStatus.status)
        )
        status_rows = self.session.execute(status_stmt).all()
        source_counts_by_status = {
            str(status): int(source_count or 0)
            for status, _, source_count in status_rows
        }
        coverage = (
            indexed_chunk_count / total_chunk_count
            if total_chunk_count > 0
            else 0.0
        )

        if source_counts_by_status.get("running", 0) or source_counts_by_status.get("queued", 0):
            index_status = "building"
        elif source_counts_by_status.get("failed", 0):
            index_status = "partial" if indexed_chunk_count > 0 else "failed"
        elif published_source_count == 0 and total_chunk_count == 0:
            index_status = "empty"
        elif total_chunk_count > 0 and indexed_chunk_count >= total_chunk_count:
            index_status = "ready"
        else:
            index_status = "not_indexed"

        return EmbeddingIndexCoverage(
            indexed_chunk_count=indexed_chunk_count,
            total_chunk_count=total_chunk_count,
            coverage=coverage,
            status=index_status,
        )

    def upsert(
        self,
        *,
        source_id: int,
        embedding_model_id: str,
        embedding_version: str,
        status: str,
        expected_chunk_count: int,
        indexed_chunk_count: int,
        last_error: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> AIKnowledgeSourceEmbeddingStatus:
        if source_id <= 0:
            raise invalid_request_error("source_id must be greater than 0")
        if not embedding_model_id.strip():
            raise invalid_request_error("embedding_model_id is required")
        if not embedding_version.strip():
            raise invalid_request_error("embedding_version is required")
        if status not in VALID_EMBEDDING_INDEX_STATUSES:
            raise invalid_request_error(f"Unsupported embedding index status: {status}")
        if expected_chunk_count < 0 or indexed_chunk_count < 0:
            raise invalid_request_error("chunk counts must be greater than or equal to 0")
        if indexed_chunk_count > expected_chunk_count:
            raise invalid_request_error("indexed_chunk_count cannot exceed expected_chunk_count")

        row = self.get(
            source_id=source_id,
            embedding_model_id=embedding_model_id,
        )
        if row is None:
            row = AIKnowledgeSourceEmbeddingStatus(
                source_id=source_id,
                embedding_model_id=embedding_model_id,
                embedding_version=embedding_version,
                status=status,
                expected_chunk_count=expected_chunk_count,
                indexed_chunk_count=indexed_chunk_count,
                last_error=last_error,
                started_at=started_at,
                finished_at=finished_at,
            )
            self.session.add(row)
        else:
            row.embedding_version = embedding_version
            row.status = status
            row.expected_chunk_count = expected_chunk_count
            row.indexed_chunk_count = indexed_chunk_count
            row.last_error = last_error
            if started_at is not None or status in {"queued", "running"}:
                row.started_at = started_at
            if finished_at is not None or status in {"queued", "running"}:
                row.finished_at = finished_at

        self.session.flush()
        return row
