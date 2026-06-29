from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from time import perf_counter
from uuid import uuid4

from google import genai
from google.genai import types

from app.core.config import settings
from app.models.ai_prompt_logs import AIPromptStatus
from app.services.indexing.langchain_embedding_service import LangChainEmbeddingService
from platform_common.errors import invalid_request_error


@dataclass(frozen=True)
class EmbeddingResult:
    embedding_model: str
    embedding_version: str
    vector: list[float]
    task_type: str
    output_dimensionality: int
    latency_ms: int | None
    request_json: dict | list | None
    response_json: dict | list | None
    status: AIPromptStatus
    error_message: str | None
    trace_id: str


@dataclass(frozen=True)
class TokenCountResult:
    provider_input_tokens: int | None
    provider_total_tokens: int | None
    request_json: dict | list | None
    response_json: dict | list | None


class EmbeddingService:
    def __init__(self) -> None:
        if settings.ai_embedding_provider.strip().lower() != "gemini":
            raise invalid_request_error(
                f"Unsupported AI_EMBEDDING_PROVIDER '{settings.ai_embedding_provider}'. "
                "Only Gemini embeddings are currently configured. Use AI_EMBEDDING_PROVIDER=gemini "
                "or add a provider-specific embedding adapter before reindexing materials."
            )
        if not settings.ai_embedding_api_key:
            raise invalid_request_error(
                "AI_EMBEDDING_API_KEY or GEMINI_API_KEY is not configured for Gemini embeddings. "
                "Configure the embedding key and reindex affected materials."
            )
        self.client = genai.Client(api_key=settings.ai_embedding_api_key)
        self.langchain_embeddings = LangChainEmbeddingService()

    def count_document_tokens(self, *, text: str) -> TokenCountResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise invalid_request_error("text is required for token counting")

        request_json = {
            "model": settings.ai_embedding_model,
            "contents_preview": normalized_text[:500],
        }
        provider_input_tokens: int | None = None
        provider_total_tokens: int | None = None
        response_json: dict[str, object] | None = None

        try:
            response = self.client.models.count_tokens(
                model=settings.ai_embedding_model,
                contents=normalized_text,
            )
            provider_total_tokens = self._extract_token_count(response)
            provider_input_tokens = provider_total_tokens
            response_json = {
                "provider_count_tokens_supported": provider_total_tokens is not None,
                "provider_total_tokens": provider_total_tokens,
            }
        except Exception as exc:
            response_json = {
                "provider_count_tokens_supported": False,
                "provider_error": f"{type(exc).__name__}: {exc}",
            }

        return TokenCountResult(
            provider_input_tokens=provider_input_tokens,
            provider_total_tokens=provider_total_tokens,
            request_json=request_json,
            response_json=response_json,
        )

    def embed_query(self, *, text: str) -> EmbeddingResult:
        return self._embed_text(text=text, title=None, task_type="RETRIEVAL_QUERY")

    def embed_document(self, *, text: str, title: str | None = None) -> EmbeddingResult:
        return self._embed_text(
            text=text,
            title=title,
            task_type=settings.ai_embedding_task_type,
        )

    def _embed_text(
        self,
        *,
        text: str,
        title: str | None,
        task_type: str,
    ) -> EmbeddingResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise invalid_request_error("text is required for embedding")

        if settings.ai_embedding_orchestrator.strip().lower() == "langchain":
            return self._embed_text_via_langchain(
                text=normalized_text,
                title=title,
                task_type=task_type,
            )

        config_kwargs: dict[str, object] = {
            "task_type": task_type,
            "output_dimensionality": settings.ai_embedding_output_dimension,
        }
        normalized_title = (title or "").strip()
        if normalized_title and task_type == "RETRIEVAL_DOCUMENT":
            config_kwargs["title"] = normalized_title

        trace_id = str(uuid4())
        request_json = {
            "model": settings.ai_embedding_model,
            "contents_preview": normalized_text[:500],
            "config": config_kwargs,
        }
        started_at = perf_counter()
        response = self.client.models.embed_content(
            model=settings.ai_embedding_model,
            contents=normalized_text,
            config=types.EmbedContentConfig(**config_kwargs),
        )
        latency_ms = int((perf_counter() - started_at) * 1000)
        if not response.embeddings:
            raise invalid_request_error("Embedding provider returned no embeddings")

        vector = list(response.embeddings[0].values)
        if len(vector) != settings.ai_embedding_dimension:
            raise invalid_request_error(
                f"Embedding dimension mismatch: expected {settings.ai_embedding_dimension}, got {len(vector)}"
            )

        return EmbeddingResult(
            embedding_model=settings.ai_embedding_model,
            embedding_version=settings.ai_embedding_version,
            vector=self._normalize_vector(vector),
            task_type=task_type,
            output_dimensionality=settings.ai_embedding_output_dimension,
            latency_ms=latency_ms,
            request_json=request_json,
            response_json={
                "embedding_count": len(response.embeddings),
                "embedding_length": len(vector),
            },
            status=AIPromptStatus.SUCCESS,
            error_message=None,
            trace_id=trace_id,
        )

    def _embed_text_via_langchain(
        self,
        *,
        text: str,
        title: str | None,
        task_type: str,
    ) -> EmbeddingResult:
        trace_id = str(uuid4())
        started_at = perf_counter()
        if task_type == "RETRIEVAL_QUERY":
            result = self.langchain_embeddings.embed_query(text=text)
        else:
            result = self.langchain_embeddings.embed_document(
                text=text,
                title=title,
                task_type=task_type,
            )
        latency_ms = int((perf_counter() - started_at) * 1000)
        vector = result.vector
        if len(vector) != settings.ai_embedding_dimension:
            raise invalid_request_error(
                f"Embedding dimension mismatch: expected {settings.ai_embedding_dimension}, got {len(vector)}"
            )

        request_json = dict(result.request_json)
        request_json["trace_id"] = trace_id
        return EmbeddingResult(
            embedding_model=settings.ai_embedding_model,
            embedding_version=settings.ai_embedding_version,
            vector=self._normalize_vector(vector),
            task_type=task_type,
            output_dimensionality=settings.ai_embedding_output_dimension,
            latency_ms=latency_ms,
            request_json=request_json,
            response_json=result.response_json,
            status=AIPromptStatus.SUCCESS,
            error_message=None,
            trace_id=trace_id,
        )

    def _extract_token_count(self, response: object) -> int | None:
        if response is None:
            return None

        total_tokens = getattr(response, "total_tokens", None)
        if isinstance(total_tokens, int):
            return total_tokens

        if isinstance(response, dict):
            value = response.get("total_tokens")
            if isinstance(value, int):
                return value

        to_dict = getattr(response, "to_dict", None)
        if callable(to_dict):
            response_dict = to_dict()
            if isinstance(response_dict, dict):
                value = response_dict.get("total_tokens")
                if isinstance(value, int):
                    return value

        to_json_dict = getattr(response, "to_json_dict", None)
        if callable(to_json_dict):
            response_dict = to_json_dict()
            if isinstance(response_dict, dict):
                value = response_dict.get("total_tokens")
                if isinstance(value, int):
                    return value

        return None

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        magnitude = sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            raise invalid_request_error("Embedding vector magnitude is zero")
        return [value / magnitude for value in vector]
