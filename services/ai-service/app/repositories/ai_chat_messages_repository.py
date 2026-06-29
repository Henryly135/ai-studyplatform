from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_chat_messages import AIChatMessage, AIMessageRole, AIMessageType


class AIChatMessagesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        session_id: int,
        role: AIMessageRole,
        content_text: str,
        parent_message_id: int | None = None,
        message_type: AIMessageType = AIMessageType.PLAIN_TEXT,
        is_visible_to_user: bool = True,
        retrieval_trace_json: dict | list | None = None,
    ) -> AIChatMessage:
        """Used by chat services to persist a single chat message row."""
        # Persist the raw message text together with any model metadata collected during generation
        message = AIChatMessage(
            session_id=session_id,
            role=role,
            message_type=message_type,
            parent_message_id=parent_message_id,
            content_text=content_text,
            is_visible_to_user=is_visible_to_user,
            retrieval_trace_json=retrieval_trace_json,
        )
        self.session.add(message)
        self.session.flush()
        return message

    def list_visible_by_session(self, session_id: int) -> list[AIChatMessage]:
        """Used by chat history APIs to load user-visible messages in chronological order."""
        stmt = (
            select(AIChatMessage)
            .where(
                AIChatMessage.session_id == session_id,
                AIChatMessage.is_visible_to_user.is_(True),
            )
            .order_by(AIChatMessage.created_at.asc(), AIChatMessage.message_id.asc())
        )
        return list(self.session.scalars(stmt))
