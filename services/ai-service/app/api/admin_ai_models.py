from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_identity_permission
from app.db.session import get_db_session
from app.repositories.ai_model_catalog_repository import AIModelCatalogRepository
from app.schemas.ai_models import (
    AdminAIDefaultsRequest,
    AdminAIDefaultsResponse,
    AdminAIProviderCredentialItem,
    AdminAIProviderCredentialRequest,
    AdminAIProviderCredentialResponse,
    AdminAIProviderHealthCheckResponse,
    AdminAIProvidersResponse,
)
from app.services.providers.credentials import ProviderCredentialService, redact_secret_text
from app.services.indexing.index_job_service import IndexJobService
from app.services.providers.model_registry import SUPPORTED_PROVIDER_KEYS
from app.services.providers.model_service import (
    AIEmbeddingInvocationService,
    AIModelCatalogService,
    AIModelInvocationService,
)
from app.services.providers.types import ProviderConfigurationError, ProviderInvocationError, ProviderQuotaError
from platform_common.permissions.codes import AI_GOVERNANCE_MANAGE


router = APIRouter(prefix="/admin/ai", tags=["admin-ai-models"])
require_ai_governance_manage_permission = require_identity_permission(AI_GOVERNANCE_MANAGE)


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _serialize_provider(repo: AIModelCatalogRepository, provider) -> AdminAIProviderCredentialItem:
    credential = repo.get_credential(provider.provider_key)
    configured = bool(credential and credential.is_enabled and credential.encrypted_api_key)
    return AdminAIProviderCredentialItem(
        provider=provider.provider_key,
        providerLabel=provider.display_name,
        backendSupported=provider.backend_supported,
        configured=configured,
        enabled=bool(credential.is_enabled) if credential else False,
        apiKeyHint=credential.api_key_hint if credential else None,
        baseUrl=(credential.base_url_override if credential and credential.base_url_override else provider.default_base_url),
        healthStatus=credential.health_status if credential else "not_configured",
        lastCheckedAt=credential.last_checked_at.isoformat() if credential and credential.last_checked_at else None,
        lastError=credential.last_error if credential else None,
    )


@router.get("/providers", response_model=AdminAIProvidersResponse)
def list_admin_ai_providers(
    current_user: dict = Depends(require_ai_governance_manage_permission),
    db: Session = Depends(get_db_session),
) -> AdminAIProvidersResponse:
    _ = current_user
    catalog = AIModelCatalogService(db)
    catalog.ensure_seeded()
    repo = AIModelCatalogRepository(db)
    defaults = repo.get_defaults()
    return AdminAIProvidersResponse(
        providers=[
            _serialize_provider(repo, provider)
            for provider in repo.list_providers()
            if provider.provider_key in SUPPORTED_PROVIDER_KEYS
        ],
        defaultChatModelId=defaults.default_chat_model_id if defaults else None,
        defaultEmbeddingModelId=defaults.default_embedding_model_id if defaults else None,
    )


@router.put("/providers/{provider_key}/credential", response_model=AdminAIProviderCredentialResponse)
def upsert_admin_ai_provider_credential(
    provider_key: str,
    payload: AdminAIProviderCredentialRequest,
    current_user: dict = Depends(require_ai_governance_manage_permission),
    db: Session = Depends(get_db_session),
) -> AdminAIProviderCredentialResponse:
    _ = current_user
    AIModelCatalogService(db).ensure_seeded()
    try:
        credential = ProviderCredentialService(db).save_credentials(
            provider_key=provider_key,
            api_key=payload.apiKey,
            base_url_override=payload.baseUrl,
            is_enabled=payload.enabled,
        )
        if payload.enabled:
            IndexJobService(db).reindex_all_materials()
    except ProviderConfigurationError as exc:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "AI_PROVIDER_CONFIGURATION_INVALID", str(exc)) from exc
    repo = AIModelCatalogRepository(db)
    provider = repo.get_provider(provider_key)
    return AdminAIProviderCredentialResponse(
        provider=provider_key,
        configured=bool(credential.encrypted_api_key),
        enabled=credential.is_enabled,
        apiKeyHint=credential.api_key_hint,
        baseUrl=credential.base_url_override or (provider.default_base_url if provider else None),
        healthStatus=credential.health_status,
    )


