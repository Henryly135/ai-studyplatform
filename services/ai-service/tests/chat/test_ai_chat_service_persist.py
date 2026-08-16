from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models.ai_chat_messages import AIMessageGenerationStatus, AIMessageRole, AIMessageType
from app.models.ai_prompt_logs import AIPromptStatus
from app.schemas.demo import ChatServiceRequest
from app.services.chat.ai_chat_service import persist_chat, retry_chat
from app.services.chat.rag_workflow_service import AIChatReplyResult, ChatWorkflowResult


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.refreshed = []

    def commit(self) -> None:
        self.commit_calls += 1

    def refresh(self, obj) -> None:
        self.refreshed.append(obj)

    def rollback(self) -> None:
        return None


class FakeSessionsRepository:
    created_sessions: list[SimpleNamespace] = []
    updated_sessions: list[SimpleNamespace] = []

    def __init__(self, db) -> None:
        self.db = db

    def create(self, **kwargs):
        session = SimpleNamespace(session_id=10, message_count=0, **kwargs)
        self.created_sessions.append(session)
        return session

    def get_by_id(self, session_id):
        return SimpleNamespace(
            session_id=session_id,
            user_id=7,
            course_id=None,
            module_id=None,
            message_count=0,
        )

    def record_user_message(self, session, **kwargs):
        session.message_count += 1
        session.recorded = kwargs
        return session

    def update_activity(self, session, **kwargs):
        session.message_count += kwargs["message_increment"]
        session.updated = kwargs
        self.updated_sessions.append(session)
        return session


class FakeMessagesRepository:
    created_messages: list[SimpleNamespace] = []
    next_id = 100
    locked_message_ids: list[int] = []

    def __init__(self, db) -> None:
        self.db = db

    def create(self, **kwargs):
        self.__class__.next_id += 1
        kwargs.setdefault("message_type", AIMessageType.PLAIN_TEXT)
        kwargs.setdefault("is_visible_to_user", True)
        kwargs.setdefault("generation_status", AIMessageGenerationStatus.COMPLETED)
        kwargs.setdefault("generation_attempt_count", 0)
        message = SimpleNamespace(message_id=self.__class__.next_id, **kwargs)
        self.created_messages.append(message)
        return message

    def get_by_id(self, message_id):
        return next(
            (message for message in self.created_messages if message.message_id == message_id),
            None,
        )

    def get_by_id_for_update(self, message_id):
        self.locked_message_ids.append(message_id)
        return self.get_by_id(message_id)

    def get_by_client_request_id(self, request_id):
        return next(
            (
                message
                for message in self.created_messages
                if getattr(message, "client_request_id", None) == request_id
            ),
            None,
        )

    def get_assistant_reply_for_user_message(self, user_message_id):
        return next(
            (
                message
                for message in reversed(self.created_messages)
                if getattr(message, "parent_message_id", None) == user_message_id
                and message.role == AIMessageRole.ASSISTANT
                and message.is_visible_to_user
            ),
            None,
        )

    def mark_generation_pending(self, message, *, timestamp):
        message.generation_status = AIMessageGenerationStatus.PENDING
        message.failure_code = None
        message.failure_message = None
        message.generation_attempt_count = int(message.generation_attempt_count or 0) + 1
        message.generation_started_at = timestamp
        message.generation_completed_at = None
        return message

    def mark_generation_failed(self, message, *, failure_code, failure_message, timestamp):
        message.generation_status = AIMessageGenerationStatus.FAILED
        message.failure_code = failure_code
        message.failure_message = failure_message
        message.generation_completed_at = timestamp
        return message

    def mark_generation_completed(self, message, *, timestamp):
        message.generation_status = AIMessageGenerationStatus.COMPLETED
        message.failure_code = None
        message.failure_message = None
        message.generation_completed_at = timestamp
        return message


class FakePromptLogsRepository:
    created_logs: list[dict] = []

    def __init__(self, db) -> None:
        self.db = db

    def create(self, **kwargs):
        self.created_logs.append(kwargs)
        return SimpleNamespace(prompt_log_id=len(self.created_logs))


def _reset_fakes() -> None:
    FakeSessionsRepository.created_sessions = []
    FakeSessionsRepository.updated_sessions = []
    FakeMessagesRepository.created_messages = []
    FakeMessagesRepository.next_id = 100
    FakeMessagesRepository.locked_message_ids = []
    FakePromptLogsRepository.created_logs = []


def _reply_result() -> AIChatReplyResult:
    return AIChatReplyResult(
        reply="Assistant reply",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
        latency_ms=4,
        request_json={
            "modelId": "gemini:model",
            "model": "model",
            "provider": "gemini",
        },
        response_json={"text": "Assistant reply"},
        status=AIPromptStatus.SUCCESS,
        error_message=None,
        trace_id="trace-1",
    )


