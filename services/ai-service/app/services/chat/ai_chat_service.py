from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.prompts import get_prompt_template
from app.core.time import now_local
from app.models.ai_chat_messages import (
    AIMessageGenerationStatus,
    AIMessageRole,
    AIMessageType,
)
from app.models.ai_chat_sessions import AIChatSession
from app.models.ai_prompt_logs import AIPromptCallType, AIPromptStatus
from app.repositories.ai_chat_messages_repository import AIChatMessagesRepository
from app.repositories.ai_chat_sessions_repository import AIChatSessionsRepository
from app.repositories.ai_prompt_logs_repository import AIPromptLogsRepository
from app.schemas.demo import ChatServiceRequest
from app.services.chat.rag_workflow_service import (
    AIChatConfigurationError,
    AIModelInvocationError,
    AIChatQuotaError,
    AIChatReplyResult,
    RAGWorkflowService,
    generate_chat_reply as workflow_generate_chat_reply,
)


logger = logging.getLogger(__name__)


class AIChatSessionError(RuntimeError):
    """Raised when the requested chat session is invalid."""


@dataclass(frozen=True)
class PersistedChatResult:
    session_id: int
    user_message_id: int
    assistant_message_id: int | None
    reply: str | None
    sources: list[dict[str, object]]
    model_id: str | None = None
    model_name: str | None = None
    provider: str | None = None
    request_id: str | None = None
    status: str = AIMessageGenerationStatus.COMPLETED.value
    retryable: bool = False
    error_code: str | None = None
    error_message: str | None = None


def generate_chat_reply(
    *,
    current_user_message: str,
    prompt_template_name: str = "chat_reply_v1",
    retrieval_result=None,
    conversation_history=None,
    db: Session | None = None,
    user_id: int | None = None,
    model_id: str | None = None,
) -> AIChatReplyResult:
    return workflow_generate_chat_reply(
        current_user_message=current_user_message,
        prompt_template_name=prompt_template_name,
        retrieval_result=retrieval_result,
        conversation_history=conversation_history,
        db=db,
        user_id=user_id,
        model_id=model_id,
    )


def _build_session_title(message: str) -> str:
    normalized = " ".join(message.split())
    return normalized[:80] if len(normalized) > 80 else normalized


def _build_summary_text(user_message: str, assistant_reply: str) -> str:
    summary = f"User: {user_message.strip()} Assistant: {assistant_reply.strip()}"
    normalized = " ".join(summary.split())
    return normalized[:1000] if len(normalized) > 1000 else normalized


def _load_or_create_session(db: Session, payload: ChatServiceRequest) -> AIChatSession:
    sessions_repo = AIChatSessionsRepository(db)
    if payload.session_id is None:
        if payload.module_id is not None and payload.course_id is None:
            raise AIChatSessionError(
                "A module-scoped chat session requires a course context."
            )
        return sessions_repo.create(
            user_id=payload.user_id,
            course_id=payload.course_id,
            module_id=payload.module_id,
            session_type="demo_chat",
            title=_build_session_title(payload.message),
        )

    session = sessions_repo.get_by_id(payload.session_id)
    if session is None:
        raise AIChatSessionError("Chat session does not exist.")
    if session.user_id != payload.user_id:
        raise AIChatSessionError("Chat session does not belong to the provided user.")
    if (
        payload.course_id is not None
        and payload.course_id != session.course_id
    ):
        raise AIChatSessionError("Chat session course context cannot change.")
    if (
        payload.module_id is not None
        and payload.module_id != session.module_id
    ):
        raise AIChatSessionError("Chat session module context cannot change.")
    if session.module_id is not None and session.course_id is None:
        raise AIChatSessionError("Chat session has an invalid context.")
    return session


def _status_value(message) -> str:
    status_value = getattr(message, "generation_status", AIMessageGenerationStatus.COMPLETED)
    return status_value.value if hasattr(status_value, "value") else str(status_value)


