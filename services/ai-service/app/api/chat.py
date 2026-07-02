import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.uuid_codec import (
    decode_course_uuid,
    decode_module_uuid,
    decode_session_uuid,
    encode_course_uuid,
    encode_module_uuid,
    encode_session_uuid,
)
from app.api.deps import require_identity_permission
from app.db.session import get_db_session
from app.repositories.ai_chat_messages_repository import AIChatMessagesRepository
from app.repositories.ai_chat_sessions_repository import AIChatSessionsRepository
from app.schemas.demo import (
    APIErrorResponse,
    ChatRequest,
    ChatResponse,
    ChatSuccessResponse,
    ChatMessageItem,
    ChatSessionDetail,
    ChatSessionSummary,
    ChatServiceRequest,
)
from app.services.chat.ai_chat_service import (
    AIChatConfigurationError,
    AIChatQuotaError,
    AIChatSessionError,
    AIModelInvocationError,
    persist_chat,
)
from app.services.chat.learning_context_access_client import LearningContextAccessClient
from app.services.provider_error_messages import (
    AI_PROVIDER_CONFIGURATION_UNAVAILABLE,
    AI_PROVIDER_QUOTA_UNAVAILABLE,
    CHAT_SESSION_INVALID,
)
from platform_common.permissions.codes import AI_CHAT_USE


router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _serialize_session(session_row) -> ChatSessionSummary:
    return ChatSessionSummary(
        session_uuid=encode_session_uuid(session_row.session_id),
        user_id=session_row.user_id,
        course_uuid=encode_course_uuid(session_row.course_id) if session_row.course_id else None,
        module_uuid=encode_module_uuid(session_row.module_id) if session_row.module_id else None,
        session_type=session_row.session_type,
        title=session_row.title,
        status=session_row.status.value if hasattr(session_row.status, "value") else str(session_row.status),
        message_count=session_row.message_count,
        summary_text=session_row.summary_text,
        last_message_at=session_row.last_message_at.isoformat() if session_row.last_message_at else None,
        created_at=session_row.created_at.isoformat(),
        updated_at=session_row.updated_at.isoformat(),
    )


def _serialize_message(message_row) -> ChatMessageItem:
    return ChatMessageItem(
        message_id=message_row.message_id,
        session_uuid=encode_session_uuid(message_row.session_id),
        role=message_row.role.value if hasattr(message_row.role, "value") else str(message_row.role),
        message_type=message_row.message_type.value
        if hasattr(message_row.message_type, "value")
        else str(message_row.message_type),
        parent_message_id=message_row.parent_message_id,
        content_text=message_row.content_text,
        created_at=message_row.created_at.isoformat(),
    )


def _ensure_session_context_access(session_row, current_user: dict) -> None:
    if not session_row.course_id:
        return

    LearningContextAccessClient().ensure_chat_context_access(
        course_uuid=encode_course_uuid(session_row.course_id),
        module_uuid=encode_module_uuid(session_row.module_id) if session_row.module_id else None,
        current_user=current_user,
    )


def _filter_accessible_sessions(session_rows, current_user: dict) -> list:
    accessible_sessions = []
    for session_row in session_rows:
        try:
            _ensure_session_context_access(session_row, current_user)
        except HTTPException as exc:
            if exc.status_code in {
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_423_LOCKED,
            }:
                continue
            raise
        accessible_sessions.append(session_row)
    return accessible_sessions


