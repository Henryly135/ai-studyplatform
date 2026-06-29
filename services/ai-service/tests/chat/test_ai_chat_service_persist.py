from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models.ai_chat_messages import AIMessageRole, AIMessageType
from app.models.ai_prompt_logs import AIPromptStatus
from app.schemas.demo import ChatServiceRequest
from app.services.chat.ai_chat_service import persist_chat
from app.services.chat.rag_workflow_service import AIChatReplyResult, ChatWorkflowResult


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.refreshed = []

    def commit(self) -> None:
        self.commit_calls += 1

    def refresh(self, obj) -> None:
        self.refreshed.append(obj)


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
        return SimpleNamespace(session_id=session_id, user_id=7, message_count=0)

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

    def __init__(self, db) -> None:
        self.db = db

    def create(self, **kwargs):
        self.__class__.next_id += 1
        kwargs.setdefault("message_type", AIMessageType.PLAIN_TEXT)
        kwargs.setdefault("is_visible_to_user", True)
        message = SimpleNamespace(message_id=self.__class__.next_id, **kwargs)
        self.created_messages.append(message)
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
    FakePromptLogsRepository.created_logs = []


def _reply_result() -> AIChatReplyResult:
    return AIChatReplyResult(
        reply="Assistant reply",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
        latency_ms=4,
        request_json={"model": "model"},
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
    assert db.commit_calls == 2


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


def test_persist_chat_logs_model_invocation_error_before_reraising(monkeypatch) -> None:
    # Tests persist_chat records failed prompt metadata for provider invocation failures.
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

    with pytest.raises(AIModelInvocationError):
        persist_chat(FakeSession(), ChatServiceRequest(user_id=7, course_id=2, message="Question"))

    assert FakePromptLogsRepository.created_logs[0]["status"] == AIPromptStatus.FAILED
    assert FakePromptLogsRepository.created_logs[0]["response_json"]["provider_error_type"] == "provider_timeout"
