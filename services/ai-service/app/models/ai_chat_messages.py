from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SqlEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import enum_values


class AIMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AIMessageType(str, Enum):
    PLAIN_TEXT = "plain_text"
    SYSTEM_NOTICE = "system_notice"
    RETRIEVAL_CONTEXT = "retrieval_context"


class AIMessageGenerationStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ai_chat_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[AIMessageRole] = mapped_column(
        SqlEnum(AIMessageRole, values_callable=enum_values, name="ai_message_role"),
        nullable=False,
    )
    message_type: Mapped[AIMessageType] = mapped_column(
        SqlEnum(AIMessageType, values_callable=enum_values, name="ai_message_type"),
        nullable=False,
        default=AIMessageType.PLAIN_TEXT,
        server_default=AIMessageType.PLAIN_TEXT.value,
    )
    parent_message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ai_chat_messages.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    content_text: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    is_visible_to_user: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    retrieval_trace_json: Mapped[dict | list | None] = mapped_column(
        JSONB, 
        nullable=True
    )
    client_request_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
    )
    requested_model_id: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )
    generation_status: Mapped[AIMessageGenerationStatus] = mapped_column(
        SqlEnum(
            AIMessageGenerationStatus,
            values_callable=enum_values,
            name="ai_message_generation_status",
        ),
        nullable=False,
        default=AIMessageGenerationStatus.COMPLETED,
        server_default=AIMessageGenerationStatus.COMPLETED.value,
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_attempt_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
    )
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generation_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )


    # Relationships
    session = relationship(
        "AIChatSession", 
        back_populates="messages"
    )
    parent_message = relationship(
        "AIChatMessage",
        remote_side="AIChatMessage.message_id",
        back_populates="child_messages",
    )
    child_messages = relationship(
        "AIChatMessage", 
        back_populates="parent_message"
    )
    prompt_logs = relationship(
        "AIPromptLog", 
        back_populates="message"
    )
    retrieval_logs = relationship(
        "AIRetrievalLog", 
        back_populates="message"
    )
    feedback_items = relationship(
        "AIFeedback",
        back_populates="message",
        cascade="all, delete-orphan",
    )
