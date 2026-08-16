from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_chat_messages import (
    AIChatMessage,
    AIMessageGenerationStatus,
    AIMessageRole,
    AIMessageType,
)


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
        client_request_id: str | None = None,
        requested_model_id: str | None = None,
        generation_status: AIMessageGenerationStatus = AIMessageGenerationStatus.COMPLETED,
        generation_attempt_count: int = 0,
        generation_started_at: datetime | None = None,
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
            client_request_id=client_request_id,
            requested_model_id=requested_model_id,
            generation_status=generation_status,
            generation_attempt_count=generation_attempt_count,
            generation_started_at=generation_started_at,
        )
        self.session.add(message)
        self.session.flush()
        return message

    def get_by_id(self, message_id: int) -> AIChatMessage | None:
        """Load a chat message for retry authorization and state transitions."""
        return self.session.get(AIChatMessage, message_id)

    def get_by_id_for_update(self, message_id: int) -> AIChatMessage | None:
        """Lock one message so only one failed-to-pending retry transition can win."""
        stmt = (
            select(AIChatMessage)
            .where(AIChatMessage.message_id == message_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self.session.scalar(stmt)

    def get_by_client_request_id(self, client_request_id: str) -> AIChatMessage | None:
        """Look up the user message that owns an idempotency key."""
        stmt = select(AIChatMessage).where(
            AIChatMessage.client_request_id == client_request_id,
        )
        return self.session.scalar(stmt)

    def get_assistant_reply_for_user_message(self, user_message_id: int) -> AIChatMessage | None:
        """Return the completed assistant child for an idempotent replay."""
        stmt = (
            select(AIChatMessage)
            .where(
                AIChatMessage.parent_message_id == user_message_id,
                AIChatMessage.role == AIMessageRole.ASSISTANT,
                AIChatMessage.is_visible_to_user.is_(True),
            )
            .order_by(AIChatMessage.message_id.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def mark_generation_pending(
        self,
        message: AIChatMessage,
        *,
        timestamp: datetime,
    ) -> AIChatMessage:
        message.generation_status = AIMessageGenerationStatus.PENDING
        message.failure_code = None
        message.failure_message = None
        message.generation_attempt_count = int(message.generation_attempt_count or 0) + 1
        message.generation_started_at = timestamp
        message.generation_completed_at = None
        self.session.flush()
        return message

    def mark_generation_failed(
        self,
        message: AIChatMessage,
        *,
        failure_code: str,
        failure_message: str,
        timestamp: datetime,
    ) -> AIChatMessage:
        message.generation_status = AIMessageGenerationStatus.FAILED
        message.failure_code = failure_code
        message.failure_message = failure_message
        message.generation_completed_at = timestamp
        self.session.flush()
        return message

    def mark_generation_completed(
        self,
        message: AIChatMessage,
        *,
        timestamp: datetime,
    ) -> AIChatMessage:
        message.generation_status = AIMessageGenerationStatus.COMPLETED
        message.failure_code = None
        message.failure_message = None
        message.generation_completed_at = timestamp
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
