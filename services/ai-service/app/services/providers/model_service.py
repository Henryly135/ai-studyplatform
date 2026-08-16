from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ai_model_catalog import AIModelCatalog, AIModelDefault, AIModelProvider, AIProviderCredential
from app.repositories.ai_model_catalog_repository import AIModelCatalogRepository
from app.repositories.ai_knowledge_source_embedding_statuses_repository import (
    AIKnowledgeSourceEmbeddingStatusesRepository,
)
from app.services.providers.adapters import build_chat_adapter, build_embedding_adapter
from app.services.providers.credentials import ProviderCredentialService, redact_secret_text
from app.services.providers.model_registry import (
    MODEL_DEFINITIONS,
    PROVIDER_DEFINITION_BY_KEY,
    PROVIDER_DEFINITIONS,
    SUPPORTED_PROVIDER_KEYS,
)
from app.services.providers.types import (
    ProviderConfigurationError,
    EmbeddingRequest,
    ProviderEmbeddingResult,
    ProviderInvocationError,
    ProviderQuotaError,
    ProviderTextResult,
    TextGenerationRequest,
)


@dataclass(frozen=True)
class ModelAvailability:
    available: bool
    reason: str | None


@dataclass(frozen=True)
class ResolvedModel:
    model: AIModelCatalog
    provider: AIModelProvider
    credential: AIProviderCredential | None
    availability: ModelAvailability


@dataclass(frozen=True)
class ResolvedModelPair:
    chat: ResolvedModel
    embedding: ResolvedModel


@dataclass(frozen=True)
class ModelInvocationResult:
    text: str
    provider: str
    model_id: str
    model_name: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    request_json: dict
    response_json: dict
    trace_id: str


@dataclass(frozen=True)
class EmbeddingInvocationResult:
    vector: list[float]
    provider: str
    model_id: str
    model_name: str
    embedding_version: str
    input_tokens: int | None
    total_tokens: int | None
    output_dimension: int
    task_type: str
    latency_ms: int
    request_json: dict
    response_json: dict
    trace_id: str


@contextmanager
def _managed_session(session: Session | None):
    if session is not None:
        yield session
        return
    local_session = SessionLocal()
    try:
        yield local_session
    finally:
        local_session.close()


def _strip_markdown_json_fence(text: str) -> str:
    normalized = text.strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        normalized = "\n".join(lines).strip()
    return normalized


class AIModelCatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = AIModelCatalogRepository(session)

    def ensure_seeded(self) -> None:
        if not settings.ai_model_catalog_seed_enabled:
            return
        for provider in PROVIDER_DEFINITIONS:
            self.repo.upsert_provider(
                provider_key=provider.provider_key,
                display_name=provider.display_name,
                adapter_type=provider.adapter_type,
                default_base_url=provider.default_base_url,
                backend_supported=provider.backend_supported,
                display_order=provider.display_order,
            )
        for model in sorted(
            MODEL_DEFINITIONS,
            key=lambda item: (not item.supports_embedding, item.display_order),
        ):
            self.repo.upsert_model(
                model_id=model.model_id,
                provider_key=model.provider_key,
                model_name=model.model_name,
                display_name=model.display_name,
                backend_supported=model.backend_supported,
                display_only=model.display_only,
                supports_chat=model.supports_chat,
                supports_json=model.supports_json,
                supports_embedding=model.supports_embedding,
                supports_rag_answer=model.supports_rag_answer,
                supports_rag_indexing=model.supports_rag_indexing,
                embedding_dimension=model.embedding_dimension,
                paired_embedding_model_id=model.paired_embedding_model_id,
                display_order=model.display_order,
                unavailable_reason=model.unavailable_reason,
            )
        defaults = self.repo.get_defaults()
        default_chat_model_id = (
            defaults.default_chat_model_id
            if defaults and defaults.default_chat_model_id
            else self._model_id_for_model_name(settings.ai_default_chat_model)
        )
        default_chat_model = (
            self.repo.get_model(default_chat_model_id)
            if default_chat_model_id
            else None
        )
        if (
            default_chat_model is None
            or default_chat_model.provider_key not in SUPPORTED_PROVIDER_KEYS
            or not default_chat_model.supports_chat
        ):
            default_chat_model = next(
                (
                    model
                    for model in self.repo.list_models()
                    if model.supports_chat
                    and model.provider_key in SUPPORTED_PROVIDER_KEYS
                    and model.is_enabled
                ),
                None,
            )
            default_chat_model_id = (
                default_chat_model.model_id if default_chat_model else None
            )
        paired_embedding_model_id = (
            default_chat_model.paired_embedding_model_id
            if default_chat_model
            else None
        )
        if (
            defaults is None
            or defaults.default_chat_model_id != default_chat_model_id
            or defaults.default_embedding_model_id != paired_embedding_model_id
        ):
            self.repo.set_defaults(
                default_chat_model_id=default_chat_model_id,
                default_embedding_model_id=paired_embedding_model_id,
            )
        self.session.commit()
        self._ensure_local_gemini_credential()

    def _ensure_local_gemini_credential(self) -> None:
        """Seed a local-only env key once, without ever logging or returning the secret."""
        if (
            settings.app_env.strip().lower() != "local"
            or not settings.local_demo_single_account_enabled
            or not settings.gemini_api_key.strip()
        ):
            return
        credential = self.repo.get_credential("gemini")
        if credential is not None and credential.encrypted_api_key:
            return
        ProviderCredentialService(self.session).save_credentials(
            provider_key="gemini",
            api_key=settings.gemini_api_key,
            base_url_override=None,
            is_enabled=True,
        )

    def _model_id_for_model_name(self, value: str) -> str | None:
        normalized = value.strip()
        if not normalized:
            return None
        if self.repo.get_model(normalized) is not None:
            return normalized
        for model in self.repo.list_models():
            if model.model_name == normalized:
                return model.model_id
        return normalized

    def get_defaults(self) -> AIModelDefault | None:
        return self.repo.get_defaults()

    def set_defaults(self, *, default_chat_model_id: str | None, default_embedding_model_id: str | None) -> None:
        derived_embedding_model_id: str | None = None
        if default_chat_model_id:
            chat_model = self.repo.get_model(default_chat_model_id)
            if chat_model is None:
                raise ProviderConfigurationError("Default chat model is not in the model catalog.")
            if not chat_model.supports_chat:
                raise ProviderConfigurationError("Default chat model must support chat.")
            derived_embedding_model_id = chat_model.paired_embedding_model_id
            if not derived_embedding_model_id:
                raise ProviderConfigurationError(
                    "Default chat model does not have a paired embedding model."
                )
            embedding_model = self.repo.get_model(derived_embedding_model_id)
            if embedding_model is None:
                raise ProviderConfigurationError(
                    "Paired embedding model is not in the model catalog."
                )
            if not embedding_model.supports_embedding:
                raise ProviderConfigurationError(
                    "Paired embedding model must support embeddings."
                )
        if (
            default_embedding_model_id
            and derived_embedding_model_id
            and default_embedding_model_id != derived_embedding_model_id
        ):
            raise ProviderConfigurationError(
                "Default embedding model is derived from the selected chat model."
            )
        self.repo.set_defaults(
            default_chat_model_id=default_chat_model_id,
            default_embedding_model_id=derived_embedding_model_id,
        )
        self.session.commit()

    def availability_for_model(
        self,
        model: AIModelCatalog,
        *,
        bypass_health_status_for_health_check: bool = False,
    ) -> ModelAvailability:
        provider = self.repo.get_provider(model.provider_key)
        credential = self.repo.get_credential(model.provider_key)
        if not model.is_enabled:
            return ModelAvailability(False, "模型已被管理员停用。")
        if (
            provider is None
            or provider.provider_key not in SUPPORTED_PROVIDER_KEYS
            or not provider.backend_supported
            or model.display_only
            or not model.backend_supported
        ):
            return ModelAvailability(False, model.unavailable_reason or "该模型当前仅展示，后端暂未接入。")
        if model.supports_embedding and model.embedding_dimension != settings.ai_embedding_dimension:
            return ModelAvailability(False, "模型向量维度与当前向量库不匹配，需要重新索引。")
        if credential is None or not credential.is_enabled or not credential.encrypted_api_key:
            return ModelAvailability(False, "管理员尚未配置该供应商 API key。")
        health_status = "ready"
        unavailable_reason: str | None = None
        if not bypass_health_status_for_health_check:
            health_status = str(
                getattr(credential, "health_status", None) or "unknown"
            ).strip().lower()
            unavailable_reason = {
                "unknown": "供应商尚未通过健康检查。",
                "failed": "供应商健康检查失败，当前暂不可用。",
                "quota": "供应商额度受限，当前暂不可用。",
            }.get(health_status)
        if health_status != "ready":
            if (
                settings.app_env.strip().lower() == "local"
                and settings.local_demo_single_account_enabled
                and model.provider_key == "gemini"
                and settings.gemini_api_key.strip()
            ):
                return ModelAvailability(True, None)
            return ModelAvailability(
                False,
                unavailable_reason or "供应商健康状态未知，当前暂不可用。",
            )
        return ModelAvailability(True, None)

    def resolve_chat_model(
        self,
        *,
        user_id: int | None,
        requested_model_id: str | None,
        bypass_health_status_for_health_check: bool = False,
    ) -> ResolvedModel:
        model_id = requested_model_id.strip() if requested_model_id and requested_model_id.strip() else None
        if model_id is None and user_id is not None:
            preference = self.repo.get_user_preference(user_id)
            if preference is not None:
                model_id = preference.chat_model_id
        if model_id is None:
            defaults = self.repo.get_defaults()
            model_id = defaults.default_chat_model_id if defaults and defaults.default_chat_model_id else None
        if model_id is None:
            model_id = self._model_id_for_model_name(settings.ai_default_chat_model)
        if not model_id:
            raise ProviderConfigurationError("Default chat model is not configured.")
        model = self.repo.get_model(model_id)
        if model is None:
            raise ProviderConfigurationError("Selected chat model is not in the model catalog.")
        if not model.supports_chat:
            raise ProviderConfigurationError("Selected model does not support chat.")
        provider = self.repo.get_provider(model.provider_key)
        if provider is None:
            raise ProviderConfigurationError("Selected provider is not configured.")
        availability = self.availability_for_model(
            model,
            bypass_health_status_for_health_check=(
                bypass_health_status_for_health_check
            ),
        )
        credential = self.repo.get_credential(model.provider_key)
        if not availability.available:
            raise ProviderConfigurationError(availability.reason or "Selected model is unavailable.")
        if user_id is not None and requested_model_id:
            self.repo.set_user_preference(user_id=user_id, chat_model_id=model.model_id)
        return ResolvedModel(model=model, provider=provider, credential=credential, availability=availability)

    def resolve_embedding_model(
        self,
        *,
        embedding_model_id: str,
        bypass_health_status_for_health_check: bool = False,
    ) -> ResolvedModel:
        normalized_model_id = embedding_model_id.strip()
        if not normalized_model_id:
            raise ProviderConfigurationError("Embedding model id is required.")
        model = self.repo.get_model(normalized_model_id)
        if model is None:
            raise ProviderConfigurationError(
                "Selected embedding model is not in the model catalog."
            )
        if not model.supports_embedding or not model.supports_rag_indexing:
            raise ProviderConfigurationError(
                "Selected model does not support RAG embeddings."
            )
        provider = self.repo.get_provider(model.provider_key)
        if provider is None:
            raise ProviderConfigurationError(
                "Selected embedding provider is not configured."
            )
        availability = self.availability_for_model(
            model,
            bypass_health_status_for_health_check=(
                bypass_health_status_for_health_check
            ),
        )
        credential = self.repo.get_credential(model.provider_key)
        if not availability.available:
            raise ProviderConfigurationError(
                availability.reason or "Selected embedding model is unavailable."
            )
        return ResolvedModel(
            model=model,
            provider=provider,
            credential=credential,
            availability=availability,
        )

    def resolve_model_pair(
        self,
        *,
        user_id: int | None,
        requested_model_id: str | None,
    ) -> ResolvedModelPair:
        chat = self.resolve_chat_model(
            user_id=user_id,
            requested_model_id=requested_model_id,
        )
        paired_embedding_model_id = chat.model.paired_embedding_model_id
        if not paired_embedding_model_id:
            raise ProviderConfigurationError(
                "Selected chat model does not have a paired embedding model."
            )
        return ResolvedModelPair(
            chat=chat,
            embedding=self.resolve_embedding_model(
                embedding_model_id=paired_embedding_model_id
            ),
        )

    def list_available_embedding_models(self) -> list[ResolvedModel]:
        available: list[ResolvedModel] = []
        for model in self.repo.list_models():
            if not model.supports_embedding or not model.supports_rag_indexing:
                continue
            try:
                available.append(
                    self.resolve_embedding_model(
                        embedding_model_id=model.model_id
                    )
                )
            except ProviderConfigurationError:
                continue
        return available

    def list_model_status(
        self,
        *,
        user_id: int | None = None,
        course_id: int | None = None,
        module_id: int | None = None,
    ) -> dict:
        self.ensure_seeded()
        defaults = self.repo.get_defaults()
        preference = self.repo.get_user_preference(user_id) if user_id is not None else None
        providers = {provider.provider_key: provider for provider in self.repo.list_providers()}
        credentials = {credential.provider_key: credential for credential in self.repo.list_credentials()}
        models = {
            model.model_id: model
            for model in self.repo.list_models()
            if model.provider_key in SUPPORTED_PROVIDER_KEYS
        }
        coverage_repo = AIKnowledgeSourceEmbeddingStatusesRepository(self.session)
        coverage_by_embedding_model_id = {}
        items = []
        for model in models.values():
            provider = providers.get(model.provider_key)
            credential = credentials.get(model.provider_key)
            availability = self.availability_for_model(model)
            paired_embedding_model = (
                models.get(model.paired_embedding_model_id)
                if model.paired_embedding_model_id
                else None
            )
            pair_availability = (
                self.availability_for_model(paired_embedding_model)
                if paired_embedding_model is not None
                else None
            )
            coverage = None
            if paired_embedding_model is not None:
                coverage = coverage_by_embedding_model_id.get(
                    paired_embedding_model.model_id
                )
                if coverage is None:
                    coverage = coverage_repo.get_coverage(
                        embedding_model_id=paired_embedding_model.model_id,
                        embedding_version=(
                            f"{paired_embedding_model.model_id}@"
                            f"{paired_embedding_model.embedding_dimension}"
                        ),
                        course_id=course_id,
                        module_id=module_id,
                    )
                    coverage_by_embedding_model_id[
                        paired_embedding_model.model_id
                    ] = coverage
            items.append(
                {
                    "modelId": model.model_id,
                    "provider": model.provider_key,
                    "providerLabel": provider.display_name if provider else model.provider_key,
                    "modelName": model.model_name,
                    "displayName": model.display_name,
                    "available": availability.available,
                    "unavailableReason": availability.reason,
                    "backendSupported": model.backend_supported,
                    "displayOnly": model.display_only,
                    "configured": bool(credential and credential.is_enabled and credential.encrypted_api_key),
                    "capabilities": {
                        "chat": model.supports_chat,
                        "json": model.supports_json,
                        "embedding": model.supports_embedding,
                        "ragAnswer": model.supports_rag_answer,
                        "ragIndexing": model.supports_rag_indexing,
                    },
                    "embeddingDimension": (
                        paired_embedding_model.embedding_dimension
                        if paired_embedding_model is not None
                        else model.embedding_dimension
                    ),
                    "pairedEmbeddingModelId": (
                        paired_embedding_model.model_id
                        if paired_embedding_model is not None
                        else None
                    ),
                    "pairedEmbeddingModelName": (
                        paired_embedding_model.display_name
                        if paired_embedding_model is not None
                        else None
                    ),
                    "ragReady": (
                        availability.available
                        and bool(pair_availability and pair_availability.available)
                        and bool(coverage and coverage.ready)
                        if model.supports_chat
                        else None
                    ),
                    "indexCoverage": (
                        coverage.coverage if coverage is not None else None
                    ),
                    "indexStatus": (
                        coverage.status if coverage is not None else None
                    ),
                    "isDefaultChat": bool(defaults and defaults.default_chat_model_id == model.model_id),
                    "isDefaultEmbedding": bool(defaults and defaults.default_embedding_model_id == model.model_id),
                    "isUserSelected": bool(preference and preference.chat_model_id == model.model_id),
                }
            )
        return {
            "defaultChatModelId": defaults.default_chat_model_id if defaults else None,
            "defaultEmbeddingModelId": defaults.default_embedding_model_id if defaults else None,
            "userSelectedChatModelId": preference.chat_model_id if preference else None,
            "items": items,
        }


