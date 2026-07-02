from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.prompts import get_prompt_template
from app.core.time import now_local
from app.models.ai_chat_messages import AIMessageRole, AIMessageType
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


class AIChatSessionError(RuntimeError):
    """Raised when the requested chat session is invalid."""


@dataclass(frozen=True)
class PersistedChatResult:
    session_id: int
    user_message_id: int
    assistant_message_id: int
    reply: str
    sources: list[dict[str, object]]


def generate_chat_reply(
    *,
    current_user_message: str,
    prompt_template_name: str = "chat_reply_v1",
    retrieval_result=None,
    conversation_history=None,
) -> AIChatReplyResult:
    return workflow_generate_chat_reply(
        current_user_message=current_user_message,
        prompt_template_name=prompt_template_name,
        retrieval_result=retrieval_result,
        conversation_history=conversation_history,
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
    return session


def persist_chat(db: Session, payload: ChatServiceRequest) -> PersistedChatResult:
    sessions_repo = AIChatSessionsRepository(db)
    messages_repo = AIChatMessagesRepository(db)
    prompt_logs_repo = AIPromptLogsRepository(db)
    session = _load_or_create_session(db, payload)
    timestamp = now_local()

    user_message = messages_repo.create(
        session_id=session.session_id,
        role=AIMessageRole.USER,
        content_text=payload.message.strip(),
    )
    sessions_repo.record_user_message(
        session,
        course_id=payload.course_id,
        module_id=payload.module_id,
        timestamp=timestamp,
    )
    db.commit()
    db.refresh(session)
    db.refresh(user_message)

    try:
        workflow_result = RAGWorkflowService(db).execute_chat_workflow(
            user_id=payload.user_id,
            session_id=session.session_id,
            message_id=user_message.message_id,
            current_user_message=payload.message.strip(),
            course_id=payload.course_id,
            module_id=payload.module_id,
        )
    except AIModelInvocationError as exc:
        prompt_logs_repo.create(
            session_id=session.session_id,
            message_id=user_message.message_id,
            user_id=payload.user_id,
            call_type=AIPromptCallType.CHAT,
            prompt_template_name="chat_rag_v1" if payload.course_id is not None else "chat_reply_v1",
            model_name=settings.ai_demo_model_name,
            input_text=payload.message.strip(),
            output_text=None,
            request_json={
                "orchestrator": exc.orchestrator,
                "chain_name": exc.chain_name,
                "fallback_used": exc.fallback_used,
                "provider_error_type": exc.provider_error_type,
            },
            response_json={
                "provider_error_type": exc.provider_error_type,
                "orchestrator": exc.orchestrator,
                "chain_name": exc.chain_name,
                "fallback_used": exc.fallback_used,
            },
            status=AIPromptStatus.FAILED,
            error_message=str(exc),
            trace_id=None,
        )
        db.commit()
        raise
    except AIChatQuotaError as exc:
        prompt_logs_repo.create(
            session_id=session.session_id,
            message_id=user_message.message_id,
            user_id=payload.user_id,
            call_type=AIPromptCallType.CHAT,
            prompt_template_name="chat_rag_v1" if payload.course_id is not None else "chat_reply_v1",
            model_name=settings.ai_demo_model_name,
            input_text=payload.message.strip(),
            output_text=None,
            request_json={
                "orchestrator": settings.ai_chat_orchestrator,
                "chain_name": "quota_failure",
                "fallback_used": settings.ai_chat_orchestrator.strip().lower() == "langchain",
                "provider_error_type": "quota",
            },
            response_json={
                "provider_error_type": "quota",
                "orchestrator": settings.ai_chat_orchestrator,
                "chain_name": "quota_failure",
                "fallback_used": settings.ai_chat_orchestrator.strip().lower() == "langchain",
            },
            status=AIPromptStatus.FAILED,
            error_message=str(exc),
            trace_id=None,
        )
        db.commit()
        raise

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

    assistant_message = messages_repo.create(
        session_id=session.session_id,
        role=AIMessageRole.ASSISTANT,
        parent_message_id=user_message.message_id,
        content_text=workflow_result.reply_result.reply,
        retrieval_trace_json=workflow_result.retrieval_result.retrieval_trace_json
        if workflow_result.used_retrieval and workflow_result.retrieval_result is not None
        else None,
    )

    prompt_logs_repo.create(
        session_id=session.session_id,
        message_id=assistant_message.message_id,
        user_id=payload.user_id,
        call_type=AIPromptCallType.CHAT,
        prompt_template_name=get_prompt_template(workflow_result.prompt_template_name).name,
        model_name=(
            str(workflow_result.reply_result.request_json.get("model") or "guardrail")
            if isinstance(workflow_result.reply_result.request_json, dict)
            else settings.ai_demo_model_name
        ),
        input_text=payload.message.strip(),
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
            user_id=payload.user_id,
            call_type=AIPromptCallType.RETRIEVAL,
            prompt_template_name=None,
            model_name=workflow_result.retrieval_result.query_embedding_model,
            input_text=payload.message.strip(),
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

    sessions_repo.update_activity(
        session,
        course_id=payload.course_id,
        module_id=payload.module_id,
        last_message_at=timestamp,
        last_user_message_at=timestamp,
        last_assistant_message_at=timestamp,
        message_increment=1,
        summary_text=_build_summary_text(payload.message, workflow_result.reply_result.reply),
    )

    db.commit()
    db.refresh(session)

    return PersistedChatResult(
        session_id=session.session_id,
        user_message_id=user_message.message_id,
        assistant_message_id=assistant_message.message_id,
        reply=workflow_result.reply_result.reply,
        sources=workflow_result.sources,
    )
