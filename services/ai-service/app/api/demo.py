import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.uuid_codec import encode_session_uuid
from app.core.config import settings
from app.db.session import get_db_session
from app.schemas.demo import AIHealthResponse, ChatResponse, ChatServiceRequest
from app.services.chat.ai_chat_service import (
    AIChatConfigurationError,
    AIChatQuotaError,
    AIChatSessionError,
    persist_chat,
)
from app.services.providers import AIProviderConfigurationError, get_chat_provider


router = APIRouter(prefix="/demo", tags=["demo"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=AIHealthResponse)
def demo_health() -> AIHealthResponse:
    try:
        provider = get_chat_provider(settings)
    except AIProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return AIHealthResponse(
        status="ok",
        module="ai-demo",
        provider=provider.provider_name,
        model=getattr(settings, "ai_chat_model", getattr(settings, "ai_demo_model_name", "")),
        configured=True,
    )


@router.post("/chat", response_model=ChatResponse)
def demo_chat(
    payload: ChatServiceRequest,
    db: Session = Depends(get_db_session),
) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    try:
        result = persist_chat(db, payload)
        return ChatResponse(
            session_uuid=encode_session_uuid(result.session_id),
            user_message_id=result.user_message_id,
            assistant_message_id=result.assistant_message_id,
            reply=result.reply,
            sources=result.sources,
        )
    except AIChatConfigurationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AIChatQuotaError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except AIChatSessionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error while processing demo chat request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI provider call failed.",
        ) from exc