class AIEmbeddingInvocationService:
    """Invokes any catalog-backed embedding adapter without provider branches."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._resolved_models: dict[tuple[str, bool], ResolvedModel] = {}
        self._credentials = {}
        self._adapters = {}

    def embed_text(
        self,
        *,
        text: str,
        model_id: str,
        task_type: str,
        title: str | None = None,
        bypass_health_status_for_health_check: bool = False,
    ) -> EmbeddingInvocationResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise ProviderConfigurationError("Embedding text is required.")

        catalog = AIModelCatalogService(self.session)
        resolved_model_key = (
            model_id,
            bypass_health_status_for_health_check,
        )
        resolved = self._resolved_models.get(resolved_model_key)
        if resolved is None:
            resolved = catalog.resolve_embedding_model(
                embedding_model_id=model_id,
                bypass_health_status_for_health_check=(
                    bypass_health_status_for_health_check
                ),
            )
            self._resolved_models[resolved_model_key] = resolved
        credentials = self._credentials.get(resolved.provider.provider_key)
        if credentials is None:
            credentials = ProviderCredentialService(
                self.session
            ).get_credentials_for_provider(resolved.provider.provider_key)
            self._credentials[resolved.provider.provider_key] = credentials
        output_dimension = resolved.model.embedding_dimension
        if output_dimension is None or output_dimension <= 0:
            raise ProviderConfigurationError(
                "Embedding model dimension is not configured."
            )

        request = EmbeddingRequest(
            provider_key=resolved.provider.provider_key,
            model_name=resolved.model.model_name,
            api_key=credentials.api_key,
            base_url=credentials.base_url,
            text=normalized_text,
            output_dimension=output_dimension,
            task_type=task_type,
            title=title,
        )
        adapter = self._adapters.get(resolved.provider.adapter_type)
        if adapter is None:
            adapter = build_embedding_adapter(resolved.provider.adapter_type)
            self._adapters[resolved.provider.adapter_type] = adapter
        started_at = perf_counter()
        trace_id = str(uuid4())
        try:
            provider_result: ProviderEmbeddingResult = adapter.embed(request)
        except (
            ProviderQuotaError,
            ProviderConfigurationError,
            ProviderInvocationError,
        ):
            raise
        except Exception as exc:
            raise ProviderInvocationError(
                redact_secret_text(exc),
                provider_error_type="unknown_provider_error",
            ) from exc

        if len(provider_result.vector) != output_dimension:
            raise ProviderInvocationError(
                "Embedding provider returned an unexpected vector dimension.",
                provider_error_type="invalid_provider_response",
            )
        latency_ms = int((perf_counter() - started_at) * 1000)
        embedding_version = f"{resolved.model.model_id}@{output_dimension}"
        return EmbeddingInvocationResult(
            vector=provider_result.vector,
            provider=resolved.provider.provider_key,
            model_id=resolved.model.model_id,
            model_name=resolved.model.model_name,
            embedding_version=embedding_version,
            input_tokens=provider_result.usage.prompt_tokens,
            total_tokens=provider_result.usage.total_tokens,
            output_dimension=output_dimension,
            task_type=task_type,
            latency_ms=latency_ms,
            request_json={
                **(provider_result.request_json or {}),
                "traceId": trace_id,
                "modelId": resolved.model.model_id,
            },
            response_json={
                **(provider_result.response_json or {}),
                "traceId": trace_id,
                "modelId": resolved.model.model_id,
            },
            trace_id=trace_id,
        )


class AIModelInvocationService:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session

    def generate_text(
        self,
        *,
        prompt: str,
        system_instruction: str | None,
        model_id: str | None = None,
        user_id: int | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool = False,
        bypass_health_status_for_health_check: bool = False,
    ) -> ModelInvocationResult:
        with _managed_session(self.session) as session:
            catalog = AIModelCatalogService(session)
            catalog.ensure_seeded()
            resolved = catalog.resolve_chat_model(
                user_id=user_id,
                requested_model_id=model_id,
                bypass_health_status_for_health_check=(
                    bypass_health_status_for_health_check
                ),
            )
            if json_mode and not resolved.model.supports_json:
                raise ProviderConfigurationError("Selected model does not support JSON generation.")

            credentials = ProviderCredentialService(session).get_credentials_for_provider(resolved.provider.provider_key)
            request = TextGenerationRequest(
                provider_key=resolved.provider.provider_key,
                model_name=resolved.model.model_name,
                api_key=credentials.api_key,
                base_url=credentials.base_url,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature if temperature is not None else settings.ai_chat_temperature,
                max_output_tokens=max_output_tokens if max_output_tokens is not None else settings.ai_chat_max_output_tokens,
                json_mode=json_mode,
                require_parameter_support=bool(
                    json_mode
                    and PROVIDER_DEFINITION_BY_KEY.get(
                        resolved.provider.provider_key
                    )
                    and PROVIDER_DEFINITION_BY_KEY[
                        resolved.provider.provider_key
                    ].require_json_parameter_support
                ),
            )
            adapter = build_chat_adapter(resolved.provider.adapter_type)
            started_at = perf_counter()
            trace_id = str(uuid4())
            try:
                provider_result: ProviderTextResult = adapter.generate_text(request)
            except (ProviderQuotaError, ProviderConfigurationError, ProviderInvocationError):
                raise
            except Exception as exc:
                raise ProviderInvocationError(
                    redact_secret_text(exc),
                    provider_error_type="unknown_provider_error",
                ) from exc

            latency_ms = int((perf_counter() - started_at) * 1000)
            return ModelInvocationResult(
                text=provider_result.text,
                provider=resolved.provider.provider_key,
                model_id=resolved.model.model_id,
                model_name=resolved.model.model_name,
                prompt_tokens=provider_result.usage.prompt_tokens,
                completion_tokens=provider_result.usage.completion_tokens,
                total_tokens=provider_result.usage.total_tokens,
                latency_ms=latency_ms,
                request_json={
                    **(provider_result.request_json or {}),
                    "traceId": trace_id,
                    "modelId": resolved.model.model_id,
                },
                response_json={
                    **(provider_result.response_json or {}),
                    "traceId": trace_id,
                    "modelId": resolved.model.model_id,
                },
                trace_id=trace_id,
            )

    def generate_json(
        self,
        *,
        prompt: str,
        system_instruction: str | None,
        model_id: str | None = None,
        user_id: int | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1800,
        validator: Callable[[dict], object] | None = None,
    ):
        result = self.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            model_id=model_id,
            user_id=user_id,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            json_mode=True,
        )
        content = _strip_markdown_json_fence(result.text)
        if not content:
            raise ProviderInvocationError("AI provider returned empty JSON.", provider_error_type="empty_response")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderInvocationError("AI provider returned invalid JSON.", provider_error_type="invalid_json") from exc
        if not isinstance(parsed, dict):
            raise ProviderInvocationError("AI provider returned an unexpected JSON payload.", provider_error_type="invalid_json")
        return validator(parsed) if validator is not None else parsed
