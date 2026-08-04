from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.providers import model_service
from app.services.providers.model_service import (
    AIEmbeddingInvocationService,
    AIModelCatalogService,
    AIModelInvocationService,
)
from app.services.providers.types import (
    ProviderConfigurationError,
    ProviderEmbeddingResult,
    ProviderTextResult,
    ProviderUsage,
)


def _chat_model(
    model_id: str,
    provider_key: str,
    paired_embedding_model_id: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        model_id=model_id,
        provider_key=provider_key,
        model_name=model_id.split(":", 1)[-1],
        display_name=model_id,
        paired_embedding_model_id=paired_embedding_model_id,
        supports_chat=True,
        supports_json=True,
        supports_embedding=False,
        supports_rag_answer=True,
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
        model_name=model_id.split(":", 1)[-1],
        display_name=model_id,
        paired_embedding_model_id=None,
        supports_chat=False,
        supports_json=False,
        supports_embedding=True,
        supports_rag_answer=False,
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
            display_name="GLM",
            backend_supported=True,
        )
        self.credential = SimpleNamespace(
            provider_key="glm",
            is_enabled=True,
            encrypted_api_key="encrypted-test-key",
            health_status="ready",
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
            default_embedding_model_id="gemini:gemini-embedding-2",
        )


@pytest.mark.parametrize(
    ("health_status", "expected_available", "expected_reason"),
    [
        ("ready", True, None),
        ("unknown", False, "供应商尚未通过健康检查。"),
        ("failed", False, "供应商健康检查失败，当前暂不可用。"),
        ("quota", False, "供应商额度受限，当前暂不可用。"),
    ],
)
def test_model_catalog_only_marks_health_checked_provider_ready(
    monkeypatch,
    health_status: str,
    expected_available: bool,
    expected_reason: str | None,
) -> None:
    service, repository, _ = _service()
    repository.credential.health_status = health_status
    repository.list_providers = lambda: [repository.provider]
    repository.list_credentials = lambda: [repository.credential]
    repository.list_models = lambda: list(repository.models.values())
    repository.get_defaults = lambda: SimpleNamespace(
        default_chat_model_id="glm:glm-4.7",
        default_embedding_model_id="glm:embedding-3",
    )
    service.ensure_seeded = lambda: None
    monkeypatch.setattr(
        "app.services.providers.model_service."
        "AIKnowledgeSourceEmbeddingStatusesRepository",
        lambda _session: SimpleNamespace(
            get_coverage=lambda **_: SimpleNamespace(
                coverage=1.0,
                ready=True,
                status="ready",
            )
        ),
    )

    payload = service.list_model_status(user_id=None, course_id=11, module_id=22)
    chat_item = next(
        item for item in payload["items"] if item["modelId"] == "glm:glm-4.7"
    )

    assert chat_item["available"] is expected_available
    assert chat_item["ragReady"] is expected_available
    assert chat_item["unavailableReason"] == expected_reason


@pytest.mark.parametrize("health_status", ["unknown", "failed"])
def test_health_check_only_bypass_can_recheck_unhealthy_provider(
    health_status: str,
) -> None:
    service, repository, _ = _service()
    repository.credential.health_status = health_status

    with pytest.raises(ProviderConfigurationError):
        service.resolve_chat_model(
            user_id=None,
            requested_model_id="glm:glm-4.7",
        )
    with pytest.raises(ProviderConfigurationError):
        service.resolve_embedding_model(
            embedding_model_id="glm:embedding-3",
        )

    chat = service.resolve_chat_model(
        user_id=None,
        requested_model_id="glm:glm-4.7",
        bypass_health_status_for_health_check=True,
    )
    embedding = service.resolve_embedding_model(
        embedding_model_id="glm:embedding-3",
        bypass_health_status_for_health_check=True,
    )

    assert chat.model.model_id == "glm:glm-4.7"
    assert embedding.model.model_id == "glm:embedding-3"


