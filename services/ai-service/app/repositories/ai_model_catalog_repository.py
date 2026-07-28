from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.time import now_local
from app.models.ai_model_catalog import (
    AIModelCatalog,
    AIModelDefault,
    AIModelProvider,
    AIProviderCredential,
    AIUserModelPreference,
)


class AIModelCatalogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_providers(self) -> list[AIModelProvider]:
        return list(
            self.session.scalars(
                select(AIModelProvider).order_by(AIModelProvider.display_order.asc(), AIModelProvider.provider_key.asc())
            )
        )

    def list_models(self) -> list[AIModelCatalog]:
        return list(
            self.session.scalars(
                select(AIModelCatalog)
                .options(joinedload(AIModelCatalog.provider))
                .order_by(AIModelCatalog.display_order.asc(), AIModelCatalog.model_id.asc())
            )
        )

    def get_model(self, model_id: str) -> AIModelCatalog | None:
        return self.session.get(AIModelCatalog, model_id)

    def get_provider(self, provider_key: str) -> AIModelProvider | None:
        return self.session.get(AIModelProvider, provider_key)

    def get_credential(self, provider_key: str) -> AIProviderCredential | None:
        return self.session.get(AIProviderCredential, provider_key)

    def list_credentials(self) -> list[AIProviderCredential]:
        return list(self.session.scalars(select(AIProviderCredential)))

    def upsert_provider(
        self,
        *,
        provider_key: str,
        display_name: str,
        adapter_type: str,
        default_base_url: str | None,
        backend_supported: bool,
        display_order: int,
    ) -> AIModelProvider:
        provider = self.get_provider(provider_key)
        if provider is None:
            provider = AIModelProvider(provider_key=provider_key)
            self.session.add(provider)
        provider.display_name = display_name
        provider.adapter_type = adapter_type
        provider.default_base_url = default_base_url
        provider.backend_supported = backend_supported
        provider.display_order = display_order
        self.session.flush()
        return provider

    def upsert_model(
        self,
        *,
        model_id: str,
        provider_key: str,
        model_name: str,
        display_name: str,
        backend_supported: bool,
        display_only: bool,
        supports_chat: bool,
        supports_json: bool,
        supports_embedding: bool,
        supports_rag_answer: bool,
        supports_rag_indexing: bool,
        embedding_dimension: int | None,
        paired_embedding_model_id: str | None,
        display_order: int,
        unavailable_reason: str | None,
    ) -> AIModelCatalog:
        model = self.get_model(model_id)
        if model is None:
            model = AIModelCatalog(model_id=model_id)
            self.session.add(model)
        model.provider_key = provider_key
        model.model_name = model_name
        model.display_name = display_name
        model.backend_supported = backend_supported
        model.display_only = display_only
        model.supports_chat = supports_chat
        model.supports_json = supports_json
        model.supports_embedding = supports_embedding
        model.supports_rag_answer = supports_rag_answer
        model.supports_rag_indexing = supports_rag_indexing
        model.embedding_dimension = embedding_dimension
        model.paired_embedding_model_id = paired_embedding_model_id
        model.display_order = display_order
        model.unavailable_reason = unavailable_reason
        self.session.flush()
        return model

    def upsert_credential(
        self,
        *,
        provider_key: str,
        encrypted_api_key: str | None,
        api_key_hint: str | None,
        base_url_override: str | None,
        is_enabled: bool,
    ) -> AIProviderCredential:
        credential = self.get_credential(provider_key)
        if credential is None:
            credential = AIProviderCredential(provider_key=provider_key)
            self.session.add(credential)
        if encrypted_api_key is not None:
            credential.encrypted_api_key = encrypted_api_key
            credential.api_key_hint = api_key_hint
        credential.base_url_override = base_url_override
        credential.is_enabled = is_enabled
        credential.health_status = "unknown"
        credential.last_error = None
        self.session.flush()
        return credential

    def delete_credential(self, provider_key: str) -> bool:
        credential = self.get_credential(provider_key)
        if credential is None:
            return False
        self.session.delete(credential)
        self.session.flush()
        return True

    def update_credential_health(
        self,
        *,
        provider_key: str,
        health_status: str,
        last_error: str | None,
    ) -> AIProviderCredential | None:
        credential = self.get_credential(provider_key)
        if credential is None:
            return None
        credential.health_status = health_status
        credential.last_error = last_error
        credential.last_checked_at = now_local()
        self.session.flush()
        return credential

    def get_user_preference(self, user_id: int) -> AIUserModelPreference | None:
        return self.session.get(AIUserModelPreference, user_id)

    def set_user_preference(self, *, user_id: int, chat_model_id: str) -> AIUserModelPreference:
        preference = self.get_user_preference(user_id)
        if preference is None:
            preference = AIUserModelPreference(user_id=user_id, chat_model_id=chat_model_id)
            self.session.add(preference)
        preference.chat_model_id = chat_model_id
        self.session.flush()
        return preference

    def get_defaults(self, scope_key: str = "global") -> AIModelDefault | None:
        return self.session.get(AIModelDefault, scope_key)

    def set_defaults(
        self,
        *,
        default_chat_model_id: str | None,
        default_embedding_model_id: str | None,
        scope_key: str = "global",
    ) -> AIModelDefault:
        defaults = self.get_defaults(scope_key)
        if defaults is None:
            defaults = AIModelDefault(scope_key=scope_key)
            self.session.add(defaults)
        defaults.default_chat_model_id = default_chat_model_id
        defaults.default_embedding_model_id = default_embedding_model_id
        self.session.flush()
        return defaults

    def ensure_models_exist(self, model_ids: Iterable[str]) -> None:
        missing = [model_id for model_id in model_ids if model_id and self.get_model(model_id) is None]
        if missing:
            raise ValueError(f"Unknown AI model id: {', '.join(missing)}")
