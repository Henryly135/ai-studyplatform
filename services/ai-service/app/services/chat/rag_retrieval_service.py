from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.ai_knowledge_chunks_repository import (
    AIKnowledgeChunksRepository,
    SimilarChunkResult,
)
from app.repositories.ai_retrieval_logs_repository import AIRetrievalLogsRepository
from app.services.indexing.embedding_service import EmbeddingService
from app.services.retrieval_readiness_service import (
    RetrievalPurpose,
    RetrievalReadinessService,
)
from platform_common.errors import http_error, invalid_request_error


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    source_id: int
    material_id: int | None
    module_id: int | None
    course_id: int | None
    chunk_index: int
    chunk_text: str
    heading_path: str | None
    score: float
    distance: float
    metadata_json: dict | list | None


@dataclass(frozen=True)
class RetrievalResult:
    query_text: str
    retrieved_chunks: list[RetrievedChunk]
    raw_retrieved_chunks: list[RetrievedChunk]
    chat_model_id: str
    query_embedding_model: str
    query_embedding_version: str
    index_status: str
    indexed_chunk_count: int
    total_chunk_count: int
    index_coverage: float
    latency_ms: int
    filters_json: dict[str, object]
    retrieval_trace_json: dict[str, object]


class RagRetrievalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.chunk_repository = AIKnowledgeChunksRepository(session)
        self.retrieval_logs = AIRetrievalLogsRepository(session)
        self.embedding_service = EmbeddingService(session)
        self.readiness_service = RetrievalReadinessService(session)

    def retrieve(
        self,
        *,
        user_id: int,
        query_text: str,
        course_id: int,
        module_id: int | None,
        session_id: int | None,
        message_id: int | None,
        top_k: int = 5,
        chat_model_id: str | None = None,
        model_user_id: int | None = None,
        readiness_purpose: RetrievalPurpose = "chat",
    ) -> RetrievalResult:
        normalized_query = query_text.strip()
        if not normalized_query:
            raise invalid_request_error("query_text is required")

        started_at = perf_counter()
        readiness = self.readiness_service.resolve(
            model_user_id=model_user_id,
            requested_chat_model_id=chat_model_id,
            course_id=course_id,
            module_id=module_id,
            purpose=readiness_purpose,
        )
        if readiness.allow_plain_chat:
            latency_ms = int((perf_counter() - started_at) * 1000)
            filters_json = {
                "courseId": course_id,
                "moduleId": module_id,
                "topK": top_k,
                "publishedOnly": True,
                "activeOnly": True,
                "chatModelId": readiness.chat_model_id,
                "embeddingModelId": readiness.embedding_model_id,
                "embeddingVersion": readiness.embedding_version,
                "indexStatus": readiness.index_status,
                "indexCoverage": readiness.index_coverage,
            }
            retrieval_trace_json = {
                "queryText": normalized_query,
                "queryEmbeddingModel": readiness.embedding_model_id,
                "queryEmbeddingVersion": readiness.embedding_version,
                "retrievalMode": "ordinary_chat_fallback",
                "fallbackReason": "no_published_learning_materials",
                "topK": top_k,
                "filters": filters_json,
                "indexStatus": readiness.index_status,
                "indexedChunkCount": readiness.indexed_chunk_count,
                "totalChunkCount": readiness.total_chunk_count,
                "indexCoverage": readiness.index_coverage,
                "rawResultCount": 0,
                "usedResultCount": 0,
                "rawResults": [],
                "results": [],
            }
            self.retrieval_logs.create(
                session_id=session_id,
                message_id=message_id,
                user_id=user_id,
                retrieval_mode="ordinary_chat_fallback",
                user_query=normalized_query,
                query_embedding_model=readiness.embedding_model_id,
                filters_json=filters_json,
                top_k=top_k,
                results_json=[],
                latency_ms=latency_ms,
            )
            return RetrievalResult(
                query_text=normalized_query,
                retrieved_chunks=[],
                raw_retrieved_chunks=[],
                chat_model_id=readiness.chat_model_id,
                query_embedding_model=readiness.embedding_model_id,
                query_embedding_version=readiness.embedding_version,
                index_status=readiness.index_status,
                indexed_chunk_count=readiness.indexed_chunk_count,
                total_chunk_count=readiness.total_chunk_count,
                index_coverage=readiness.index_coverage,
                latency_ms=latency_ms,
                filters_json=filters_json,
                retrieval_trace_json=retrieval_trace_json,
            )

        try:
            query_embedding = self.embedding_service.embed_query(
                text=normalized_query,
                embedding_model_id=readiness.embedding_model_id,
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            if (
                exc.status_code == 503
                and detail.get("code")
                == "AI_EMBEDDING_PROVIDER_UNAVAILABLE"
            ):
                raise http_error(
                    status_code=503,
                    code="AI_RAG_PROVIDER_UNAVAILABLE",
                    message=(
                        "The paired embedding provider is temporarily "
                        "unavailable. Please retry later."
                    ),
                ) from exc
            raise
        if (
            query_embedding.embedding_model_id != readiness.embedding_model_id
            or query_embedding.embedding_version != readiness.embedding_version
        ):
            raise http_error(
                status_code=503,
                code="AI_RAG_EMBEDDING_VERSION_MISMATCH",
                message=(
                    "The query embedding does not match the fully indexed model "
                    "version. Reindex or restore the configured embedding model."
                ),
            )
        title_matches = self.chunk_repository.list_title_matched_chunks(
            query_text=normalized_query,
            embedding_model_id=query_embedding.embedding_model_id,
            embedding_version=query_embedding.embedding_version,
            course_id=course_id,
            module_id=module_id,
            top_k=top_k,
        )
        vector_matches = self.chunk_repository.search_similar_chunks(
            query_embedding=query_embedding.vector,
            embedding_model_id=query_embedding.embedding_model_id,
            embedding_version=query_embedding.embedding_version,
            course_id=course_id,
            module_id=module_id,
            top_k=top_k,
        )
        matches = self._merge_matches(
            title_matches=title_matches,
            vector_matches=vector_matches,
            top_k=top_k,
        )
        latency_ms = int((perf_counter() - started_at) * 1000)

        raw_retrieved_chunks = [self._serialize_match(match) for match in matches]
        retrieved_chunks = [
            chunk for chunk in raw_retrieved_chunks if chunk.score >= settings.ai_retrieval_min_score
        ]
        filters_json = {
            "courseId": course_id,
            "moduleId": module_id,
            "topK": top_k,
            "publishedOnly": True,
            "activeOnly": True,
            "minScore": settings.ai_retrieval_min_score,
            "titleMatchEnabled": True,
            "titleMatchCount": len(title_matches),
            "chatModelId": readiness.chat_model_id,
            "embeddingModelId": query_embedding.embedding_model_id,
            "embeddingVersion": query_embedding.embedding_version,
            "indexStatus": readiness.index_status,
            "indexCoverage": readiness.index_coverage,
        }
        retrieval_trace_json = {
            "queryText": normalized_query,
            "queryEmbeddingModel": query_embedding.embedding_model_id,
            "queryEmbeddingVersion": query_embedding.embedding_version,
            "retrievalMode": "vector_similarity",
            "topK": top_k,
            "filters": filters_json,
            "rawResultCount": len(raw_retrieved_chunks),
            "usedResultCount": len(retrieved_chunks),
            "indexStatus": readiness.index_status,
            "indexedChunkCount": readiness.indexed_chunk_count,
            "totalChunkCount": readiness.total_chunk_count,
            "indexCoverage": readiness.index_coverage,
            "rawResults": [
                {
                    "chunkId": chunk.chunk_id,
                    "sourceId": chunk.source_id,
                    "courseId": chunk.course_id,
                    "moduleId": chunk.module_id,
                    "materialId": chunk.material_id,
                    "chunkIndex": chunk.chunk_index,
                    "headingPath": chunk.heading_path,
                    "score": round(chunk.score, 6),
                    "distance": round(chunk.distance, 6),
                    "preview": chunk.chunk_text[:300],
                }
                for chunk in raw_retrieved_chunks
            ],
            "results": [
                {
                    "chunkId": chunk.chunk_id,
                    "sourceId": chunk.source_id,
                    "courseId": chunk.course_id,
                    "moduleId": chunk.module_id,
                    "materialId": chunk.material_id,
                    "chunkIndex": chunk.chunk_index,
                    "headingPath": chunk.heading_path,
                    "score": round(chunk.score, 6),
                    "distance": round(chunk.distance, 6),
                    "preview": chunk.chunk_text[:300],
                }
                for chunk in retrieved_chunks
            ],
        }
        self.retrieval_logs.create(
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            retrieval_mode="vector_similarity",
            user_query=normalized_query,
            query_embedding_model=query_embedding.embedding_model_id,
            filters_json=filters_json,
            top_k=top_k,
            results_json=retrieval_trace_json["results"],
            latency_ms=latency_ms,
        )

        return RetrievalResult(
            query_text=normalized_query,
            retrieved_chunks=retrieved_chunks,
            raw_retrieved_chunks=raw_retrieved_chunks,
            chat_model_id=readiness.chat_model_id,
            query_embedding_model=query_embedding.embedding_model_id,
            query_embedding_version=query_embedding.embedding_version,
            index_status=readiness.index_status,
            indexed_chunk_count=readiness.indexed_chunk_count,
            total_chunk_count=readiness.total_chunk_count,
            index_coverage=readiness.index_coverage,
            latency_ms=latency_ms,
            filters_json=filters_json,
            retrieval_trace_json=retrieval_trace_json,
        )

    def _serialize_match(self, match: SimilarChunkResult) -> RetrievedChunk:
        chunk = match.chunk
        return RetrievedChunk(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            material_id=chunk.material_id,
            module_id=chunk.module_id,
            course_id=chunk.course_id,
            chunk_index=chunk.chunk_index,
            chunk_text=chunk.chunk_text,
            heading_path=chunk.heading_path,
            score=match.score,
            distance=match.distance,
            metadata_json=chunk.metadata_json,
        )

    def _merge_matches(
        self,
        *,
        title_matches: list[SimilarChunkResult],
        vector_matches: list[SimilarChunkResult],
        top_k: int,
    ) -> list[SimilarChunkResult]:
        merged: list[SimilarChunkResult] = []
        seen_chunk_ids: set[int] = set()
        for match in [*title_matches, *vector_matches]:
            if match.chunk.chunk_id in seen_chunk_ids:
                continue
            merged.append(match)
            seen_chunk_ids.add(match.chunk.chunk_id)
            if len(merged) >= top_k:
                break
        return merged
