from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.schemas.demo import ChatServiceRequest
from app.services.chat.ai_chat_service import (
    AIChatSessionError,
    _build_session_title,
    _build_summary_text,
    _load_or_create_session,
)


def test_build_session_title_collapses_whitespace_and_limits_length() -> None:
    # Tests chat session titles are whitespace-normalized and capped at 80 chars.
    title = _build_session_title("  hello\n   world  " + "x" * 100)

    assert "\n" not in title
    assert "  " not in title
    assert len(title) == 80


def test_build_summary_text_collapses_and_limits_length() -> None:
    # Tests chat summaries combine user/assistant text and cap at 1000 chars.
    summary = _build_summary_text(" question " * 200, " answer " * 200)

    assert summary.startswith("User: question")
    assert len(summary) == 1000
    assert "\n" not in summary


def test_load_or_create_session_creates_new_session(monkeypatch) -> None:
    # Tests missing session_id creates a new demo chat session.
    created_session = SimpleNamespace(session_id=10)
    created_payloads = []

    class FakeSessionsRepository:
        def __init__(self, db) -> None:
            self.db = db

        def create(self, **kwargs):
            created_payloads.append(kwargs)
            return created_session

    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatSessionsRepository", FakeSessionsRepository)

    session = _load_or_create_session(
        object(),
        ChatServiceRequest(user_id=7, course_id=2, module_id=3, message="  New topic  "),
    )

    assert session is created_session
    assert created_payloads == [
        {
            "user_id": 7,
            "course_id": 2,
            "module_id": 3,
            "session_type": "demo_chat",
            "title": "New topic",
        }
    ]


@pytest.mark.parametrize(
    "loaded_session",
    [None, SimpleNamespace(session_id=5, user_id=99)],
)
def test_load_or_create_session_rejects_missing_or_wrong_owner(monkeypatch, loaded_session) -> None:
    # Tests missing sessions or owner mismatches are rejected.
    class FakeSessionsRepository:
        def __init__(self, db) -> None:
            self.db = db

        def get_by_id(self, session_id):
            assert session_id == 5
            return loaded_session

    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatSessionsRepository", FakeSessionsRepository)

    with pytest.raises(AIChatSessionError):
        _load_or_create_session(
            object(),
            ChatServiceRequest(session_id=5, user_id=7, message="hello"),
        )


def test_load_or_create_session_returns_existing_session_for_owner(monkeypatch) -> None:
    # Tests an existing session is returned when it belongs to the user.
    loaded_session = SimpleNamespace(
        session_id=5,
        user_id=7,
        course_id=2,
        module_id=3,
    )

    class FakeSessionsRepository:
        def __init__(self, db) -> None:
            self.db = db

        def get_by_id(self, session_id):
            assert session_id == 5
            return loaded_session

    monkeypatch.setattr("app.services.chat.ai_chat_service.AIChatSessionsRepository", FakeSessionsRepository)

    assert (
        _load_or_create_session(
            object(),
            ChatServiceRequest(session_id=5, user_id=7, message="hello"),
        )
        is loaded_session
    )


@pytest.mark.parametrize(
    ("course_id", "module_id"),
    [
        (4, 3),
        (2, 5),
    ],
)
def test_load_or_create_session_rejects_existing_context_mismatch(
    monkeypatch,
    course_id,
    module_id,
) -> None:
    # The service boundary independently protects immutable session scope for
    # callers that do not pass through the authenticated HTTP endpoint.
    loaded_session = SimpleNamespace(
        session_id=5,
        user_id=7,
        course_id=2,
        module_id=3,
    )

    class FakeSessionsRepository:
        def __init__(self, db) -> None:
            self.db = db

        def get_by_id(self, session_id):
            assert session_id == 5
            return loaded_session

    monkeypatch.setattr(
        "app.services.chat.ai_chat_service.AIChatSessionsRepository",
        FakeSessionsRepository,
    )

    with pytest.raises(AIChatSessionError):
        _load_or_create_session(
            object(),
            ChatServiceRequest(
                session_id=5,
                user_id=7,
                course_id=course_id,
                module_id=module_id,
                message="hello",
            ),
        )
