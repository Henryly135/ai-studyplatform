from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.ai_chat_messages import AIChatMessage
from app.repositories.ai_chat_messages_repository import AIChatMessagesRepository


@dataclass(frozen=True)
class ChatHistoryMessage:
    message_id: int
    role: str
    content_text: str


class ChatHistoryService:
    def __init__(self, session: Session) -> None:
        self.messages = AIChatMessagesRepository(session)

    def list_visible_history(
        self,
        *,
        session_id: int,
        before_message_id: int | None = None,
    ) -> list[ChatHistoryMessage]:
        visible_messages = self.messages.list_visible_by_session(session_id)
        filtered_messages = [
            message
            for message in visible_messages
            if before_message_id is None or message.message_id < before_message_id
        ]
        return [self._to_history_message(message) for message in filtered_messages]

    def _to_history_message(self, message: AIChatMessage) -> ChatHistoryMessage:
        role = message.role.value if hasattr(message.role, "value") else str(message.role)
        return ChatHistoryMessage(
            message_id=message.message_id,
            role=role,
            content_text=message.content_text,
        )
