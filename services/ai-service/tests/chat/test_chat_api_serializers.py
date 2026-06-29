from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.chat import _http_error, _serialize_message, _serialize_session


def test_http_error_uses_structured_detail() -> None:
    # Tests chat API errors use the shared structured detail shape.
    error = _http_error(418, "TEAPOT", "short and stout")

    assert error.status_code == 418
    assert error.detail == {"code": "TEAPOT", "message": "short and stout"}


def test_serialize_session_encodes_ids_and_datetime_fields(monkeypatch) -> None:
    # Tests session rows are serialized with public ids and ISO datetimes.
    monkeypatch.setattr("app.api.chat.encode_session_uuid", lambda value: f"session-{value}")
    monkeypatch.setattr("app.api.chat.encode_course_uuid", lambda value: f"course-{value}")
    monkeypatch.setattr("app.api.chat.encode_module_uuid", lambda value: f"module-{value}")
    timestamp = datetime(2026, 4, 29, 1, 2, 3, tzinfo=timezone.utc)

    result = _serialize_session(
        SimpleNamespace(
            session_id=1,
            user_id=2,
            course_id=3,
            module_id=4,
            session_type="demo_chat",
            title="Title",
            status=SimpleNamespace(value="active"),
            message_count=5,
            summary_text="Summary",
            last_message_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
    )

    assert result.session_uuid == "session-1"
    assert result.course_uuid == "course-3"
    assert result.module_uuid == "module-4"
    assert result.status == "active"
    assert result.last_message_at == timestamp.isoformat()
    assert result.created_at == timestamp.isoformat()


def test_serialize_message_encodes_session_and_enum_values(monkeypatch) -> None:
    # Tests message rows are serialized with public session id and enum values.
    monkeypatch.setattr("app.api.chat.encode_session_uuid", lambda value: f"session-{value}")
    timestamp = datetime(2026, 4, 29, 1, 2, 3)

    result = _serialize_message(
        SimpleNamespace(
            message_id=10,
            session_id=20,
            role=SimpleNamespace(value="assistant"),
            message_type=SimpleNamespace(value="chat"),
            parent_message_id=9,
            content_text="hello",
            created_at=timestamp,
        )
    )

    assert result.message_id == 10
    assert result.session_uuid == "session-20"
    assert result.role == "assistant"
    assert result.message_type == "chat"
    assert result.parent_message_id == 9
    assert result.created_at == timestamp.isoformat()
