from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.repositories.ai_knowledge_source_embedding_statuses_repository import (
    AIKnowledgeSourceEmbeddingStatusesRepository,
)
from app.services.providers.model_service import AIModelCatalogService
from app.services.providers.types import ProviderConfigurationError
from platform_common.errors import http_error, invalid_request_error


RetrievalPurpose = Literal["chat", "quiz"]


@dataclass(frozen=True)
class RetrievalReadinessSnapshot:
    """One authoritative model pair and its exact index coverage."""

    chat_model_id: str
    embedding_model_id: str
    embedding_version: str
    index_status: str
    indexed_chunk_count: int
    total_chunk_count: int
    index_coverage: float
    allow_plain_chat: bool


class RetrievalReadinessService:
    """Resolves the model pair once and enforces grounded-retrieval readiness."""

    def __init__(self, session: Session) -> None:
        self.catalog = AIModelCatalogService(session)
        self.catalog.ensure_seeded()
        self.coverage_repository = AIKnowledgeSourceEmbeddingStatusesRepository(
            session
        )

    def resolve(
        self,
        *,
        model_user_id: int | None,
        requested_chat_model_id: str | None,
        course_id: int,
        module_id: int | None,
        purpose: RetrievalPurpose,
    ) -> RetrievalReadinessSnapshot:
        if purpose not in {"chat", "quiz"}:
            raise invalid_request_error(
                f"Unsupported retrieval readiness purpose: {purpose}"
            )

        try:
            chat = self.catalog.resolve_chat_model(
                user_id=model_user_id,
                requested_model_id=requested_chat_model_id,
            )
        except ProviderConfigurationError as exc:
            raise self._provider_unavailable_error() from exc

        embedding_model_id = chat.model.paired_embedding_model_id
        embedding_model = (
            self.catalog.repo.get_model(embedding_model_id)
            if embedding_model_id
            else None
        )
        dimension = (
            int(embedding_model.embedding_dimension or 0)
            if embedding_model is not None
            else 0
        )
        if (
            embedding_model is None
            or not embedding_model.supports_embedding
            or not embedding_model.supports_rag_indexing
            or dimension <= 0
        ):
            raise self._provider_unavailable_error()

        embedding_version = f"{embedding_model.model_id}@{dimension}"
        coverage = self.coverage_repository.get_coverage(
            embedding_model_id=embedding_model.model_id,
            embedding_version=embedding_version,
            course_id=course_id,
            module_id=module_id,
        )
        snapshot = RetrievalReadinessSnapshot(
            chat_model_id=chat.model.model_id,
            embedding_model_id=embedding_model.model_id,
            embedding_version=embedding_version,
            index_status=coverage.status,
            indexed_chunk_count=coverage.indexed_chunk_count,
            total_chunk_count=coverage.total_chunk_count,
            index_coverage=coverage.coverage,
            allow_plain_chat=purpose == "chat" and coverage.status == "empty",
        )

        if coverage.status == "empty":
            if purpose == "chat":
                return snapshot
            raise http_error(
                status_code=409,
                code="AI_RAG_NO_MATERIALS",
                message=(
                    "No published learning materials are available for quiz "
                    "generation in this course scope."
                ),
            )

        if not coverage.ready:
            raise http_error(
                status_code=503,
                code="AI_RAG_INDEX_NOT_READY",
                message=(
                    "The selected model's learning-material index is not ready "
                    f"(status={coverage.status}, "
                    f"coverage={coverage.indexed_chunk_count}/"
                    f"{coverage.total_chunk_count}, "
                    f"embeddingVersion={embedding_version}). "
                    "Complete reindexing before using grounded AI features."
                ),
            )

        try:
            self.catalog.resolve_embedding_model(
                embedding_model_id=embedding_model.model_id
            )
        except ProviderConfigurationError as exc:
            raise self._provider_unavailable_error() from exc
        return snapshot

    @staticmethod
    def _provider_unavailable_error():
        return http_error(
            status_code=503,
            code="AI_RAG_PROVIDER_UNAVAILABLE",
            message=(
                "The selected chat model and its paired embedding model are not "
                "both available. Ask an administrator to configure the model pair."
            ),
        )
