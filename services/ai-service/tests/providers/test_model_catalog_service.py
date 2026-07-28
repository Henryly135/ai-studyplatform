from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.providers.model_service import AIModelCatalogService
from app.services.providers.types import ProviderConfigurationError


def _chat_model(
    model_id: str,
    provider_key: str,
    paired_embedding_model_id: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        model_id=model_id,
        provider_key=provider_key,
        paired_embedding_model_id=paired_embedding_model_id,
        supports_chat=True,
        supports_embedding=False,
        supports_rag_indexing=False,
        embedding_dimension=None,
        is_enabled=True,
        backend_supported=True,
        display_only=False,
        unavailable_reason=None,
    )


def _embedding_model(model_id: str, provider_key: str) -> SimpleNamespace:
    return SimpleNamespace(
        model_id=model_id,
        provider_key=provider_key,
        paired_embedding_model_id=None,
        supports_chat=False,
        supports_embedding=True,
        supports_rag_indexing=True,
        embedding_dimension=1024,
        is_enabled=True,
        backend_supported=True,
        display_only=False,
        unavailable_reason=None,
    )


class FakeCatalogRepository:
    def __init__(self) -> None:
        chat = _chat_model("glm:glm-4.7", "glm", "glm:embedding-3")
        embedding = _embedding_model("glm:embedding-3", "glm")
        self.models = {chat.model_id: chat, embedding.model_id: embedding}
        self.provider = SimpleNamespace(
            provider_key="glm",
            backend_supported=True,
        )
        self.credential = SimpleNamespace(
            provider_key="glm",
            is_enabled=True,
            encrypted_api_key="encrypted-test-key",
        )
        self.preference_calls: list[tuple[int, str]] = []
        self.default_calls: list[tuple[str | None, str | None]] = []

    def get_model(self, model_id: str):
        return self.models.get(model_id)

    def get_provider(self, provider_key: str):
        return self.provider if provider_key == "glm" else None

    def get_credential(self, provider_key: str):
        return self.credential if provider_key == "glm" else None

    def get_user_preference(self, _user_id: int):
        return None

    def set_user_preference(self, *, user_id: int, chat_model_id: str) -> None:
        self.preference_calls.append((user_id, chat_model_id))

    def set_defaults(
        self,
        *,
        default_chat_model_id: str | None,
        default_embedding_model_id: str | None,
    ) -> None:
        self.default_calls.append(
            (default_chat_model_id, default_embedding_model_id)
        )


def _service() -> tuple[AIModelCatalogService, FakeCatalogRepository, SimpleNamespace]:
    session = SimpleNamespace(commit_count=0)

    def commit() -> None:
        session.commit_count += 1

    session.commit = commit
    repository = FakeCatalogRepository()
    service = AIModelCatalogService(session)
    service.repo = repository
    return service, repository, session


def test_explicit_chat_selection_resolves_authoritative_embedding_pair() -> None:
    service, repository, _ = _service()

    pair = service.resolve_model_pair(
        user_id=42,
        requested_model_id="glm:glm-4.7",
    )

    assert pair.chat.model.model_id == "glm:glm-4.7"
    assert pair.embedding.model.model_id == "glm:embedding-3"
    assert pair.embedding.model.embedding_dimension == 1024
    assert repository.preference_calls == [(42, "glm:glm-4.7")]


def test_default_embedding_is_derived_from_chat_model() -> None:
    service, repository, session = _service()

    service.set_defaults(
        default_chat_model_id="glm:glm-4.7",
        default_embedding_model_id=None,
    )

    assert repository.default_calls == [
        ("glm:glm-4.7", "glm:embedding-3")
    ]
    assert session.commit_count == 1


def test_default_api_cannot_override_chat_embedding_pair() -> None:
    service, _, _ = _service()

    with pytest.raises(
        ProviderConfigurationError,
        match="derived from the selected chat model",
    ):
        service.set_defaults(
            default_chat_model_id="glm:glm-4.7",
            default_embedding_model_id="gemini:gemini-embedding-001",
        )