def test_health_check_only_bypass_does_not_skip_disabled_credential() -> None:
    service, repository, _ = _service()
    repository.credential.health_status = "unknown"
    repository.credential.is_enabled = False

    with pytest.raises(
        ProviderConfigurationError,
        match="管理员尚未配置该供应商 API key",
    ):
        service.resolve_chat_model(
            user_id=None,
            requested_model_id="glm:glm-4.7",
            bypass_health_status_for_health_check=True,
        )


def test_invocation_health_check_bypass_is_explicit_and_cache_isolated(
    monkeypatch,
) -> None:
    resolution_calls: list[tuple[str, dict]] = []
    resolved_chat = SimpleNamespace(
        model=SimpleNamespace(
            model_id="glm:glm-4.7",
            model_name="glm-4.7",
            supports_json=True,
        ),
        provider=SimpleNamespace(
            provider_key="glm",
            adapter_type="openai_compatible",
        ),
    )
    resolved_embedding = SimpleNamespace(
        model=SimpleNamespace(
            model_id="glm:embedding-3",
            model_name="embedding-3",
            embedding_dimension=1024,
        ),
        provider=SimpleNamespace(
            provider_key="glm",
            adapter_type="openai_compatible",
        ),
    )

    class FakeCatalog:
        def __init__(self, _session) -> None:
            pass

        def ensure_seeded(self) -> None:
            pass

        def resolve_chat_model(self, **kwargs):
            resolution_calls.append(("chat", kwargs))
            return resolved_chat

        def resolve_embedding_model(self, **kwargs):
            resolution_calls.append(("embedding", kwargs))
            return resolved_embedding

    monkeypatch.setattr(model_service, "AIModelCatalogService", FakeCatalog)
    monkeypatch.setattr(
        model_service,
        "ProviderCredentialService",
        lambda _session: SimpleNamespace(
            get_credentials_for_provider=lambda _provider: SimpleNamespace(
                api_key="test-key",
                base_url="https://provider.invalid/v1",
            )
        ),
    )
    monkeypatch.setattr(
        model_service,
        "build_chat_adapter",
        lambda _adapter_type: SimpleNamespace(
            generate_text=lambda _request: ProviderTextResult(
                text="OK",
                usage=ProviderUsage(),
            )
        ),
    )
    monkeypatch.setattr(
        model_service,
        "build_embedding_adapter",
        lambda _adapter_type: SimpleNamespace(
            embed=lambda _request: ProviderEmbeddingResult(
                vector=[0.0] * 1024,
                usage=ProviderUsage(),
            )
        ),
    )

    text_service = AIModelInvocationService(object())
    text_service.generate_text(
        prompt="check",
        system_instruction=None,
        model_id="glm:glm-4.7",
    )
    text_service.generate_text(
        prompt="check",
        system_instruction=None,
        model_id="glm:glm-4.7",
        bypass_health_status_for_health_check=True,
    )
    embedding_service = AIEmbeddingInvocationService(object())
    embedding_service.embed_text(
        text="check",
        model_id="glm:embedding-3",
        task_type="RETRIEVAL_QUERY",
    )
    embedding_service.embed_text(
        text="check",
        model_id="glm:embedding-3",
        task_type="RETRIEVAL_QUERY",
        bypass_health_status_for_health_check=True,
    )

    assert resolution_calls == [
        (
            "chat",
            {
                "user_id": None,
                "requested_model_id": "glm:glm-4.7",
                "bypass_health_status_for_health_check": False,
            },
        ),
        (
            "chat",
            {
                "user_id": None,
                "requested_model_id": "glm:glm-4.7",
                "bypass_health_status_for_health_check": True,
            },
        ),
        (
            "embedding",
            {
                "embedding_model_id": "glm:embedding-3",
                "bypass_health_status_for_health_check": False,
            },
        ),
        (
            "embedding",
            {
                "embedding_model_id": "glm:embedding-3",
                "bypass_health_status_for_health_check": True,
            },
        ),
    ]
