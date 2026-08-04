import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_identity_permission
from app.core.uuid_codec import encode_session_uuid
from app.db.session import get_db_session
from app.schemas.demo import AIHealthResponse, ChatResponse, ChatServiceRequest
from app.services.providers.model_service import AIModelCatalogService
from app.services.chat.ai_chat_service import (
    AIChatConfigurationError,
    AIChatQuotaError,
    AIChatSessionError,
    persist_chat,
)
from app.services.provider_error_messages import (
    AI_PROVIDER_CONFIGURATION_UNAVAILABLE,
    AI_PROVIDER_QUOTA_UNAVAILABLE,
    CHAT_SESSION_INVALID,
)
from platform_common.permissions.codes import AI_CHAT_USE


router = APIRouter(prefix="/demo", tags=["demo"])
logger = logging.getLogger(__name__)


def _demo_payload_for_authenticated_user(payload: ChatServiceRequest, current_user: dict) -> ChatServiceRequest:
    return ChatServiceRequest(
        session_id=payload.session_id,
        user_id=int(current_user["id"]),
        message=payload.message,
        model_id=payload.model_id,
    )


@router.get("/health", response_model=AIHealthResponse)
def demo_health(db: Session = Depends(get_db_session)) -> AIHealthResponse:
    catalog = AIModelCatalogService(db)
    catalog.ensure_seeded()
    payload = catalog.list_model_status()
    default_model_id = payload.get("defaultChatModelId")
    default_item = next(
        (
            item
            for item in payload["items"]
            if item["modelId"] == default_model_id
        ),
        None,
    )
    if default_item is None or not default_item["available"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AI_PROVIDER_CONFIGURATION_UNAVAILABLE,
        )

    return AIHealthResponse(
        status="ok",
        module="ai-demo",
        provider=default_item["provider"],
        model=default_item["modelName"],
        configured=True,
    )


@router.post("/chat", response_model=ChatResponse)
def demo_chat(
    payload: ChatServiceRequest,
    current_user: dict = Depends(require_identity_permission(AI_CHAT_USE)),
    db: Session = Depends(get_db_session),
) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    try:
        result = persist_chat(db, _demo_payload_for_authenticated_user(payload, current_user))
        return ChatResponse(
            session_uuid=encode_session_uuid(result.session_id),
            user_message_id=result.user_message_id,
            assistant_message_id=result.assistant_message_id,
            reply=result.reply,
            sources=result.sources,
            model_id=getattr(result, "model_id", None),
            model_name=getattr(result, "model_name", None),
            provider=getattr(result, "provider", None),
        )
    except AIChatConfigurationError as exc:
        db.rollback()
        logger.error("AI demo provider is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AI_PROVIDER_CONFIGURATION_UNAVAILABLE,
        ) from exc
    except AIChatQuotaError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=AI_PROVIDER_QUOTA_UNAVAILABLE,
        ) from exc
    except AIChatSessionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CHAT_SESSION_INVALID,
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error while processing demo chat request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI provider call failed.",
        ) from exc