def test_persist_chat_writes_user_assistant_messages_and_prompt_log(monkeypatch) -> None:
    # Tests persist_chat happy path without retrieval context.
    _reset_fakes()
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatSessionsRepository", FakeSessionsRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatMessagesRepository", FakeMessagesRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIPromptLogsRepository", FakePromptLogsRepository)
    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.now_local",
        lambda: datetime(2026, 4, 29, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.RAGWorkflowService",
        lambda db: SimpleNamespace(
            execute_chat_workflow=lambda **_: ChatWorkflowResult(
                reply_result=_reply_result(),
                prompt_template_name="chat_reply_v1",
                retrieval_result=None,
                used_retrieval=False,
                retrieval_context_text=None,
                conversation_history=[],
            )
        ),
    )
    db = FakeSession()

    result = persist_chat(db, ChatServiceRequest(user_id=7, message=" Hello "))

    assert result.session_id == 10
    assert result.reply == "Assistant reply"
    assert [message.role for message in FakeMessagesRepository.created_messages] == [
        AIMessageRole.USER,
        AIMessageRole.ASSISTANT,
    ]
    assert FakePromptLogsRepository.created_logs[0]["prompt_template_name"] == "chat_reply_v1"
    # The visible pending state is committed before provider invocation, then
    # atomically completed with the assistant reply.
    assert db.commit_calls == 2


def test_persist_chat_uses_stored_context_when_follow_up_omits_it(monkeypatch) -> None:
    # Internal callers cannot clear or move an existing session by omitting its
    # context; RAG and session activity use the stored immutable scope.
    _reset_fakes()
    stored_session = SimpleNamespace(
        session_id=10,
        user_id=7,
        course_id=2,
        module_id=3,
        message_count=2,
    )
    workflow_calls = []
    activity_calls = []

    class ExistingSessionsRepository:
        def __init__(self, db) -> None:
            self.db = db

        def get_by_id(self, session_id):
            assert session_id == 10
            return stored_session

        def record_user_message(self, session, **kwargs):
            activity_calls.append(("user", kwargs))
            session.message_count += 1
            return session

        def update_activity(self, session, **kwargs):
            activity_calls.append(("assistant", kwargs))
            session.message_count += kwargs["message_increment"]
            return session

    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.AIChatSessionsRepository",
        ExistingSessionsRepository,
    )
    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.AIChatMessagesRepository",
        FakeMessagesRepository,
    )
    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.AIPromptLogsRepository",
        FakePromptLogsRepository,
    )
    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.now_local",
        lambda: datetime(2026, 4, 29, tzinfo=timezone.utc),
    )

    def _execute_chat_workflow(**kwargs):
        workflow_calls.append(kwargs)
        return ChatWorkflowResult(
            reply_result=_reply_result(),
            prompt_template_name="chat_reply_v1",
            retrieval_result=None,
            used_retrieval=False,
            retrieval_context_text=None,
            conversation_history=[],
        )

    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.RAGWorkflowService",
        lambda db: SimpleNamespace(execute_chat_workflow=_execute_chat_workflow),
    )

    result = persist_chat(
        FakeSession(),
        ChatServiceRequest(session_id=10, user_id=7, message="Follow up"),
    )

    assert result.session_id == 10
    assert workflow_calls[0]["course_id"] == 2
    assert workflow_calls[0]["module_id"] == 3
    assert (stored_session.course_id, stored_session.module_id) == (2, 3)
    assert all(
        "course_id" not in kwargs and "module_id" not in kwargs
        for _, kwargs in activity_calls
    )


def test_persist_chat_writes_retrieval_context_message_and_log(monkeypatch) -> None:
    # Tests persist_chat stores hidden retrieval context and retrieval prompt log when RAG is used.
    _reset_fakes()
    retrieval_result = SimpleNamespace(
        retrieval_trace_json={"results": [{"chunkId": 1}]},
        query_embedding_model="embedding-model",
        filters_json={"courseId": 2},
        query_text="Question",
        latency_ms=8,
    )
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatSessionsRepository", FakeSessionsRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatMessagesRepository", FakeMessagesRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIPromptLogsRepository", FakePromptLogsRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.now_local", lambda: datetime(2026, 4, 29, tzinfo=timezone.utc))
    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.RAGWorkflowService",
        lambda db: SimpleNamespace(
            execute_chat_workflow=lambda **_: SimpleNamespace(
                reply_result=_reply_result(),
                prompt_template_name="chat_rag_v1",
                retrieval_result=retrieval_result,
                used_retrieval=True,
                retrieval_context_text="retrieved context",
                sources=[{"chunk_index": 0}],
            )
        ),
    )

    result = persist_chat(
        FakeSession(),
        ChatServiceRequest(user_id=7, course_id=2, module_id=3, message="Question"),
    )

    assert result.sources == [{"chunk_index": 0}]
    assert [message.message_type for message in FakeMessagesRepository.created_messages] == [
        AIMessageType.PLAIN_TEXT,
        AIMessageType.RETRIEVAL_CONTEXT,
        AIMessageType.PLAIN_TEXT,
    ]
    assert FakeMessagesRepository.created_messages[1].is_visible_to_user is False
    assert len(FakePromptLogsRepository.created_logs) == 2