def _result_for_existing_message(
    *,
    messages_repo: AIChatMessagesRepository,
    session: AIChatSession,
    user_message,
) -> PersistedChatResult:
    status_value = _status_value(user_message)
    request_id = getattr(user_message, "client_request_id", None)
    if status_value == AIMessageGenerationStatus.PENDING.value:
        return PersistedChatResult(
            session_id=session.session_id,
            user_message_id=user_message.message_id,
            assistant_message_id=None,
            reply=None,
            sources=[],
            request_id=request_id,
            status=AIMessageGenerationStatus.PENDING.value,
        )

    if status_value == AIMessageGenerationStatus.FAILED.value:
        return PersistedChatResult(
            session_id=session.session_id,
            user_message_id=user_message.message_id,
            assistant_message_id=None,
            reply=None,
            sources=[],
            request_id=request_id,
            status=AIMessageGenerationStatus.FAILED.value,
            retryable=True,
            error_code=getattr(user_message, "failure_code", None) or "AI_PROVIDER_UNAVAILABLE",
            error_message=getattr(user_message, "failure_message", None)
            or "The AI provider is temporarily unavailable. Please try again shortly.",
        )

    assistant_message = messages_repo.get_assistant_reply_for_user_message(user_message.message_id)
    if assistant_message is None:
        return PersistedChatResult(
            session_id=session.session_id,
            user_message_id=user_message.message_id,
            assistant_message_id=None,
            reply=None,
            sources=[],
            request_id=request_id,
            status=AIMessageGenerationStatus.FAILED.value,
            retryable=True,
            error_code="AI_REPLY_INCOMPLETE",
            error_message="The previous AI response was incomplete. Please retry the message.",
        )

    response_metadata = {}
    retrieval_trace = getattr(assistant_message, "retrieval_trace_json", None)
    if isinstance(retrieval_trace, dict):
        candidate_metadata = retrieval_trace.get("_chatResponse")
        if isinstance(candidate_metadata, dict):
            response_metadata = candidate_metadata
    sources = response_metadata.get("sources")
    if not isinstance(sources, list):
        sources = []

    return PersistedChatResult(
        session_id=session.session_id,
        user_message_id=user_message.message_id,
        assistant_message_id=assistant_message.message_id,
        reply=assistant_message.content_text,
        sources=sources,
        model_id=response_metadata.get("modelId"),
        model_name=response_metadata.get("model"),
        provider=response_metadata.get("provider"),
        request_id=request_id,
        status=AIMessageGenerationStatus.COMPLETED.value,
    )


def _ensure_existing_request_matches(
    *,
    session: AIChatSession,
    user_message,
    payload: ChatServiceRequest,
) -> None:
    if session.user_id != payload.user_id:
        raise AIChatSessionError("Chat request is unavailable.")
    if payload.session_id is not None and payload.session_id != session.session_id:
        raise AIChatSessionError("Chat request cannot be moved to another session.")
    if payload.course_id is not None and payload.course_id != session.course_id:
        raise AIChatSessionError("Chat request course context cannot change.")
    if payload.module_id is not None and payload.module_id != session.module_id:
        raise AIChatSessionError("Chat request module context cannot change.")
    if user_message.content_text != payload.message.strip():
        raise AIChatSessionError("Chat request id cannot be reused for a different message.")
    if getattr(user_message, "requested_model_id", None) != payload.model_id:
        raise AIChatSessionError("Chat request id cannot be reused with a different model.")


def _failure_details(exc: Exception) -> tuple[str, str, str]:
    if isinstance(exc, AIChatConfigurationError):
        return (
            "AI_NOT_CONFIGURED",
            "AI provider configuration is unavailable. Contact an administrator or try again later.",
            "configuration",
        )
    if isinstance(exc, AIChatQuotaError):
        return (
            "AI_QUOTA_EXCEEDED",
            "The AI provider quota is temporarily unavailable. Please try again later.",
            "quota",
        )
    if isinstance(exc, AIModelInvocationError):
        return (
            "AI_PROVIDER_UNAVAILABLE",
            "The AI provider is temporarily unavailable. Please try again shortly.",
            exc.provider_error_type,
        )
    return (
        "AI_INTERNAL_ERROR",
        "The AI response could not be completed. Please retry the message.",
        "unexpected_error",
    )