@router.delete("/providers/{provider_key}/credential", response_model=AdminAIProviderCredentialResponse)
def delete_admin_ai_provider_credential(
    provider_key: str,
    current_user: dict = Depends(require_ai_governance_manage_permission),
    db: Session = Depends(get_db_session),
) -> AdminAIProviderCredentialResponse:
    _ = current_user
    AIModelCatalogService(db).ensure_seeded()
    try:
        ProviderCredentialService(db).delete_credentials(
            provider_key=provider_key
        )
    except ProviderConfigurationError as exc:
        raise _http_error(
            status.HTTP_400_BAD_REQUEST,
            "AI_PROVIDER_CONFIGURATION_INVALID",
            str(exc),
        ) from exc
    provider = AIModelCatalogRepository(db).get_provider(provider_key)
    return AdminAIProviderCredentialResponse(
        provider=provider_key,
        configured=False,
        enabled=False,
        apiKeyHint=None,
        baseUrl=provider.default_base_url if provider else None,
        healthStatus="not_configured",
    )


@router.post("/providers/{provider_key}/health-check", response_model=AdminAIProviderHealthCheckResponse)
def health_check_admin_ai_provider(
    provider_key: str,
    current_user: dict = Depends(require_ai_governance_manage_permission),
    db: Session = Depends(get_db_session),
) -> AdminAIProviderHealthCheckResponse:
    _ = current_user
    catalog = AIModelCatalogService(db)
    catalog.ensure_seeded()
    if provider_key not in SUPPORTED_PROVIDER_KEYS:
        raise _http_error(
            status.HTTP_400_BAD_REQUEST,
            "AI_PROVIDER_UNSUPPORTED",
            "该供应商不在当前版本的支持列表中。",
        )
    repo = AIModelCatalogRepository(db)
    provider_models = [
        model for model in repo.list_models() if model.provider_key == provider_key and model.supports_chat
    ]
    if not provider_models:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "AI_PROVIDER_UNSUPPORTED", "该供应商没有可用的聊天模型。")
    chat_model = provider_models[0]
    model_id = chat_model.model_id
    try:
        AIModelInvocationService(db).generate_text(
            prompt="Reply with OK.",
            system_instruction="You are checking whether an AI provider is reachable.",
            model_id=model_id,
            max_output_tokens=64,
            temperature=0,
            bypass_health_status_for_health_check=True,
        )
        embedding_model_id = chat_model.paired_embedding_model_id
        if not embedding_model_id:
            raise ProviderConfigurationError(
                "The provider chat model has no paired embedding model."
            )
        embedding_result = AIEmbeddingInvocationService(db).embed_text(
            text="AI provider embedding health check.",
            model_id=embedding_model_id,
            task_type="RETRIEVAL_QUERY",
            bypass_health_status_for_health_check=True,
        )
        if embedding_result.output_dimension != 1024:
            raise ProviderInvocationError(
                "AI provider health check returned an unexpected embedding dimension.",
                provider_error_type="invalid_provider_response",
            )
        repo.update_credential_health(provider_key=provider_key, health_status="ready", last_error=None)
        db.commit()
        IndexJobService(db).reindex_all_materials()
        return AdminAIProviderHealthCheckResponse(provider=provider_key, status="ready", message="供应商连接正常。")
    except ProviderQuotaError as exc:
        repo.update_credential_health(provider_key=provider_key, health_status="quota", last_error="供应商额度已受限。")
        db.commit()
        return AdminAIProviderHealthCheckResponse(provider=provider_key, status="quota", message=str(exc))
    except (ProviderConfigurationError, ProviderInvocationError) as exc:
        message = redact_secret_text(exc)
        repo.update_credential_health(provider_key=provider_key, health_status="failed", last_error=message)
        db.commit()
        return AdminAIProviderHealthCheckResponse(provider=provider_key, status="failed", message=message)


@router.patch("/defaults", response_model=AdminAIDefaultsResponse)
def update_admin_ai_defaults(
    payload: AdminAIDefaultsRequest,
    current_user: dict = Depends(require_ai_governance_manage_permission),
    db: Session = Depends(get_db_session),
) -> AdminAIDefaultsResponse:
    _ = current_user
    catalog = AIModelCatalogService(db)
    catalog.ensure_seeded()
    repo = AIModelCatalogRepository(db)
    current_defaults = repo.get_defaults()
    next_chat_model_id = (
        payload.defaultChatModelId
        if "defaultChatModelId" in payload.model_fields_set
        else current_defaults.default_chat_model_id if current_defaults else None
    )
    try:
        catalog.set_defaults(
            default_chat_model_id=next_chat_model_id,
            # Embedding defaults are always derived from the authoritative
            # chat-to-embedding catalog pair.
            default_embedding_model_id=None,
        )
    except ProviderConfigurationError as exc:
        raise _http_error(status.HTTP_400_BAD_REQUEST, "AI_DEFAULT_MODEL_INVALID", str(exc)) from exc
    defaults = repo.get_defaults()
    return AdminAIDefaultsResponse(
        defaultChatModelId=defaults.default_chat_model_id if defaults else None,
        defaultEmbeddingModelId=defaults.default_embedding_model_id if defaults else None,
    )
