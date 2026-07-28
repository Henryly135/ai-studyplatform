from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import admin_ai_models
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.ai_model_catalog import (
    AIModelCatalog,
    AIModelDefault,
    AIModelProvider,
    AIProviderCredential,
    AIUserModelPreference,
)
from app.schemas.ai_models import AdminAIProviderCredentialRequest


def test_saving_enabled_provider_key_queues_historical_vector_backfill(
    monkeypatch,
) -> None:
    calls: list[tuple[str, object]] = []
    provider = SimpleNamespace(
        provider_key="glm",
        default_base_url="https://open.bigmodel.cn/api/paas/v4",
    )
    credential = SimpleNamespace(
        encrypted_api_key="encrypted",
        is_enabled=True,
        api_key_hint="****test",
        base_url_override=None,
        health_status="unknown",
    )

    monkeypatch.setattr(
        admin_ai_models,
        "AIModelCatalogService",
        lambda _db: SimpleNamespace(ensure_seeded=lambda: None),
    )
    monkeypatch.setattr(
        admin_ai_models,
        "ProviderCredentialService",
        lambda _db: SimpleNamespace(
            save_credentials=lambda **kwargs: (
                calls.append(("credential", kwargs)) or credential
            )
        ),
    )
    monkeypatch.setattr(
        admin_ai_models,
        "IndexJobService",
        lambda _db: SimpleNamespace(
            reindex_all_materials=lambda: calls.append(("backfill", None))
        ),
    )
    monkeypatch.setattr(
        admin_ai_models,
        "AIModelCatalogRepository",
        lambda _db: SimpleNamespace(
            get_provider=lambda _provider_key: provider
        ),
    )

    response = admin_ai_models.upsert_admin_ai_provider_credential(
        provider_key="glm",
        payload=AdminAIProviderCredentialRequest(
            apiKey="sk-test",
            enabled=True,
        ),
        current_user={"user_id": 1},
        db=object(),
    )

    assert response.provider == "glm"
    assert response.configured is True
    assert [name for name, _ in calls] == ["credential", "backfill"]


def test_admin_provider_list_filters_legacy_removed_provider(
    monkeypatch,
) -> None:
    providers = [
        SimpleNamespace(
            provider_key=provider_key,
            display_name=provider_key.upper(),
            backend_supported=True,
            default_base_url=None,
        )
        for provider_key in ["gemini", "glm", "openrouter", "deepseek"]
    ]
    repository = SimpleNamespace(
        list_providers=lambda: providers,
        get_credential=lambda _provider_key: None,
        get_defaults=lambda: None,
    )
    monkeypatch.setattr(
        admin_ai_models,
        "AIModelCatalogService",
        lambda _db: SimpleNamespace(ensure_seeded=lambda: None),
    )
    monkeypatch.setattr(
        admin_ai_models,
        "AIModelCatalogRepository",
        lambda _db: repository,
    )

    response = admin_ai_models.list_admin_ai_providers(
        current_user={"user_id": 1},
        db=object(),
    )

    assert [item.provider for item in response.providers] == [
        "gemini",
        "glm",
        "openrouter",
    ]


def test_admin_provider_http_lifecycle_uses_auth_real_db_and_encryption(
    monkeypatch,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            AIModelProvider.__table__,
            AIModelCatalog.__table__,
            AIProviderCredential.__table__,
            AIUserModelPreference.__table__,
            AIModelDefault.__table__,
        ],
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    backfill_calls = []
    monkeypatch.setattr(
        "app.services.providers.credentials.settings",
        SimpleNamespace(
            ai_provider_key_encryption_secret="integration-test-secret"
        ),
    )
    monkeypatch.setattr(
        admin_ai_models,
        "IndexJobService",
        lambda _db: SimpleNamespace(
            reindex_all_materials=lambda: backfill_calls.append("queued")
        ),
    )

    def override_db():
        with testing_session() as session:
            yield session

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db_session] = override_db
    try:
        with TestClient(app) as client:
            unauthorized = client.get("/admin/ai/providers")
            assert unauthorized.status_code == 401

            app.dependency_overrides[
                admin_ai_models.require_ai_governance_manage_permission
            ] = lambda: {"id": 1}

            saved = client.put(
                "/admin/ai/providers/glm/credential",
                json={
                    "apiKey": "glm-key-one",
                    "baseUrl": " https://glm.example/v4 ",
                    "enabled": True,
                },
            )
            assert saved.status_code == 200
            assert saved.json()["apiKeyHint"] == "****-one"
            assert "glm-key-one" not in saved.text
            assert backfill_calls == ["queued"]

            defaults = client.patch(
                "/admin/ai/defaults",
                json={"defaultChatModelId": "glm:glm-4.7"},
            )
            assert defaults.status_code == 200
            assert defaults.json() == {
                "defaultChatModelId": "glm:glm-4.7",
                "defaultEmbeddingModelId": "glm:embedding-3",
            }

            listed = client.get("/admin/ai/providers")
            assert listed.status_code == 200
            glm_item = next(
                item
                for item in listed.json()["providers"]
                if item["provider"] == "glm"
            )
            assert glm_item["configured"] is True
            assert glm_item["apiKeyHint"] == "****-one"
            assert "glm-key-one" not in listed.text

            overwritten = client.put(
                "/admin/ai/providers/glm/credential",
                json={"apiKey": "glm-key-two", "enabled": True},
            )
            assert overwritten.status_code == 200
            assert overwritten.json()["apiKeyHint"] == "****-two"
            assert backfill_calls == ["queued", "queued"]

            with testing_session() as session:
                rows = list(
                    session.scalars(
                        select(AIProviderCredential).where(
                            AIProviderCredential.provider_key == "glm"
                        )
                    )
                )
                assert len(rows) == 1
                assert rows[0].encrypted_api_key not in {
                    "glm-key-one",
                    "glm-key-two",
                }
                assert "glm-key-two" not in (rows[0].encrypted_api_key or "")

            removed = client.delete("/admin/ai/providers/glm/credential")
            assert removed.status_code == 200
            assert removed.json()["configured"] is False
            with testing_session() as session:
                assert session.get(AIProviderCredential, "glm") is None

            unsupported = client.put(
                "/admin/ai/providers/deepseek/credential",
                json={"apiKey": "legacy-key", "enabled": True},
            )
            assert unsupported.status_code == 400
            assert (
                unsupported.json()["error"]["code"]
                == "AI_PROVIDER_CONFIGURATION_INVALID"
            )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        Base.metadata.drop_all(
            engine,
            tables=[
                AIModelDefault.__table__,
                AIUserModelPreference.__table__,
                AIProviderCredential.__table__,
                AIModelCatalog.__table__,
                AIModelProvider.__table__,
            ],
        )
        engine.dispose()