def _persist_generation_failure(
    *,
    db: Session,
    sessions_repo: AIChatSessionsRepository,
    messages_repo: AIChatMessagesRepository,
    prompt_logs_repo: AIPromptLogsRepository,
    session: AIChatSession,
    user_message,
    user_id: int,
    course_id: int | None,
    model_id: str | None,
    exc: Exception,
) -> PersistedChatResult:
    failure_code, failure_message, provider_error_type = _failure_details(exc)
    timestamp = now_local()
    messages_repo.mark_generation_failed(
        user_message,
        failure_code=failure_code,
        failure_message=failure_message,
        timestamp=timestamp,
    )
    request_json = {
        "orchestrator": getattr(exc, "orchestrator", "provider_adapter"),
        "chain_name": getattr(exc, "chain_name", "chat_generation"),
        "fallback_used": bool(getattr(exc, "fallback_used", False)),
        "provider_error_type": provider_error_type,
        "requestedModelId": model_id,
        "requestId": getattr(user_message, "client_request_id", None),
    }
    prompt_logs_repo.create(
        session_id=session.session_id,
        message_id=user_message.message_id,
        user_id=user_id,
        call_type=AIPromptCallType.CHAT,
        prompt_template_name="chat_rag_v1" if course_id is not None else "chat_reply_v1",
        model_name=model_id or settings.ai_default_chat_model,
        input_text=user_message.content_text,
        output_text=None,
        request_json=request_json,
        response_json={
            "provider_error_type": provider_error_type,
            "failure_code": failure_code,
        },
        status=AIPromptStatus.FAILED,
        error_message=failure_message,
        trace_id=None,
    )
    db.commit()
    return _result_for_existing_message(
        messages_repo=messages_repo,
        session=session,
        user_message=user_message,
    )