def test_persist_chat_keeps_failed_message_and_failure_metadata(monkeypatch) -> None:
    # Tests provider failures become visible retryable message state instead of an orphaned history gap.
    from app.services.chat.rag_workflow_service import AIModelInvocationError

    _reset_fakes()
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatSessionsRepository", FakeSessionsRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatMessagesRepository", FakeMessagesRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIPromptLogsRepository", FakePromptLogsRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.now_local", lambda: datetime(2026, 4, 29, tzinfo=timezone.utc))
    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.RAGWorkflowService",
        lambda db: SimpleNamespace(
            execute_chat_workflow=lambda **_: (_ for _ in ()).throw(
                AIModelInvocationError(
                    "failed",
                    provider_error_type="provider_timeout",
                    orchestrator="langchain",
                    chain_name="rag_chat",
                    fallback_used=False,
                )
            )
        ),
    )

    result = persist_chat(
        FakeSession(),
        ChatServiceRequest(
            user_id=7,
            course_id=2,
            message="Question",
            request_id="request-failure-001",
        ),
    )

    assert FakePromptLogsRepository.created_logs[0]["status"] == AIPromptStatus.FAILED
    assert FakePromptLogsRepository.created_logs[0]["response_json"]["provider_error_type"] == "provider_timeout"
    assert result.status == "failed"
    assert result.retryable is True
    failed_message = FakeMessagesRepository.created_messages[0]
    assert failed_message.is_visible_to_user is True
    assert failed_message.generation_status == AIMessageGenerationStatus.FAILED


def test_persist_chat_returns_cached_result_for_repeated_request_id(monkeypatch) -> None:
    _reset_fakes()
    workflow_calls = []
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatSessionsRepository", FakeSessionsRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatMessagesRepository", FakeMessagesRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIPromptLogsRepository", FakePromptLogsRepository)
    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.RAGWorkflowService",
        lambda db: SimpleNamespace(
            execute_chat_workflow=lambda **kwargs: (
                workflow_calls.append(kwargs)
                or SimpleNamespace(
                    reply_result=_reply_result(),
                    prompt_template_name="chat_reply_v1",
                    retrieval_result=None,
                    used_retrieval=False,
                    retrieval_context_text=None,
                    conversation_history=[],
                    sources=[{"material_id": 42, "score": 0.95}],
                )
            )
        ),
    )
    db = FakeSession()
    payload = ChatServiceRequest(
        user_id=7,
        message="Idempotent message",
        request_id="request-idempotent-001",
    )

    first = persist_chat(db, payload)
    second = persist_chat(db, payload)

    assert first.status == "completed"
    assert second.status == "completed"
    assert second.user_message_id == first.user_message_id
    assert second.assistant_message_id == first.assistant_message_id
    assert second.sources == first.sources
    assert second.model_id == first.model_id
    assert second.model_name == first.model_name
    assert second.provider == first.provider
    assert len(workflow_calls) == 1


def test_retry_chat_reuses_failed_message_and_increments_attempt_count(monkeypatch) -> None:
    from app.services.chat.rag_workflow_service import AIModelInvocationError

    _reset_fakes()
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatSessionsRepository", FakeSessionsRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatMessagesRepository", FakeMessagesRepository)
    monkeypatch.setattr("app.services.chat.ai_chat_service.AIPromptLogsRepository", FakePromptLogsRepository)
    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.RAGWorkflowService",
        lambda db: SimpleNamespace(
            execute_chat_workflow=lambda **_: (_ for _ in ()).throw(
                AIModelInvocationError(
                    "failed",
                    provider_error_type="provider_timeout",
                    orchestrator="adapter",
                    chain_name="plain_chat",
                    fallback_used=False,
                )
            )
        ),
    )
    db = FakeSession()
    failed = persist_chat(
        db,
        ChatServiceRequest(
            user_id=7,
            message="Retry me",
            request_id="request-retry-001",
            model_id="gemini:gemini-3.5-flash-lite",
        ),
    )
    assert failed.status == "failed"

    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.RAGWorkflowService",
        lambda db: SimpleNamespace(
            execute_chat_workflow=lambda **_: ChatWorkflowResult(
                reply_result=_reply_result(),
                prompt_template_name="chat_reply_v1",
                retrieval_result=None,
                used_retrieval=False,
                retrieval_context_text=None,
                conversation_history=[],
            )
        ),
    )

    retried = retry_chat(db, user_id=7, message_id=failed.user_message_id)

    assert retried.status == "completed"
    assert retried.user_message_id == failed.user_message_id
    assert FakeMessagesRepository.created_messages[0].generation_attempt_count == 2
    assert FakeMessagesRepository.locked_message_ids == [failed.user_message_id]