@router.post("/chat", response_model=ChatSuccessResponse)
def chat(
    payload: ChatRequest,
    current_user: dict = Depends(require_identity_permission(AI_CHAT_USE)),
    db: Session = Depends(get_db_session),
) -> ChatSuccessResponse:
    try:
        if payload.module_uuid and not payload.course_uuid:
            raise _http_error(
                status.HTTP_400_BAD_REQUEST,
                "AI_COURSE_CONTEXT_REQUIRED",
                "module_uuid requires course_uuid.",
            )
        if payload.course_uuid:
            LearningContextAccessClient().ensure_chat_context_access(
                course_uuid=payload.course_uuid,
                module_uuid=payload.module_uuid,
                current_user=current_user,
            )

        service_payload = ChatServiceRequest(
            session_id=decode_session_uuid(payload.session_uuid) if payload.session_uuid else None,
            user_id=int(current_user["id"]),
            course_id=decode_course_uuid(payload.course_uuid) if payload.course_uuid else None,
            module_id=decode_module_uuid(payload.module_uuid) if payload.module_uuid else None,
            message=payload.message,
            model_id=payload.model_id,
        )
        chat_response = persist_chat(db, service_payload)
        return ChatSuccessResponse(
            data=ChatResponse(
                session_uuid=encode_session_uuid(chat_response.session_id),
                user_message_id=chat_response.user_message_id,
                assistant_message_id=chat_response.assistant_message_id,
                reply=chat_response.reply,
                sources=chat_response.sources,
                model_id=getattr(chat_response, "model_id", None),
                model_name=getattr(chat_response, "model_name", None),
                provider=getattr(chat_response, "provider", None),
            )
        )
    except HTTPException:
        db.rollback()
        raise
    except AIChatConfigurationError as exc:
        db.rollback()
        raise _http_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI_NOT_CONFIGURED",
            AI_PROVIDER_CONFIGURATION_UNAVAILABLE,
        ) from exc
    except AIChatQuotaError as exc:
        db.rollback()
        raise _http_error(status.HTTP_429_TOO_MANY_REQUESTS, "AI_QUOTA_EXCEEDED", AI_PROVIDER_QUOTA_UNAVAILABLE) from exc
    except AIChatSessionError as exc:
        db.rollback()
        raise _http_error(status.HTTP_400_BAD_REQUEST, "CHAT_SESSION_INVALID", CHAT_SESSION_INVALID) from exc
    except AIModelInvocationError as exc:
        db.rollback()
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.provider_error_type in {"provider_timeout", "transient_network_error", "unknown_provider_error"}
            else status.HTTP_502_BAD_GATEWAY
        )
        raise _http_error(
            status_code,
            "AI_PROVIDER_UNAVAILABLE",
            "The AI provider is temporarily unavailable. Please try again shortly.",
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error while processing authenticated chat request")
        raise _http_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "AI_INTERNAL_ERROR", "AI provider call failed.") from exc


@router.get("/chat/sessions", response_model=list[ChatSessionSummary])
def list_chat_sessions(
    current_user: dict = Depends(require_identity_permission(AI_CHAT_USE)),
    db: Session = Depends(get_db_session),
) -> list[ChatSessionSummary]:
    sessions = AIChatSessionsRepository(db).list_by_user(int(current_user["id"]))
    return [_serialize_session(session_row) for session_row in _filter_accessible_sessions(sessions, current_user)]


@router.get("/chat/modules/{module_uuid}/sessions", response_model=list[ChatSessionSummary])
def list_module_chat_sessions(
    module_uuid: str,
    current_user: dict = Depends(require_identity_permission(AI_CHAT_USE)),
    db: Session = Depends(get_db_session),
) -> list[ChatSessionSummary]:
    module_id = decode_module_uuid(module_uuid)
    sessions = AIChatSessionsRepository(db).list_by_user_and_module(
        user_id=int(current_user["id"]),
        module_id=module_id,
    )
    return [_serialize_session(session_row) for session_row in _filter_accessible_sessions(sessions, current_user)]


@router.get("/chat/sessions/{session_uuid}", response_model=ChatSessionDetail)
def get_chat_session(
    session_uuid: str,
    current_user: dict = Depends(require_identity_permission(AI_CHAT_USE)),
    db: Session = Depends(get_db_session),
) -> ChatSessionDetail:
    session_id = decode_session_uuid(session_uuid)
    sessions_repo = AIChatSessionsRepository(db)
    session_row = sessions_repo.get_by_id(session_id)
    if session_row is None or session_row.user_id != int(current_user["id"]):
        raise _http_error(status.HTTP_404_NOT_FOUND, "CHAT_SESSION_NOT_FOUND", "Chat session not found.")
    _ensure_session_context_access(session_row, current_user)

    messages = AIChatMessagesRepository(db).list_visible_by_session(session_id)
    return ChatSessionDetail(
        session=_serialize_session(session_row),
        messages=[_serialize_message(message_row) for message_row in messages],
    )
