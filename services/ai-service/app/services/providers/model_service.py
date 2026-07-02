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
from app.services.providers.adapters import build_chat_adapter
from app.services.providers.credentials import ProviderCredentialService, redact_secret_text
from app.services.providers.model_registry import MODEL_DEFINITIONS, PROVIDER_DEFINITIONS
from app.services.providers.types import (
    ProviderConfigurationError,
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
        for model in MODEL_DEFINITIONS:
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
                display_order=model.display_order,
                unavailable_reason=model.unavailable_reason,
            )
        defaults = self.repo.get_defaults()
        if defaults is None:
            self.repo.set_defaults(
                default_chat_model_id=self._model_id_for_model_name(settings.ai_default_chat_model),
                default_embedding_model_id=self._model_id_for_model_name(settings.ai_default_embedding_model),
            )
        self.session.commit()

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
        if default_chat_model_id:
            chat_model = self.repo.get_model(default_chat_model_id)
            if chat_model is None:
                raise ProviderConfigurationError("Default chat model is not in the model catalog.")
            if not chat_model.supports_chat:
                raise ProviderConfigurationError("Default chat model must support chat.")
        if default_embedding_model_id:
            embedding_model = self.repo.get_model(default_embedding_model_id)
            if embedding_model is None:
                raise ProviderConfigurationError("Default embedding model is not in the model catalog.")
            if not embedding_model.supports_embedding:
                raise ProviderConfigurationError("Default embedding model must support embeddings.")
        self.repo.set_defaults(
            default_chat_model_id=default_chat_model_id,
            default_embedding_model_id=default_embedding_model_id,
        )
        self.session.commit()

    def availability_for_model(self, model: AIModelCatalog) -> ModelAvailability:
        provider = self.repo.get_provider(model.provider_key)
        credential = self.repo.get_credential(model.provider_key)
        if not model.is_enabled:
            return ModelAvailability(False, "模型已被管理员停用。")
        if provider is None or not provider.backend_supported or model.display_only or not model.backend_supported:
            return ModelAvailability(False, model.unavailable_reason or "该模型当前仅展示，后端暂未接入。")
        if model.supports_embedding and model.embedding_dimension != settings.ai_embedding_dimension:
            return ModelAvailability(False, "模型向量维度与当前向量库不匹配，需要重新索引。")
        if credential is None or not credential.is_enabled or not credential.encrypted_api_key:
            return ModelAvailability(False, "管理员尚未配置该供应商 API key。")
        return ModelAvailability(True, None)

    def resolve_chat_model(self, *, user_id: int | None, requested_model_id: str | None) -> ResolvedModel:
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
        availability = self.availability_for_model(model)
        credential = self.repo.get_credential(model.provider_key)
        if not availability.available:
            raise ProviderConfigurationError(availability.reason or "Selected model is unavailable.")
        if user_id is not None and requested_model_id:
            self.repo.set_user_preference(user_id=user_id, chat_model_id=model.model_id)
        return ResolvedModel(model=model, provider=provider, credential=credential, availability=availability)

    def list_model_status(self, *, user_id: int | None = None) -> dict:
        self.ensure_seeded()
        defaults = self.repo.get_defaults()
        preference = self.repo.get_user_preference(user_id) if user_id is not None else None
        providers = {provider.provider_key: provider for provider in self.repo.list_providers()}
        credentials = {credential.provider_key: credential for credential in self.repo.list_credentials()}
        items = []
        for model in self.repo.list_models():
            provider = providers.get(model.provider_key)
            credential = credentials.get(model.provider_key)
            availability = self.availability_for_model(model)
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
                    "embeddingDimension": model.embedding_dimension,
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
    ) -> ModelInvocationResult:
        with _managed_session(self.session) as session:
            catalog = AIModelCatalogService(session)
            catalog.ensure_seeded()
            resolved = catalog.resolve_chat_model(user_id=user_id, requested_model_id=model_id)
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
            )
            adapter = build_chat_adapter(resolved.provider.provider_key)
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
