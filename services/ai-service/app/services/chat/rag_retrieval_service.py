from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.ai_knowledge_chunks_repository import (
    AIKnowledgeChunksRepository,
    SimilarChunkResult,
)
from app.repositories.ai_retrieval_logs_repository import AIRetrievalLogsRepository
from app.services.indexing.embedding_service import EmbeddingService
from platform_common.errors import invalid_request_error


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
    query_embedding_model: str
    latency_ms: int
    filters_json: dict[str, object]
    retrieval_trace_json: dict[str, object]


class RagRetrievalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.chunk_repository = AIKnowledgeChunksRepository(session)
        self.retrieval_logs = AIRetrievalLogsRepository(session)
        self.embedding_service = EmbeddingService(session)

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
    ) -> RetrievalResult:
        normalized_query = query_text.strip()
        if not normalized_query:
            raise invalid_request_error("query_text is required")

        started_at = perf_counter()
        query_embedding = self.embedding_service.embed_query(text=normalized_query)
        title_matches = self.chunk_repository.list_title_matched_chunks(
            query_text=normalized_query,
            course_id=course_id,
            module_id=module_id,
            top_k=top_k,
        )
        vector_matches = self.chunk_repository.search_similar_chunks(
            query_embedding=query_embedding.vector,
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
        }
        retrieval_trace_json = {
            "queryText": normalized_query,
            "queryEmbeddingModel": query_embedding.embedding_model,
            "queryEmbeddingVersion": query_embedding.embedding_version,
            "retrievalMode": "vector_similarity",
            "topK": top_k,
            "filters": filters_json,
            "rawResultCount": len(raw_retrieved_chunks),
            "usedResultCount": len(retrieved_chunks),
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
            query_embedding_model=query_embedding.embedding_model,
            filters_json=filters_json,
            top_k=top_k,
            results_json=retrieval_trace_json["results"],
            latency_ms=latency_ms,
        )

        return RetrievalResult(
            query_text=normalized_query,
            retrieved_chunks=retrieved_chunks,
            raw_retrieved_chunks=raw_retrieved_chunks,
            query_embedding_model=query_embedding.embedding_model,
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
