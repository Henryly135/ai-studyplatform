from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_prompt_logs import AIPromptStatus
from app.services.provider_error_messages import (
    AI_EMBEDDING_PROVIDER_UNAVAILABLE,
    AI_PROVIDER_QUOTA_UNAVAILABLE,
)
from app.services.providers.model_service import (
    AIEmbeddingInvocationService,
    AIModelCatalogService,
)
from app.services.providers.types import (
    ProviderConfigurationError,
    ProviderInvocationError,
    ProviderQuotaError,
)
from platform_common.errors import http_error, invalid_request_error


@dataclass(frozen=True)
class EmbeddingModelTarget:
    model_id: str
    display_name: str
    embedding_version: str
    dimension: int


@dataclass(frozen=True)
class EmbeddingResult:
    embedding_model_id: str
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
    provider_input_tokens: int | None = None
    provider_total_tokens: int | None = None

    @property
    def embedding_model(self) -> str:
        """Compatibility alias for telemetry callers during migration."""

        return self.embedding_model_id


@dataclass(frozen=True)
class TokenCountResult:
    provider_input_tokens: int | None
    provider_total_tokens: int | None
    request_json: dict | list | None
    response_json: dict | list | None


class EmbeddingService:
    """Catalog-driven embedding facade shared by indexing and retrieval."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog = AIModelCatalogService(session)
        self.catalog.ensure_seeded()
        self.invocation = AIEmbeddingInvocationService(session)

    def list_available_embedding_models(self) -> list[EmbeddingModelTarget]:
        return [
            EmbeddingModelTarget(
                model_id=resolved.model.model_id,
                display_name=resolved.model.display_name,
                embedding_version=(
                    f"{resolved.model.model_id}@{resolved.model.embedding_dimension}"
                ),
                dimension=int(resolved.model.embedding_dimension or 0),
            )
            for resolved in self.catalog.list_available_embedding_models()
        ]

    def count_document_tokens(
        self,
        *,
        text: str,
        embedding_model_id: str | None = None,
    ) -> TokenCountResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise invalid_request_error("text is required for token counting")
        return TokenCountResult(
            provider_input_tokens=None,
            provider_total_tokens=None,
            request_json={
                "modelId": embedding_model_id,
                "contentsPreview": normalized_text[:500],
                "mode": "provider_usage_from_embedding_response",
            },
            response_json={
                "providerCountTokensSupported": False,
            },
        )

    def embed_query(
        self,
        *,
        text: str,
        chat_model_id: str | None = None,
        user_id: int | None = None,
        embedding_model_id: str | None = None,
    ) -> EmbeddingResult:
        selected_embedding_model_id = embedding_model_id
        if selected_embedding_model_id is None:
            try:
                pair = self.catalog.resolve_model_pair(
                    user_id=user_id,
                    requested_model_id=chat_model_id,
                )
            except ProviderConfigurationError as exc:
                raise http_error(
                    status_code=503,
                    code="AI_EMBEDDING_PROVIDER_UNAVAILABLE",
                    message=AI_EMBEDDING_PROVIDER_UNAVAILABLE,
                ) from exc
            selected_embedding_model_id = pair.embedding.model.model_id
        return self._embed_text(
            text=text,
            title=None,
            task_type="RETRIEVAL_QUERY",
            embedding_model_id=selected_embedding_model_id,
        )

    def embed_document(
        self,
        *,
        text: str,
        title: str | None = None,
        embedding_model_id: str | None = None,
    ) -> EmbeddingResult:
        selected_embedding_model_id = embedding_model_id
        if selected_embedding_model_id is None:
            try:
                pair = self.catalog.resolve_model_pair(
                    user_id=None,
                    requested_model_id=None,
                )
            except ProviderConfigurationError as exc:
                raise http_error(
                    status_code=503,
                    code="AI_EMBEDDING_PROVIDER_UNAVAILABLE",
                    message=AI_EMBEDDING_PROVIDER_UNAVAILABLE,
                ) from exc
            selected_embedding_model_id = pair.embedding.model.model_id
        return self._embed_text(
            text=text,
            title=title,
            task_type=settings.ai_embedding_task_type,
            embedding_model_id=selected_embedding_model_id,
        )

    def _embed_text(
        self,
        *,
        text: str,
        title: str | None,
        task_type: str,
        embedding_model_id: str,
    ) -> EmbeddingResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise invalid_request_error("text is required for embedding")
        try:
            result = self.invocation.embed_text(
                text=normalized_text,
                model_id=embedding_model_id,
                task_type=task_type,
                title=title,
            )
        except ProviderQuotaError as exc:
            raise http_error(
                status_code=429,
                code="AI_QUOTA_EXCEEDED",
                message=AI_PROVIDER_QUOTA_UNAVAILABLE,
            ) from exc
        except (ProviderConfigurationError, ProviderInvocationError) as exc:
            raise http_error(
                status_code=503,
                code="AI_EMBEDDING_PROVIDER_UNAVAILABLE",
                message=AI_EMBEDDING_PROVIDER_UNAVAILABLE,
            ) from exc

        return EmbeddingResult(
            embedding_model_id=result.model_id,
            embedding_version=result.embedding_version,
            vector=result.vector,
            task_type=result.task_type,
            output_dimensionality=result.output_dimension,
            latency_ms=result.latency_ms,
            request_json=result.request_json,
            response_json=result.response_json,
            status=AIPromptStatus.SUCCESS,
            error_message=None,
            trace_id=result.trace_id,
            provider_input_tokens=result.input_tokens,
            provider_total_tokens=result.total_tokens,
        )