def _run_generation(
    *,
    db: Session,
    sessions_repo: AIChatSessionsRepository,
    messages_repo: AIChatMessagesRepository,
    prompt_logs_repo: AIPromptLogsRepository,
    session: AIChatSession,
    user_message,
    user_id: int,
    model_id: str | None,
) -> PersistedChatResult:
    course_id = session.course_id
    module_id = session.module_id
    try:
        workflow_result = RAGWorkflowService(db).execute_chat_workflow(
            user_id=user_id,
            session_id=session.session_id,
            message_id=user_message.message_id,
            current_user_message=user_message.content_text,
            course_id=course_id,
            module_id=module_id,
            model_id=model_id,
        )
    except (AIChatConfigurationError, AIChatQuotaError, AIModelInvocationError) as exc:
        return _persist_generation_failure(
            db=db,
            sessions_repo=sessions_repo,
            messages_repo=messages_repo,
            prompt_logs_repo=prompt_logs_repo,
            session=session,
            user_message=user_message,
            user_id=user_id,
            course_id=course_id,
            model_id=model_id,
            exc=exc,
        )
    except Exception as exc:
        logger.exception("Unexpected error while generating an AI chat response")
        return _persist_generation_failure(
            db=db,
            sessions_repo=sessions_repo,
            messages_repo=messages_repo,
            prompt_logs_repo=prompt_logs_repo,
            session=session,
            user_message=user_message,
            user_id=user_id,
            course_id=course_id,
            model_id=model_id,
            exc=exc,
        )

    retrieval_message_id: int | None = None
    if workflow_result.used_retrieval and workflow_result.retrieval_context_text is not None:
        retrieval_message = messages_repo.create(
            session_id=session.session_id,
            role=AIMessageRole.SYSTEM,
            message_type=AIMessageType.RETRIEVAL_CONTEXT,
            parent_message_id=user_message.message_id,
            content_text=workflow_result.retrieval_context_text,
            is_visible_to_user=False,
            retrieval_trace_json=workflow_result.retrieval_result.retrieval_trace_json
            if workflow_result.retrieval_result is not None
            else None,
        )
        retrieval_message_id = retrieval_message.message_id

    reply_request_json = (
        workflow_result.reply_result.request_json
        if isinstance(workflow_result.reply_result.request_json, dict)
        else {}
    )
    assistant_trace = (
        dict(workflow_result.retrieval_result.retrieval_trace_json)
        if workflow_result.used_retrieval
        and workflow_result.retrieval_result is not None
        and isinstance(workflow_result.retrieval_result.retrieval_trace_json, dict)
        else {}
    )
    assistant_trace["_chatResponse"] = {
        "sources": workflow_result.sources,
        "modelId": reply_request_json.get("modelId"),
        "model": reply_request_json.get("model"),
        "provider": reply_request_json.get("provider"),
    }

    assistant_message = messages_repo.create(
        session_id=session.session_id,
        role=AIMessageRole.ASSISTANT,
        parent_message_id=user_message.message_id,
        content_text=workflow_result.reply_result.reply,
        retrieval_trace_json=assistant_trace,
    )

    prompt_logs_repo.create(
        session_id=session.session_id,
        message_id=assistant_message.message_id,
        user_id=user_id,
        call_type=AIPromptCallType.CHAT,
        prompt_template_name=get_prompt_template(workflow_result.prompt_template_name).name,
        model_name=(
            str(workflow_result.reply_result.request_json.get("model") or "guardrail")
            if isinstance(workflow_result.reply_result.request_json, dict)
            else settings.ai_default_chat_model
        ),
        input_text=user_message.content_text,
        output_text=workflow_result.reply_result.reply,
        request_json=workflow_result.reply_result.request_json,
        response_json=workflow_result.reply_result.response_json,
        prompt_tokens=workflow_result.reply_result.prompt_tokens,
        completion_tokens=workflow_result.reply_result.completion_tokens,
        total_tokens=workflow_result.reply_result.total_tokens,
        latency_ms=workflow_result.reply_result.latency_ms,
        status=workflow_result.reply_result.status,
        error_message=workflow_result.reply_result.error_message,
        trace_id=workflow_result.reply_result.trace_id,
    )

    if workflow_result.retrieval_result is not None and retrieval_message_id is not None:
        prompt_logs_repo.create(
            session_id=session.session_id,
            message_id=retrieval_message_id,
            user_id=user_id,
            call_type=AIPromptCallType.RETRIEVAL,
            prompt_template_name=None,
            model_name=workflow_result.retrieval_result.query_embedding_model,
            input_text=user_message.content_text,
            output_text=None,
            request_json={
                "filters": workflow_result.retrieval_result.filters_json,
                "queryText": workflow_result.retrieval_result.query_text,
                "topK": workflow_result.retrieval_result.retrieval_trace_json.get("topK"),
            },
            response_json=workflow_result.retrieval_result.retrieval_trace_json,
            status=AIPromptStatus.SUCCESS,
            latency_ms=workflow_result.retrieval_result.latency_ms,
            error_message=None,
            trace_id=None,
        )

    completed_at = now_local()
    messages_repo.mark_generation_completed(user_message, timestamp=completed_at)
    sessions_repo.update_activity(
        session,
        last_message_at=completed_at,
        last_user_message_at=getattr(session, "last_user_message_at", None) or completed_at,
        last_assistant_message_at=completed_at,
        message_increment=1,
        summary_text=_build_summary_text(user_message.content_text, workflow_result.reply_result.reply),
    )
    db.commit()
    db.refresh(session)

    return PersistedChatResult(
        session_id=session.session_id,
        user_message_id=user_message.message_id,
        assistant_message_id=assistant_message.message_id,
        reply=workflow_result.reply_result.reply,
        sources=workflow_result.sources,
        model_id=reply_request_json.get("modelId"),
        model_name=reply_request_json.get("model"),
        provider=reply_request_json.get("provider"),
        request_id=getattr(user_message, "client_request_id", None),
        status=AIMessageGenerationStatus.COMPLETED.value,
    )


