from __future__ import annotations

from dataclasses import dataclass

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings
from app.services.provider_error_messages import AI_EMBEDDING_PROVIDER_UNAVAILABLE
from platform_common.errors import invalid_request_error


@dataclass(frozen=True)
class LangChainEmbeddingExecutionResult:
    vector: list[float]
    request_json: dict[str, object]
    response_json: dict[str, object]


class LangChainEmbeddingService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key.strip()
        if not self.api_key:
            raise invalid_request_error(AI_EMBEDDING_PROVIDER_UNAVAILABLE)

    def embed_query(self, *, text: str) -> LangChainEmbeddingExecutionResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise invalid_request_error("text is required for embedding")

        embeddings = self._build_embeddings(task_type="retrieval_query")
        vector = list(
            embeddings.embed_query(
                normalized_text,
                output_dimensionality=settings.ai_embedding_output_dimension,
            )
        )
        return LangChainEmbeddingExecutionResult(
            vector=vector,
            request_json={
                "orchestrator": "langchain",
                "model": settings.ai_embedding_model,
                "task_type": "RETRIEVAL_QUERY",
                "contents_preview": normalized_text[:500],
                "output_dimensionality": settings.ai_embedding_output_dimension,
            },
            response_json={
                "orchestrator": "langchain",
                "embedding_count": 1,
                "embedding_length": len(vector),
            },
        )

    def embed_document(
        self,
        *,
        text: str,
        title: str | None = None,
        task_type: str,
    ) -> LangChainEmbeddingExecutionResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise invalid_request_error("text is required for embedding")

        normalized_title = (title or "").strip()
        embeddings = self._build_embeddings(task_type=task_type.lower())
        embed_kwargs: dict[str, object] = {
            "output_dimensionality": settings.ai_embedding_output_dimension,
        }
        if normalized_title:
            embed_kwargs["titles"] = [normalized_title]

        vectors = embeddings.embed_documents([normalized_text], **embed_kwargs)
        if not vectors:
            raise invalid_request_error("Embedding provider returned no embeddings")

        vector = list(vectors[0])
        return LangChainEmbeddingExecutionResult(
            vector=vector,
            request_json={
                "orchestrator": "langchain",
                "model": settings.ai_embedding_model,
                "task_type": task_type,
                "title": normalized_title or None,
                "contents_preview": normalized_text[:500],
                "output_dimensionality": settings.ai_embedding_output_dimension,
            },
            response_json={
                "orchestrator": "langchain",
                "embedding_count": len(vectors),
                "embedding_length": len(vector),
            },
        )

    def _build_embeddings(self, *, task_type: str) -> GoogleGenerativeAIEmbeddings:
        return GoogleGenerativeAIEmbeddings(
            model=settings.ai_embedding_model,
            google_api_key=self.api_key,
            task_type=task_type,
        )
