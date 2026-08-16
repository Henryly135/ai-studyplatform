from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.ai_chat_sessions import AIChatSession


class AIChatSessionsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, session_id: int) -> AIChatSession | None:
        """Used by chat services to load an existing chat session by primary key."""
        return self.session.get(AIChatSession, session_id)

    def list_by_user(self, user_id: int, *, limit: int = 50, offset: int = 0) -> list[AIChatSession]:
        """Used by chat history APIs to load a user's sessions ordered by recent activity."""
        stmt = (
            select(AIChatSession)
            .where(AIChatSession.user_id == user_id)
            .order_by(
                desc(AIChatSession.last_message_at),
                desc(AIChatSession.updated_at),
                desc(AIChatSession.created_at),
            )
            .offset(max(0, offset))
            .limit(max(1, min(limit, 100)))
        )
        return list(self.session.scalars(stmt))

    def list_by_user_and_module(
        self,
        *,
        user_id: int,
        module_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AIChatSession]:
        """Used by chat history APIs to load a user's sessions scoped to a module."""
        stmt = (
            select(AIChatSession)
            .where(
                AIChatSession.user_id == user_id,
                AIChatSession.module_id == module_id,
            )
            .order_by(
                desc(AIChatSession.last_message_at),
                desc(AIChatSession.updated_at),
                desc(AIChatSession.created_at),
            )
            .offset(max(0, offset))
            .limit(max(1, min(limit, 100)))
        )
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        user_id: int,
        course_id: int | None,
        module_id: int | None,
        session_type: str,
        title: str | None,
    ) -> AIChatSession:
        """Used by chat services to persist a new chat session row."""
        # A new session starts with the minimum identifying context
        session_row = AIChatSession(
            user_id=user_id,
            course_id=course_id,
            module_id=module_id,
            session_type=session_type,
            title=title,
        )
        self.session.add(session_row)
        self.session.flush()
        return session_row

    def update_activity(
        self,
        session_row: AIChatSession,
        *,
        last_message_at: datetime,
        last_user_message_at: datetime,
        last_assistant_message_at: datetime,
        message_increment: int,
        summary_text: str | None = None,
    ) -> AIChatSession:
        """Update activity without changing the session's authorization scope."""
        # Session summary is a lightweight recap of the latest exchange
        session_row.last_message_at = last_message_at
        session_row.last_user_message_at = last_user_message_at
        session_row.last_assistant_message_at = last_assistant_message_at
        session_row.message_count += message_increment
        session_row.summary_text = summary_text
        self.session.flush()
        return session_row

    def record_user_message(
        self,
        session_row: AIChatSession,
        *,
        timestamp: datetime,
    ) -> AIChatSession:
        """Persist user activity without changing the session's scope."""
        session_row.last_message_at = timestamp
        session_row.last_user_message_at = timestamp
        session_row.message_count += 1
        self.session.flush()
        return session_row