def persist_chat(db: Session, payload: ChatServiceRequest) -> PersistedChatResult:
    """Persist a visible pending user message before invoking the provider.

    The client request id turns retry-after-timeout into an idempotent read of the
    original state instead of a duplicate provider call.
    """
    sessions_repo = AIChatSessionsRepository(db)
    messages_repo = AIChatMessagesRepository(db)
    prompt_logs_repo = AIPromptLogsRepository(db)
    request_id = (payload.request_id or str(uuid4())).strip()

    existing_message = messages_repo.get_by_client_request_id(request_id)
    if existing_message is not None:
        existing_session = sessions_repo.get_by_id(existing_message.session_id)
        if existing_session is None:
            raise AIChatSessionError("Chat request is unavailable.")
        _ensure_existing_request_matches(
            session=existing_session,
            user_message=existing_message,
            payload=payload,
        )
        return _result_for_existing_message(
            messages_repo=messages_repo,
            session=existing_session,
            user_message=existing_message,
        )

    session = _load_or_create_session(db, payload)
    timestamp = now_local()
    try:
        user_message = messages_repo.create(
            session_id=session.session_id,
            role=AIMessageRole.USER,
            content_text=payload.message.strip(),
            client_request_id=request_id,
            requested_model_id=payload.model_id,
            generation_status=AIMessageGenerationStatus.PENDING,
            generation_attempt_count=1,
            generation_started_at=timestamp,
        )
        sessions_repo.record_user_message(session, timestamp=timestamp)
        db.commit()
    except IntegrityError:
        # Concurrent delivery of the same idempotency key loses this insert race
        # and must return the in-progress/original result, not invoke twice.
        db.rollback()
        existing_message = messages_repo.get_by_client_request_id(request_id)
        if existing_message is None:
            raise
        existing_session = sessions_repo.get_by_id(existing_message.session_id)
        if existing_session is None:
            raise AIChatSessionError("Chat request is unavailable.")
        _ensure_existing_request_matches(
            session=existing_session,
            user_message=existing_message,
            payload=payload,
        )
        return _result_for_existing_message(
            messages_repo=messages_repo,
            session=existing_session,
            user_message=existing_message,
        )

    return _run_generation(
        db=db,
        sessions_repo=sessions_repo,
        messages_repo=messages_repo,
        prompt_logs_repo=prompt_logs_repo,
        session=session,
        user_message=user_message,
        user_id=payload.user_id,
        model_id=payload.model_id,
    )


def retry_chat(
    db: Session,
    *,
    user_id: int,
    message_id: int,
) -> PersistedChatResult:
    """Retry only the failed user message owned by the current user."""
    sessions_repo = AIChatSessionsRepository(db)
    messages_repo = AIChatMessagesRepository(db)
    prompt_logs_repo = AIPromptLogsRepository(db)
    user_message = messages_repo.get_by_id_for_update(message_id)
    if user_message is None or _status_value(user_message) not in {
        AIMessageGenerationStatus.FAILED.value,
        AIMessageGenerationStatus.PENDING.value,
        AIMessageGenerationStatus.COMPLETED.value,
    }:
        raise AIChatSessionError("Chat message is unavailable.")
    session = sessions_repo.get_by_id(user_message.session_id)
    if session is None or session.user_id != user_id:
        raise AIChatSessionError("Chat message is unavailable.")
    role = user_message.role.value if hasattr(user_message.role, "value") else str(user_message.role)
    if role != AIMessageRole.USER.value:
        raise AIChatSessionError("Only user messages can be retried.")

    current_result = _result_for_existing_message(
        messages_repo=messages_repo,
        session=session,
        user_message=user_message,
    )
    if current_result.status != AIMessageGenerationStatus.FAILED.value:
        return current_result

    timestamp = now_local()
    messages_repo.mark_generation_pending(user_message, timestamp=timestamp)
    db.commit()
    return _run_generation(
        db=db,
        sessions_repo=sessions_repo,
        messages_repo=messages_repo,
        prompt_logs_repo=prompt_logs_repo,
        session=session,
        user_message=user_message,
        user_id=user_id,
        model_id=getattr(user_message, "requested_model_id", None),
    )
